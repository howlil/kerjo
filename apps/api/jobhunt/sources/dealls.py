import urllib.request
import urllib.parse
import json
import logging
from typing import Optional
from jobhunt.models import Job, SourceResult
from jobhunt.location import match_area

logger = logging.getLogger(__name__)

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

def parse_dealls_payload(data: dict) -> list[Job]:
    docs = (data.get("data") or {}).get("docs", [])
    jobs = []

    for item in docs:
        job_id = str(item.get("id", ""))
        if not job_id:
            continue

        title = (item.get("role") or "").strip()
        comp_obj = item.get("company") or {}
        company = comp_obj.get("name") or "Unknown Company"
        company_logo = comp_obj.get("logo") or comp_obj.get("logoUrl") or comp_obj.get("avatar") or item.get("companyLogo")

        city_obj = item.get("city") or {}
        city_name = city_obj.get("name") or ""
        country_obj = item.get("country") or {}
        country_name = country_obj.get("name") or ""

        loc_parts = [p for p in [city_name, country_name] if p]
        loc_str = ", ".join(loc_parts) if loc_parts else "Jakarta"

        area = match_area(loc_str)
        if area is None:
            # Excluded area
            continue

        slug = item.get("slug")
        url = f"https://dealls.com/loker/{slug}" if slug else f"https://dealls.com/loker/{job_id}"

        # Salary
        salary = None
        sal_range = item.get("salaryRange")
        if sal_range and isinstance(sal_range, dict):
            mn = sal_range.get("min")
            mx = sal_range.get("max")
            cur = sal_range.get("currency") or "IDR"
            if mn and mx:
                salary = f"{cur} {mn:,} - {mx:,}"
            elif mn:
                salary = f"{cur} {mn:,}+"

        # Remote / Work arrangement
        wp = (item.get("workplaceType") or "").lower()
        is_remote = wp in ("remote", "hybrid")

        emp_types = item.get("employmentTypes") or []
        work_type = ", ".join(emp_types) if emp_types else None

        posted_at = item.get("publishedAt") or item.get("createdAt")
        desc = (item.get("description") or item.get("jobDescription") or item.get("requirements") or "").strip()

        jobs.append(
            Job(
                source="dealls",
                external_id=job_id,
                title=title,
                company=company,
                location_raw=loc_str,
                area=area,
                url=url,
                salary=salary,
                work_type=work_type,
                is_remote=is_remote,
                posted_at=posted_at,
                description=desc or None,
                company_logo=company_logo,
            )
        )
    return jobs

def fetch_dealls(keyword: str, page: int = 1, limit: int = 30) -> SourceResult:
    query_params = {
        "page": str(page),
        "limit": str(limit),
        "search": keyword,
    }
    url = f"https://api.sejutacita.id/v1/explore-job/job?{urllib.parse.urlencode(query_params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_UA,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                return SourceResult(
                    source="dealls",
                    success=False,
                    jobs=[],
                    error_message=f"HTTP status {response.status}",
                )
            payload = json.loads(response.read().decode("utf-8"))
            jobs = parse_dealls_payload(payload)
            return SourceResult(source="dealls", success=True, jobs=jobs)
    except urllib.error.HTTPError as e:
        return SourceResult(
            source="dealls",
            success=False,
            jobs=[],
            error_message=f"HTTP Error {e.code}: {e.reason}",
        )
    except Exception as e:
        return SourceResult(
            source="dealls",
            success=False,
            jobs=[],
            error_message=str(e),
        )
