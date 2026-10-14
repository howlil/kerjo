import unittest
import json
import pathlib
from jobhunt.sources.jobstreet import parse_jobstreet_payload
from jobhunt.sources.kalibrr import parse_kalibrr_payload

from jobhunt.sources.linkedin import parse_linkedin_html
from jobhunt.sources.glints import parse_glints_payload
from jobhunt.sources.dealls import parse_dealls_payload

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"

class TestSourcesParser(unittest.TestCase):
    def test_parse_jobstreet(self):
        js_file = FIXTURES_DIR / "jobstreet.json"
        self.assertTrue(js_file.exists(), "Required test fixture missing")
        data = json.loads(js_file.read_text(encoding="utf-8"))
        jobs = parse_jobstreet_payload(data)
        self.assertGreater(len(jobs), 0)
        first = jobs[0]
        self.assertEqual(first.source, "jobstreet")
        self.assertTrue(first.title)
        self.assertTrue(first.company)
        self.assertTrue(first.url.startswith("https://id.jobstreet.com/job/"))
        self.assertIsNotNone(first.area)

    def test_parse_kalibrr(self):
        kb_file = FIXTURES_DIR / "kalibrr.json"
        self.assertTrue(kb_file.exists(), "Required test fixture missing")
        data = json.loads(kb_file.read_text(encoding="utf-8"))
        jobs = parse_kalibrr_payload(data)
        self.assertGreater(len(jobs), 0)
        first = jobs[0]
        self.assertEqual(first.source, "kalibrr")
        self.assertTrue(first.title)
        self.assertTrue(first.company)
        self.assertTrue("kalibrr.com" in first.url)
        self.assertIsNotNone(first.area)

    def test_parse_linkedin(self):
        li_file = FIXTURES_DIR / "linkedin.html"
        self.assertTrue(li_file.exists(), "Required test fixture missing")
        html_content = li_file.read_text(encoding="utf-8")
        jobs = parse_linkedin_html(html_content)
        self.assertGreater(len(jobs), 0)
        first = jobs[0]
        self.assertEqual(first.source, "linkedin")
        self.assertTrue(first.title)
        self.assertTrue(first.company)
        self.assertTrue("linkedin.com" in first.url)
        self.assertIsNotNone(first.area)

    def test_parse_glints(self):
        gl_file = FIXTURES_DIR / "glints_next_data.json"
        self.assertTrue(gl_file.exists(), "Required test fixture missing")
        data = json.loads(gl_file.read_text(encoding="utf-8"))
        jobs = parse_glints_payload(data)
        self.assertGreater(len(jobs), 0)
        first = jobs[0]
        self.assertEqual(first.source, "glints")
        self.assertTrue(first.title)
        self.assertTrue(first.company)
        self.assertTrue("glints.com" in first.url)
        self.assertIsNotNone(first.area)

    def test_parse_dealls(self):
        sample = {
            "data": {
                "docs": [
                    {
                        "id": "abc123",
                        "slug": "senior-backend-engineer",
                        "role": "Senior Backend Engineer",
                        "company": {"name": "Tokopedia"},
                        "city": {"name": "Jakarta Selatan"},
                        "country": {"name": "Indonesia"},
                        "workplaceType": "hybrid",
                        "employmentTypes": ["fullTime"],
                        "salaryRange": {"min": 20000000, "max": 35000000, "currency": "IDR"},
                        "publishedAt": "2026-10-14T07:00:00Z"
                    }
                ]
            }
        }
        jobs = parse_dealls_payload(sample)
        self.assertEqual(len(jobs), 1)
        j = jobs[0]
        self.assertEqual(j.source, "dealls")
        self.assertEqual(j.title, "Senior Backend Engineer")
        self.assertEqual(j.company, "Tokopedia")
        self.assertEqual(j.area, "jakarta_selatan")
        self.assertEqual(j.url, "https://dealls.com/loker/senior-backend-engineer")
        self.assertTrue(j.is_remote)
        self.assertEqual(j.salary, "IDR 20,000,000 - 35,000,000")

if __name__ == "__main__":
    unittest.main()
