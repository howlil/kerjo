import re
from typing import Dict, Any, Optional, Tuple

NON_SW_EXCLUSIONS = {
    "civil", "sipil", "mechanical", "mekanikal", "mesin", "sales", "penjualan",
    "construction", "konstruksi", "gedung", "building", "hvac", "plumbing",
    "surveyor", "mining", "tambang", "geologi", "kimia", "chemical", "site project",
    "struktur dermaga", "arsitek bangunan", "drafter bangunan"
}

ROLE_PATTERNS = [
    ("backend", [r"\bbackend\b", r"\bback-end\b", r"\bback end\b", r"\bgolang\b", r"\bpython developer\b", r"\bjava developer\b", r"\bnode(?:\.js)?\b", r"\bruby\b", r"\bphp developer\b", r"\bapi engineer\b"]),
    ("frontend", [r"\bfrontend\b", r"\bfront-end\b", r"\bfront end\b", r"\breact\b", r"\bvue\b", r"\bsvelte\b", r"\bangular\b", r"\bweb developer\b", r"\bui/ux engineer\b"]),
    ("fullstack", [r"\bfullstack\b", r"\bfull-stack\b", r"\bfull stack\b"]),
    ("mobile", [r"\bmobile\b", r"\bandroid\b", r"\bios\b", r"\bflutter\b", r"\breact native\b", r"\bswift\b", r"\bkotlin\b"]),
    ("devops", [r"\bdevops\b", r"\bsre\b", r"\bsite reliability\b", r"\bcloud engineer\b", r"\binfrastructure\b", r"\bsysadmin\b", r"\bsystem administrator\b"]),
    ("qa", [r"\bqa\b", r"\bquality assurance\b", r"\bsdet\b", r"\btest engineer\b", r"\btester\b", r"\bautomation engineer\b"]),
    ("data", [r"\bdata engineer\b", r"\bdata scientist\b", r"\bdata analyst\b", r"\bmachine learning\b", r"\bai engineer\b", r"\bml engineer\b", r"\bbig data\b"]),
    ("software_engineer", [r"\bsoftware engineer\b", r"\bsoftware developer\b", r"\bprogrammer\b", r"\bengineer\b", r"\bdeveloper\b"]),
]

def is_non_software_engineering(title: str) -> bool:
    t_lower = title.lower()
    for exc in NON_SW_EXCLUSIONS:
        if exc in t_lower:
            # Check if it also explicitly says software/IT
            if not any(sw in t_lower for sw in ["software", "programmer", "developer", "it ", "ti ", "web"]):
                return True
    return False

def classify_role(title: str) -> str:
    if is_non_software_engineering(title):
        return "other"

    t_lower = title.lower()
    for role_name, patterns in ROLE_PATTERNS:
        for pat in patterns:
            if re.search(pat, t_lower):
                return role_name

    return "other"

