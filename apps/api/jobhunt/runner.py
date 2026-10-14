import os
import pathlib
import logging
import time
import threading
import queue
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Callable, List, Any, Optional
from jobhunt.db import Database
from jobhunt.models import Job, SourceResult
from jobhunt.freshness import posting_age_status, parse_posted_at
from jobhunt.collection import collect_pages
from jobhunt.enrichment import enrich_jobs
from jobhunt.sources.jobstreet import fetch_jobstreet
from jobhunt.sources.kalibrr import fetch_kalibrr
from jobhunt.sources.linkedin import fetch_linkedin
from jobhunt.sources.glints import fetch_glints
from jobhunt.sources.dealls import fetch_dealls
from jobhunt.sources.karir import fetch_karir
from jobhunt.sources.techinasia import fetch_techinasia
from jobhunt.sources.ats import fetch_ats
from jobhunt.sources.linkedin_posts import fetch_linkedin_posts

logger = logging.getLogger(__name__)



DEFAULT_SOURCES: Dict[str, Callable[[str], SourceResult]] = {
    "jobstreet": lambda kw: collect_pages("jobstreet", lambda p: fetch_jobstreet(kw, page=p)),
    "kalibrr": lambda kw: collect_pages("kalibrr", lambda p: fetch_kalibrr(kw, offset=(p - 1) * 30)),
    # Preserve the legacy source identifier to report why old saved searches
    # no longer run the undocumented LinkedIn guest endpoint.
    "linkedin": lambda kw: SourceResult(
        "linkedin", False, [],
        "Legacy guest endpoint retired; use linkedin_posts (authorized) or import HR post manually"),
    "linkedin_posts": fetch_linkedin_posts,
    "ats": fetch_ats,
    "glints": lambda kw: fetch_glints(kw),
    "dealls": lambda kw: collect_pages("dealls", lambda p: fetch_dealls(kw, page=p)),
    "karir": lambda kw: collect_pages("karir", lambda p: fetch_karir(kw, page=p)),
    "techinasia": lambda kw: collect_pages("techinasia", lambda p: fetch_techinasia(kw, page=p)),
}

class LockAcquireError(Exception):
    pass

