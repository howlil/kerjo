import re
from typing import Dict, Any, Optional, Tuple, List

# ---------------------------------------------------------------------------
# STRICT EXCLUSIONS: Non-IT, Business, Document IT, Trades, Non-SW Engineering
# ---------------------------------------------------------------------------
NON_TECHNICAL_EXCLUSIONS: List[str] = [
    # Business, Sales, Marketing, Customer Care
    r"\bsales\b", r"\bpenjualan\b", r"\baccount executive\b", r"\baccount manager\b",
    r"\bbusiness development\b", r"\bbizdev\b", r"\bmarketing\b", r"\bpemasaran\b",
    r"\btelemarketing\b", r"\btelesales\b", r"\bmedia buyer\b", r"\bbrand manager\b",
    r"\bcustomer service\b", r"\bcall center\b", r"\bcontact center\b", r"\bclient relations\b",
    r"\bkey account\b", r"\bchannel sales\b", r"\bmerchant acquisition\b", r"\bgovernment relations\b",
    r"\bstakeholder\b", r"\bpartnership\b",

    # HR, Finance, Admin, Legal, Logistics
    r"\bhuman resource(?:s)?\b", r"\bhr\b", r"\bhrd\b", r"\brecruit(?:er|ment)?\b",
    r"\btalent acquisition\b", r"\bpeople operations\b",
    r"\bfinance\b", r"\bkeuangan\b", r"\baccounting\b", r"\bakuntansi\b", r"\btax(?:ation)?\b",
    r"\bperpajakan\b", r"\bkasir\b", r"\bcashier\b", r"\bprocurement\b", r"\bpembelian\b",
    r"\bwarehouse\b", r"\bgudang\b", r"\blogistics\b", r"\blogistik\b", r"\bsupply chain\b",
    r"\blegal\b", r"\bnotary\b", r"\bcompliance officer\b", r"\bcorporate communication\b",
    r"\bpublic relation(?:s)?\b", r"\bpr officer\b",
    r"\bproject administrator\b", r"\bsekretaris\b", r"\bsecretary\b", r"\breceptionist\b",
    r"\boffice boy\b", r"\bcleaner\b", r"\bsatpam\b", r"\bsecurity guard\b",

    # Document / Non-Coding IT Management (EXCLUDED)
    # Note: "product manager" is excluded, but "product engineer" is ALLOWED!
    r"\bproduct manag(?:er|ement)\b", r"\bassociate product manager\b", r"\bapm\b",
    r"\bgroup product manager\b", r"\bgpm\b", r"\bhead of product\b", r"\bvp of product\b",
    r"\bchief product officer\b", r"\bcpo\b",
    r"\bproject manag(?:er|ement)\b", r"\bit project manager\b", r"\bproject coordinator\b",
    r"\bproject officer\b", r"\bpmo\b", r"\bprogram manager\b", r"\bdelivery manager\b",
    r"\bscrum master\b", r"\bagile coach\b", r"\bscrum\b",
    r"\bbusiness analyst\b", r"\bit business analyst\b", r"\bbusiness process\b",
    r"\btechnical writer\b", r"\btech writer\b", r"\bdocumentation specialist\b",
    r"\bdocument controller\b", r"\bcopywriter\b", r"\bcontent writer\b",
    r"\bit auditor\b", r"\bit governance\b",
    r"\bit support\b", r"\bdesktop support\b", r"\bhelpdesk\b", r"\bservice desk\b",

    # Design / Creative / Animation
    r"\bui/ux designer\b", r"\bux designer\b", r"\bui designer\b", r"\bproduct designer\b",
    r"\bgraphic designer\b", r"\bux researcher\b", r"\banimat(?:or|ion)\b", r"\b3d animator\b",
    r"\billustrat(?:or|ion)\b", r"\bvideographer\b", r"\bvideo editor\b",

    # Non-Software Engineering & Field Trades
    r"\bcivil\b", r"\bsipil\b", r"\bmechanical\b", r"\bmekanikal\b", r"\bmesin\b",
    r"\belectrical\b", r"\belektro\b", r"\bkelistrikan\b", r"\bchemical\b", r"\bkimia\b",
    r"\bconstruction\b", r"\bkonstruksi\b", r"\bgedung\b", r"\bbuilding\b", r"\barchitectural\b",
    r"\barsitek bangunan\b", r"\bdrafter\b", r"\bbim\b", r"\bestimator\b", r"\brigger\b",
    r"\bmaintenance\b", r"\bpemeliharaan\b", r"\bteknisi\b", r"\btechnician\b", r"\bbengkel\b",
    r"\bmekanik\b", r"\bcctv\b", r"\bhvac\b", r"\bplumbing\b", r"\bperpipaan\b", r"\bev charger\b",
    r"\botomotif\b", r"\bautomotive\b", r"\bipsrs\b", r"\bmining\b", r"\btambang\b",
    r"\bpetroleum\b", r"\bminyak\b", r"\bgeologi\b", r"\bsurveyor\b", r"\bstatic engineer\b",
    r"\bstructural engineer\b", r"\bsite engineer\b", r"\bqc engineer\b",
]

