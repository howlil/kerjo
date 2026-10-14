import unittest
from jobhunt.dedup import normalize_key, group_dedup_jobs

class TestDedup(unittest.TestCase):
    def test_normalize_key(self):
        k1 = normalize_key("PT. Tokopedia Jaya", "Senior Backend Engineer (Golang)")
        k2 = normalize_key("Tokopedia", "Senior Backend Engineer - Golang")
        self.assertEqual(k1, k2)

    def test_group_jobs(self):
        jobs = [
            {
                "id": 1,
                "source": "jobstreet",
                "title": "Senior Backend Engineer (Golang)",
                "company": "PT Tokopedia",
                "area": "jakarta_selatan",
                "location_raw": "Kebayoran, Jakarta",
                "url": "https://id.jobstreet.com/job/1",
                "salary": "IDR 25M",
                "is_new": 1,
                "first_seen_at": "2026-10-14T01:00:00Z"
            },
            {
                "id": 2,
                "source": "linkedin",
                "title": "Senior Backend Engineer - Golang",
                "company": "Tokopedia",
                "area": "jakarta_selatan",
                "location_raw": "Jakarta Selatan",
                "url": "https://linkedin.com/jobs/view/2",
                "salary": None,
                "is_new": 0,
                "first_seen_at": "2026-10-14T02:00:00Z"
            },
            {
                "id": 3,
                "source": "kalibrr",
                "title": "DevOps Engineer",
                "company": "Gojek",
                "area": "jakarta_selatan",
                "location_raw": "Blok M",
                "url": "https://kalibrr.com/3",
                "salary": None,
                "is_new": 1,
                "first_seen_at": "2026-10-14T03:00:00Z"
            }
        ]

        grouped = group_dedup_jobs(jobs)
        # Should be grouped into 2 distinct jobs
        self.assertEqual(len(grouped), 2)

        # Tokopedia job should have both sources
        tokopedia_job = [g for g in grouped if "tokopedia" in g["company"].lower()][0]
        self.assertEqual(sorted(tokopedia_job["sources"]), ["jobstreet", "linkedin"])
        # Should preserve new state if at least one is new
        self.assertEqual(tokopedia_job["is_new"], 1)

if __name__ == "__main__":
    unittest.main()
