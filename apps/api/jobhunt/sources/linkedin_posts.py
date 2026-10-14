"""Recruiter-post ingestion with explicit application evidence.

Two supported paths:
  1. User-supplied post text/URL through local API.
  2. Official LinkedIn Posts API for authors the user is authorized to read.
No unauthenticated feed crawling, cookies, CAPTCHA bypass, or engagement automation.
"""
import datetime
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from jobhunt.enrichment import allowed_detail_url, enrich_job
from jobhunt.freshness import posting_age_status
from jobhunt.location import match_area
from jobhunt.models import Job, SourceResult

URL_RE = re.compile(r"https://[^\s<>\[\]()]+", re.I)
ROLE_RE = re.compile(
    r"\b(?:junior |senior |associate |staff |lead |graduate |internship |intern )?"
    r"(?:backend|back-end|frontend|front-end|full.?stack|software|platform|cloud|devops|data|qa|site reliability)"
    r"\s+(?:engineer|developer|intern|programmer)\b", re.I)
BLOCKED_HOSTS = (
    "linkedin.com", "www.linkedin.com", "facebook.com", "www.facebook.com",
    "instagram.com", "www.instagram.com", "t.me", "wa.me",
    "bit.ly", "tinyurl.com", "forms.gle", "docs.google.com",
)
APPLY_PATH = re.compile(r"(^|/)(jobs?|careers?|vacanc(?:y|ies)|positions?|apply|recruitment)(/|$)", re.I)


def valid_post_url(url):
    try:
        p = urllib.parse.urlsplit(url)
        return (p.scheme == "https" and p.hostname in ("www.linkedin.com", "linkedin.com")
                and not p.username and not p.password
                and (p.path.startswith("/posts/") or p.path.startswith("/feed/update/")))
    except (ValueError, TypeError):
        return False


def application_link(url):
    if not isinstance(url, str) or len(url) > 2048:
        return None
    url = url.strip().rstrip(".,;:!>)")
    try:
        p = urllib.parse.urlsplit(url)
        host = (p.hostname or "").lower()
        if p.scheme != "https" or not host or p.username or p.password or p.port not in (None, 443):
            return None
        if host in BLOCKED_HOSTS or host.endswith(".linkedin.com"):
            return None
        # Trusted ATS destinations or an explicitly job-related company careers path.
        trusted = allowed_detail_url(url) or host in ("apply.workable.com", "jobs.smartrecruiters.com")
        if not trusted and not APPLY_PATH.search(p.path):
            return None
        return url
    except ValueError:
        return None


def pick_apply_link(text, supplied=None):
    candidates = ([supplied] if supplied else []) + URL_RE.findall(text or "")
    for candidate in candidates:
        valid = application_link(candidate)
        if valid:
            return valid
    return None


def make_post_job(data):
    """Validate recruiter post before persisting; reject comment-only calls to action."""
    if not isinstance(data, dict):
        raise ValueError("Expected recruiter post object")
    url, text = data.get("post_url"), data.get("text")
    if not valid_post_url(url):
        raise ValueError("A public LinkedIn post URL is required")
    if not isinstance(text, str) or len(text) > 20000:
        raise ValueError("Post text must be at most 20,000 characters")
    title = data.get("title") or ""
    company = data.get("company") or ""
    location = data.get("location") or ""
    if not all(isinstance(x, str) for x in (title, company, location)):
        raise ValueError("Title, company, and location must be strings")
    match = ROLE_RE.search(title) or ROLE_RE.search(text)
    if not match:
        raise ValueError("Post has no identifiable software engineering vacancy")
    if not title:
        title = match.group(0)
    if not company.strip():
        raise ValueError("Company is required to avoid unattributed recruitment claims")
    apply_url = pick_apply_link(text, data.get("apply_url"))
    if not apply_url:
        raise ValueError("No direct careers/application link; comments and DMs are not evidence")
    if posting_age_status(data.get("posted_at")) != "recent":
        raise ValueError("Post is undated or outside the 14-day publication window")
    area = match_area(location)
    if area is None:
        raise ValueError("Location outside configured discovery areas")
    key = hashlib.sha256((url + "|" + title.lower() + "|" + apply_url).encode("utf-8")).hexdigest()[:24]
    job = Job(
        source="linkedin_posts", external_id=key, title=title[:180], company=company[:180],
        location_raw=location[:200], area=area, url=apply_url,
        posted_at=data["posted_at"], description=text.strip() or None,
        description_status="partial" if text.strip() else "missing",
        description_source="recruiter-post", origin_url=url,
        application_url=apply_url,
        application_evidence=("ats-link" if allowed_detail_url(apply_url) else "careers-link-unverified"),
    )
    # Only the approved public ATS pages are fetched, never LinkedIn content itself.
    return job