# ---------------------------------------------------------------------------
# POSITIVE TECHNICAL ROLES & STACKS
# ---------------------------------------------------------------------------
TECHNICAL_ROLE_PATTERNS = [
    # 1. Product Engineer (Special priority: Allowed, distinct from Product Manager)
    (
        "product_engineer",
        [
            r"\bproduct engineer\b",
            r"\bproduct software engineer\b",
            r"\bproduct engineering\b",
        ],
    ),
    # 2. Backend & Server-side
    (
        "backend",
        [
            r"\bbackend\b",
            r"\bback-end\b",
            r"\bback end\b",
            r"\bgolang\b",
            r"\bgo dev(?:eloper)?\b",
            r"\bgo engineer\b",
            r"\bpython dev(?:eloper)?\b",
            r"\bpython engineer\b",
            r"\bjava dev(?:eloper)?\b",
            r"\bjava engineer\b",
            r"\bnode(?:\.js)?\b",
            r"\bruby\b",
            r"\bror\b",
            r"\bphp dev(?:eloper)?\b",
            r"\bphp engineer\b",
            r"\blaravel\b",
            r"\bspring boot\b",
            r"\b\.net\b",
            r"\bc#\b",
            r"\brust dev(?:eloper)?\b",
            r"\brust engineer\b",
            r"\bapi engineer\b",
            r"\bapi dev(?:eloper)?\b",
            r"\bserver(?:\s+side)? dev(?:eloper)?\b",
            r"\bmicroservices\b",
            r"\belixir\b",
            r"\bscala\b",
            r"\bdjango\b",
            r"\bfastapi\b",
        ],
    ),
    # 3. Frontend & Web Client
    (
        "frontend",
        [
            r"\bfrontend\b",
            r"\bfront-end\b",
            r"\bfront end\b",
            r"\breact(?:\.js)?\b",
            r"\bvue(?:\.js)?\b",
            r"\bsvelte\b",
            r"\bangular\b",
            r"\bnext(?:\.js)?\b",
            r"\bnuxt(?:\.js)?\b",
            r"\bweb dev(?:eloper)?\b",
            r"\bweb programmer\b",
            r"\bjavascript dev(?:eloper)?\b",
            r"\btypescript dev(?:eloper)?\b",
            r"\bui engineer\b",
        ],
    ),
    # 4. Fullstack
    (
        "fullstack",
        [
            r"\bfullstack\b",
            r"\bfull-stack\b",
            r"\bfull stack\b",
        ],
    ),
    # 5. Mobile
    (
        "mobile",
        [
            r"\bmobile\b",
            r"\bandroid\b",
            r"\bios dev(?:eloper)?\b",
            r"\bios engineer\b",
            r"\bflutter\b",
            r"\breact native\b",
            r"\bswift\b",
            r"\bkotlin\b",
            r"\bapp dev(?:eloper)?\b",
        ],
    ),
    # 6. Data, ML & AI
    (
        "data",
        [
            r"\bdata engineer\b",
            r"\bdata scientist\b",
            r"\bdata science\b",
            r"\bmachine learning\b",
            r"\bml engineer\b",
            r"\bai engineer\b",
            r"\bai developer\b",
            r"\bartificial intelligence\b",
            r"\bdeep learning\b",
            r"\bbig data\b",
            r"\bdata warehouse\b",
            r"\betl developer\b",
            r"\banalytics engineer\b",
            r"\bcomputer vision\b",
            r"\bnlp engineer\b",
            r"\bgenai\b",
            r"\bllm\b",
            r"\btalend\b",
        ],
    ),
    # 7. Infra, Network, DevOps & Security
    (
        "infra_network",
        [
            r"\bdevops\b",
            r"\bsre\b",
            r"\bsite reliability\b",
            r"\bcloud engineer\b",
            r"\bcloud architect\b",
            r"\bplatform engineer\b",
            r"\binfrastructure engineer\b",
            r"\binfra engineer\b",
            r"\bsysadmin\b",
            r"\bsystem administrator\b",
            r"\bsystem engineer\b",
            r"\bnetwork engineer\b",
            r"\bnetwork administrator\b",
            r"\bnoc engineer\b",
            r"\bsecurity engineer\b",
            r"\bcyber security\b",
            r"\binformation security\b",
            r"\bsecops\b",
            r"\bdevsecops\b",
            r"\bpenetration tester\b",
            r"\bpentester\b",
            r"\bappsec\b",
            r"\bdatabase administrator\b",
            r"\bdba\b",
            r"\bkubernetes\b",
            r"\bf5\b",
        ],
    ),
    # 8. QA & Test Automation
    (
        "qa",
        [
            r"\bqa\b",
            r"\bquality assurance\b",
            r"\bsdet\b",
            r"\btest automation\b",
            r"\bautomation tester\b",
            r"\bsoftware tester\b",
            r"\bsoftware test\b",
            r"\btesting engineer\b",
            r"\bperformance tester\b",
            r"\buat tester\b",
            r"\bqa engineer\b",
            r"\btest engineer\b",
        ],
    ),
    # 9. General Software Engineer & Specific Software Applications
    (
        "software_engineer",
        [
            r"\bsoftware engineer\b",
            r"\bsoftware dev(?:eloper)?\b",
            r"\bsoftware programmer\b",
            r"\bprogrammer\b",
            r"\bapplication dev(?:eloper)?\b",
            r"\bapp programmer\b",
            r"\bembedded software\b",
            r"\bfirmware engineer\b",
            r"\bsolutions architect\b",
            r"\btechnical lead\b",
            r"\btech lead\b",
            r"\bengineering manager\b",
            r"\bswe\b",
            r"\bodoo dev(?:eloper)?\b",
            r"\berp dev(?:eloper)?\b",
            r"\bforward deployed engineer\b",
        ],
    ),
]


