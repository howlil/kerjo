"""Publication freshness, manual run, and legacy database regression tests."""
import datetime as dt
import pathlib
import tempfile
import unittest

from jobhunt.db import Database
from jobhunt.freshness import parse_posted_at, posting_age_status, recent_posting, utc_now
from jobhunt.models import Job, SourceResult
from jobhunt.runner import JobRunner


def make_job(external_id, posted_at, source="jobstreet"):
    return Job(source=source, external_id=external_id, title="Backend Engineer",
               company="Acme", location_raw="Jakarta Selatan",
               area="jakarta_selatan", url="https://example.com/job/" + external_id,
               posted_at=posted_at)


class TestFourteenDayFreshness(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 10, 14, 10, 0, tzinfo=dt.timezone.utc)

    def test_exact_rolling_cutoff_and_future(self):
        now = self.now
        self.assertEqual(posting_age_status(now.isoformat(), now), "recent")
        self.assertEqual(posting_age_status((now-dt.timedelta(days=14)).isoformat(), now), "recent")
        self.assertEqual(posting_age_status((now-dt.timedelta(days=14, seconds=1)).isoformat(), now), "old")
        self.assertEqual(posting_age_status((now+dt.timedelta(minutes=6)).isoformat(), now), "future")
        self.assertEqual(posting_age_status(None, now), "unknown")
        self.assertEqual(posting_age_status("recently", now), "unknown")

    def test_timezone_and_date_only_boundaries(self):
        self.assertEqual(posting_age_status("2026-09-30", self.now), "old")
        self.assertEqual(posting_age_status("2026-10-01", self.now), "recent")
        self.assertEqual(parse_posted_at("2026-10-14").isoformat(), "2026-10-13T17:00:00+00:00")
        self.assertEqual(posting_age_status("2026-10-13T08:00:00+07:00", self.now), "recent")

    def test_relative_and_epoch_data(self):
        self.assertEqual(posting_age_status("2 days ago", self.now), "recent")
        self.assertEqual(posting_age_status("3 hari lalu", self.now), "recent")
        self.assertEqual(posting_age_status("3 weeks ago", self.now), "old")
        self.assertEqual(posting_age_status(int(self.now.timestamp()), self.now), "recent")
        self.assertEqual(posting_age_status(int(self.now.timestamp() * 1000), self.now), "recent")

    def test_manual_runner_records_exclusion_reasons(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(str(pathlib.Path(folder) / "jobs.db"))
            now = utc_now()
            received = [
                make_job("recent", (now-dt.timedelta(days=1)).isoformat()),
                make_job("old", (now-dt.timedelta(days=17)).isoformat()),
                make_job("unknown", None),
                make_job("future", (now+dt.timedelta(hours=3)).isoformat()),
            ]
            def fetch(_):
                return SourceResult(source="jobstreet", success=True, jobs=received)
            runner = JobRunner(db=db, sources={"jobstreet": fetch})
            result = runner.run_single("backend", source_names=["jobstreet"])
            self.assertEqual(len(result), 1)
            summary = result[0]
            self.assertEqual(summary["status"], "success")
            self.assertEqual(summary["found_count"], 4)
            self.assertEqual(summary["recent_count"], 1)
            self.assertEqual(summary["filtered_old"], 1)
            self.assertEqual(summary["filtered_unknown"], 1)
            self.assertEqual(summary["filtered_future"], 1)
            self.assertEqual([j["external_id"] for j in db.get_jobs()], ["recent"])
            last = db.get_latest_runs(limit=1)[0]
            self.assertEqual(last["jobs_recent"], 1)
            self.assertEqual(last["filtered_unknown"], 1)

    def test_discovery_filters_legacy_rows_without_deleting_applications(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(str(pathlib.Path(folder) / "jobs.db"))
            now = utc_now()
            db.upsert_jobs([
                make_job("new", now.isoformat()),
                make_job("old", (now-dt.timedelta(days=30)).isoformat()),
                make_job("undated", None)
            ])
            all_rows = db.get_jobs(limit=None)
            self.assertEqual(len(all_rows), 3)
            recent_rows = db.get_jobs(limit=None, posted_within_days=14)
            self.assertEqual([r["external_id"] for r in recent_rows], ["new"])
            self.assertEqual(db.get_companies(posted_within_days=14)[0]["job_count"], 1)
            from jobhunt.features import FeatureStore
            store = FeatureStore(db)
            old_id = next(j["id"] for j in all_rows if j["external_id"] == "old")
            store.update_application([old_id], {"status":"applied","notes":"Historical record retained"})
            self.assertEqual(store.applications()[0]["job_id"], old_id)
            self.assertEqual(len(db.get_jobs(limit=None, posted_within_days=14)), 1)


if __name__=="__main__":
    unittest.main()
