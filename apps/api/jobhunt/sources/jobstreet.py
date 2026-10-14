import urllib.request
import urllib.parse
import json
import logging
from typing import Optional
from jobhunt.models import Job, SourceResult
from jobhunt.location import match_area

logger = logging.getLogger(__name__)

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

def parse_jobstreet_payload(data: dict) -> list[Job]:
    items = data.get("data", [])
    jobs = []
    for item in items:
        job_id = str(item.get("id", ""))
        if not job_id:
            continue

        title = item.get("title", "").strip()
        company = (item.get("companyName") or (item.get("advertiser") or {}).get("description") or "Unknown Company").strip()

        branding = item.get("branding") or {}
        advertiser = item.get("advertiser") or {}
        branding_assets = branding.get("assets") or {}
        raw_logo = (
            branding.get("logo")
            or advertiser.get("logo")
            or item.get("companyLogo")
            or (branding_assets.get("logo") or {}).get("url")
        )
        company_logo = raw_logo.get("url") if isinstance(raw_logo, dict) else raw_logo

        # Extract locations
        loc_labels = [l.get("label", "").strip() for l in item.get("locations", []) if l.get("label")]
        loc_str = ", ".join(loc_labels) if loc_labels else ""

        area = match_area(loc_str)
        if area is None:
            # Excluded area
            continue

        url = f"https://id.jobstreet.com/job/{job_id}"

        # Salary
        salary = item.get("salaryLabel")

        # Work arrangements / types
        work_types = item.get("workTypes", [])
        work_type_str = ", ".join(work_types) if work_types else None

        arrangements = (item.get("workArrangements") or {}).get("data", [])
        labels = []
        for arr in arrangements:
            if not isinstance(arr, dict):
                continue
            label = arr.get("label") or ""
            if isinstance(label, dict):
                label = label.get("text") or ""
            labels.append(str(label).lower())
        # Keep remote and hybrid distinct. Never infer onsite from silence.
        work_mode = (
            "remote" if any("remote" in label for label in labels) else
            "hybrid" if any("hybrid" in label for label in labels) else
            "onsite" if any("onsite" in label or "on-site" in label for label in labels) else
            "unknown"
        )
        is_remote = work_mode in ("remote", "hybrid")

        posted_at = item.get("listingDate")
        teaser = item.get("teaser") or ""
        bullet_points = item.get("bulletPoints") or []
        desc = (teaser + " " + " ".join(bullet_points)).strip() or None

        jobs.append(
            Job(
                source="jobstreet",
                external_id=job_id,
                title=title,
                company=company,
                location_raw=loc_str,
                area=area,
                url=url,
                salary=salary,
                work_type=work_type_str,
                is_remote=is_remote,
                work_mode=work_mode,
                posted_at=posted_at,
                description=desc,
                company_logo=company_logo,
            )
        )
    return jobs

def fetch_jobstreet(keyword: str, where: str = "Jakarta Raya", page: int = 1, page_size: int = 30) -> SourceResult:
    query_params = {
        "siteKey": "ID-Main",
        "keywords": keyword,
        "where": where,
        "page": str(page),
        "pageSize": str(page_size),
        "sortmode": "ListedDate",
        "locale": "en-ID",
    }
    url = f"https://id.jobstreet.com/api/jobsearch/v5/search?{urllib.parse.urlencode(query_params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_UA,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                return SourceResult(
                    source="jobstreet",
                    success=False,
                    jobs=[],
                    error_message=f"HTTP status {response.status}",
                )
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                return SourceResult(source="jobstreet", success=False, jobs=[], error_message="Unexpected provider schema")
            jobs = parse_jobstreet_payload(payload)
            return SourceResult(source="jobstreet", success=True, jobs=jobs)
    except urllib.error.HTTPError as e:
        return SourceResult(
            source="jobstreet",
            success=False,
            jobs=[],
            error_message=f"HTTP Error {e.code}: {e.reason}",
        )
    except Exception as e:
        return SourceResult(
            source="jobstreet",
            success=False,
            jobs=[],
            error_message=str(e),
        )
