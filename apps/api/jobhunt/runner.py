import os
import pathlib
import logging
from typing import Dict, Callable, List, Any, Optional
from jobhunt.db import Database
from jobhunt.models import Job, SourceResult
from jobhunt.sources.jobstreet import fetch_jobstreet
from jobhunt.sources.kalibrr import fetch_kalibrr

logger = logging.getLogger(__name__)

DEFAULT_SOURCES: Dict[str, Callable[[str], SourceResult]] = {
    "jobstreet": lambda kw: fetch_jobstreet(kw),
    "kalibrr": lambda kw: fetch_kalibrr(kw),
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
            raise LockAcquireError("Another runner process is already running.")
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

    def run_all_active(self) -> List[Dict[str, Any]]:
        """
        Executes all active saved searches across their configured sources.
        """
        searches = self.db.get_searches(active_only=True)
        if not searches:
            logger.info("No active searches found.")
            return []

        results = []
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

        return results

    def run_single(self, keyword: str, area_filter: str = "all", source_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Executes a one-off run for a given keyword and sources.
        """
        if not source_names:
            source_names = list(self.sources.keys())

        results = []
        for src_name in source_names:
            fetcher = self.sources.get(src_name)
            if not fetcher:
                continue
            res = self._execute_search_on_source(None, keyword, area_filter, src_name, fetcher)
            results.append(res)
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
        self.db.record_run(
            source=source_name,
            status="success",
            jobs_found=len(matched_jobs),
            jobs_new=new_count,
            search_id=search_id,
        )

        return {
            "source": source_name,
            "keyword": keyword,
            "status": "success",
            "found_count": len(matched_jobs),
            "new_count": new_count,
            "error": None,
        }
