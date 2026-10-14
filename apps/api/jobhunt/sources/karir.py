import urllib.request
import urllib.error
import json
import logging
from typing import Optional
from jobhunt.models import Job, SourceResult
from jobhunt.collection import retry_after_seconds
from jobhunt.location import match_area

logger = logging.getLogger(__name__)

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

def parse_karir_payload(data: dict) -> list[Job]:
    opps = (data.get("data") or {}).get("opportunities") or []
    jobs = []

    for item in opps:
        job_id = str(item.get("id", ""))
        if not job_id:
            continue

        title = (item.get("job_position") or "").strip()
        company = (item.get("company_name") or "Unknown Company").strip()
        company_logo = item.get("company_logo") or (item.get("company") or {}).get("logo") or item.get("logo")

        # Job description is not a geographical field. Missing location is unknown.
        location = (item.get("location") or item.get("city_name") or
                    item.get("city") or item.get("work_location") or
                    item.get("location_name") or "")
        if isinstance(location, dict):
            location = (location.get("name") or location.get("label") or
                        location.get("city") or "")
        loc_str = location.strip() if isinstance(location, str) else ""
        area = match_area(loc_str)
        if area is None:
            # Excluded area
            continue

        url = f"https://www.karir.com/opportunities/{job_id}"

        # Salary
        salary = None
        s_low = item.get("salary_lower") or 0
        s_up = item.get("salary_upper") or 0
        if s_low > 0 and s_up > 0:
            salary = f"Rp {s_low:,.0f} - Rp {s_up:,.0f}".replace(",", ".")
        elif s_low > 0:
            salary = f"Rp {s_low:,.0f}+".replace(",", ".")

        posted_at = item.get("posted_at")  # update timestamps cannot prove a new vacancy
        desc = (item.get("description") or item.get("job_description") or "").strip()

        jobs.append(
            Job(
                source="karir",
                external_id=job_id,
                title=title,
                company=company,
                location_raw=loc_str,
                area=area,
                url=url,
                salary=salary,
                work_type=None,
                is_remote=False,
                work_mode="unknown",
                posted_at=posted_at,
                description=desc or None,
                company_logo=company_logo,
            )
        )
    return jobs

def fetch_karir(keyword: str, page: int = 1, limit: int = 30) -> SourceResult:
    url = "https://gateway2-beta.karir.com/v2/search/opportunities"
    offset = (page - 1) * limit
    payload = json.dumps({
        "keyword": keyword,
        "limit": limit,
        "offset": offset,
        "sort_order": "newest",
        "is_opportunity": True
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "User-Agent": DEFAULT_UA,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://www.karir.com",
            "Referer": "https://www.karir.com/",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                return SourceResult(
                    source="karir",
                    success=False,
                    jobs=[],
                    error_message=f"HTTP status {response.status}",
                    http_status=response.status,
                )
            payload_data = json.loads(response.read().decode("utf-8"))
            if not isinstance((payload_data.get("data") or {}).get("opportunities"), list):
                return SourceResult(source="karir", success=False, jobs=[], error_message="Unexpected provider schema")
            jobs = parse_karir_payload(payload_data)
            return SourceResult(source="karir", success=True, jobs=jobs, raw_count=len(payload_data["data"]["opportunities"]), pages_fetched=1)
    except urllib.error.HTTPError as e:
        return SourceResult(
            source="karir",
            success=False,
            jobs=[],
            error_message=f"HTTP Error {e.code}: {e.reason}",
        http_status=e.code,
        retry_after_seconds=retry_after_seconds(e.headers.get("Retry-After") if e.headers else None),
        )
    except Exception as e:
        return SourceResult(
            source="karir",
            success=False,
            jobs=[],
            error_message=str(e),
        )