class RunnerLock:
    """Cross-process advisory lock.

    Uses operating-system locks instead of interpreting a PID file. The kernel
    releases ownership on crash; the lock *file remains* to avoid an inode
    replacement race where two writers both believe they own the lock.
    """
    def __init__(self, lock_file: str = "data/runner.lock"):
        self.lock_file = lock_file
        self._fd: Optional[int] = None

    def __enter__(self):
        path = pathlib.Path(self.lock_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.name == "nt":
                import msvcrt
                # Lock byte zero. Never call os.kill(pid, 0) on Windows.
                if os.fstat(self._fd).st_size == 0:
                    os.write(self._fd, b"\0")
                os.lseek(self._fd, 0, os.SEEK_SET)
                try:
                    msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise LockAcquireError("Another runner process is already running.") from exc
            else:
                import fcntl
                try:
                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise LockAcquireError("Another runner process is already running.") from exc
            # Diagnostic PID, not an authority to delete files or kill processes.
            os.lseek(self._fd, 0, os.SEEK_SET)
            os.write(self._fd, str(os.getpid()).encode("ascii") + b"\n")
            os.ftruncate(self._fd, os.lseek(self._fd, 0, os.SEEK_CUR))
            os.fsync(self._fd)
            return self
        except BaseException:
            os.close(self._fd)
            self._fd = None
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

class JobRunner:
    def __init__(
        self,
        db: Optional[Database] = None,
        sources: Optional[Dict[str, Callable[[str], SourceResult]]] = None,
        lock_file: str = "data/runner.lock",
        max_workers: Optional[int] = None,
    ):
        self.db = db or Database()
        self.sources = sources if sources is not None else dict(DEFAULT_SOURCES)
        if sources is None:
            configured = self.db.get_ats_boards()
            if configured:
                company_boards = [(entry["provider"], entry["slug"]) for entry in configured]
                self.sources["ats"] = lambda kw: fetch_ats(kw, boards=company_boards)
        self.lock_file = lock_file
        try:
            configured = int(os.getenv("KERJO_MAX_WORKERS", "3")) if max_workers is None else int(max_workers)
        except (TypeError, ValueError):
            configured = 3
        self.max_workers = max(1, min(4, configured))
        self._source_locks = {source: threading.Lock() for source in self.sources}
        self._blocked_until = {}
        self._last_finished = {}
        # Shared across keywords for this single, manually triggered run.
        try:
            detail_budget = int(os.getenv("KERJO_RUN_DETAIL_BUDGET", "8"))
        except (ValueError, TypeError):
            detail_budget = 8
        self._detail_remaining = {
            source: max(0, min(16, detail_budget)) for source in self.sources
        }

    def run_all_active(self, on_progress=None) -> List[Dict[str, Any]]:
        """Run only when manually invoked, even for active saved searches."""
        searches = self.db.get_searches(active_only=True)
        if not searches:
            if not self.db.get_searches():
                logger.info("First manual run: seeding default technical searches.")
                self.db.seed_default_searches()
                searches = self.db.get_searches(active_only=True)
            else:
                logger.info("Saved searches are paused; manual run skipped.")
        tasks = []
        for search in searches:
            for source in dict.fromkeys(x.strip() for x in search["sources"].split(",")):
                if source in self.sources:
                    tasks.append((search["id"], search["keyword"], search["area"], source))
                elif source:
                    logger.warning("Unsupported source %s in search %s", source, search["id"])
        return self._run_tasks(tasks, on_progress)

    def run_single(self, keyword: str, area_filter: str = "all", source_names=None, on_progress=None):
        """Manual CLI/API one-off search."""
        selected = list(self.sources) if source_names is None else source_names
        tasks = [(None, keyword, area_filter, source)
                 for source in dict.fromkeys(selected) if source in self.sources]
        return self._run_tasks(tasks, on_progress)

    def _fetch_source(self, source_name, keyword):
        """Network-only task. No SQLite mutations happen in worker threads."""
        lock = self._source_locks[source_name]
        with lock:
            started = time.monotonic()
            remaining = self._blocked_until.get(source_name, 0) - time.monotonic()
            if remaining > 0:
                return SourceResult(source=source_name, success=False, jobs=[],
                                    error_message="Provider cooldown in effect (rate-limit/access response)",
                                    http_status=429)
            # Extra pacing across successive keywords on the same provider.
            gap = max(0.0, min(3.0, self._last_finished.get(source_name, 0) +
                                   0.4 - time.monotonic()))
            if gap:
                time.sleep(gap)
            try:
                result = self.sources[source_name](keyword)
            except Exception as exc:
                result = SourceResult(source=source_name, success=False,
                                      jobs=[], error_message=str(exc))
            if (result.success and result.jobs and result.http_status not in (401, 403, 429, 503)
                    and self._detail_remaining[source_name] > 0):
                attempts = {}
                try:
                    per_keyword_budget = max(0, min(10, int(os.getenv("KERJO_DETAIL_ENRICH_LIMIT", "3"))))
                except (ValueError, TypeError):
                    per_keyword_budget = 3
                result.enriched_count = enrich_jobs(
                    result.jobs, source_name,
                    max_details=min(per_keyword_budget, self._detail_remaining[source_name]),
                    stats=attempts,
                )
                self._detail_remaining[source_name] -= attempts.get("attempted", 0)
            self._last_finished[source_name] = time.monotonic()
            result.elapsed_ms = max(result.elapsed_ms,
                                    int((self._last_finished[source_name] - started) * 1000))
            if result.http_status in (403, 429, 503):
                # A failed page may have returned partial data. Either way,
                # avoid hammering the same provider on subsequent keywords.
                self._blocked_until[source_name] = time.monotonic() + (
                    60 if result.http_status == 403 else
                    min(60, max(30, result.retry_after_seconds or 0))
                )
            return result

    def _run_tasks(self, tasks, on_progress):
        total = len(tasks)
        if on_progress:
            on_progress(None, 0, total)
        if not tasks:
            return []

        # Each provider gets its own sequential task lane: fast sites cannot
        # be starved behind N queued keywords from a slow/rate-limited site.
        grouped = {}
        provider_lanes = {}
        for index, task in enumerate(tasks):
            _, keyword, _, source = task
            key = (source, keyword.strip().casefold())
            if key not in grouped:
                grouped[key] = []
                provider_lanes.setdefault(source, []).append(key)
            grouped[key].append(index)

        completed_queue = queue.Queue()
        ordered = [None] * total
        completed = 0

        def provider_lane(source, keys):
            for key in keys:
                keyword = tasks[grouped[key][0]][1]
                try:
                    fetched = self._fetch_source(source, keyword)
                except Exception as exc:
                    fetched = SourceResult(source=source, success=False,
                                           jobs=[], error_message=str(exc))
                completed_queue.put((key, fetched))

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(provider_lanes)),
                                thread_name_prefix="kerjo-provider") as pool:
            futures = [pool.submit(provider_lane, source, keys)
                       for source, keys in provider_lanes.items()]
            for _ in range(len(grouped)):
                key, fetched = completed_queue.get()
                indexes = grouped[key]
                for group_index, index in enumerate(indexes):
                    search_id, keyword, area_filter, source = tasks[index]
                    # Metrics count real network work only once when several
                    # saved searches share this provider/keyword request.
                    measured = fetched if group_index == 0 else replace(
                        fetched, pages_fetched=0, retry_count=0,
                        enriched_count=0, elapsed_ms=0)
                    result = self._execute_search_on_source(
                        search_id, keyword, area_filter, source,
                        self.sources[source], prefetched=measured)
                    ordered[index] = result
                    completed += 1
                    if on_progress:
                        on_progress(result, completed, total)
            # Preserve the exceptions of the lane itself rather than silently
            # claiming success if a provider worker unexpectedly terminated.
            for future in futures:
                future.result()
        return ordered

    def _execute_search_on_source(
        self,
        search_id: Optional[int],
        keyword: str,
        area_filter: str,
        source_name: str,
        fetcher: Callable[[str], SourceResult],
        prefetched: Optional[SourceResult] = None,
    ) -> Dict[str, Any]:
        # Invoked on the coordinating thread; keep all SQLite writes serial.
        source_result = prefetched if prefetched is not None else self._fetch_source(source_name, keyword)

        if not source_result.success:
            self.db.record_run(
                source=source_name,
                status="error",
                jobs_found=0,
                jobs_new=0,
                error_message=source_result.error_message,
                search_id=search_id,
                pages_fetched=source_result.pages_fetched,
                retry_count=source_result.retry_count,
                details_enriched=source_result.enriched_count,
                duration_ms=source_result.elapsed_ms,
            )
            return {
                "source": source_name,
                "keyword": keyword,
                "status": "error",
                "found_count": 0,
                "new_count": 0,
                "pages_fetched": source_result.pages_fetched,
                "retry_count": source_result.retry_count,
                "details_enriched": source_result.enriched_count,
                "duration_ms": source_result.elapsed_ms,
                "error": source_result.error_message,
            }

        # The publication date is mandatory for 14-day discovery. Never
        # substitute first_seen_at / last_seen_at / updated_at for posted_at.
        matched_jobs = source_result.jobs
        if area_filter and area_filter != "all":
            matched_jobs = [j for j in matched_jobs if j.area in (area_filter, "unspecified")]

        age_counts = {"recent": 0, "old": 0, "unknown": 0, "future": 0}
        recent_jobs = []
        for job in matched_jobs:
            age = posting_age_status(job.posted_at)
            age_counts[age] += 1
            if age == "recent":
                # Persist normalized timezone-aware UTC for deterministic sorting.
                job.posted_at = parse_posted_at(job.posted_at).isoformat()
                recent_jobs.append(job)

        new_count, _ = self.db.upsert_jobs(recent_jobs)
        description_complete = sum(j.description_status == "complete" for j in recent_jobs)
        description_missing = sum(not j.description for j in recent_jobs)
        status = "partial" if source_result.error_message else "success"
        self.db.record_run(
            source=source_name,
            status=status,
            jobs_found=len(matched_jobs),
            jobs_new=new_count,
            jobs_recent=age_counts["recent"],
            filtered_old=age_counts["old"],
            filtered_unknown=age_counts["unknown"],
            filtered_future=age_counts["future"],
            error_message=source_result.error_message,
            search_id=search_id,
            pages_fetched=source_result.pages_fetched,
            retry_count=source_result.retry_count,
            details_enriched=source_result.enriched_count,
            duration_ms=source_result.elapsed_ms,
        )

        return {
            "source": source_name,
            "keyword": keyword,
            "status": status,
            "found_count": len(matched_jobs),
            "recent_count": age_counts["recent"],
            "filtered_old": age_counts["old"],
            "filtered_unknown": age_counts["unknown"],
            "filtered_future": age_counts["future"],
            "new_count": new_count,
            "pages_fetched": source_result.pages_fetched,
            "retry_count": source_result.retry_count,
            "details_enriched": source_result.enriched_count,
            "descriptions_complete": description_complete,
            "descriptions_missing": description_missing,
            "job_external_ids": [job.external_id for job in recent_jobs],
            "duration_ms": source_result.elapsed_ms,
            "error": source_result.error_message,
        }
