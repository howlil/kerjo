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

    def test_rejection_of_non_technical_jobs(self):
        j_pm = Job(
            source="jobstreet",
            external_id="pm1",
            title="IT Project Manager (Junior)",
            company="Agency",
            location_raw="Jakarta",
            area="jakarta_selatan",
            url="https://jobstreet.com/pm1",
            description="Manage sprints and document meetings"
        )
        j_maintenance = Job(
            source="jobstreet",
            external_id="m1",
            title="Maintenance Service Engineer EV Charger",
            company="EV Co",
            location_raw="Jakarta",
            area="jakarta_barat",
            url="https://jobstreet.com/m1",
            description="Service EV charger units"
        )
        j_sales = Job(
            source="glints",
            external_id="s1",
            title="Technical Sales Engineer",
            company="B2B Co",
            location_raw="Jakarta",
            area="jakarta_pusat",
            url="https://glints.com/s1",
            description="Sell B2B industrial machinery"
        )
        j_valid = Job(
            source="kalibrr",
            external_id="v1",
            title="Go Backend Developer",
            company="Tech Corp",
            location_raw="Jakarta Selatan",
            area="jakarta_selatan",
            url="https://kalibrr.com/v1",
            description="Golang microservices and PostgreSQL"
        )

        new_count, total = self.db.upsert_jobs([j_pm, j_maintenance, j_sales, j_valid])
        # Only the valid technical job should be inserted!
        self.assertEqual(new_count, 1)

        jobs = self.db.get_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Go Backend Developer")

    def test_reset_database(self):
        j_valid = Job(
            source="kalibrr",
            external_id="v2",
            title="DevOps Engineer",
            company="Cloud Co",
            location_raw="Jakarta",
            area="jakarta_selatan",
            url="https://kalibrr.com/v2",
        )
        self.db.upsert_jobs([j_valid])
        self.assertEqual(len(self.db.get_jobs()), 1)

        self.db.reset_database()
        self.assertEqual(len(self.db.get_jobs()), 0)

    def test_company_filter_and_logo(self):
        j1 = Job(
            source="jobstreet",
            external_id="c1",
            title="Backend Engineer",
            company="Tokopedia",
            location_raw="Jakarta",
            area="jakarta_selatan",
            url="https://jobstreet.com/c1",
            company_logo="https://logo.com/tokopedia.png",
        )
        j2 = Job(
            source="kalibrr",
            external_id="c2",
            title="Frontend Engineer",
            company="Shopee",
            location_raw="Jakarta",
            area="jakarta_selatan",
            url="https://kalibrr.com/c2",
            company_logo="https://logo.com/shopee.png",
        )
        j3 = Job(
            source="linkedin",
            external_id="c3",
            title="Fullstack Developer",
            company="Tokopedia",
            location_raw="Jakarta",
            area="jakarta_selatan",
            url="https://linkedin.com/c3",
        )
        self.db.upsert_jobs([j1, j2, j3])

        # Test company filter
        tokopedia_jobs = self.db.get_jobs(company="Tokopedia")
        self.assertEqual(len(tokopedia_jobs), 2)
        self.assertTrue(all(j["company"] == "Tokopedia" for j in tokopedia_jobs))

        shopee_jobs = self.db.get_jobs(company="Shopee")
        self.assertEqual(len(shopee_jobs), 1)
        self.assertEqual(shopee_jobs[0]["company_logo"], "https://logo.com/shopee.png")

        # Test get_companies aggregation
        companies = self.db.get_companies()
        company_names = [c["company"] for c in companies]
        self.assertIn("Tokopedia", company_names)
        self.assertIn("Shopee", company_names)
        tokopedia_stat = next(c for c in companies if c["company"] == "Tokopedia")
        self.assertEqual(tokopedia_stat["job_count"], 2)
        self.assertEqual(tokopedia_stat["company_logo"], "https://logo.com/tokopedia.png")

if __name__ == "__main__":
    unittest.main()
