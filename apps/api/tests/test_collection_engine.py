"""Provider pagination, retry, date metadata, and bounded concurrency contracts."""
import datetime as dt
import pathlib
import tempfile
import threading
import time
import unittest

from jobhunt.collection import collect_pages, is_transient, retry_after_seconds
from jobhunt.db import Database
from jobhunt.freshness import utc_now
from jobhunt.models import Job, SourceResult
from jobhunt.runner import JobRunner


def job(identifier, source="jobstreet"):
    return Job(source=source, external_id=identifier, title="Backend Engineer",
               company="Acme", area="jakarta_selatan",
               location_raw="Jakarta Selatan",
               url="https://example.org/" + identifier,
               posted_at=utc_now().isoformat())


class TestCollectionPolicy(unittest.TestCase):
    def test_retries_429_with_retry_after_and_recovers(self):
        calls, pauses = [], []
        def fetch(page):
            calls.append(page)
            if len(calls) == 1:
                return SourceResult(source="jobstreet",success=False,jobs=[],
                                    http_status=429,error_message="Rate limited",
                                    retry_after_seconds=2)
            return SourceResult(source="jobstreet",success=True,jobs=[job("a")],
                                raw_count=1,has_more=False)
        result = collect_pages("jobstreet", fetch, page_limit=5,
                               sleep=pauses.append,jitter=lambda a,b:0,gap_seconds=0)
        self.assertTrue(result.success)
        self.assertEqual(len(calls),2)
        self.assertEqual(pauses,[2])
        self.assertEqual(result.retry_count,1)
        self.assertEqual(result.pages_fetched,1)

    def test_never_retry_403_or_captcha(self):
        calls = []
        def fetch(page):
            calls.append(page)
            return SourceResult(source="linkedin",success=False,jobs=[],
                                http_status=403,error_message="Forbidden")
        result = collect_pages("linkedin",fetch,sleep=lambda _:None,
                               jitter=lambda a,b:0,gap_seconds=0)
        self.assertFalse(result.success)
        self.assertEqual(calls,[1])
        self.assertEqual(result.retry_count,0)
        self.assertFalse(is_transient(SourceResult(source="linkedin",success=False,
                        jobs=[],error_message="CAPTCHA challenge")))

    def test_filtered_empty_page_not_terminal(self):
        calls=[]
        def fetch(page):
            calls.append(page)
            if page==1:
                return SourceResult(source="jobstreet",success=True,jobs=[],raw_count=30)
            return SourceResult(source="jobstreet",success=True,
                                jobs=[job("later")],raw_count=1,has_more=False)
        result=collect_pages("jobstreet",fetch,page_limit=5,gap_seconds=0)
        self.assertEqual(calls,[1,2])
        self.assertEqual(len(result.jobs),1)

    def test_genuinely_empty_page_or_repeat_terminates(self):
        counts=[]
        def fetch(page):
            counts.append(page)
            if page==1:
                return SourceResult(source="jobstreet",success=True,jobs=[job("1")],raw_count=30)
            return SourceResult(source="jobstreet",success=True,jobs=[],raw_count=0)
        result=collect_pages("jobstreet",fetch,page_limit=5,gap_seconds=0)
        self.assertEqual(counts,[1,2])
        self.assertEqual(result.pages_fetched,2)
        counts.clear()
        def repeat(page):
            counts.append(page)
            return SourceResult(source="jobstreet",success=True,jobs=[job("1")],raw_count=30)
        result=collect_pages("jobstreet",repeat,page_limit=5,gap_seconds=0)
        self.assertEqual(counts,[1,2])
        self.assertEqual(len(result.jobs),1)

    def test_partial_later_page_not_reported_full_success(self):
        def fetch(page):
            if page==1:
                return SourceResult(source="jobstreet",success=True,jobs=[job("first")],raw_count=30)
            return SourceResult(source="jobstreet",success=False,jobs=[],
                                http_status=403,error_message="Access denied")
        r=collect_pages("jobstreet",fetch,page_limit=5,gap_seconds=0)
        self.assertTrue(r.success)
        self.assertIn("Partial",r.error_message)
        self.assertEqual(r.http_status,403)
        self.assertEqual(r.pages_fetched,2)

    def test_retry_after_parses_http_date_and_numbers(self):
        self.assertEqual(retry_after_seconds("12"),12)
        self.assertEqual(retry_after_seconds("nope"),None)
        self.assertEqual(retry_after_seconds("Wed, 14 Oct 2026 10:00:10 GMT",
                         now=dt.datetime(2026,10,14,10,0,tzinfo=dt.timezone.utc)),10)