def authorized_authors(raw=None):
    """Allow explicit URN|company pairs, e.g. urn:li:organization:123|Acme."""
    raw = os.getenv("KERJO_LINKEDIN_AUTHORS", "") if raw is None else raw
    entries = []
    for entry in raw.split(",")[:20]:
        urn, sep, company = entry.strip().partition("|")
        if sep and re.fullmatch(r"urn:li:(?:organization:[0-9]+|person:[A-Za-z0-9_-]+)", urn) and company.strip():
            entries.append((urn, company.strip()[:180]))
    return entries


def parse_official_post(item, company):
    if not isinstance(item, dict) or item.get("lifecycleState") != "PUBLISHED":
        return None
    raw_id = item.get("id") or ""
    if not re.fullmatch(r"urn:li:(?:share|ugcPost):[0-9]+", raw_id):
        return None
    published = item.get("publishedAt")
    if not isinstance(published, (float, int)):
        return None
    posted_at = datetime.datetime.fromtimestamp(published / 1000, datetime.timezone.utc).isoformat()
    text = item.get("commentary") or ""
    if not isinstance(text, str):
        return None
    article = (item.get("content") or {}).get("article") or {}
    linked_url = article.get("source") if isinstance(article, dict) else None
    slug = raw_id.replace(":", "%3A")
    url = "https://www.linkedin.com/feed/update/" + slug + "/"
    title_match = ROLE_RE.search(text)
    if not title_match:
        return None
    payload = {"post_url": url, "text": text, "company": company,
               "title": title_match.group(0), "posted_at": posted_at,
               "apply_url": linked_url, "location": ""}
    try:
        return make_post_job(payload)
    except ValueError:
        return None


def fetch_linkedin_posts(keyword):
    token = os.getenv("KERJO_LINKEDIN_ACCESS_TOKEN")
    authors = authorized_authors()
    if not token or not authors:
        return SourceResult("linkedin_posts", True, [],
                            error_message="Not configured: approved LinkedIn API token and author URNs required")
    version = os.getenv("KERJO_LINKEDIN_VERSION", "202609")
    if not re.fullmatch(r"20[0-9]{4}", version):
        return SourceResult("linkedin_posts", False, [], "Invalid LinkedIn API version")
    jobs, errors = [], []
    for author, company in authors:
        query = urllib.parse.urlencode({"q": "author", "author": author, "count": 50,
                                        "sortBy": "CREATED"})
        req = urllib.request.Request("https://api.linkedin.com/rest/posts?" + query, headers={
            "Authorization": "Bearer " + token,
            "Linkedin-Version": version,
            "X-Restli-Protocol-Version": "2.0.0",
            "X-RestLi-Method": "FINDER",
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("API response too large")
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload.get("elements"), list):
                raise ValueError("Unexpected LinkedIn API response")
            for entry in payload["elements"]:
                job = parse_official_post(entry, company)
                if job and keyword.lower() in (job.title + " " + job.description).lower():
                    jobs.append(job)
        except (OSError, ValueError, TypeError) as exc:
            errors.append(author + ": " + type(exc).__name__)
    return SourceResult("linkedin_posts", bool(jobs) or not errors, jobs,
                        error_message="; ".join(errors) or None)
