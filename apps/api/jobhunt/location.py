import re
from typing import Optional

# Order matters: more specific areas first
BSD_PATTERNS = [
    r"\bbsd\b",
    r"\bbsd city\b",
    r"\bbumi serpong damai\b",
    r"\bcisauk\b",
    r"\bpagedangan\b",
    r"\bedutown\b",
]

ALSUT_PATTERNS = [
    r"\balam sutera\b",
    r"\balsut\b",
    r"\bpanunggangan timur\b",
    r"\bpinang\b",
]

JAKSEL_PATTERNS = [
    r"\bjakarta selatan\b",
    r"\bsouth jakarta\b",
    r"\bjaksel\b",
    r"\bkebayoran\b",
    r"\bkebayoran baru\b",
    r"\bkebayoran lama\b",
    r"\bsenopati\b",
    r"\bblok m\b",
    r"\bfatmawati\b",
    r"\bcilandak\b",
    r"\btebet\b",
    r"\bmampang\b",
    r"\bpancoran\b",
    r"\bpasar minggu\b",
    r"\bjagakarsa\b",
    r"\bpesanggrahan\b",
    r"\bsetiabudi\b",
    r"\bkuningan\b",
    r"\bgatot subroto\b",
    r"\btb simatupang\b",
    r"\bpondok indah\b",
    r"\bkemang\b",
    r"\bscbd\b",
    r"\bsenayan\b",
]

JAKBAR_PATTERNS = [
    r"\bjakarta barat\b",
    r"\bwest jakarta\b",
    r"\bjakbar\b",
    r"\bkebon jeruk\b",
    r"\bpuri\b",
    r"\bpuri indah\b",
    r"\bkembangan\b",
    r"\bpalmerah\b",
    r"\bgrogol\b",
    r"\bpetamburan\b",
    r"\btaman sari\b",
    r"\btambora\b",
    r"\bcengkareng\b",
    r"\bkalideres\b",
    r"\btomang\b",
    r"\bslipi\b",
    r"\bmeruya\b",
]

JAKPUS_PATTERNS = [
    r"\bjakarta pusat\b",
    r"\bcentral jakarta\b",
    r"\bjakpus\b",
    r"\bgambir\b",
    r"\btanah abang\b",
    r"\bmenteng\b",
    r"\bsenen\b",
    r"\bcempaka putih\b",
    r"\bjohar baru\b",
    r"\bkemayoran\b",
    r"\bsawah besar\b",
    r"\bsudirman\b",
    r"\bthamrin\b",
    r"\bmonas\b",
]

TANGSEL_PATTERNS = [
    r"\btangerang selatan\b",
    r"\bsouth tangerang\b",
    r"\btangsel\b",
    r"\bserpong\b",
    r"\bserpong utara\b",
    r"\bpondok aren\b",
    r"\bbintaro\b",
    r"\bciputat\b",
    r"\bpamulang\b",
    r"\bsetu\b",
]

EXCLUDED_PATTERNS = [
    r"\bjakarta utara\b",
    r"\bnorth jakarta\b",
    r"\bjakut\b",
    r"\bkelapa gading\b",
    r"\bpluit\b",
    r"\bpik\b",
    r"\bpantai indah kapuk\b",
    r"\btanjung priok\b",
    r"\bpenjaringan\b",
    r"\bpademangan\b",
    r"\bkoja\b",
    r"\bcilincing\b",
    r"\bsunter\b",
    r"\bancol\b",
    r"\bjakarta timur\b",
    r"\beast jakarta\b",
    r"\bjaktim\b",
    r"\bduren sawit\b",
    r"\bjatinegara\b",
    r"\bcakung\b",
    r"\bpulogadung\b",
    r"\bciracas\b",
    r"\bpasar rebo\b",
    r"\bkramat jati\b",
    r"\bmatraman\b",
    r"\bcipayung\b",
    r"\bbekasi\b",
    r"\bdepok\b",
    r"\bbogor\b",
    r"\bbandung\b",
    r"\bsurabaya\b",
    r"\bsemarang\b",
    r"\byogyakarta\b",
    r"\bbali\b",
    r"\bdenpasar\b",
    r"\bmedan\b",
    r"\bkarawang\b",
    r"\bcikarang\b",
]

GENERIC_UNSPECIFIED = [
    r"^jakarta$",
    r"^dki jakarta$",
    r"^jakarta raya$",
    r"^tangerang$",
    r"^banten$",
    r"^indonesia$",
    r"^jabodetabek$",
]

def _matches_any(text: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def match_area(location_raw: Optional[str]) -> Optional[str]:
    """
    Classifies a raw location string into one of the target areas:
    - bsd
    - alam_sutera
    - jakarta_selatan
    - jakarta_barat
    - jakarta_pusat
    - tangerang_selatan
    - unspecified (kept, broad general location like 'Jakarta' or 'Tangerang')
    - None (definitely outside target area, e.g. Jakarta Utara, Bekasi, Bandung)
    """
    if not location_raw:
        return "unspecified"

    text = location_raw.strip().lower()
    if not text:
        return "unspecified"

    # 1. BSD and Alam Sutera take highest precedence
    if _matches_any(text, BSD_PATTERNS):
        return "bsd"
    if _matches_any(text, ALSUT_PATTERNS):
        return "alam_sutera"

    # 2. Check specific target areas before general exclusions
    # (e.g. if something says "Kuningan, Jakarta", we want it classified before checking generic terms)
    if _matches_any(text, JAKSEL_PATTERNS):
        return "jakarta_selatan"
    if _matches_any(text, JAKBAR_PATTERNS):
        return "jakarta_barat"
    if _matches_any(text, JAKPUS_PATTERNS):
        return "jakarta_pusat"
    if _matches_any(text, TANGSEL_PATTERNS):
        return "tangerang_selatan"

    # 3. Check excluded regions
    if _matches_any(text, EXCLUDED_PATTERNS):
        return None

    # 4. Check if it's broad/unspecified
    # Remove punctuation for generic check
    cleaned = re.sub(r"[^\w\s]", " ", text).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    for p in GENERIC_UNSPECIFIED:
        if re.search(p, cleaned, re.IGNORECASE):
            return "unspecified"

    # If it contains "jakarta" or "tangerang" without specific excluded keywords
    if "jakarta" in text or "tangerang" in text or "banten" in text:
        return "unspecified"

    # Otherwise, it might be an unspecified location or general
    return "unspecified"
