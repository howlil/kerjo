import unittest
from jobhunt.dedup import normalize_key, group_dedup_jobs, canonical_vacancy_url

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

        # Same employer/title is not evidence of the same requisition.
        grouped = group_dedup_jobs(jobs)
        self.assertEqual(len(grouped), 3)
        self.assertEqual(sorted(len(g["ids"]) for g in grouped), [1, 1, 1])

        # Verified shared vacancy URL (tracking parameters ignored) may merge.
        jobs[1]["url"] = "https://id.jobstreet.com/job/1?utm_source=linkedin"
        grouped = group_dedup_jobs(jobs)
        self.assertEqual(len(grouped), 2)
        tokopedia = next(g for g in grouped if "tokopedia" in g["company"].lower())
        self.assertEqual(sorted(tokopedia["sources"]), ["jobstreet", "linkedin"])

    def test_canonical_url_preserves_vacancy_id_query(self):
        first = canonical_vacancy_url("https://www.example.com/jobs?id=10&utm_source=mail")
        second = canonical_vacancy_url("https://example.com/jobs?id=11")
        self.assertNotEqual(first, second)
        self.assertEqual(first, "https://example.com/jobs?id=10")

    def test_distinct_external_ids_same_title_do_not_merge(self):
        jobs = [
            {"id": 1, "source": "jobstreet", "external_id": "a", "url": "https://jobstreet.com/job/a",
             "title": "Backend Engineer", "company": "Acme", "area": "jakarta_selatan", "is_new": 1},
            {"id": 2, "source": "jobstreet", "external_id": "b", "url": "https://jobstreet.com/job/b",
             "title": "Backend Engineer", "company": "Acme", "area": "jakarta_selatan", "is_new": 1},
        ]
        self.assertEqual(len(group_dedup_jobs(jobs)), 2)


if __name__ == "__main__":
    unittest.main()
