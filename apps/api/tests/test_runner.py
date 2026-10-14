import unittest
import tempfile
import os
from jobhunt.db import Database
from jobhunt.freshness import utc_now
from jobhunt.runner import JobRunner
from jobhunt.models import Job, SourceResult

class FakeScraper:
    def __init__(self, jobs, succeed=True):
        self.jobs = jobs
        self.succeed = succeed

    def fetch(self, keyword: str) -> SourceResult:
        if not self.succeed:
            return SourceResult(source="fake", success=False, jobs=[], error_message="Mock error")
        return SourceResult(source="fake", success=True, jobs=self.jobs)

class TestRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.tmp.close()
        self.db = Database(self.tmp.name)

    def tearDown(self):
        try:
            os.remove(self.tmp.name)
        except OSError:
            pass

    def test_runner_executes_source_and_records_run(self):
        job = Job(
            source="fake",
            external_id="1",
            title="Python Dev",
            company="Acme",
            location_raw="SCBD, Jakarta",
            area="jakarta_selatan",
            url="https://example.com/1",
            posted_at=utc_now().isoformat(),
        )
        fake_scraper = FakeScraper([job])
        runner = JobRunner(db=self.db, sources={"fake": fake_scraper.fetch})

        # Create active search
        self.db.create_search(keyword="python", area="all", sources=["fake"])

        summary = runner.run_all_active()
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["status"], "success")
        self.assertEqual(summary[0]["new_count"], 1)

        # Check DB
        jobs = self.db.get_jobs()
        self.assertEqual(len(jobs), 1)

        # Check runs recorded
        runs = self.db.get_latest_runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "success")

if __name__ == "__main__":
    unittest.main()
