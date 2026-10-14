import os
import pathlib
import logging
import time
from typing import Dict, Callable, List, Any, Optional
from jobhunt.db import Database
from jobhunt.models import Job, SourceResult
from jobhunt.sources.jobstreet import fetch_jobstreet
from jobhunt.sources.kalibrr import fetch_kalibrr
from jobhunt.sources.linkedin import fetch_linkedin
from jobhunt.sources.glints import fetch_glints
from jobhunt.sources.dealls import fetch_dealls
from jobhunt.sources.karir import fetch_karir
from jobhunt.sources.techinasia import fetch_techinasia

logger = logging.getLogger(__name__)

def collect_pages(source, fetch_page, page_limit=None):
    """Bounded provider pagination with retry and partial-failure visibility."""
    limit = min(5, max(1, int(page_limit or os.getenv("KERJO_MAX_PAGES", "2"))))
    output, identifiers = [], set()
    for page in range(1, limit + 1):
        result = None
        for attempt in range(2):
            try:
                result = fetch_page(page)
            except Exception as exc:
                result = SourceResult(source=source, success=False, jobs=[], error_message=str(exc))
            if result.success:
                break
            msg = (result.error_message or "").lower()
            if attempt == 0 and any(tag in msg for tag in ("429", "503", "timeout", "timed out")):
                time.sleep(2)
                continue
            break
        if not result.success:
            if output:
                return SourceResult(source=source, success=True, jobs=output,
                                    error_message="Partial collection: " + str(result.error_message))
            return result
        if not result.jobs:
            # The adapter might have filtered this page by area; later pages can still match.
            continue
        for job in result.jobs:
            identity = (job.source, job.external_id)
            if identity not in identifiers:
                identifiers.add(identity)
                output.append(job)
    return SourceResult(source=source, success=True, jobs=output)


DEFAULT_SOURCES: Dict[str, Callable[[str], SourceResult]] = {
    "jobstreet": lambda kw: collect_pages("jobstreet", lambda p: fetch_jobstreet(kw, page=p)),
    "kalibrr": lambda kw: collect_pages("kalibrr", lambda p: fetch_kalibrr(kw, offset=(p - 1) * 30)),
    "linkedin": lambda kw: collect_pages("linkedin", lambda p: fetch_linkedin(kw, start=(p - 1) * 25)),
    "glints": lambda kw: fetch_glints(kw),
    "dealls": lambda kw: collect_pages("dealls", lambda p: fetch_dealls(kw, page=p)),
    "karir": lambda kw: collect_pages("karir", lambda p: fetch_karir(kw, page=p)),
    "techinasia": lambda kw: collect_pages("techinasia", lambda p: fetch_techinasia(kw, page=p)),
}

class LockAcquireError(Exception):
    pass

class RunnerLock:
    def __init__(self, lock_file: str = "data/runner.lock"):
        self.lock_file = lock_file
        self._fd: Optional[int] = None

    def __enter__(self):
        parent = pathlib.Path(self.lock_file).parent
        parent.mkdir(parents=True, exist_ok=True)
        try:
            # Atomic file creation
            self._fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(self._fd, str(os.getpid()).encode())
        except FileExistsError:
            # Recover a dead worker's orphan lock, but never steal from a live PID.
            try:
                pid = int(pathlib.Path(self.lock_file).read_text().strip())
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    pathlib.Path(self.lock_file).unlink(missing_ok=True)
                    self._fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                    os.write(self._fd, str(os.getpid()).encode())
                else:
                    raise LockAcquireError("Another runner process is already running.")
            except (ValueError, OSError) as exc:
                raise LockAcquireError("Runner lock is present; inspect " + self.lock_file) from exc
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            try:
                os.remove(self.lock_file)
            except OSError:
                pass

class JobRunner:
    def __init__(
        self,
        db: Optional[Database] = None,
        sources: Optional[Dict[str, Callable[[str], SourceResult]]] = None,
        lock_file: str = "data/runner.lock",
    ):
        self.db = db or Database()
        self.sources = sources if sources is not None else DEFAULT_SOURCES
        self.lock_file = lock_file

    def run_all_active(self, on_progress=None) -> List[Dict[str, Any]]:
        """
        Executes all active saved searches across their configured sources.
        """
        searches = self.db.get_searches(active_only=True)
        if not searches:
            logger.info("No active searches found. Seeding default technical searches.")
            self.db.seed_default_searches()
            searches = self.db.get_searches(active_only=True)
        if not searches:
            return []

        results = []
        total_tasks = sum(len([n for n in s["sources"].split(",") if n.strip() in self.sources]) for s in searches)
        if on_progress:
            on_progress(None, 0, total_tasks)
        for s in searches:
            search_id = s["id"]
            keyword = s["keyword"]
            area_filter = s["area"]
            src_names = [name.strip() for name in s["sources"].split(",") if name.strip()]

            for src_name in src_names:
                fetcher = self.sources.get(src_name)
                if not fetcher:
                    logger.warning(f"Unknown source '{src_name}', skipping.")
                    continue

                res = self._execute_search_on_source(search_id, keyword, area_filter, src_name, fetcher)
                results.append(res)
                if on_progress:
                    on_progress(res, len(results), total_tasks)

        return results

    def run_single(self, keyword: str, area_filter: str = "all", source_names: Optional[List[str]] = None, on_progress=None) -> List[Dict[str, Any]]:
        """
        Executes a one-off run for a given keyword and sources.
        """
        if not source_names:
            source_names = list(self.sources.keys())

        results = []
        valid_sources = [n for n in source_names if n in self.sources]
        if on_progress:
            on_progress(None, 0, len(valid_sources))
        for src_name in valid_sources:
            fetcher = self.sources.get(src_name)
            if not fetcher:
                continue
            res = self._execute_search_on_source(None, keyword, area_filter, src_name, fetcher)
            results.append(res)
            if on_progress:
                on_progress(res, len(results), len(valid_sources))
        return results

    def _execute_search_on_source(
        self,
        search_id: Optional[int],
        keyword: str,
        area_filter: str,
        source_name: str,
        fetcher: Callable[[str], SourceResult],
    ) -> Dict[str, Any]:
        try:
            source_result: SourceResult = fetcher(keyword)
        except Exception as e:
            source_result = SourceResult(
                source=source_name,
                success=False,
                jobs=[],
                error_message=str(e),
            )

        if not source_result.success:
            self.db.record_run(
                source=source_name,
                status="error",
                jobs_found=0,
                jobs_new=0,
                error_message=source_result.error_message,
                search_id=search_id,
            )
            return {
                "source": source_name,
                "keyword": keyword,
                "status": "error",
                "found_count": 0,
                "new_count": 0,
                "error": source_result.error_message,
            }

        # Filter by area if specific area is desired
        matched_jobs = source_result.jobs
        if area_filter and area_filter != "all":
            # Keep jobs matching the area OR unspecified
            matched_jobs = [j for j in matched_jobs if j.area in (area_filter, "unspecified")]

        new_count, total = self.db.upsert_jobs(matched_jobs)
        status = "partial" if source_result.error_message else "success"
        self.db.record_run(
            source=source_name,
            status=status,
            jobs_found=len(matched_jobs),
            jobs_new=new_count,
            error_message=source_result.error_message,
            search_id=search_id,
        )

        return {
            "source": source_name,
            "keyword": keyword,
            "status": status,
            "found_count": len(matched_jobs),
            "new_count": new_count,
            "error": source_result.error_message,
        }
