import unittest
import json
import pathlib
from jobhunt.sources.jobstreet import parse_jobstreet_payload
from jobhunt.sources.kalibrr import parse_kalibrr_payload

FIXTURES_DIR = pathlib.Path(r"C:\Users\howlil\.gemini\antigravity-cli\brain\1fe91d56-424d-4447-a570-033c3b5e0792\scratch\fixtures")

class TestSourcesParser(unittest.TestCase):
    def test_parse_jobstreet(self):
        js_file = FIXTURES_DIR / "jobstreet.json"
        if not js_file.exists():
            self.skipTest("jobstreet.json fixture not found")
        data = json.loads(js_file.read_text(encoding="utf-8"))
        jobs = parse_jobstreet_payload(data)
        self.assertGreater(len(jobs), 0)
        first = jobs[0]
        self.assertEqual(first.source, "jobstreet")
        self.assertTrue(first.title)
        self.assertTrue(first.company)
        self.assertTrue(first.url.startswith("https://id.jobstreet.com/job/"))
        # Area should be matched (e.g., jakarta_barat or unspecified) and not None
        self.assertIsNotNone(first.area)

    def test_parse_kalibrr(self):
        kb_file = FIXTURES_DIR / "kalibrr.json"
        if not kb_file.exists():
            self.skipTest("kalibrr.json fixture not found")
        data = json.loads(kb_file.read_text(encoding="utf-8"))
        jobs = parse_kalibrr_payload(data)
        # Note: some jobs in fixture might be in Bekasi/excluded areas, so only non-excluded areas are returned
        self.assertGreater(len(jobs), 0)
        first = jobs[0]
        self.assertEqual(first.source, "kalibrr")
        self.assertTrue(first.title)
        self.assertTrue(first.company)
        self.assertTrue("kalibrr.com" in first.url)
        self.assertIsNotNone(first.area)

if __name__ == "__main__":
    unittest.main()