def extract_experience(text: str) -> Dict[str, Any]:
    """
    Extracts experience level and year bracket from text (title or description).
    Returns dict:
      level: 'entry' | 'mid' | 'senior' | 'unspecified'
      min_years: Optional[float]
      max_years: Optional[float]
      raw: Optional[str]
    """
    if not text:
        return {"level": "unspecified", "min_years": None, "max_years": None, "raw": None}

    t_lower = text.lower()

    # 1. Fresh graduate / no experience patterns -> Entry
    fresh_patterns = [
        r"\bfresh\s*grad(?:uate)?\b",
        r"\blulusan\s*baru\b",
        r"\btanpa\s*pengalaman\b",
        r"\bno\s*experience\b",
        r"\bentry\s*level\b",
    ]
    for pat in fresh_patterns:
        if re.search(pat, t_lower):
            return {
                "level": "entry",
                "min_years": 0,
                "max_years": 1,
                "raw": "0 - 1 tahun (Fresh Grad)",
            }

    # 2. Year ranges e.g. "0 - 1 tahun", "0 - 2 years", "1 - 3 years", "2 - 4 thn"
    range_match = re.search(
        r"(?:pengalaman|experience|min(?:imal)?|kualifikasi|qualification|syarat)?\s*[:\s]*(\d+)\s*(?:-|sampai|to)\s*(\d+)\s*(?:tahun|thn|th|years|yrs|yoe)\b",
        t_lower,
    )
    if range_match:
        mn = float(range_match.group(1))
        mx = float(range_match.group(2))
        raw = f"{int(mn)} - {int(mx)} tahun"
        if mx <= 2:
            return {"level": "entry", "min_years": mn, "max_years": mx, "raw": raw}
        elif mn >= 3 or mx >= 5:
            return {"level": "senior", "min_years": mn, "max_years": mx, "raw": raw}
        else:
            return {"level": "mid", "min_years": mn, "max_years": mx, "raw": raw}

    # 3. Maksimal N tahun e.g. "maksimal 1 tahun pengalaman", "max 2 years"
    max_match = re.search(r"\b(?:maksimal|maks|max(?:imum)?)\s*(\d+)\s*(?:tahun|thn|th|years|yrs)\b", t_lower)
    if max_match:
        mx = float(max_match.group(1))
        raw = f"0 - {int(mx)} tahun"
        level = "entry" if mx <= 2 else "mid"
        return {"level": level, "min_years": 0, "max_years": mx, "raw": raw}

    # 4. Greater than / Minimal N years e.g. "> 5 years", "lebih dari 3 tahun", "min 5 tahun", "5+ years", "at least 3 years"
    gt_match = re.search(
        r"(?:>|lebih dari|above|over|minimal|min|at least|sekurang-kurangnya)\s*(\d+)\s*(?:\+|\s*(?:tahun|thn|th|years|yrs|yoe))\b",
        t_lower,
    )
    if not gt_match:
        gt_match = re.search(r"\b(\d+)\+\s*(?:tahun|thn|th|years|yrs|yoe)\b", t_lower)
    if not gt_match:
        gt_match = re.search(r"(?:pengalaman|experience)\s*[:\s]*(\d+)\s*(?:tahun|thn|th|years|yrs|yoe)\b", t_lower)

    if gt_match:
        years = float(gt_match.group(1))
        if years >= 3:
            return {
                "level": "senior",
                "min_years": years,
                "max_years": None,
                "raw": f"> {int(years)} tahun" if years >= 5 else f"Min. {int(years)} tahun",
            }
        elif years >= 1:
            return {
                "level": "mid",
                "min_years": years,
                "max_years": None,
                "raw": f"Min. {int(years)} tahun",
            }
        else:
            return {
                "level": "entry",
                "min_years": 0,
                "max_years": 1,
                "raw": "0 - 1 tahun",
            }

    return {"level": "unspecified", "min_years": None, "max_years": None, "raw": None}

def classify_job(title: str, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Comprehensive classification combining title, description, and seniority signals.
    """
    role = classify_role(title)
    desc_text = description or ""
    combined_text = f"{title}\n{desc_text}"

    # First check experience extracted from description / combined text
    exp = extract_experience(combined_text)

    # Check title seniority markers which may override or refine experience level
    t_lower = title.lower()
    has_junior_title = any(re.search(rf"\b{w}\b", t_lower) for w in ["junior", "jr", "entry level", "fresh graduate", "intern", "magang", "trainee", "associate"])
    has_senior_title = any(re.search(rf"\b{w}\b", t_lower) for w in ["senior", "sr", "lead", "principal", "head", "architect", "staff", "manager", "vp"])

    level = exp["level"]
    min_years = exp["min_years"]
    max_years = exp["max_years"]
    raw = exp["raw"]

    if has_junior_title:
        level = "entry"
        if not raw:
            raw = "Junior / Entry Level"
            min_years = 0
            max_years = 2
    elif has_senior_title:
        level = "senior"
        if not raw:
            raw = "Senior / Pro Hire"
            min_years = 3 if min_years is None or min_years < 3 else min_years

    return {
        "role_category": role,
        "experience_level": level,
        "min_years": min_years,
        "max_years": max_years,
        "experience_raw": raw,
    }
