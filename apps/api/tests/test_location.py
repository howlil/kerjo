import unittest
from jobhunt.location import match_area

class TestLocationMatcher(unittest.TestCase):
    def test_direct_areas(self):
        self.assertEqual(match_area("South Jakarta, Jakarta"), "jakarta_selatan")
        self.assertEqual(match_area("Jakarta Selatan"), "jakarta_selatan")
        self.assertEqual(match_area("West Jakarta, Jakarta"), "jakarta_barat")
        self.assertEqual(match_area("Jakarta Barat"), "jakarta_barat")
        self.assertEqual(match_area("Central Jakarta, Jakarta"), "jakarta_pusat")
        self.assertEqual(match_area("Jakarta Pusat"), "jakarta_pusat")
        self.assertEqual(match_area("Tangerang Selatan"), "tangerang_selatan")
        self.assertEqual(match_area("South Tangerang"), "tangerang_selatan")

    def test_subdistricts_and_landmarks(self):
        self.assertEqual(match_area("Kebayoran Lama, Jakarta"), "jakarta_selatan")
        self.assertEqual(match_area("Kuningan, Jakarta"), "jakarta_selatan")
        self.assertEqual(match_area("SCBD, Senayan"), "jakarta_selatan")
        self.assertEqual(match_area("Kebon Jeruk, Jakarta"), "jakarta_barat")
        self.assertEqual(match_area("Puri Indah, Kembangan"), "jakarta_barat")
        self.assertEqual(match_area("Kemayoran, Jakarta"), "jakarta_pusat")
        self.assertEqual(match_area("Bintaro, Tangerang Selatan"), "tangerang_selatan")
        self.assertEqual(match_area("Ciputat Timur"), "tangerang_selatan")

    def test_bsd_and_alsut(self):
        self.assertEqual(match_area("BSD City, Tangerang"), "bsd")
        self.assertEqual(match_area("Bumi Serpong Damai"), "bsd")
        self.assertEqual(match_area("Alam Sutera, Tangerang"), "alam_sutera")
        self.assertEqual(match_area("Alsut"), "alam_sutera")

    def test_unspecified_general(self):
        self.assertEqual(match_area("Jakarta"), "unspecified")
        self.assertEqual(match_area("DKI Jakarta"), "unspecified")
        self.assertEqual(match_area("Jakarta Raya"), "unspecified")
        self.assertEqual(match_area("Tangerang"), "unspecified")
        self.assertEqual(match_area("Indonesia"), "unspecified")
        self.assertEqual(match_area(""), "unspecified")
        self.assertEqual(match_area(None), "unspecified")

    def test_excluded_areas(self):
        self.assertIsNone(match_area("North Jakarta, Jakarta"))
        self.assertIsNone(match_area("Jakarta Utara"))
        self.assertIsNone(match_area("Kelapa Gading, Jakarta"))
        self.assertIsNone(match_area("East Jakarta, Jakarta"))
        self.assertIsNone(match_area("Jakarta Timur"))
        self.assertIsNone(match_area("Duren Sawit, Jakarta"))
        self.assertIsNone(match_area("Bekasi"))
        self.assertIsNone(match_area("Depok"))
        self.assertIsNone(match_area("Bandung"))
        self.assertIsNone(match_area("Surabaya"))

if __name__ == "__main__":
    unittest.main()
