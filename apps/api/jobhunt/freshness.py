"""Publication-date gate for manual job discovery.

Kerjo guarantees that discovery shows only verifiably published jobs from the
last 14 *24-hour periods*. Observation timestamps (first/last seen) and
provider update timestamps do not prove a fresh job posting.
"""
import datetime as dt
import re
from typing import Any, Optional

MAX_POST_AGE_DAYS = 14
UTC = dt.timezone.utc


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def parse_posted_at(value: Any, now: Optional[dt.datetime] = None) -> Optional[dt.datetime]:
    """Return timezone-aware UTC publication time or None if unreliable.

    Date-only values represent local midnight Asia/Jakarta (UTC+07), so a
    boundary date is not silently assumed to be as recent as end-of-day.
    Relative timestamps are estimates, supported only for exact numerical
    offsets; vague values like "recently" are rejected.
    """
    now = now or utc_now()
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, dt.date):
        parsed = dt.datetime.combine(value, dt.time.min, tzinfo=dt.timezone(dt.timedelta(hours=7)))
    elif isinstance(value, (int, float)):
        try:
            numeric = float(value)
            if not 946684800 <= numeric <= 32503680000000:
                return None
            parsed = dt.datetime.fromtimestamp(
                numeric / 1000 if numeric > 32503680000 else numeric, tz=UTC
            )
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if re.fullmatch(r"\d{10}|\d{13}", raw):
            return parse_posted_at(int(raw), now=now)
        relative = re.fullmatch(
            r"(?:posted\s+)?(\d+)\s*(minute|hour|day|week|menit|jam|hari|minggu)s?"
            r"\s*(?:ago|lalu)?",
            raw.lower(),
        )
        if relative:
            amount = int(relative.group(1))
            unit = relative.group(2)
            if unit in ("minute", "menit"):
                return (now - dt.timedelta(minutes=amount)).astimezone(UTC)
            if unit in ("hour", "jam"):
                return (now - dt.timedelta(hours=amount)).astimezone(UTC)
            if unit in ("day", "hari"):
                return (now - dt.timedelta(days=amount)).astimezone(UTC)
            if unit in ("week", "minggu"):
                return (now - dt.timedelta(weeks=amount)).astimezone(UTC)
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                parsed = dt.datetime.combine(
                    dt.date.fromisoformat(raw),
                    dt.time.min,
                    tzinfo=dt.timezone(dt.timedelta(hours=7)),
                )
            else:
                parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%b %d, %Y", "%d %b %Y"):
                try:
                    parsed = dt.datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    pass
            if parsed is None:
                return None
    else:
        return None
    if parsed.tzinfo is None:
        # Provider timestamps without offsets are interpreted as Jakarta time.
        parsed = parsed.replace(tzinfo=dt.timezone(dt.timedelta(hours=7)))
    return parsed.astimezone(UTC)


def posting_age_status(
    posted_at: Any, now: Optional[dt.datetime] = None, max_days: int = MAX_POST_AGE_DAYS
) -> str:
    """One of recent, old, unknown, future; excludes unknown/future by default."""
    now = now or utc_now()
    timestamp = parse_posted_at(posted_at, now=now)
    if timestamp is None:
        return "unknown"
    age = now.astimezone(UTC) - timestamp
    if age.total_seconds() < -300:  # >5 minutes ahead is not a past publication.
        return "future"
    if age > dt.timedelta(days=max_days):
        return "old"
    return "recent"


def recent_posting(posted_at: Any, now: Optional[dt.datetime] = None) -> bool:
    return posting_age_status(posted_at, now=now) == "recent"
