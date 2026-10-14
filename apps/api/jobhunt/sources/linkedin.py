import urllib.request
import urllib.parse
import re
import html
import logging
from typing import Optional
from jobhunt.models import Job, SourceResult
from jobhunt.collection import retry_after_seconds
from jobhunt.location import match_area

logger = logging.getLogger(__name__)

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

def parse_linkedin_html(html_text: str) -> list[Job]:
    # Match search result cards
    cards = re.findall(r'<div[^>]*base-search-card[^>]*>.*?</div>\s*</li>', html_text, re.S)
    jobs = []

    for card in cards:
        # Extract URN / ID
        urn_m = re.search(r'data-entity-urn="urn:li:jobPosting:(\d+)"', card, re.S)
        if not urn_m:
            continue
        job_id = urn_m.group(1)

        # Title
        title_m = re.search(r'<h3[^>]*base-search-card__title[^>]*>\s*(.*?)\s*</h3>', card, re.S)
        title = html.unescape(title_m.group(1)).strip() if title_m else ""

        # Company
        comp_m = re.search(r'<h4[^>]*base-search-card__subtitle[^>]*>.*?<a[^>]*>\s*(.*?)\s*</a>', card, re.S)
        if not comp_m:
            comp_m = re.search(r'<h4[^>]*base-search-card__subtitle[^>]*>\s*(.*?)\s*</h4>', card, re.S)
        company = html.unescape(comp_m.group(1)).strip() if comp_m else "Unknown Company"

        # Location
        loc_m = re.search(r'<span[^>]*job-search-card__location[^>]*>\s*(.*?)\s*</span>', card, re.S)
        loc_str = html.unescape(loc_m.group(1)).strip() if loc_m else ""

        area = match_area(loc_str)
        if area is None:
            # Excluded area
            continue

        # URL
        link_m = re.search(r'<a[^>]*base-card__full-link[^>]*href="([^"]+)"', card, re.S)
        if link_m:
            raw_url = html.unescape(link_m.group(1))
            clean_url = raw_url.split("?")[0]
        else:
            clean_url = f"https://www.linkedin.com/jobs/view/{job_id}"

        # Posted date
        time_m = re.search(r'<time[^>]*datetime="([^"]+)"', card, re.S)
        posted_at = time_m.group(1) if time_m else None

        is_remote = "remote" in title.lower() or "hybrid" in title.lower() or "remote" in loc_str.lower()
        snippet_m = re.search(r'<div[^>]*base-search-card__metadata[^>]*>(.*?)</div>', card, re.S)
        desc = re.sub(r'<[^>]+>', ' ', snippet_m.group(1)).strip() if snippet_m else None

        logo_m = re.search(r'<img[^>]+class="[^"]*artdeco-entity-image[^"]*"[^>]+(?:data-delayed-url|src)="([^"]+)"', card, re.S)
        if not logo_m:
            logo_m = re.search(r'<img[^>]+(?:data-delayed-url|src)="([^"]+)"[^>]+class="[^"]*artdeco-entity-image', card, re.S)
        company_logo = html.unescape(logo_m.group(1)).strip() if logo_m else None
        if company_logo and ("data:image" in company_logo or "ghost" in company_logo):
            company_logo = None

        jobs.append(
            Job(
                source="linkedin",
                external_id=job_id,
                title=title,
                company=company,
                location_raw=loc_str,
                area=area,
                url=clean_url,
                salary=None,
                work_type=None,
                is_remote=is_remote,
                work_mode=("remote" if "remote" in (title + " " + loc_str).lower() else "hybrid" if "hybrid" in (title + " " + loc_str).lower() else "unknown"),
                posted_at=posted_at,
                description=desc,
                company_logo=company_logo,
            )
        )

    return jobs

def fetch_linkedin(keyword: str, location: str = "Jakarta, Indonesia", start: int = 0) -> SourceResult:
    query_params = {
        "keywords": keyword,
        "location": location,
        "start": str(start),
        "f_TPR": "r1209600",  # Request last 14 days; final date gate remains local.
    }
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{urllib.parse.urlencode(query_params)}"
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
                    source="linkedin",
                    success=False,
                    jobs=[],
                    error_message=f"HTTP status {response.status}",
                    http_status=response.status,
                )
            html_content = response.read().decode("utf-8", "replace")
            jobs = parse_linkedin_html(html_content)
            if not jobs and any(marker in html_content.lower() for marker in
                                ("captcha", "security verification", "challenge", "base-search-card")):
                return SourceResult(source="linkedin", success=False, jobs=[],
                                    error_message="Blocked or LinkedIn parser structure changed")
            return SourceResult(source="linkedin", success=True, jobs=jobs, raw_count=len(re.findall(r'<div[^>]*base-search-card', html_content)), pages_fetched=1)
    except urllib.error.HTTPError as e:
        status_desc = "Rate-limited / blocked" if e.code in (429, 403) else e.reason
        return SourceResult(
            source="linkedin",
            success=False,
            jobs=[],
            error_message=f"HTTP {e.code}: {status_desc}",
        )
    except Exception as e:
        return SourceResult(
            source="linkedin",
            success=False,
            jobs=[],
            error_message=str(e),
        )
