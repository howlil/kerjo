import unittest
import tempfile
import pathlib
import os
from jobhunt.db import Database
from jobhunt.models import Job

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.tmp.close()
        self.db = Database(self.tmp.name)

    def tearDown(self):
        try:
            os.remove(self.tmp.name)
        except OSError:
            pass

    def test_save_and_dedup_jobs(self):
        job1 = Job(
            source="jobstreet",
            external_id="123",
            title="Backend Engineer",
            company="Tech Corp",
            location_raw="Kebayoran, Jakarta",
            area="jakarta_selatan",
            url="https://id.jobstreet.com/job/123",
            salary="IDR 15,000,000",
            work_type="Full time",
            is_remote=False,
            posted_at="2026-10-14T07:00:00Z",
        )
        # First save: should be recorded as new
        new_count, total = self.db.upsert_jobs([job1])
        self.assertEqual(new_count, 1)
        self.assertEqual(total, 1)

        jobs = self.db.get_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["is_new"], 1)

        # Mark as read/seen
        self.db.mark_job_seen(jobs[0]["id"])
        jobs_after = self.db.get_jobs()
        self.assertEqual(jobs_after[0]["is_new"], 0)

        # Upsert again in subsequent run: should NOT be new, and should keep is_new = 0
        new_count2, total2 = self.db.upsert_jobs([job1])
        self.assertEqual(new_count2, 0)
        jobs_again = self.db.get_jobs()
        self.assertEqual(len(jobs_again), 1)
        self.assertEqual(jobs_again[0]["is_new"], 0)

    def test_searches_crud(self):
        search_id = self.db.create_search(keyword="python", area="all", sources=["jobstreet", "kalibrr"])
        self.assertGreater(search_id, 0)

        searches = self.db.get_searches()
        self.assertEqual(len(searches), 1)
        self.assertEqual(searches[0]["keyword"], "python")
        self.assertEqual(searches[0]["is_active"], 1)

        self.db.set_search_active(search_id, active=False)
        searches_after = self.db.get_searches(active_only=True)
        self.assertEqual(len(searches_after), 0)

    def test_experience_and_category_filtering(self):
        j_junior = Job(
            source="kalibrr",
            external_id="j1",
            title="Junior Frontend Engineer",
            company="Startup",
            location_raw="Jakarta",
            area="unspecified",
            url="https://kalibrr.com/j1",
            description="Fresh graduate are welcome. 0-1 tahun pengalaman.",
        )
        j_senior = Job(
            source="linkedin",
            external_id="j2",
            title="Senior Backend Engineer",
            company="BigTech",
            location_raw="Jakarta Selatan",
            area="jakarta_selatan",
            url="https://linkedin.com/j2",
            description="Minimal 5 tahun pengalaman di arsitektur microservices.",
        )
        self.db.upsert_jobs([j_junior, j_senior])

        # Query all
        all_jobs = self.db.get_jobs()
        self.assertEqual(len(all_jobs), 2)

        # Query entry level only
        entry_jobs = self.db.get_jobs(experience_level="entry")
        self.assertEqual(len(entry_jobs), 1)
        self.assertEqual(entry_jobs[0]["title"], "Junior Frontend Engineer")

        # Query senior level only
        senior_jobs = self.db.get_jobs(experience_level="senior")
        self.assertEqual(len(senior_jobs), 1)
        self.assertEqual(senior_jobs[0]["title"], "Senior Backend Engineer")

        # Query by role category
        fe_jobs = self.db.get_jobs(role_category="frontend")
        self.assertEqual(len(fe_jobs), 1)
        self.assertEqual(fe_jobs[0]["title"], "Junior Frontend Engineer")

if __name__ == "__main__":
    unittest.main()
