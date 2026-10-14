import unittest
from jobhunt.classifier import classify_job, extract_experience, classify_role

class TestJobClassifier(unittest.TestCase):
    def test_extract_experience_entry(self):
        cases = [
            ("Fresh graduate are welcome to apply", "entry", 0, 1),
            ("Lulusan baru D3/S1 Teknik Informatika", "entry", 0, 1),
            ("Memiliki pengalaman 0-1 tahun", "entry", 0, 1),
            ("0 - 2 years of experience in Python", "entry", 0, 2),
            ("Maksimal 1 tahun pengalaman", "entry", 0, 1),
        ]
        for text, exp_level, exp_min, exp_max in cases:
            with self.subTest(text=text):
                res = extract_experience(text)
                self.assertEqual(res["level"], exp_level, f"Failed for text: {text}")
                self.assertEqual(res["min_years"], exp_min)
                self.assertEqual(res["max_years"], exp_max)

    def test_extract_experience_mid(self):
        cases = [
            ("Minimal 1 tahun pengalaman kerja", "mid", 1, None),
            ("Min 2 tahun pengalaman sebagai backend developer", "mid", 2, None),
            ("Pengalaman 1 - 3 tahun dalam React", "mid", 1, 3),
            ("At least 2 years experience in Go", "mid", 2, None),
            ("2-4 years of professional experience", "mid", 2, 4),
        ]
        for text, exp_level, exp_min, exp_max in cases:
            with self.subTest(text=text):
                res = extract_experience(text)
                self.assertEqual(res["level"], exp_level, f"Failed for text: {text}")
                self.assertEqual(res["min_years"], exp_min)

    def test_extract_experience_senior(self):
        cases = [
            ("Minimal 5 tahun pengalaman", "senior", 5, None),
            ("Lebih dari 3 tahun pengalaman", "senior", 3, None),
            ("At least 5+ years experience as team lead", "senior", 5, None),
            ("> 5 years experience in distributed systems", "senior", 5, None),
        ]
        for text, exp_level, exp_min, exp_max in cases:
            with self.subTest(text=text):
                res = extract_experience(text)
                self.assertEqual(res["level"], exp_level, f"Failed for text: {text}")
                self.assertGreaterEqual(res["min_years"], 3)

    def test_classify_role_and_exclusion(self):
        # Software engineering roles
        self.assertEqual(classify_role("Junior Backend Engineer"), "backend")
        self.assertEqual(classify_role("Frontend Developer React"), "frontend")
        self.assertEqual(classify_role("Fullstack Software Engineer"), "fullstack")
        self.assertEqual(classify_role("Software Engineer - Core Platform"), "software_engineer")
        self.assertEqual(classify_role("DevOps Engineer / SRE"), "devops")
        self.assertEqual(classify_role("Mobile Developer (Flutter/iOS)"), "mobile")
        self.assertEqual(classify_role("QA Automation Engineer"), "qa")
        self.assertEqual(classify_role("Data Engineer / Analyst"), "data")

        # Excluded non-software engineering roles
        self.assertEqual(classify_role("Civil Engineer Project"), "other")
        self.assertEqual(classify_role("Mechanical Engineer Maintenance"), "other")
        self.assertEqual(classify_role("Sales Engineer B2B"), "other")
        self.assertEqual(classify_role("Electrical Site Engineer Building"), "other")

    def test_full_job_classification(self):
        # Junior Engineer specifically
        job_junior = classify_job(
            title="Junior Backend Engineer",
            description="Kualifikasi: Fresh graduate atau pengalaman 0-1 tahun dengan Node.js"
        )
        self.assertEqual(job_junior["experience_level"], "entry")
        self.assertEqual(job_junior["role_category"], "backend")
        self.assertIn("0 - 1", job_junior["experience_raw"])

        # Senior Engineer specifically
        job_senior = classify_job(
            title="Senior Software Engineer",
            description="Requirements: Min 5 years in software architecture"
        )
        self.assertEqual(job_senior["experience_level"], "senior")
        self.assertEqual(job_senior["role_category"], "software_engineer")

        # Title is generic "Software Engineer" but description requires min 2 years
        job_mid = classify_job(
            title="Software Engineer",
            description="Minimal 2 tahun pengalaman kerja di bidang Go/Python"
        )
        self.assertEqual(job_mid["experience_level"], "mid")
        self.assertEqual(job_mid["role_category"], "software_engineer")

if __name__ == "__main__":
    unittest.main()
