from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Job:
    source: str
    external_id: str
    title: str
    company: str
    location_raw: str
    area: str  # jakarta_selatan, jakarta_barat, jakarta_pusat, tangerang_selatan, bsd, alam_sutera, unspecified
    url: str
    salary: Optional[str] = None
    work_type: Optional[str] = None
    is_remote: bool = False
    posted_at: Optional[str] = None
    description: Optional[str] = None
    experience_level: Optional[str] = None
    min_years: Optional[float] = None
    max_years: Optional[float] = None
    experience_raw: Optional[str] = None
    role_category: Optional[str] = None
    company_logo: Optional[str] = None
    work_mode: Optional[str] = None
    description_status: str = "missing"
    description_source: Optional[str] = None
    application_url: Optional[str] = None
    application_evidence: Optional[str] = None
    origin_url: Optional[str] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class SourceResult:
    source: str
    success: bool
    jobs: list[Job]
    error_message: Optional[str] = None
    # Optional provider metadata; existing adapters and tests remain compatible.
    raw_count: Optional[int] = None  # Count before location/title filtering
    has_more: Optional[bool] = None  # Only set when the provider supplies an explicit signal
    http_status: Optional[int] = None
    retry_after_seconds: Optional[float] = None
    pages_fetched: int = 0
    retry_count: int = 0
    enriched_count: int = 0
    elapsed_ms: int = 0
