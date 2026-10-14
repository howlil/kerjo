import urllib.request
import urllib.parse
import json
import logging
import time
from typing import Optional
from jobhunt.models import Job, SourceResult
from jobhunt.collection import retry_after_seconds
from jobhunt.location import match_area

logger = logging.getLogger(__name__)

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

def parse_kalibrr_payload(data: dict) -> list[Job]:
    items = data.get("jobs", [])
    jobs = []
    for item in items:
        job_id = str(item.get("id", ""))
        if not job_id:
            continue

        title = (item.get("name") or "").strip()
        company_name = (item.get("company_name") or (item.get("company") or {}).get("name") or "Unknown Company").strip()
        company_logo = (
            (item.get("company_info") or {}).get("logo")
            or (item.get("company") or {}).get("logo")
            or item.get("company_logo")
            or (item.get("company_info") or {}).get("logo_url")
        )

        # Location extraction
        g_loc = item.get("google_location") or {}
        addr = g_loc.get("address_components") or {}
        city = addr.get("city", "")
        region = addr.get("region", "")
        line1 = addr.get("address_line_1", "")

        loc_parts = [p for p in [line1, city, region] if p]
        loc_str = ", ".join(loc_parts) if loc_parts else ""

        area = match_area(loc_str)
        if area is None:
            # Excluded area
            continue

        slug = item.get("slug") or ""
        company_code = (item.get("company") or {}).get("code") or (item.get("company_info") or {}).get("code")
        if company_code and slug:
            url = f"https://www.kalibrr.com/c/{company_code}/jobs/{job_id}/{slug}"
        elif slug:
            url = f"https://www.kalibrr.com/job-board/te/{slug}/{job_id}"
        else:
            url = f"https://www.kalibrr.com/job-board/te/{job_id}"

        # Salary formatting
        salary = None
        base_sal = item.get("base_salary")
        max_sal = item.get("maximum_salary")
        currency = item.get("salary_currency") or "IDR"
        if base_sal and max_sal:
            salary = f"{currency} {base_sal:,} - {max_sal:,}"
        elif base_sal:
            salary = f"{currency} {base_sal:,}+"

        # Remote / Work arrangement
        is_remote = bool(item.get("is_work_from_home") or item.get("is_hybrid"))
        work_type = item.get("tenure")

        posted_at = item.get("activation_date") or item.get("published_at")
        desc = (item.get("description") or item.get("summary") or item.get("qualification") or "").strip()
        min_exp = item.get("minimum_experience")
        if min_exp is not None:
            desc = f"{desc}\nPengalaman minimal {min_exp} tahun.".strip()

        jobs.append(
            Job(
                source="kalibrr",
                external_id=job_id,
                title=title,
                company=company_name,
                location_raw=loc_str,
                area=area,
                url=url,
                salary=salary,
                work_type=work_type,
                is_remote=is_remote,
                work_mode=("remote" if item.get("is_work_from_home") else "hybrid" if item.get("is_hybrid") else "unknown"),
                posted_at=posted_at,
                description=desc or None,
                company_logo=company_logo,
            )
        )
    return jobs

def fetch_kalibrr(keyword: str, limit: int = 30, offset: int = 0, retries: int = 1) -> SourceResult:
    query_params = {
        "limit": str(limit),
        "offset": str(offset),
        "text": keyword,
        "country": "Indonesia",
    }
    url = f"https://www.kalibrr.com/kjs/job_board/search?{urllib.parse.urlencode(query_params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_UA,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    last_error = ""
    last_status = None
    last_retry_after = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                if response.status != 200:
                    return SourceResult(
                        source="kalibrr",
                        success=False,
                        jobs=[],
                        error_message=f"HTTP status {response.status}",
                        http_status=response.status,
                    )
                payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
                    return SourceResult(source="kalibrr", success=False, jobs=[], error_message="Unexpected provider schema")
                jobs = parse_kalibrr_payload(payload)
                return SourceResult(source="kalibrr", success=True, jobs=jobs, raw_count=len(payload["jobs"]), pages_fetched=1)
        except urllib.error.HTTPError as e:
            last_error = f"HTTP Error {e.code}: {e.reason}"
            last_status = e.code
            last_retry_after = retry_after_seconds(e.headers.get("Retry-After") if e.headers else None)
            break
        except Exception as e:
            last_error = str(e)
            if attempt < retries - 1:
                time.sleep(2)
                continue

    return SourceResult(
        source="kalibrr",
        success=False,
        jobs=[],
        error_message=last_error or "Unknown error",
        http_status=last_status,
        retry_after_seconds=last_retry_after,
    )
