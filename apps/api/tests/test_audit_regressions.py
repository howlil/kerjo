"""Cross-platform lock and startup correctness regressions.

These tests must run on both Windows and Linux; pure mock tests cannot
detect Windows-specific file locking errors.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from jobhunt.db import Database
from jobhunt.runner import JobRunner, RunnerLock
from jobhunt.sources.karir import parse_karir_payload


class TestLockAndInitialization(unittest.TestCase):
    def test_exclusive_lock_across_processes_and_reentry(self):
        with tempfile.TemporaryDirectory(prefix="kerjo test ") as directory:
            lock_path = str(pathlib.Path(directory) / "worker.lock")
            child = (
                "import sys; "
                "from jobhunt.runner import RunnerLock,LockAcquireError; "
                "lock=RunnerLock(sys.argv[1]); "
                "\ntry:\n"
                " with lock: sys.exit(0)\n"
                "except LockAcquireError: sys.exit(75)\n"
            )
            with RunnerLock(lock_path):
                conflict = subprocess.run([sys.executable, "-c", child, lock_path],
                                          capture_output=True, text=True, timeout=10)
                self.assertEqual(conflict.returncode, 75, conflict.stderr)
                self.assertTrue(pathlib.Path(lock_path).exists())
            allowed = subprocess.run([sys.executable, "-c", child, lock_path],
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            # Lock file persists: removing it causes inode replacement races.
            self.assertTrue(pathlib.Path(lock_path).exists())

    def test_crashed_process_releases_lock(self):
        with tempfile.TemporaryDirectory(prefix="kerjo crash ") as directory:
            lock_path = str(pathlib.Path(directory) / "worker.lock")
            script = (
                "import os,sys;from jobhunt.runner import RunnerLock;"
                "\nwith RunnerLock(sys.argv[1]): os._exit(0)\n"
            )
            child = subprocess.run([sys.executable, "-c", script, lock_path],
                                   capture_output=True, text=True, timeout=10)
            self.assertEqual(child.returncode, 0, child.stderr)
            with RunnerLock(lock_path):
                self.assertTrue(pathlib.Path(lock_path).is_file())

    def test_seed_all_eight_default_searches_and_do_not_restart_paused(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(str(pathlib.Path(directory) / "db.sqlite"))
            db.seed_default_searches()
            searches = db.get_searches()
            self.assertEqual(len(searches), 8)
            self.assertEqual({s["keyword"] for s in searches},
                             {"Backend Engineer", "Frontend Engineer", "Fullstack Developer",
                              "Mobile Developer", "DevOps Engineer", "Data Engineer",
                              "QA Engineer", "Product Engineer"})
            for search in searches:
                db.set_search_active(search["id"], False)
            progress = []
            result = JobRunner(db=db, sources={}).run_all_active(on_progress=lambda *v: progress.append(v))
            self.assertEqual(result, [])
            self.assertEqual(progress[-1], (None, 0, 0))
            self.assertEqual(len(db.get_searches(active_only=True)), 0)

    def test_seniority_filters_do_not_overlap(self):
        from jobhunt.models import Job
        with tempfile.TemporaryDirectory() as directory:
            db=Database(str(pathlib.Path(directory)/"jobs.db"))
            db.upsert_jobs([
                Job(source="jobstreet",external_id="entry",title="Junior Backend Engineer",
                    company="Acme",location_raw="Jakarta",area="unspecified",
                    url="https://example.com/entry",description="Fresh graduate"),
                Job(source="linkedin",external_id="mid",title="Backend Engineer",
                    company="Acme",location_raw="Jakarta",area="unspecified",
                    url="https://example.com/mid",description="Minimum 1 year experience"),
                Job(source="kalibrr",external_id="senior",title="Senior Backend Engineer",
                    company="Acme",location_raw="Jakarta",area="unspecified",
                    url="https://example.com/senior",description="Minimum 5 years experience"),
            ])
            groups={key:{j["external_id"] for j in db.get_jobs(experience_level=key)}
                    for key in ("entry","mid","senior")}
            self.assertEqual(groups,{"entry":{"entry"},"mid":{"mid"},"senior":{"senior"}})

    def test_karir_description_is_not_location(self):
        item={"id":"x","job_position":"Backend Engineer","company_name":"Acme",
              "description":"Backend Engineer in Surabaya, responsible for APIs"}
        jobs=parse_karir_payload({"data":{"opportunities":[item]}})
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0].location_raw,"")
        self.assertEqual(jobs[0].area,"unspecified")
        item["city_name"]="Jakarta Selatan"
        jobs=parse_karir_payload({"data":{"opportunities":[item]}})
        self.assertEqual(jobs[0].area,"jakarta_selatan")


if __name__=="__main__":
    unittest.main()
