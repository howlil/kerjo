"""Official public company-job feeds, configured per company rather than scraping search engines.

KERJO_ATS_BOARDS="ashby:company,greenhouse:company,lever:company"
Greenhouse/Lever omit reliable publish dates for some posts: never infer one from updates.
"""
import json
import os
import re
import urllib.parse
import urllib.request

from jobhunt.enrichment import clean_text
from jobhunt.location import match_area
from jobhunt.models import Job, SourceResult

BOARD_NAME = re.compile(r"^[A-Za-z0-9_-]{2,90}$")
PROVIDERS = {"greenhouse", "lever", "ashby"}


def configured_boards(value=None):
    raw = os.environ.get("KERJO_ATS_BOARDS", "") if value is None else value
    boards = []
    for chunk in raw.split(",")[:30]:
        provider, sep, token = chunk.strip().partition(":")
        if sep and provider in PROVIDERS and BOARD_NAME.fullmatch(token):
            pair = (provider, token)
            if pair not in boards:
                boards.append(pair)
    return boards


def public_json(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Kerjo/2.0 (personal job discovery; public board APIs)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=10) as response:
        raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError("ATS payload too large")
        return json.loads(raw.decode("utf-8"))


def parse_ats_board(provider, board, payload):
    if provider == "lever":
        if not isinstance(payload, list):
            raise ValueError("Lever schema changed")
        records = payload
    else:
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError(provider + " schema changed")
        records = payload["jobs"]
    out = []
    for item in records:
        if not isinstance(item, dict):
            continue
        if provider == "greenhouse":
            ident = item.get("id")
            title = item.get("title") or ""
            location = (item.get("location") or {}).get("name") or ""
            url = item.get("absolute_url")
            description = clean_text(item.get("content") or "")
            published = item.get("first_published_at") or item.get("published_at")
            apply_url = url
            work_mode = "unknown"
        elif provider == "lever":
            ident = item.get("id")
            title = item.get("text") or ""
            categories = item.get("categories") or {}
            location = categories.get("location") or ""
            url = item.get("hostedUrl")
            blocks = [item.get("descriptionPlain") or item.get("description") or ""]
            blocks += [entry.get("text", "") + "\n" + clean_text(entry.get("content") or "")
                       for entry in (item.get("lists") or []) if isinstance(entry, dict)]
            blocks.append(item.get("additionalPlain") or item.get("additional") or "")
            description = clean_text("\n\n".join(blocks))
            published = item.get("publishedAt") or item.get("datePosted")
            apply_url = item.get("applyUrl") or url
            work_mode = str(item.get("workplaceType") or "unknown").lower()
        else:
            if item.get("isListed") is False:
                continue
            ident = item.get("jobUrl") or item.get("id")
            title = item.get("title") or ""
            location = item.get("location") or ""
            url = item.get("jobUrl")
            description = clean_text(item.get("descriptionPlain") or item.get("descriptionHtml") or "")
            published = item.get("publishedAt")
            apply_url = item.get("applyUrl") or url
            work_mode = {"onsite": "onsite", "remote": "remote", "hybrid": "hybrid"}.get(
                str(item.get("workplaceType") or "").lower(), "unknown")
        if not ident or not title or not url or not str(url).startswith("https://"):
            continue
        area = match_area(location)
        if area is None:
            continue
        if not any(word in title.lower() for word in ("engineer", "developer", "programmer", "devops", "software", "backend", "frontend", "cloud", "platform", "data", "qa")):
            # The classifier remains authoritative; pre-filter avoids distant unrelated roles.
            continue
        job = Job(
            source="ats", external_id=f"{provider}:{board}:{ident}",
            title=title.strip(), company=board.replace("-", " ").title(),
            location_raw=location, area=area, url=url,
            is_remote=work_mode == "remote", work_mode=work_mode,
            posted_at=published, description=description or None,
            application_url=apply_url, application_evidence="official-ats",
            description_status="complete" if len(description) >= 180 else ("partial" if description else "missing"),
            description_source=provider + "-api",
        )
        out.append(job)
    return out


def fetch_ats(keyword):
    boards = configured_boards()
    if not boards:
        return SourceResult("ats", True, [])
    jobs, failures = [], []
    for provider, board in boards:
        endpoint = {
            "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true",
            "lever": f"https://api.lever.co/v0/postings/{board}?mode=json",
            "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{board}",
        }[provider]
        try:
            parsed = parse_ats_board(provider, board, public_json(endpoint))
            # Board APIs return all jobs. Search locally; don't depend on fuzzy remote ranking.
            tokens = [word.lower() for word in keyword.split() if len(word) > 2]
            jobs.extend(job for job in parsed if not tokens or any(t in job.title.lower() for t in tokens))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            failures.append(f"{provider}:{board}: {type(exc).__name__}")
    return SourceResult("ats", bool(jobs) or not failures, jobs,
                        error_message="; ".join(failures) or None)
