import re
from typing import List, Dict, Any, Set

COMPANY_STOPWORDS = {"pt", "cv", "tbk", "inc", "corp", "corporation", "ltd", "limited", "llc", "group", "indonesia", "jaya"}
TITLE_STOPWORDS = {"and", "or", "the", "a", "an", "full", "time", "part", "intern", "internship", "remote", "wfh", "hybrid", "on", "site", "onsite", "in", "at", "for"}

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
    c_key = c_tokens[0] if c_tokens else clean_fallback(company)
    t_tokens = sorted(get_title_tokens(title))
    t_key = " ".join(t_tokens) if t_tokens else clean_fallback(title)
    return f"{c_key}::{t_key}"

def clean_fallback(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", "", (text or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()

def group_dedup_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped_map: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []

    for job in jobs:
        key = normalize_key(job.get("company", ""), job.get("title", ""))
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

    return [grouped_map[k] for k in order]