def is_strictly_technical_role(title: str, description: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates whether a job is strictly a technical IT / engineering role.
    Excludes business, document-only IT (PM, Scrum, Tech Writer), non-software engineering.

    Returns:
        (is_technical: bool, role_category: Optional[str], rejection_reason: Optional[str])
    """
    if not title:
        return False, None, "Empty title"

    t_lower = title.lower()

    # Step 1: Check Exclusions
    for exc_pattern in NON_TECHNICAL_EXCLUSIONS:
        if re.search(exc_pattern, t_lower):
            return False, None, f"Excluded by rule: {exc_pattern}"

    # Step 2: Prefer explicit fullstack titles over incidental backend/frontend stack mentions.
    if any(re.search(p, t_lower) for p in (r"\bfullstack\b", r"\bfull-stack\b", r"\bfull stack\b")):
        return True, "fullstack", None

    # Step 3: Positive match on title
    for role_cat, patterns in TECHNICAL_ROLE_PATTERNS:
        for pat in patterns:
            if re.search(pat, t_lower):
                return True, role_cat, None

    # Step 3: Check description if title has ambiguous technical keywords like "Developer" or "Engineer"
    if re.search(r"\b(?:developer|programmer|engineer)\b", t_lower):
        desc_lower = (description or "").lower()
        # Look for explicit software / coding evidence in description
        code_markers = [
            r"\bgolang\b", r"\bpython\b", r"\bjavascript\b", r"\btypescript\b", r"\breact\b",
            r"\bjava\b", r"\bnode(?:\.js)?\b", r"\bphp\b", r"\bc#\b", r"\b\.net\b", r"\bsql\b",
            r"\bgit\b", r"\bapi\b", r"\bdocker\b", r"\bkubernetes\b", r"\baws\b", r"\bcloud\b",
            r"\bsoftware development\b", r"\bmicroservices\b"
        ]
        matched_markers = [m for m in code_markers if re.search(m, desc_lower)]
        if len(matched_markers) >= 2:
            return True, "software_engineer", None

    return False, None, "No technical engineering role pattern matched"


def classify_role(title: str, description: Optional[str] = None) -> str:
    """
    Returns the role category or 'other' if not a technical role.
    """
    is_tech, role_cat, _ = is_strictly_technical_role(title, description)
    return role_cat if is_tech and role_cat else "other"


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
    fresh_signal = any(re.search(pat, t_lower) for pat in fresh_patterns)
    # Numeric requirements take precedence over promotional 'fresh graduates welcome'.
    if fresh_signal and not re.search(r"(?:\bmin(?:imal)?\b|\bat least\b|\b[3-9]\+?\s*(?:years|tahun)\b)", t_lower):
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
    Returns:
        is_technical: bool
        role_category: str ('backend'|'frontend'|'fullstack'|'mobile'|'data'|'infra_network'|'qa'|'product_engineer'|'software_engineer'|'other')
        experience_level: str ('entry'|'mid'|'senior'|'unspecified')
        min_years: Optional[float]
        max_years: Optional[float]
        experience_raw: Optional[str]
        rejection_reason: Optional[str]
    """
    is_tech, role_cat, reason = is_strictly_technical_role(title, description)
    role = role_cat if (is_tech and role_cat) else "other"

    desc_text = description or ""
    combined_text = f"{title}\n{desc_text}"

    # Extract experience from text
    exp = extract_experience(combined_text)

    # Check title seniority markers which may override or refine experience level
    t_lower = title.lower()
    has_junior_title = any(re.search(rf"\b{w}\b", t_lower) for w in ["junior", "jr", "entry level", "fresh graduate", "intern", "magang", "trainee", "associate"])
    has_senior_title = any(re.search(rf"\b{w}\b", t_lower) for w in ["senior", "sr", "lead", "principal", "head", "architect", "staff", "vp"])

    level = exp["level"]
    min_years = exp["min_years"]
    max_years = exp["max_years"]
    raw = exp["raw"]

    if has_junior_title and (min_years is None or min_years <= 2):
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
        "is_technical": is_tech,
        "role_category": role,
        "experience_level": level,
        "min_years": min_years,
        "max_years": max_years,
        "experience_raw": raw,
        "rejection_reason": reason,
    }
