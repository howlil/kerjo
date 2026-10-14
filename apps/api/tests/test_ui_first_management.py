"""UI-first manual scraping and destructive job management tests.

Only tests mock a provider; production /api/run executes the configured live adapters.
"""
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
from jobhunt.features import FeatureStore, ProtectedJobsError
from jobhunt.freshness import utc_now
from jobhunt.models import Job, SourceResult
from jobhunt.server import create_server


def sample(source="jobstreet", external_id="job-1", title="Backend Engineer"):
    return Job(source=source, external_id=external_id, title=title,
               company="Demo Company", area="jakarta_selatan",
               location_raw="Jakarta Selatan",
               url="https://example.org/careers/" + external_id,
               posted_at=utc_now().isoformat())


class TestDeletionInvariants(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db = Database(str(pathlib.Path(self.folder.name) / "kerjo.db"))
        self.features = FeatureStore(self.db)
        self.db.upsert_jobs([sample(external_id="a"), sample(external_id="b"), sample(external_id="c")])
        self.ids = [j["id"] for j in self.db.get_jobs(limit=None)]

    def tearDown(self):
        self.folder.cleanup()

    def test_inventory_reads_persisted_rows(self):
        self.assertEqual(self.features.scraped_inventory(), {"total": 3, "protected": 0, "deletable": 3})
        self.features.set_saved([self.ids[0]], True)
        self.features.update_application([self.ids[1]], {"status": "applied"})
        self.assertEqual(self.features.scraped_inventory(), {"total": 3, "protected": 2, "deletable": 1})

    def test_selected_deletion_is_atomic_and_protects_saved_applications(self):
        self.features.set_saved([self.ids[0]], True)
        self.features.update_application([self.ids[1]], {"status": "applied", "notes": "important"})
        with self.assertRaises(ProtectedJobsError):
            self.features.delete_scraped_jobs(ids=self.ids)
        self.assertEqual(self.features.scraped_inventory()["total"], 3)
        result = self.features.delete_scraped_jobs(ids=[self.ids[2]])
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(len(self.features.applications()), 1)
        self.assertEqual(self.features.scraped_inventory()["total"], 2)

    def test_delete_all_skips_tracked_unless_explicit(self):
        self.features.set_saved([self.ids[0]], True)
        self.features.update_application([self.ids[1]], {"status": "applied"})
        result = self.features.delete_scraped_jobs(scope="all")
        self.assertEqual((result["deleted"], result["protected_skipped"]), (1, 2))
        self.assertEqual(self.features.scraped_inventory()["total"], 2)
        result = self.features.delete_scraped_jobs(scope="all", include_tracked=True)
        self.assertEqual(result["deleted"], 2)
        self.assertEqual(self.features.scraped_inventory()["total"], 0)
        self.assertEqual(self.features.applications(), [])

    def test_invalid_and_stale_id_requests_never_partially_delete(self):
        for args in ({"ids": [self.ids[0], self.ids[0]]},
                     {"ids": [self.ids[0], 99999]},
                     {"scope": "all", "ids": [self.ids[0]]},
                     {"ids": [True]}):
            with self.assertRaises((ValueError, LookupError)):
                self.features.delete_scraped_jobs(**args)
        self.assertEqual(self.features.scraped_inventory()["total"], 3)


class TestManualScrapingAndDeleteAPI(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db = Database(str(pathlib.Path(self.folder.name) / "jobs.db"))
        self.db.create_search("Backend", sources=["jobstreet"])
        self.server = create_server("127.0.0.1", 0, self.db)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.folder.cleanup()

    def req(self, path, method="GET", body=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}" + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=4) as res:
            return res.status, json.loads(res.read())

    def test_manual_run_persists_before_reporting_completed(self):
        def stub(_kw):
            return SourceResult(source="jobstreet", success=True,
                                jobs=[sample(external_id="persisted-live-adapter")],
                                pages_fetched=1, raw_count=1)
        with patch("jobhunt.runner.DEFAULT_SOURCES", {"jobstreet": stub}):
            status, batch = self.req("/api/run", "POST", {})
            self.assertEqual(status, 202)
            for _ in range(90):
                _, data = self.req("/api/run/" + str(batch["run_id"]))
                if data["run"]["status"] in ("completed", "partial", "failed", "skipped"):
                    break
                time.sleep(0.05)
            self.assertEqual(data["run"]["status"], "completed", data)
            self.assertEqual(data["run"]["jobs_new"], 1)
            self.assertEqual(data["run"]["pages_fetched"], 1)
            self.assertEqual(self.req("/api/jobs/inventory")[1]["total"], 1)
            self.assertEqual(self.req("/api/jobs")[1]["jobs"][0]["external_id"], "persisted-live-adapter")

    def test_ats_boards_can_be_configured_only_from_ui_api(self):
        status, created = self.req("/api/ats-boards", "POST",
                                   {"provider": "ashby", "slug": "acme"})
        self.assertEqual(status, 201)
        _, listing = self.req("/api/ats-boards")
        self.assertEqual([(b["provider"], b["slug"]) for b in listing["boards"]],
                         [("ashby", "acme")])
        from jobhunt.runner import JobRunner
        from unittest.mock import patch
        with patch("jobhunt.runner.fetch_ats") as fetch:
            fetch.return_value = SourceResult("ats", True, [])
            JobRunner(self.db).sources["ats"]("Backend")
            self.assertEqual(fetch.call_args.kwargs["boards"], [("ashby", "acme")])
        status, deleted = self.req("/api/ats-boards/" + str(created["id"]), "DELETE")
        self.assertEqual((status, deleted["deleted"]), (200, 1))
        self.assertEqual(self.req("/api/ats-boards")[1]["boards"], [])

    def test_unconfigured_ats_is_not_fake_success(self):
        from jobhunt.sources.ats import fetch_ats
        with patch.dict("os.environ", {"KERJO_ATS_BOARDS": ""}):
            result = fetch_ats("Backend")
        self.assertFalse(result.success)
        self.assertEqual(result.jobs, [])
        self.assertIn("belum dikonfigurasi", result.error_message)

    def test_delete_works_via_api_and_requires_confirmation(self):
        self.db.upsert_jobs([sample()])
        job_id = self.req("/api/jobs")[1]["jobs"][0]["id"]
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.req("/api/jobs", "DELETE", {"ids": [job_id]})
        self.assertEqual(err.exception.code, 400)
        self.req("/api/jobs", "DELETE", {"ids": [job_id], "confirm": "DELETE"})
        self.assertEqual(self.req("/api/jobs/inventory")[1]["total"], 0)
        self.assertEqual(self.req("/api/jobs")[1]["total"], 0)

    def test_conflict_while_scraping_blocks_mutation(self):
        self.db.upsert_jobs([sample()])
        self.server.RequestHandlerClass.run_gate.acquire()
        try:
            with self.assertRaises(urllib.error.HTTPError) as err:
                self.req("/api/jobs", "DELETE", {"scope": "all", "confirm": "DELETE"})
            self.assertEqual(err.exception.code, 409)
            self.assertEqual(self.req("/api/jobs/inventory")[1]["total"], 1)
        finally:
            self.server.RequestHandlerClass.run_gate.release()

    def test_cors_blocks_delete_and_tracked_requires_override(self):
        self.db.upsert_jobs([sample()])
        job_id = self.req("/api/jobs")[1]["jobs"][0]["id"]
        FeatureStore(self.db).set_saved([job_id], True)
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.req("/api/jobs", "DELETE", {"ids": [job_id], "confirm": "DELETE"})
        self.assertEqual(err.exception.code, 409)
        self.req("/api/jobs", "DELETE", {"ids": [job_id], "confirm": "DELETE",
                                         "include_tracked": True})
        self.assertEqual(self.req("/api/jobs/inventory")[1]["total"], 0)


if __name__ == "__main__":
    unittest.main()
