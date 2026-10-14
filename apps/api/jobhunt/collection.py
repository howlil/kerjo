"""Bounded, polite pagination with explicit failures and retry accounting.

This does not bypass site restrictions: 401/403/CAPTCHA failures stop immediately.
All sleeps are bounded; call sites can inject sleep/jitter for deterministic tests.
"""
import datetime as dt
import email.utils
import os
import random
import re
import time

from jobhunt.models import SourceResult

RETRYABLE_HTTP = {429, 500, 502, 503, 504}


def retry_after_seconds(value, now=None):
    """Parse Retry-After delta-seconds or HTTP-date; never return a negative wait."""
    if value is None:
        return None
    try:
        text = str(value).strip()
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            return max(0.0, float(text))
        when = email.utils.parsedate_to_datetime(text)
        if when is None:
            return None
        now = now or dt.datetime.now(dt.timezone.utc)
        return max(0.0, (when - now).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return None


def is_transient(result):
    if result.http_status is not None:
        return result.http_status in RETRYABLE_HTTP
    # Compatibility with older adapters that only return an error message.
    message = (result.error_message or "").lower()
    if any(word in message for word in ("captcha", "challenge", "forbidden", "blocked", "403", "401")):
        return False
    return bool(re.search(r"\b(?:429|500|502|503|504)\b", message) or
                any(word in message for word in ("timeout", "timed out", "connection reset")))


def collect_pages(source, fetch_page, page_limit=None, *, sleep=None, jitter=None, gap_seconds=None):
    """Fetch pages with bounded retry and stop conditions.

    A filtered-empty page is *not* end-of-results; raw_count=0 is.
    Repeating an identical nonempty page terminates pagination.
    """
    started = time.monotonic()
    sleep = sleep if sleep is not None else time.sleep
    jitter = jitter if jitter is not None else random.uniform
    try:
        maximum = int(os.getenv("KERJO_MAX_PAGES", "2")) if page_limit is None else int(page_limit)
        gap = float(os.getenv("KERJO_REQUEST_GAP_SECONDS", "0.4")) if gap_seconds is None else float(gap_seconds)
    except (ValueError, TypeError):
        maximum, gap = 2, 0.4
    maximum = min(5, max(1, maximum))
    gap = min(3.0, max(0.0, gap))
    jobs, identifiers = [], set()
    pages, retries, last_status = 0, 0, None

    def finish(success, error=None, status=None):
        return SourceResult(
            source=source, success=success, jobs=jobs, error_message=error,
            pages_fetched=pages, retry_count=retries, http_status=status,
            elapsed_ms=max(0, int((time.monotonic()-started)*1000)),
        )

    for page in range(1, maximum+1):
        if page > 1 and gap:
            sleep(gap)
        result = None
        for attempt in range(3):
            try:
                result = fetch_page(page)
            except Exception as exc:
                result = SourceResult(source=source, success=False, jobs=[], error_message=str(exc))
            if result.success or attempt == 2 or not is_transient(result):
                break
            retries += 1
            # Honor provider guidance but cap waits; never hot-loop a 429.
            base = 0.75 * (2**attempt) + jitter(0.0, 0.35)
            delay = max(base, result.retry_after_seconds or 0.0)
            sleep(min(20.0, delay))
        pages += 1
        last_status = result.http_status
        if not result.success:
            reason = result.error_message or "Provider request failed"
            return finish(bool(jobs), "Partial page collection: " + reason if jobs else reason,
                          result.http_status)
        raw_count = result.raw_count
        page_jobs = result.jobs
        before = len(identifiers)
        for job in page_jobs:
            identity = (job.source, job.external_id)
            if identity not in identifiers:
                identifiers.add(identity)
                jobs.append(job)
        if result.has_more is False:
            break
        if raw_count == 0:
            break
        if page > 1 and page_jobs and len(identifiers) == before:
            # A provider can return page 1 repeatedly while ignoring the offset.
            break
        # Empty parsed jobs can mean location filtering, not an empty source page.
    return finish(True, status=last_status)
