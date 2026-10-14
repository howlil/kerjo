import unittest
from jobhunt.sources.karir import parse_karir_payload
from jobhunt.sources.techinasia import parse_tia_payload

class TestKarirAndTiaParsers(unittest.TestCase):
    def test_karir_parsing(self):
        sample_karir = {
            "code": 200,
            "data": {
                "opportunities": [
                    {
                        "id": 12345,
                        "job_position": "Backend Engineer",
                        "company_name": "Tech Corp",
                        "description": "Jakarta Selatan",
                        "salary_lower": 10000000,
                        "salary_upper": 15000000,
                        "posted_at": "2026-10-10T12:00:00Z"
                    },
                    {
                        "id": 67890,
                        "job_position": "Civil Engineer",
                        "company_name": "Build Corp",
                        "description": "Bekasi",  # Excluded area
                        "salary_lower": 0,
                        "salary_upper": 0,
                        "posted_at": "2026-10-11T12:00:00Z"
                    }
                ]
            }
        }
        jobs = parse_karir_payload(sample_karir)
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job.source, "karir")
        self.assertEqual(job.external_id, "12345")
        self.assertEqual(job.title, "Backend Engineer")
        self.assertEqual(job.company, "Tech Corp")
        self.assertEqual(job.area, "jakarta_selatan")
        self.assertIn("10.000.000", job.salary)
        self.assertEqual(job.url, "https://www.karir.com/opportunities/12345")

    def test_tia_parsing(self):
        sample_tia = {
            "data": [
                {
                    "id": "tia-1",
                    "title": "Fullstack Developer",
                    "company": {"name": "Startup Indo"},
                    "city": {"name": "Tangerang"},
                    "salary_min": 8000000,
                    "salary_max": 12000000,
                    "currency": {"currency_symbol": "Rp"},
                    "is_remote": True,
                    "published_at": "2026-10-12 10:00:00"
                },
                {
                    "id": "tia-2",
                    "title": "Site Manager",
                    "company": {"name": "Bandung Tech"},
                    "city": {"name": "Bandung"},  # Excluded area
                    "salary_min": 0,
                    "salary_max": 0,
                    "is_remote": False
                }
            ]
        }
        jobs = parse_tia_payload(sample_tia)
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job.source, "techinasia")
        self.assertEqual(job.external_id, "tia-1")
        self.assertEqual(job.title, "Fullstack Developer")
        self.assertEqual(job.company, "Startup Indo")
        self.assertEqual(job.area, "unspecified")  # Tangerang maps to unspecified
        self.assertTrue(job.is_remote)
        self.assertIn("8.000.000", job.salary)

if __name__ == "__main__":
    unittest.main()
