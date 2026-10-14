import tempfile
import pathlib
import unittest
from jobhunt.db import Database
from jobhunt.features import FeatureStore, rank_job
from jobhunt.dedup import group_dedup_jobs
from jobhunt.models import Job


def sample(source, external_id, title="Backend Engineer"):
    return Job(source=source, external_id=external_id, title=title, company="Acme",
               location_raw="Jakarta Selatan", area="jakarta_selatan",
               url="https://example.org/" + external_id, work_mode="hybrid")


class TestWorkflowFeatures(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db = Database(str(pathlib.Path(self.folder.name) / "nested" / "jobs.db"))
        self.store = FeatureStore(self.db)
        self.db.upsert_jobs([sample("jobstreet","a"), sample("linkedin","b", "Backend Engineer Intern"),
                             sample("kalibrr","c")])
        self.jobs = self.db.get_jobs()

    def tearDown(self):
        self.folder.cleanup()

    def test_bootstrap_nested_database_directory(self):
        self.assertTrue(pathlib.Path(self.db.db_path).is_file())

    def test_cross_provider_dedup_does_not_merge_internship(self):
        grouped = group_dedup_jobs(self.jobs)
        self.assertEqual(len(grouped), 2)
        normal = next(j for j in grouped if "intern" not in j["title"].lower())
        self.assertEqual(len(normal["ids"]), 2)

    def test_seen_scoped_to_requested_ids(self):
        ids = [j["id"] for j in self.jobs]
        self.assertEqual(self.db.mark_jobs_seen([ids[0]]), 1)
        remaining = {j["id"]:j["is_new"] for j in self.db.get_jobs()}
        self.assertEqual(remaining[ids[0]], 0)
        self.assertTrue(all(remaining[i] == 1 for i in ids[1:]))

    def test_preferences_validation_and_explainable_eligibility(self):
        with self.assertRaises(ValueError):
            self.store.set_preferences({"areas":["surabaya"]})
        prefs = self.store.set_preferences({"role_categories":["backend"],"areas":["jakarta_selatan"],
                                            "work_modes":["hybrid"],"max_required_years":1,
                                            "keywords":["backend"]})
        self.assertEqual(prefs["max_required_years"], 1)
        jobs = self.store.annotate(self.jobs)
        self.assertTrue(any(j["match"]["score"] > 0 for j in jobs))
        senior = dict(self.jobs[0], min_years=5)
        self.assertEqual(rank_job(senior,prefs)["eligibility"],"mismatch")
        unknown = dict(self.jobs[0], min_years=None)
        self.assertEqual(rank_job(unknown,prefs)["eligibility"],"uncertain")

    def test_save_and_application_transition_invariants(self):
        ids = [j["id"] for j in self.jobs]
        result = self.store.set_saved(ids[:2],True)
        self.assertEqual(result["updated"],2)
        self.assertEqual(sum(j["is_saved"] for j in self.store.annotate(self.db.get_jobs())),2)
        with self.assertRaises(ValueError):
            self.store.update_application([ids[0]], {"status":"interview"})
        self.store.update_application(ids[:2], {"status":"applied","notes":"Sent application"})
        self.assertEqual(len(self.store.applications()),2)
        self.store.update_application(ids[:2], {"status":"interview"})
        with self.assertRaises(ValueError):
            self.store.update_application(ids[:2], {"status":"screening"})
        self.assertEqual({j["status"] for j in self.store.applications()}, {"interview"})

    def test_run_batch_lifecycle(self):
        run_id = self.store.create_batch()
        self.store.update_batch(run_id,status="running",total_tasks=3,processed_tasks=1,
                                jobs_found=5,jobs_new=2)
        result = self.store.get_batch(run_id)
        self.assertEqual(result["processed_tasks"],1)
        self.assertEqual(result["jobs_new"],2)

    def test_pipeline_groups_identical_cross_portal_applications(self):
        # Backend Engineer is exposed by jobstreet + kalibrr.
        grouped = group_dedup_jobs(self.db.get_jobs())
        backend = next(j for j in grouped if j["title"] == "Backend Engineer")
        self.store.update_application(backend["ids"], {"status":"applied","notes":"Sent"})
        pipeline = self.store.applications()
        self.assertEqual(len(pipeline),1)
        self.assertEqual(set(pipeline[0]["ids"]),set(backend["ids"]))

    def test_rank_without_profile_does_not_claim_eligible(self):
        match = rank_job(self.jobs[0], self.store.get_preferences())
        self.assertEqual(match["eligibility"],"uncertain")

    def test_reject_invalid_dates_and_external_links(self):
        job_id = self.jobs[0]["id"]
        with self.assertRaises(ValueError):
            self.store.update_application([job_id], {"status":"applied","follow_up_at":"tomorrow"})
        with self.assertRaises(ValueError):
            self.store.update_application([job_id], {"status":"applied","application_url":"javascript:alert(1)"})


if __name__ == "__main__":
    unittest.main()
