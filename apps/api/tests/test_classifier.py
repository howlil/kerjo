import unittest
from jobhunt.classifier import classify_job, extract_experience, classify_role, is_strictly_technical_role

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

    def test_strictly_technical_roles_allowed(self):
        allowed_roles = [
            ("Junior Backend Engineer", "backend"),
            ("Frontend Developer React", "frontend"),
            ("Fullstack Software Engineer", "fullstack"),
            ("Software Engineer - Core Platform", "software_engineer"),
            ("DevOps Engineer / SRE", "infra_network"),
            ("Mobile Developer (Flutter/iOS)", "mobile"),
            ("Android Engineer", "mobile"),
            ("iOS Developer (Swift)", "mobile"),
            ("QA Automation Engineer", "qa"),
            ("SDET", "qa"),
            ("Data Engineer", "data"),
            ("Machine Learning Engineer", "data"),
            ("AI Engineer (GenAI)", "data"),
            ("Network Engineer F5", "infra_network"),
            ("Cyber Security Engineer", "infra_network"),
            ("Database Administrator (DBA)", "infra_network"),
            ("Golang Developer", "backend"),
            ("Python Developer", "backend"),
            ("Java Developer (Spring Boot)", "backend"),
            ("Next.js Developer", "frontend"),
            # Product Engineer is explicitly ALLOWED!
            ("Product Engineer", "product_engineer"),
            ("Senior Product Engineer - Merchant Experience", "product_engineer"),
        ]
        for title, expected_cat in allowed_roles:
            with self.subTest(title=title):
                is_tech, cat, reason = is_strictly_technical_role(title)
                self.assertTrue(is_tech, f"Expected {title} to be accepted, but rejected: {reason}")
                self.assertEqual(cat, expected_cat)

    def test_non_technical_roles_strictly_rejected(self):
        rejected_roles = [
            # IT Document & Management (PM, Scrum, Tech Writer, BA)
            "Product Manager",
            "Associate Product Manager (APM)",
            "Group Product Manager",
            "Head of Product",
            "IT Project Manager (Junior)",
            "Project Manager",
            "Project Administrator",
            "Scrum Master",
            "Agile Coach",
            "Lead Technical & Scrum",
            "Business Analyst",
            "IT Business Analyst",
            "Technical Writer",
            "IT Technical Writer",
            "Document Controller",
            "IT Auditor",
            "IT Support / Helpdesk",
            "Desktop Support Technician",
            # Creative & Design
            "UI/UX Designer",
            "Product Designer",
            "Graphic Designer",
            "Senior 3D Animator at MDN",
            # Business, Sales, Marketing
            "Sales Engineer",
            "Technical Sales Engineer",
            "Business Process Improvement",
            "Account Executive",
            "Management Trainee - Key Account Manager",
            "Stakeholder & Government Relations Expert",
            "HR Specialist",
            "Finance & Tax Officer",
            # Non-IT Engineering & Field Trades
            "Maintenance Service Engineer EV Charger",
            "Maintenance / Teknisi Gedung (Education)",
            "Helper Teknisi CCTV",
            "Teknisi",
            "Expression of Interest - Lead Mechanical Static Engineer",
            "Expression of Interest - Lead Structural Engineer",
            "Estimator Engineer - Construction (EPC)",
            "BIM MANAGER",
            "SENIOR RIGGER",
            "Civil Engineer",
            "Site Engineer (Project)",
        ]
        for title in rejected_roles:
            with self.subTest(title=title):
                is_tech, cat, reason = is_strictly_technical_role(title)
                self.assertFalse(is_tech, f"Expected {title} to be rejected, but was classified as {cat}")
                self.assertEqual(classify_role(title), "other")

    def test_full_job_classification(self):
        # Junior Engineer specifically
        job_junior = classify_job(
            title="Junior Backend Engineer",
            description="Kualifikasi: Fresh graduate atau pengalaman 0-1 tahun dengan Node.js"
        )
        self.assertTrue(job_junior["is_technical"])
        self.assertEqual(job_junior["experience_level"], "entry")
        self.assertEqual(job_junior["role_category"], "backend")
        self.assertIn("0 - 1", job_junior["experience_raw"])

        # Product Engineer allowed
        job_pe = classify_job(
            title="Senior Product Engineer",
            description="Requirements: 4+ years in fullstack product development"
        )
        self.assertTrue(job_pe["is_technical"])
        self.assertEqual(job_pe["experience_level"], "senior")
        self.assertEqual(job_pe["role_category"], "product_engineer")

        # Excluded PM job
        job_pm = classify_job(
            title="Product Manager",
            description="Lead agile sprint and PRD specifications"
        )
        self.assertFalse(job_pm["is_technical"])
        self.assertEqual(job_pm["role_category"], "other")

if __name__ == "__main__":
    unittest.main()
