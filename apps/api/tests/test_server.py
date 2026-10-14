import unittest
import urllib.request
import urllib.parse
import json
import threading
import tempfile
import os
from jobhunt.db import Database
from jobhunt.server import create_server

class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        cls.tmp.close()
        cls.db = Database(cls.tmp.name)
        # Add sample search & job
        cls.db.create_search(keyword="python", area="all", sources=["jobstreet"])
        from jobhunt.models import Job
        cls.db.upsert_jobs([
            Job(
                source="jobstreet",
                external_id="101",
                title="Python Developer",
                company="Startup Inc",
                location_raw="Kuningan, Jakarta Selatan",
                area="jakarta_selatan",
                url="https://id.jobstreet.com/job/101",
            )
        ])
        cls.server = create_server(host="127.0.0.1", port=0, db=cls.db)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        try:
            os.remove(cls.tmp.name)
        except OSError:
            pass

    def test_get_jobs(self):
        url = f"http://127.0.0.1:{self.port}/api/jobs"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertIn("jobs", data)
            self.assertEqual(len(data["jobs"]), 1)
            self.assertEqual(data["jobs"][0]["title"], "Python Developer")

    def test_get_searches(self):
        url = f"http://127.0.0.1:{self.port}/api/searches"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertIn("searches", data)
            self.assertEqual(len(data["searches"]), 1)

    def test_mark_seen(self):
        url = f"http://127.0.0.1:{self.port}/api/jobs/1/seen"
        req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)

        # Check job is no longer new
        url_get = f"http://127.0.0.1:{self.port}/api/jobs"
        with urllib.request.urlopen(url_get) as resp:
            data = json.loads(resp.read().decode())
            self.assertEqual(data["jobs"][0]["is_new"], 0)

    def test_get_companies_and_filter(self):
        url = f"http://127.0.0.1:{self.port}/api/companies"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertIn("companies", data)
            self.assertEqual(len(data["companies"]), 1)
            self.assertEqual(data["companies"][0]["company"], "Startup Inc")

        # Test filter jobs by company
        url_filter = f"http://127.0.0.1:{self.port}/api/jobs?company=Startup+Inc"
        with urllib.request.urlopen(url_filter) as resp:
            data = json.loads(resp.read().decode())
            self.assertEqual(len(data["jobs"]), 1)

        url_filter_none = f"http://127.0.0.1:{self.port}/api/jobs?company=NonExistentCo"
        with urllib.request.urlopen(url_filter_none) as resp:
            data = json.loads(resp.read().decode())
            self.assertEqual(len(data["jobs"]), 0)

if __name__ == "__main__":
    unittest.main()
