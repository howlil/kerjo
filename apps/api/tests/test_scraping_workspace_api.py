"""Run-scoped scraping observability contract: activity != result preview != Discover."""
import json
import pathlib
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from jobhunt.db import Database
from jobhunt.features import FeatureStore
from jobhunt.freshness import utc_now
from jobhunt.models import Job, SourceResult
from jobhunt.server import create_server


class ScrapingWorkspaceAPITest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(str(pathlib.Path(self.temp.name) / "jobs.db"))
        self.db.create_search("Backend Engineer", sources=["jobstreet"])
        self.server = create_server("127.0.0.1", 0, db=self.db)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def get(self, path, method="GET", payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.server.server_port, path),
            data=body, method=method, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=4) as response:
            return response.status, json.loads(response.read().decode())

    def result(self, source, external_id, status="success"):
        return {
            "source": source, "keyword": "Backend Engineer", "status": status,
            "found_count": 1, "recent_count": 1, "new_count": 1,
            "pages_fetched": 1, "retry_count": 0, "details_enriched": 1,
            "filtered_old": 0, "filtered_unknown": 0, "filtered_future": 0,
            "job_external_ids": [external_id],
        }

    def test_cursor_isolation_history_and_fresh_preview(self):
        self.db.upsert_jobs([
            Job(source="jobstreet", external_id="a", title="Backend Engineer",
                company="Test Corp", location_raw="Jakarta", area="unspecified",
                url="https://example.org/a", posted_at=utc_now().isoformat(),
                description="Build transactional APIs."),
        ])
        features = self.server.RequestHandlerClass.features
        first = features.create_batch()
        second = features.create_batch()
        features.add_run_event(first, "system", "info", "run_started", "Started")
        features.record_batch_result(first, self.result("jobstreet", "a"))
        features.add_run_event(second, "system", "info", "run_started", "Other")
        status, batch_list = self.get("/api/run-batches")
        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in batch_list["runs"][:2]], [second, first])
        _, all_events = self.get("/api/run/%d/events?limit=1" % first)
        self.assertEqual(len(all_events["events"]), 1)
        cursor = all_events["next_cursor"]
        _, next_events = self.get("/api/run/%d/events?after=%d" % (first, cursor))
        self.assertEqual(len(next_events["events"]), 1)
        self.assertEqual(next_events["events"][0]["source"], "jobstreet")
        _, other_events = self.get("/api/run/%d/events" % second)
        self.assertEqual(len(other_events["events"]), 1)
        _, preview = self.get("/api/run/%d/preview" % first)
        self.assertEqual(preview["total"], 1)
        self.assertEqual(preview["jobs"][0]["description"], "Build transactional APIs.")
        _, other_preview = self.get("/api/run/%d/preview" % second)
        self.assertEqual(other_preview["total"], 0)
        _, filtered = self.get("/api/run/%d/preview?source=glints&q=Backend" % first)
        self.assertEqual(filtered["total"], 0)
        _, text_match = self.get("/api/run/%d/preview?q=transactional" % first)
        self.assertEqual(text_match["total"], 1)

    def test_invalid_scope_and_inputs(self):
        features = self.server.RequestHandlerClass.features
        batch = features.create_batch()
        for url,code in [
            ("/api/run/99999/events",404), ("/api/run/99999/preview",404),
            ("/api/run/%d/events?after=-1" % batch,400),
            ("/api/run/%d/events?limit=9999" % batch,400),
            ("/api/run/%d/preview?source=bogus" % batch,400),
            ("/api/run/%d/preview?offset=-2" % batch,400),
        ]:
            with self.subTest(url=url):
                with self.assertRaises(urllib.error.HTTPError) as failure:
                    self.get(url)
                self.assertEqual(failure.exception.code, code)

    def test_actual_worker_writes_run_events_and_links_only_valid_jobs(self):
        valid = Job(source="jobstreet", external_id="valid", title="Backend Engineer",
                    company="Valid Co", location_raw="Jakarta", area="unspecified",
                    url="https://example.org/valid", posted_at=utc_now().isoformat(),
                    description="Maintain API services and databases.")
        bad_date = Job(source="jobstreet", external_id="undated", title="Backend Engineer",
                       company="Unknown Co", location_raw="Jakarta", area="unspecified",
                       url="https://example.org/undated", posted_at=None)
        def fetch(_):
            return SourceResult(source="jobstreet",success=True,
                                jobs=[valid,bad_date], pages_fetched=1)
        with patch("jobhunt.runner.DEFAULT_SOURCES", {"jobstreet":fetch}):
            status, response = self.get("/api/run", "POST", {})
            self.assertEqual(status,202)
            batch_id=response["run_id"]
            for _ in range(80):
                _, snapshot=self.get("/api/run/%d" % batch_id)
                if snapshot["run"]["status"] in ("completed","failed","partial"):
                    break
                time.sleep(.025)
            self.assertEqual(snapshot["run"]["status"],"completed")
            _, events=self.get("/api/run/%d/events" % batch_id)
            self.assertEqual([e["event_type"] for e in events["events"]],
                             ["run_started","source_task_completed","run_finished"])
            self.assertEqual(events["events"][1]["metrics"]["filtered_unknown"],1)
            _, preview=self.get("/api/run/%d/preview" % batch_id)
            self.assertEqual(preview["total"],1)
            self.assertEqual(preview["jobs"][0]["company"],"Valid Co")
            self.assertEqual(snapshot["run"]["filtered_unknown"],1)


if __name__ == "__main__":
    unittest.main()
