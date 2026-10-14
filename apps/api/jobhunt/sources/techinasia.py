import urllib.request
import urllib.parse
import urllib.error
import ssl
import json
import logging
from typing import Optional
from jobhunt.models import Job, SourceResult
from jobhunt.location import match_area

logger = logging.getLogger(__name__)

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

def parse_tia_payload(data: dict) -> list[Job]:
    items = data.get("data") or []
    jobs = []

    for item in items:
        job_id = str(item.get("id", ""))
        if not job_id:
            continue

        title = (item.get("title") or "").strip()
        comp_obj = item.get("company") or {}
        company = comp_obj.get("name") or "Unknown Company"
        company_logo = comp_obj.get("logo") or comp_obj.get("logo_url") or comp_obj.get("avatar_url") or item.get("company_logo")

        city_obj = item.get("city") or {}
        city_name = city_obj.get("name") or ""
        loc_str = city_name if city_name else ""

        area = match_area(loc_str)
        if area is None:
            # Excluded area
            continue

        url = item.get("external_link") or f"https://www.techinasia.com/jobs/{job_id}"

        # Salary
        salary = None
        s_min = item.get("salary_min") or 0
        s_max = item.get("salary_max") or 0
        cur_obj = item.get("currency") or {}
        cur_sym = cur_obj.get("currency_symbol") or cur_obj.get("currency_code") or "Rp"
        if s_min > 0 and s_max > 0:
            salary = f"{cur_sym} {s_min:,.0f} - {s_max:,.0f}".replace(",", ".")
        elif s_min > 0:
            salary = f"{cur_sym} {s_min:,.0f}+".replace(",", ".")

        is_remote = bool(item.get("is_remote"))
        work_type = item.get("work_arrangement") or item.get("job_type")
        posted_at = item.get("published_at") or item.get("updated_at")
        desc = (item.get("description") or "").strip()
        exp_min = item.get("experience_min")
        exp_max = item.get("experience_max")
        if exp_min is not None or exp_max is not None:
            desc = f"{desc}\nPengalaman {exp_min or 0} - {exp_max or exp_min} tahun.".strip()

        jobs.append(
            Job(
                source="techinasia",
                external_id=job_id,
                title=title,
                company=company,
                location_raw=loc_str,
                area=area,
                url=url,
                salary=salary,
                work_type=work_type,
                is_remote=is_remote,
                work_mode=("remote" if is_remote else str(work_type or "unknown").lower() if str(work_type or "").lower() in ("onsite","hybrid") else "unknown"),
                posted_at=posted_at,
                description=desc or None,
                company_logo=company_logo,
            )
        )
    return jobs

def fetch_techinasia(keyword: str, page: int = 1, limit: int = 25) -> SourceResult:
    query_params = {
        "query": keyword,
        "page": str(page),
    }
    url = f"https://www.techinasia.com/api/2.0/job-postings?{urllib.parse.urlencode(query_params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_UA,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            if response.status != 200:
                return SourceResult(
                    source="techinasia",
                    success=False,
                    jobs=[],
                    error_message=f"HTTP status {response.status}",
                )
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload.get("data"), list):
                return SourceResult(source="techinasia", success=False, jobs=[], error_message="Unexpected provider schema")
            jobs = parse_tia_payload(payload)
            return SourceResult(source="techinasia", success=True, jobs=jobs)
    except urllib.error.HTTPError as e:
        return SourceResult(
            source="techinasia",
            success=False,
            jobs=[],
            error_message=f"HTTP Error {e.code}: {e.reason}",
        )
    except Exception as e:
        return SourceResult(
            source="techinasia",
            success=False,
            jobs=[],
            error_message=str(e),
        )
