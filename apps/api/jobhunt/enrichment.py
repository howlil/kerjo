"""Best-effort detail enrichment from public JobPosting JSON-LD only.

Security boundary: HTTPS, exact allowlisted host per source, no credentials,
no custom ports, no redirects, strict response size and request budget.
No CAPTCHA handling, credential automation, or anti-bot bypass.
"""
from html import unescape
from html.parser import HTMLParser
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from jobhunt.freshness import posting_age_status, parse_posted_at

SOURCE_HOSTS = {
    "jobstreet": frozenset({"id.jobstreet.com"}),
    "kalibrr": frozenset({"kalibrr.com", "www.kalibrr.com"}),
    "linkedin": frozenset({"linkedin.com", "www.linkedin.com"}),
    "glints": frozenset({"glints.com", "www.glints.com"}),
    "dealls": frozenset({"dealls.com", "www.dealls.com"}),
    "karir": frozenset({"karir.com", "www.karir.com"}),
    "techinasia": frozenset({"techinasia.com", "www.techinasia.com"}),
}
MAX_HTML_BYTES = 300_000


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def text(self):
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def allowed_detail_url(source, url):
    if not isinstance(url, str) or source not in SOURCE_HOSTS:
        return False
    try:
        parts = urllib.parse.urlsplit(url)
        return (parts.scheme == "https" and
                parts.hostname in SOURCE_HOSTS[source] and
                parts.port in (None, 443) and
                parts.username is None and parts.password is None and
                bool(parts.path.strip("/")) and len(url) <= 2000)
    except ValueError:
        return False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def get_detail_html(url):
    """Fetch exactly one allowlisted destination; never follow external redirects."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "Kerjo/3.0 (manual, public-job-metadata)",
                      "Accept": "text/html,application/xhtml+xml"})
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=6) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            return ""
        content = response.read(MAX_HTML_BYTES + 1)
        if len(content) > MAX_HTML_BYTES:
            return ""
        return content.decode("utf-8", "replace")


def jobposting_metadata(html_text, expected_title=""):
    """Extract only JobPosting JSON-LD, never use page modified timestamps."""
    if not isinstance(html_text, str):
        return {}
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script\s*>", html_text,
                         flags=re.IGNORECASE | re.DOTALL)
    desired = re.sub(r"[^a-z0-9]+", " ", (expected_title or "").lower()).split()
    for attributes, raw_json in scripts:
        if not re.search(r"""type\s*=\s*['"]application/ld\+json['"]""",
                         attributes, flags=re.IGNORECASE):
            continue
        try:
            payload = json.loads(unescape(raw_json.strip()))
        except (json.JSONDecodeError, ValueError):
            continue
        queue = [payload]
        while queue:
            item = queue.pop()
            if isinstance(item, list):
                queue.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                queue.extend(graph)
            kinds = item.get("@type") or []
            if isinstance(kinds, str):
                kinds = [kinds]
            if not any(str(t).lower().split("/")[-1] == "jobposting" for t in kinds):
                continue
            title = str(item.get("title") or "")
            title_terms = set(re.sub(r"[^a-z0-9]+", " ", title.lower()).split())
            # Reject landing pages with a clearly different requisition title.
            if desired and title and not (set(desired) & title_terms):
                continue
            description = item.get("description")
            if isinstance(description, str) and description.strip():
                parser = TextOnly()
                parser.feed(description)
                clean_desc = parser.text()[:12000]
            else:
                clean_desc = None
            date = item.get("datePosted") or None
            return {"posted_at": date, "description": clean_desc}
    return {}


def enrich_jobs(jobs, source, *, max_details=None, fetch_html=None):
    """Mutate only known posting fields and return count of enriched vacancies.

    Unknown posting date has priority, followed by recent listings with brief
    descriptions; never fetch a known >14-day-old vacancy.
    """
    try:
        budget = (int(os.getenv("KERJO_DETAIL_ENRICH_LIMIT", "3"))
                  if max_details is None else int(max_details))
    except (TypeError, ValueError):
        budget = 3
    budget = max(0, min(10, budget))
    fetch_html = fetch_html or get_detail_html
    candidates = []
    for job in jobs:
        if not allowed_detail_url(source, job.url):
            continue
        freshness = posting_age_status(job.posted_at)
        if freshness in ("old", "future"):
            continue
        if freshness == "unknown":
            candidates.append((0, job))
        elif len(job.description or "") < 240:
            candidates.append((1, job))
    candidates.sort(key=lambda item: item[0])
    changed = 0
    seen_urls = set()
    for _, job in candidates:
        if len(seen_urls) >= budget:
            break
        if job.url in seen_urls:
            continue
        seen_urls.add(job.url)
        try:
            metadata = jobposting_metadata(fetch_html(job.url),
                                           expected_title=job.title)
            updated = False
            if posting_age_status(job.posted_at) == "unknown" and metadata.get("posted_at"):
                parsed = parse_posted_at(metadata["posted_at"])
                if parsed is not None:
                    job.posted_at = parsed.isoformat()
                    updated = True
            description = metadata.get("description")
            if description and len(description) > len(job.description or ""):
                job.description = description
                updated = True
            if updated:
                changed += 1
        except (OSError, ValueError, urllib.error.URLError, UnicodeError):
            # Details are optional. The authoritative 14-day gate still applies.
            continue
    return changed
