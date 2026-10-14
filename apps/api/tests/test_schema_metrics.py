"""Additive metric migrations preserve local single-user data."""
import pathlib
import tempfile
import unittest
from jobhunt.db import Database
from jobhunt.features import FeatureStore


class TestMetricMigration(unittest.TestCase):
    def test_legacy_source_run_schema_is_additively_upgraded(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(pathlib.Path(directory)/"legacy.sqlite")
            db=Database(path)
            with db._get_connection() as conn:
                conn.execute("DROP TABLE job_runs")
                conn.execute("""CREATE TABLE job_runs(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_id INTEGER, source TEXT, status TEXT,
                    jobs_found INTEGER DEFAULT 0, jobs_new INTEGER DEFAULT 0,
                    error_message TEXT, ran_at TEXT)""")
                conn.execute("""INSERT INTO job_runs(source,status,jobs_found,
                    jobs_new,error_message,ran_at) VALUES(
                    'jobstreet','success',5,2,NULL,'2026-10-10T00:00:00Z')""")
            upgraded=Database(path)
            self.assertEqual(upgraded.get_latest_runs(5)[0]["jobs_new"],2)
            upgraded.record_run(source="linkedin",status="partial",
                                pages_fetched=2,retry_count=1,
                                details_enriched=1,duration_ms=400)
            rows=upgraded.get_latest_runs(5)
            self.assertEqual(rows[0]["pages_fetched"],2)
            self.assertEqual(rows[0]["retry_count"],1)
            self.assertEqual(rows[0]["details_enriched"],1)
            self.assertEqual(rows[0]["duration_ms"],400)
            self.assertEqual(rows[1]["jobs_new"],2)

    def test_legacy_batch_schema_is_upgraded_without_deleting_history(self):
        with tempfile.TemporaryDirectory() as directory:
            db=Database(str(pathlib.Path(directory)/"db.sqlite"))
            FeatureStore(db)
            with db._get_connection() as conn:
                conn.execute("DROP TABLE run_batches")
                conn.execute("""CREATE TABLE run_batches(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL, total_tasks INTEGER DEFAULT 0,
                    processed_tasks INTEGER DEFAULT 0,
                    jobs_found INTEGER DEFAULT 0, jobs_new INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,error_message TEXT,
                    created_at TEXT NOT NULL,started_at TEXT,finished_at TEXT)""")
                conn.execute("""INSERT INTO run_batches(status,created_at)
                                VALUES('completed','2026-10-10T00:00:00Z')""")
            store=FeatureStore(db)
            self.assertEqual(store.get_batch(1)["status"],"completed")
            run_id=store.create_batch()
            store.update_batch(run_id,pages_fetched=4,retry_count=2,
                               details_enriched=1,duration_ms=700)
            batch=store.get_batch(run_id)
            self.assertEqual(batch["pages_fetched"],4)
            self.assertEqual(batch["retry_count"],2)
            self.assertEqual(store.get_batch(1)["status"],"completed")


if __name__=="__main__":
    unittest.main()
