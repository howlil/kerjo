"""Bounded, provenance-aware extraction from publicly accessible job detail pages.

Do not fetch LinkedIn pages, arbitrary URLs, private networks, or HTML behind login.
JSON-LD JobPosting and job-description sections outrank search-card snippets.
"""
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

ALLOWED_HOSTS = (
    "id.jobstreet.com", "glints.com", "www.glints.com",
    "dealls.com", "www.dealls.com", "www.kalibrr.com",
    "www.karir.com", "www.techinasia.com",
    "boards.greenhouse.io", "job-boards.greenhouse.io",
    "jobs.lever.co", "jobs.eu.lever.co", "jobs.ashbyhq.com",
)
DETAIL_MARKERS = (
    "job-description", "jobdescription", "job_description",
    "job-details", "jobdetails", "job-detail",
    "description__text", "job-content", "jobcontent",
    "posting-description", "section-description",
    "job-desc", "jobdesc", "job_advertisement",
)
MAX_RESPONSE = 2_000_000
MIN_COMPLETE_CHARS = 180


def allowed_detail_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        parsed = urllib.parse.urlsplit(value)
        hostname = (parsed.hostname or "").lower()
        return (parsed.scheme == "https" and not parsed.username and not parsed.password
                and parsed.port in (None, 443) and hostname in ALLOWED_HOSTS)
    except ValueError:
        return False


def clean_text(value):
    if not isinstance(value, str):
        return ""
    for _ in range(2):
        value = html.unescape(value)
    if "<" in value and re.search(r"</?(?:p|div|li|br|ul|ol|h[1-6])\\b", value, re.I):
        value = html_to_text(value)
    value = re.sub(r"[ \\t]+", " ", value)
    value = re.sub(r" *\\n *", "\\n", value)
    return re.sub(r"\\n{3,}", "\\n\\n", value).strip()[:30000]


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.hidden += 1
        if not self.hidden and tag in ("p", "div", "li", "br", "h1", "h2", "h3", "h4"):
            self.parts.append("\\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.hidden:
            self.hidden -= 1
        elif not self.hidden and tag in ("p", "li", "div", "h1", "h2", "h3", "h4"):
            self.parts.append("\\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def html_to_text(value):
    parser = TextOnly()
    parser.feed(value)
    return "".join(parser.parts).strip()


@dataclass
class Detail:
    description: str = ""
    status: str = "missing"
    provenance: str = ""
    posted_at: str | None = None


def _postings(payload):
    if isinstance(payload, list):
        for item in payload:
            yield from _postings(item)
    elif isinstance(payload, dict):
        types = payload.get("@type") or []
        if isinstance(types, str):
            types = [types]
        if any(str(t).lower().endswith("jobposting") for t in types):
            yield payload
        if "@graph" in payload:
            yield from _postings(payload["@graph"])


class JobDetailHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.target_depth = None
        self.target_text = []
        self.sections = []
        self.script_depth = None
        self.script_buffer = []
        self.jsonld = []
        self.date_posted = None
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        self.depth += 1
        a = dict(attrs)
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self.script_depth = self.depth
            self.script_buffer = []
        if tag in ("script", "style", "nav", "footer", "noscript", "svg"):
            self.suppressed += 1
        tokens = (a.get("class") or "") + " " + (a.get("id") or "") + " " + (a.get("data-testid") or "")
        tokens = tokens.lower()
        if (self.target_depth is None and not self.suppressed
                and any(marker in tokens for marker in DETAIL_MARKERS)):
            self.target_depth = self.depth
            self.target_text = []
        if tag == "meta" and (a.get("itemprop") or "").lower() == "dateposted":
            self.date_posted = a.get("content") or self.date_posted
        if tag in ("p", "li", "br", "h2", "h3", "h4") and self.target_depth is not None:
            self.target_text.append("\\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self.script_depth is not None:
            self.script_buffer.append(data)
        elif self.target_depth is not None and not self.suppressed:
            self.target_text.append(data)

    def handle_endtag(self, tag):
        if self.script_depth == self.depth and tag == "script":
            try:
                self.jsonld.extend(_postings(json.loads("".join(self.script_buffer))))
            except (ValueError, TypeError):
                pass
            self.script_depth = None
        if self.target_depth == self.depth:
            self.sections.append(clean_text("".join(self.target_text)))
            self.target_depth = None
            self.target_text = []
        if tag in ("script", "style", "nav", "footer", "noscript", "svg") and self.suppressed:
            self.suppressed -= 1
        self.depth = max(0, self.depth - 1)


def parse_job_detail(raw_html):
    parser = JobDetailHTML()
    parser.feed(raw_html)
    ld = [p for p in parser.jsonld if isinstance(p.get("description"), str)]
    ranked = [(clean_text(p["description"]), "jsonld") for p in ld]
    ranked.extend((section, "html-section") for section in parser.sections)
    ranked = [(s, provenance) for s, provenance in ranked if s]
    if not ranked:
        return Detail(posted_at=parser.date_posted)
    description, provenance = max(ranked, key=lambda item: len(item[0]))
    posted_at = next((p.get("datePosted") for p in ld if p.get("datePosted")), parser.date_posted)
    return Detail(description=description,
                  status="complete" if len(description) >= MIN_COMPLETE_CHARS else "partial",
                  provenance=provenance, posted_at=posted_at)


class SafeRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_detail_url(newurl):
            raise ValueError("Redirect outside approved public job hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_job_detail(url, opener=None):
    """Single bounded request, only to approved job-board hosts; no authentication."""
    if not allowed_detail_url(url):
        raise ValueError("Unsupported job detail host")
    opener = opener or urllib.request.build_opener(SafeRedirects())
    req = urllib.request.Request(url, headers={
        "User-Agent": "Kerjo/2.0 (personal job discovery; public pages only)",
        "Accept": "text/html",
    })
    with opener.open(req, timeout=9) as response:
        if not allowed_detail_url(response.geturl()):
            raise ValueError("Redirect to disallowed host")
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type:
            raise ValueError("Job detail is not HTML")
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("Job detail response too large")
        return parse_job_detail(raw.decode("utf-8", "replace"))


def enrich_job(job, fetcher=fetch_job_detail):
    """Keep snippets when detail cannot be confirmed; never relabel snippet as full."""
    job.description_status = "partial" if job.description else "missing"
    job.description_source = "search-result" if job.description else None
    if not allowed_detail_url(job.url):
        return job
    try:
        detail = fetcher(job.url)
    except (OSError, ValueError, urllib.error.URLError):
        return job
    if detail.status == "complete":
        job.description = detail.description
        job.description_status = "complete"
        job.description_source = detail.provenance
    elif detail.description and len(detail.description) > len(job.description or ""):
        job.description = detail.description
        job.description_status = "partial"
        job.description_source = detail.provenance
    if not job.posted_at and detail.posted_at:
        job.posted_at = detail.posted_at
    return job
