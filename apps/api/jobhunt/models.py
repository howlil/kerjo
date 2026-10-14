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

    def to_dict(self):
        return asdict(self)

@dataclass
class SourceResult:
    source: str
    success: bool
    jobs: list[Job]
    error_message: Optional[str] = None