class TestConcurrentManualBatch(unittest.TestCase):
    def test_parallel_across_providers_and_serial_db_writes(self):
        barrier = threading.Barrier(2)
        calls=[]
        def make_fetch(source):
            def fetch(keyword):
                barrier.wait(timeout=3)
                calls.append((source,threading.get_ident()))
                return SourceResult(source=source,success=True,
                                    jobs=[job(source,source)])
            return fetch
        with tempfile.TemporaryDirectory() as folder:
            db=Database(str(pathlib.Path(folder)/"jobs.db"))
            original=db.record_run
            main_thread=threading.get_ident()
            writer_threads=[]
            def record_run(**kwargs):
                writer_threads.append(threading.get_ident())
                return original(**kwargs)
            db.record_run=record_run
            runner=JobRunner(db=db,sources={
                "jobstreet":make_fetch("jobstreet"),
                "linkedin":make_fetch("linkedin")},max_workers=2)
            progress=[]
            results=runner.run_single("backend",on_progress=lambda *args:progress.append(args))
            self.assertEqual([r["status"] for r in results],["success","success"])
            self.assertEqual(len(calls),2)
            self.assertEqual(writer_threads,[main_thread,main_thread])
            self.assertEqual([p[1] for p in progress],[0,1,2])
            self.assertEqual(len(db.get_jobs()),2)

    def test_same_provider_serializes_and_same_keyword_reuses_fetch(self):
        active=0
        peak=0
        num_calls=0
        state_lock=threading.Lock()
        def fetch(keyword):
            nonlocal active,peak,num_calls
            with state_lock:
                active+=1
                num_calls+=1
                peak=max(peak,active)
            time.sleep(.04)
            with state_lock:
                active-=1
            return SourceResult(source="jobstreet",success=True,
                                jobs=[job(keyword)])
        with tempfile.TemporaryDirectory() as folder:
            db=Database(str(pathlib.Path(folder)/"jobs.db"))
            db.create_search("backend",sources=["jobstreet"])
            db.create_search("backend",sources=["jobstreet"])
            db.create_search("golang",sources=["jobstreet"])
            runner=JobRunner(db=db,sources={"jobstreet":fetch},max_workers=3)
            results=runner.run_all_active()
            self.assertEqual(len(results),3)
            self.assertEqual(num_calls,2)
            self.assertEqual(peak,1)
            self.assertEqual(len(db.get_latest_runs()),3)
            self.assertEqual(len(db.get_jobs()),2)

    def test_provider_cooldown_prevents_repeated_429(self):
        num_calls=0
        def blocked(keyword):
            nonlocal num_calls
            num_calls+=1
            return SourceResult(source="linkedin",success=False,jobs=[],
                                http_status=429,error_message="rate limited")
        with tempfile.TemporaryDirectory() as folder:
            db=Database(str(pathlib.Path(folder)/"jobs.db"))
            runner=JobRunner(db=db,sources={"linkedin":blocked},max_workers=3)
            result=runner.run_single("first",source_names=["linkedin"])
            self.assertEqual(result[0]["status"],"error")
            second=runner.run_single("second",source_names=["linkedin"])
            self.assertIn("cooldown",second[0]["error"].lower())
            self.assertEqual(num_calls,1)


if __name__=="__main__":
    unittest.main()
