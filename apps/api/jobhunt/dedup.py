import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from typing import List, Dict, Any, Set

COMPANY_STOPWORDS = {"pt", "cv", "tbk", "inc", "corp", "corporation", "ltd", "limited", "llc", "group", "indonesia", "jaya"}
TITLE_STOPWORDS = {"and", "or", "the", "a", "an", "full", "time", "part", "remote", "wfh", "hybrid", "on", "site", "onsite", "in", "at", "for"}

def get_company_tokens(name: str) -> List[str]:
    if not name:
        return []
    words = re.findall(r"\b[a-zA-Z0-9]+\b", name.lower())
    return [w for w in words if w not in COMPANY_STOPWORDS and len(w) > 1]

def get_title_tokens(title: str) -> Set[str]:
    if not title:
        return set()
    words = re.findall(r"\b[a-zA-Z0-9]+\b", title.lower())
    return {w for w in words if w not in TITLE_STOPWORDS and len(w) > 1}

def normalize_key(company: str, title: str) -> str:
    c_tokens = get_company_tokens(company)
    c_key = " ".join(c_tokens) if c_tokens else clean_fallback(company)
    t_tokens = sorted(get_title_tokens(title))
    t_key = " ".join(t_tokens) if t_tokens else clean_fallback(title)
    return f"{c_key}::{t_key}"

def clean_fallback(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", "", (text or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()

def canonical_vacancy_url(url: str) -> str:
    """Normalize a concrete posting URL, not a guessed company/title identity."""
    if not isinstance(url, str) or not url.strip():
        return ""
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return ""
        host = parsed.hostname.lower().removeprefix("www.")
        if parsed.port and parsed.port not in (80, 443):
            host += ":" + str(parsed.port)
        path = parsed.path.rstrip("/") or "/"
        # Query params may contain actual vacancy IDs: retain these.
        tracking = {"trk", "tracking", "trackingid",
                    "utm_source", "utm_medium", "utm_campaign", "utm_term",
                    "utm_content", "fbclid", "gclid"}
        query = urlencode(sorted((k, v) for k, v in parse_qsl(parsed.query)
                                 if k.lower() not in tracking))
        return urlunsplit(("https", host, path, query, ""))
    except (ValueError, TypeError):
        return ""


def verified_vacancy_key(job: Dict[str, Any]) -> tuple:
    """Shared verified URL can group provider records; similarity alone never can.

    This deliberately favors false negatives (duplicate cards) over incorrect
    merges that would change seen/saved/application state on another vacancy.
    """
    normalized_url = canonical_vacancy_url(job.get("url") or "")
    # A homepage or generic category URL cannot identify a particular job.
    parsed = urlsplit(normalized_url) if normalized_url else None
    segments = [part.lower() for part in parsed.path.split("/") if part] if parsed else []
    generic_category = (len(segments) == 1 and
                        segments[0] in {"jobs", "job", "careers", "vacancies",
                                        "opportunities", "positions", "listings", "search"} and
                        not parsed.query)
    if normalized_url and parsed.path != "/" and not generic_category:
        return ("url", normalized_url,
                normalize_key(job.get("company", ""), job.get("title", "")),
                job.get("area") or "unspecified",
                job.get("work_mode") or "unknown")
    return ("source", job.get("source", ""), str(job.get("external_id") or
                                                job.get("id") or job.get("job_id") or ""))


def group_dedup_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped_map: Dict[tuple, Dict[str, Any]] = {}
    order: List[tuple] = []

    for job in jobs:
        key = verified_vacancy_key(job)
        src = job.get("source", "unknown")

        if key not in grouped_map:
            merged = dict(job)
            merged["sources"] = [src]
            merged["urls"] = {src: job["url"]}
            merged["ids"] = [job["id"]]
            grouped_map[key] = merged
            order.append(key)
        else:
            existing = grouped_map[key]
            if src not in existing["sources"]:
                existing["sources"].append(src)
            existing["urls"][src] = job["url"]
            if job["id"] not in existing["ids"]:
                existing["ids"].append(job["id"])
            if job.get("is_new"):
                existing["is_new"] = 1
            if not existing.get("salary") and job.get("salary"):
                existing["salary"] = job["salary"]
            if (len(job.get("location_raw") or "")) > (len(existing.get("location_raw") or "")):
                existing["location_raw"] = job["location_raw"]
            # A complete job description outranks a longer search-card snippet.
            better_description = (
                (job.get("description_status") == "complete" and existing.get("description_status") != "complete")
                or (job.get("description_status") == existing.get("description_status")
                    and len(job.get("description") or "") > len(existing.get("description") or ""))
            )
            if better_description:
                existing["description"] = job.get("description")
                existing["description_status"] = job.get("description_status")
                existing["description_source"] = job.get("description_source")
            if not existing.get("origin_url") and job.get("origin_url"):
                existing["origin_url"] = job["origin_url"]
            if not existing.get("application_url") and job.get("application_url"):
                existing["application_url"] = job["application_url"]
                existing["application_evidence"] = job.get("application_evidence")
            if (existing.get("experience_level") in (None, "unspecified")) and job.get("experience_level") not in (None, "unspecified"):
                existing["experience_level"] = job["experience_level"]
                existing["min_years"] = job.get("min_years")
                existing["max_years"] = job.get("max_years")
                existing["experience_raw"] = job.get("experience_raw")
            if (existing.get("role_category") in (None, "other")) and job.get("role_category") not in (None, "other"):
                existing["role_category"] = job["role_category"]
            if not existing.get("company_logo") and job.get("company_logo"):
                existing["company_logo"] = job["company_logo"]

    return [grouped_map[k] for k in order]
