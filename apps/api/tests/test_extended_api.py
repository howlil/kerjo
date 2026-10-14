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
from jobhunt.freshness import utc_now
from jobhunt.models import Job, SourceResult
from jobhunt.server import create_server


class TestExtendedAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(pathlib.Path(self.tmp.name) / "jobs.db"))
        self.db.upsert_jobs([
            Job(source="jobstreet",external_id="1",title="Backend Engineer",company="Acme",
                location_raw="Jakarta Selatan",area="jakarta_selatan",url="https://example.org/a",posted_at=utc_now().isoformat()),
            Job(source="linkedin",external_id="2",title="Backend Engineer",company="Acme",
                location_raw="Jakarta Selatan",area="jakarta_selatan",url="https://example.org/a?utm_source=linkedin",posted_at=utc_now().isoformat()),
            Job(source="jobstreet",external_id="3",title="Frontend Developer",company="Acme",
                location_raw="Jakarta Selatan",area="jakarta_selatan",url="https://example.org/c",posted_at=utc_now().isoformat()),
        ])
        self.db.create_search("Backend",sources=["jobstreet"])
        self.server = create_server("127.0.0.1",0,self.db)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def api(self,path,method="GET",payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:%s%s" % (self.port,path),
            data=body,method=method,
            headers={"Content-Type":"application/json"}
        )
        with urllib.request.urlopen(req,timeout=3) as response:
            return response.status, json.loads(response.read().decode())

    def test_dedup_before_pagination_and_total(self):
        _, first = self.api("/api/jobs?limit=1&offset=0")
        _, second = self.api("/api/jobs?limit=1&offset=1")
        self.assertEqual(first["total"],2)
        self.assertEqual(second["total"],2)
        self.assertNotEqual(first["jobs"][0]["title"],second["jobs"][0]["title"])

    def test_scoped_seen_endpoint(self):
        _, jobs = self.api("/api/jobs?dedup=0")
        first_id = jobs["jobs"][0]["id"]
        self.api("/api/jobs/seen-all","POST",{"ids":[first_id]})
        _, updated = self.api("/api/jobs?dedup=0")
        seen = {j["id"]:j["is_new"] for j in updated["jobs"]}
        self.assertEqual(seen[first_id],0)
        self.assertEqual(sum(v==0 for v in seen.values()),1)

    def test_preferences_and_application_api(self):
        self.api("/api/preferences","PUT",{"role_categories":["backend"],"max_required_years":1})
        _, prefs = self.api("/api/preferences")
        self.assertEqual(prefs["preferences"]["max_required_years"],1)
        _, data = self.api("/api/jobs?dedup=0")
        job_id = data["jobs"][0]["id"]
        self.api("/api/jobs/%s/save" % job_id,"POST",{"saved":True})
        self.api("/api/jobs/%s/application" % job_id,"PUT",{"status":"applied","notes":"sent"})
        _, apps = self.api("/api/applications")
        self.assertEqual(len(apps["applications"]),1)
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.api("/api/jobs/%s/application" % job_id,"PUT",{"status":"not_applied"})
        self.assertEqual(err.exception.code,400)

    def test_async_run_does_not_block_reads(self):
        def fetch(_):
            time.sleep(0.5)
            return SourceResult(source="jobstreet",success=True,jobs=[])
        with patch("jobhunt.runner.DEFAULT_SOURCES",{"jobstreet":fetch}):
            status, started = self.api("/api/run","POST",{})
            self.assertEqual(status,202)
            start = time.monotonic()
            self.api("/api/jobs?limit=1")
            self.assertLess(time.monotonic()-start,0.45)
            run_id=started["run_id"]
            for _ in range(40):
                _, progress = self.api("/api/run/%s" % run_id)
                if progress["run"]["status"] in ("completed","partial","failed"):
                    break
                time.sleep(0.05)
            self.assertEqual(progress["run"]["status"],"completed")

    def test_paused_search_returns_skipped_without_new_tasks(self):
        for search in self.db.get_searches():
            self.db.set_search_active(search["id"], False)
        status, response = self.api("/api/run","POST",{})
        self.assertEqual(status,202)
        for _ in range(50):
            _, result = self.api("/api/run/" + str(response["run_id"]))
            if result["run"]["status"] in ("skipped", "completed", "failed"):
                break
            time.sleep(0.05)
        self.assertEqual(result["run"]["status"],"skipped")
        self.assertEqual(result["run"]["total_tasks"],0)
        self.assertEqual(len(self.db.get_searches(active_only=True)),0)

    def test_paginated_results_visit_every_unique_vacancy(self):
        extra = [Job(source="kalibrr", external_id="page-" + str(n),
                     title="Backend Engineer", company="Pagination Corp",
                     location_raw="Jakarta Selatan", area="jakarta_selatan",
                     url="https://example.org/roles/" + str(n), posted_at=utc_now().isoformat())
                 for n in range(125)]
        self.db.upsert_jobs(extra)
        seen_ids = set()
        # Initial 3 source records contain one verified cross-source URL
        # representing the same vacancy, therefore 2 unique + 125 = 127.
        for offset in range(0, 127, 30):
            _, response = self.api("/api/jobs?limit=30&offset=" + str(offset))
            self.assertEqual(response["total"], 127)
            for job in response["jobs"]:
                self.assertNotIn(job["id"], seen_ids)
                seen_ids.add(job["id"])
        self.assertEqual(len(seen_ids), 127)

    def test_untrusted_origin_write_rejected(self):
        req=urllib.request.Request(
            "http://127.0.0.1:%s/api/jobs/seen-all" % self.port,
            data=b'{"ids":[1]}',method="POST",
            headers={"Content-Type":"application/json","Origin":"https://malicious.example"}
        )
        with self.assertRaises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(req)
        self.assertEqual(err.exception.code,403)


if __name__ == "__main__":
    unittest.main()
