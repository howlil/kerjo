import urllib.request
import urllib.parse
import json
import re
import logging
from typing import Optional
from jobhunt.models import Job, SourceResult
from jobhunt.location import match_area

logger = logging.getLogger(__name__)

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

def parse_glints_payload(data: dict) -> list[Job]:
    initial_jobs = data.get("props", {}).get("pageProps", {}).get("initialJobs", {})
    if isinstance(initial_jobs, dict):
        items = initial_jobs.get("jobsInPage") or initial_jobs.get("jobs", [])
    elif isinstance(initial_jobs, list):
        items = initial_jobs
    else:
        items = []

    jobs = []
    for item in items:
        job_id = str(item.get("id", ""))
        if not job_id:
            continue

        title = (item.get("title") or "").strip()
        comp_obj = item.get("company") or {}
        company = comp_obj.get("name") or "Unknown Company"
        company_logo = comp_obj.get("logo") or comp_obj.get("logoUrl") or comp_obj.get("avatar")

        # Build location
        loc = item.get("location") or {}
        loc_name = loc.get("name") or ""
        loc_parents = [p.get("name") for p in loc.get("parents") or [] if p.get("name")]
        loc_parts = [p for p in [loc_name] + loc_parents if p]
        loc_str = ", ".join(loc_parts) if loc_parts else "Jakarta"

        area = match_area(loc_str)
        if area is None:
            # Excluded area
            continue

        url = f"https://glints.com/id/opportunities/jobs/{job_id}"

        # Salary
        salary = None
        salaries = item.get("salaries") or []
        if salaries:
            s0 = salaries[0]
            cur = s0.get("CurrencyCode") or "IDR"
            mn = s0.get("minAmount")
            mx = s0.get("maxAmount")
            if mn and mx:
                salary = f"{cur} {mn:,} - {mx:,}"
            elif mn:
                salary = f"{cur} {mn:,}+"

        # Work arrangements
        arrangement = (item.get("workArrangementOption") or "").upper()
        is_remote = arrangement in ("REMOTE", "HYBRID")
        work_type = item.get("type")

        posted_at = item.get("createdAt")
        desc = (item.get("briefJobDescription") or item.get("description") or "").strip()
        min_exp = item.get("minYearsOfExperience")
        max_exp = item.get("maxYearsOfExperience")
        if min_exp is not None or max_exp is not None:
            desc = f"{desc}\nPengalaman {min_exp or 0} - {max_exp or min_exp} tahun.".strip()

        jobs.append(
            Job(
                source="glints",
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

def fetch_glints(keyword: str, country: str = "ID") -> SourceResult:
    query_params = {
        "keyword": keyword,
        "country": country,
    }
    url = f"https://glints.com/id/opportunities/jobs/explore?{urllib.parse.urlencode(query_params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                return SourceResult(
                    source="glints",
                    success=False,
                    jobs=[],
                    error_message=f"HTTP status {response.status}",
                )
            html_content = response.read().decode("utf-8", "replace")
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_content, re.S)
            if not m:
                return SourceResult(
                    source="glints",
                    success=False,
                    jobs=[],
                    error_message="Could not find __NEXT_DATA__ in page",
                )
            payload = json.loads(m.group(1))
            jobs = parse_glints_payload(payload)
            return SourceResult(source="glints", success=True, jobs=jobs)
    except urllib.error.HTTPError as e:
        return SourceResult(
            source="glints",
            success=False,
            jobs=[],
            error_message=f"HTTP Error {e.code}: {e.reason}",
        )
    except Exception as e:
        return SourceResult(
            source="glints",
            success=False,
            jobs=[],
            error_message=str(e),
        )
