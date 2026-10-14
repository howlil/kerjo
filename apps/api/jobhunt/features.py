"""Single-user discovery preferences, durable run metadata, and application pipeline.

Kept separate from ingestion persistence: no external services required.
"""
import datetime as dt
import json
import sqlite3
from typing import Optional
from jobhunt.dedup import verified_vacancy_key, group_dedup_jobs
from jobhunt.freshness import recent_posting, parse_posted_at

CATEGORIES = {"backend", "frontend", "fullstack", "mobile", "data",
              "infra_network", "qa", "product_engineer", "software_engineer"}
AREAS = {"jakarta_selatan", "jakarta_barat", "jakarta_pusat",
         "tangerang_selatan", "bsd", "alam_sutera", "unspecified"}
WORK_MODES = {"onsite", "hybrid", "remote"}
APPLICATION_TRANSITIONS = {
    "not_applied": {"applied"},
    "applied": {"screening", "interview", "offer", "rejected", "withdrawn"},
    "screening": {"interview", "offer", "rejected", "withdrawn"},
    "interview": {"offer", "rejected", "withdrawn"},
    "offer": {"withdrawn"},
    "rejected": {"applied"},
    "withdrawn": {"applied"},
}
VALID_STATUSES = set(APPLICATION_TRANSITIONS)
DEFAULT_PREFERENCES = {"role_categories": [], "areas": [], "work_modes": [],
                       "keywords": [], "max_required_years": None}


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def rank_job(job, preferences, now=None):
    """Transparent, deterministic scoring. Missing requirements remain uncertain."""
    now = now or dt.datetime.now(dt.timezone.utc)
    score, reasons, blockers, unknown = 0, [], [], []
    roles = preferences["role_categories"]
    areas = preferences["areas"]
    modes = preferences["work_modes"]
    keywords = preferences["keywords"]
    max_years = preferences["max_required_years"]
    if not any((roles, areas, modes, keywords)) and max_years is None:
        unknown.append("Preferensi belum diatur")
    if roles:
        if job.get("role_category") in roles:
            score += 45
            reasons.append("Target role")
        else:
            blockers.append("Role di luar target")
    if areas:
        area = job.get("area")
        if area in areas:
            if area == "unspecified":
                unknown.append("Lokasi belum terverifikasi")
            else:
                score += 20
                reasons.append("Lokasi sesuai")
        elif area == "unspecified":
            unknown.append("Lokasi belum terverifikasi")
        else:
            blockers.append("Lokasi di luar preferensi")
    if modes:
        mode = job.get("work_mode") or "unknown"
        if mode in modes:
            score += 15
            reasons.append("Work arrangement sesuai")
        elif mode == "unknown":
            unknown.append("Work arrangement tidak disebutkan")
        else:
            blockers.append("Work arrangement tidak sesuai")
    if max_years is not None:
        years = job.get("min_years")
        if years is None:
            unknown.append("Syarat pengalaman tidak jelas")
        elif years <= max_years:
            score += 15
            reasons.append("Pengalaman memenuhi batas")
        else:
            blockers.append("Membutuhkan pengalaman lebih tinggi")
    if keywords:
        text = (str(job.get("title") or "") + " " + str(job.get("description") or "")).lower()
        hits = [kw for kw in keywords if kw.lower() in text]
        if hits:
            score += min(15, len(hits) * 5)
            reasons.append("Skill/keyword: " + ", ".join(hits[:3]))
    last_seen = job.get("last_seen_at")
    if last_seen:
        try:
            timestamp = dt.datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
            age = (now - timestamp).total_seconds() / 86400
            if age < 2:
                score += 5
                reasons.append("Baru terindeks")
            if age > 14:
                unknown.append("Data sudah lama tidak ditemukan")
        except (TypeError, ValueError):
            unknown.append("Waktu observasi tidak valid")
    status = "mismatch" if blockers else ("uncertain" if unknown else "eligible")
    return {"score": max(0, min(score, 100)), "eligibility": status,
            "reasons": reasons, "blockers": blockers, "unknowns": unknown}


class FeatureStore:
    def __init__(self, database):
        self.db = database
        with self.db._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS saved_jobs (
                    job_id INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
                    saved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS applications (
                    job_id INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    applied_at TEXT,
                    follow_up_at TEXT,
                    application_url TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    settings TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL,
                    total_tasks INTEGER NOT NULL DEFAULT 0,
                    processed_tasks INTEGER NOT NULL DEFAULT 0,
                    jobs_found INTEGER NOT NULL DEFAULT 0,
                    jobs_new INTEGER NOT NULL DEFAULT 0,
                    jobs_recent INTEGER NOT NULL DEFAULT 0,
                    filtered_old INTEGER NOT NULL DEFAULT 0,
                    filtered_unknown INTEGER NOT NULL DEFAULT 0,
                    filtered_future INTEGER NOT NULL DEFAULT 0,
                    pages_fetched INTEGER NOT NULL DEFAULT 0,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    details_enriched INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    errors INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                );
                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id INTEGER NOT NULL REFERENCES run_batches(id) ON DELETE CASCADE,
                    source TEXT NOT NULL,
                    level TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_run_events_cursor
                    ON run_events(batch_id, id);
                CREATE TABLE IF NOT EXISTS run_job_links (
                    batch_id INTEGER NOT NULL REFERENCES run_batches(id) ON DELETE CASCADE,
                    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    PRIMARY KEY(batch_id, job_id)
                );
            """)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(run_batches)")}
            for name in ("jobs_recent", "filtered_old", "filtered_unknown", "filtered_future",
                         "pages_fetched", "retry_count", "details_enriched", "duration_ms"):
                if name not in columns:
                    conn.execute(f"ALTER TABLE run_batches ADD COLUMN {name} INTEGER NOT NULL DEFAULT 0")
            conn.execute("UPDATE run_batches SET status='failed', finished_at=?, error_message='Worker interrupted by server restart' WHERE status IN ('running','queued')", (utc_now(),))

    # Run observability is durable and read-only to clients. Events are written on
    # the runner coordinator thread after each completed provider/search task.
    def add_run_event(self, batch_id, source, level, event_type, message, metrics=None):
        if level not in ("info", "success", "warning", "error"):
            raise ValueError("Invalid event level")
        with self.db._get_connection() as conn:
            conn.execute("""INSERT INTO run_events
                (batch_id,source,level,event_type,message,metrics_json,created_at)
                VALUES(?,?,?,?,?,?,?)""",
                (batch_id, str(source)[:80], level, str(event_type)[:80],
                 str(message)[:500], json.dumps(metrics or {}), utc_now()))

    def record_batch_result(self, batch_id, result):
        """Associate only persisted, accepted vacancies with their actual batch.

        This does not stage/publish jobs; existing discovery behavior is preserved.
        Jobs rejected by technical classification do not receive a link.
        """
        source = result["source"]
        status = result["status"]
        summary = {
            name: result.get(name, 0) for name in (
                "found_count", "recent_count", "new_count", "filtered_old",
                "filtered_unknown", "filtered_future", "pages_fetched",
                "retry_count", "details_enriched", "descriptions_complete",
                "descriptions_missing", "duration_ms")
        }
        summary["keyword"] = result.get("keyword", "")
        summary["status"] = status
        level = "error" if status == "error" else "warning" if status == "partial" else "success"
        message = (result.get("error") or
                   f"{result.get('keyword', '')}: {result.get('recent_count', 0)} dated candidates, "
                   f"{result.get('new_count', 0)} new, "
                   f"{sum(result.get(k, 0) for k in ('filtered_old','filtered_unknown','filtered_future'))} excluded")
        # A single transaction keeps batch preview links and progress events in sync.
        with self.db._get_connection() as conn:
            conn.execute("""INSERT INTO run_events
                (batch_id,source,level,event_type,message,metrics_json,created_at)
                VALUES(?,?,?,?,?,?,?)""",
                (batch_id, source, level, "source_task_completed",
                 str(message)[:500], json.dumps(summary), utc_now()))
            # Deduplicate provider keys and bind query parameters; never use URLs
            # or first_seen timestamps as an approximation of run membership.
            for external_id in set(result.get("job_external_ids", ())):
                conn.execute("""INSERT OR IGNORE INTO run_job_links(batch_id,job_id)
                    SELECT ?, id FROM jobs WHERE source=? AND external_id=? AND role_category!='other'""",
                    (batch_id, source, external_id))

    def get_run_events(self, batch_id, after=0, limit=100):
        with self.db._get_connection() as conn:
            rows = conn.execute("""SELECT * FROM run_events
                WHERE batch_id=? AND id>? ORDER BY id LIMIT ?""",
                (batch_id, after, limit)).fetchall()
        return [{**dict(r), "metrics": json.loads(r["metrics_json"])} for r in rows]

    def list_batches(self, limit=20):
        with self.db._get_connection() as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM run_batches ORDER BY id DESC LIMIT ?", (limit,))]

    def get_run_preview(self, batch_id, limit=60, offset=0, source=None, query_text=None):
        """Run-scoped, freshness-gated preview with total AFTER verified dedup."""
        with self.db._get_connection() as conn:
            rows = conn.execute("""SELECT j.* FROM jobs j
                JOIN run_job_links b ON b.job_id=j.id
                WHERE b.batch_id=?""", (batch_id,)).fetchall()
        jobs = [dict(row) for row in rows if recent_posting(row["posted_at"])]
        if source and source != "all":
            jobs = [job for job in jobs if job["source"] == source]
        if query_text:
            needle = query_text.casefold()
            jobs = [job for job in jobs if needle in (
                (job.get("title") or "") + " " + (job.get("company") or "") +
                " " + (job.get("description") or "")).casefold()]
        jobs = group_dedup_jobs(jobs)
        jobs.sort(key=lambda j: (
            parse_posted_at(j["posted_at"]).timestamp(), j["id"]), reverse=True)
        total = len(jobs)
        page = jobs[offset:offset + limit]
        self.annotate(page)
        return {"jobs": page, "total": total, "limit": limit, "offset": offset,
                "batch_id": batch_id, "max_post_age_days": 14}

    def get_preferences(self):
        with self.db._get_connection() as conn:
            row = conn.execute("SELECT settings FROM preferences WHERE id=1").fetchone()
        return {**DEFAULT_PREFERENCES, **(json.loads(row["settings"]) if row else {})}

    def set_preferences(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Preferences must be a JSON object")
        result = self.get_preferences()
        for field, allowed in (("role_categories", CATEGORIES),
                               ("areas", AREAS), ("work_modes", WORK_MODES)):
            if field in payload:
                values = payload[field]
                if not isinstance(values, list) or len(values) > 30 or any(type(v) is not str or v not in allowed for v in values):
                    raise ValueError("Invalid " + field)
                result[field] = list(dict.fromkeys(values))
        if "keywords" in payload:
            values = payload["keywords"]
            if not isinstance(values, list) or len(values) > 20 or any(type(v) is not str or len(v) > 80 for v in values):
                raise ValueError("Invalid keywords")
            result["keywords"] = list(dict.fromkeys(v.strip() for v in values if v.strip()))
        if "max_required_years" in payload:
            years = payload["max_required_years"]
            if years is not None and (type(years) not in (int, float) or not 0 <= years <= 50):
                raise ValueError("Invalid max_required_years")
            result["max_required_years"] = years
        with self.db._get_connection() as conn:
            conn.execute("""INSERT INTO preferences(id,settings,updated_at) VALUES (1,?,?)
                            ON CONFLICT(id) DO UPDATE SET settings=excluded.settings,updated_at=excluded.updated_at""",
                         (json.dumps(result), utc_now()))
        return result

    def annotate(self, jobs, preferences=None):
        """Add saved, application and deterministic ranking to each result."""
        if not jobs:
            return jobs
        prefs = preferences if preferences is not None else self.get_preferences()
        ids = sorted({int(i) for job in jobs for i in (job.get("ids") or [job["id"]])})
        saved = set()
        apps = {}
        # Bound parameter counts even on older SQLite builds.
        with self.db._get_connection() as conn:
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                placeholders = ",".join("?" for _ in chunk)
                saved.update(row["job_id"] for row in conn.execute(
                    "SELECT job_id FROM saved_jobs WHERE job_id IN (" + placeholders + ")", chunk))
                apps.update({row["job_id"]: dict(row) for row in conn.execute(
                    "SELECT * FROM applications WHERE job_id IN (" + placeholders + ")", chunk)})
        for job in jobs:
            group_ids = job.get("ids") or [job["id"]]
            job["is_saved"] = int(any(i in saved for i in group_ids))
            record = next((apps[i] for i in group_ids if i in apps), None)
            job["application_status"] = record["status"] if record else "not_applied"
            job["application_notes"] = record["notes"] if record else ""
            job["follow_up_at"] = record["follow_up_at"] if record else None
            job["match"] = rank_job(job, prefs)
            try:
                age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(
                    job["last_seen_at"].replace("Z","+00:00"))).total_seconds()/86400
                job["freshness"] = "recently_seen" if age <= 2 else ("stale" if age > 14 else "not_recently_verified")
            except (KeyError, TypeError, ValueError, AttributeError):
                job["freshness"] = "unknown"
        return jobs

    def set_saved(self, job_ids, saved):
        ids = sorted({v for v in job_ids if type(v) is int and v > 0})
        if not ids:
            raise ValueError("At least one job ID is required")
        with self.db._get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM jobs WHERE id IN (" +
                                 ",".join("?" for _ in ids) + ")", ids).fetchone()[0]
            if count != len(ids):
                raise LookupError("Job not found")
            for job_id in ids:
                if saved:
                    conn.execute("INSERT OR IGNORE INTO saved_jobs(job_id,saved_at) VALUES(?,?)", (job_id, utc_now()))
                else:
                    conn.execute("DELETE FROM saved_jobs WHERE job_id=?", (job_id,))
        return {"saved": bool(saved), "updated": len(ids)}

    def applications(self, status=None):
        if status and status not in VALID_STATUSES and status != "all":
            raise ValueError("Unknown application status")
        sql = """SELECT a.*, j.title, j.company, j.source, j.url, j.area, j.work_mode
                 FROM applications a JOIN jobs j ON a.job_id=j.id
                 WHERE a.status!='not_applied'"""
        params = []
        if status and status != "all":
            sql += " AND a.status=?"
            params.append(status)
        sql += " ORDER BY COALESCE(a.follow_up_at,a.updated_at) DESC"
        with self.db._get_connection() as conn:
            rows = [dict(row) for row in conn.execute(sql, params)]
        # Combine application records ONLY if a verified URL identifies the
        # same vacancy. Similar employer/title is not sufficient evidence.
        groups = {}
        for row in rows:
            key = (verified_vacancy_key(row), row["status"], row.get("applied_at"))
            if key not in groups:
                row["ids"] = [row["job_id"]]
                row["sources"] = [row["source"]]
                groups[key] = row
            else:
                groups[key]["ids"].append(row["job_id"])
                groups[key]["sources"].append(row["source"])
        return list(groups.values())

    def update_application(self, job_ids, payload):
        ids = sorted({v for v in job_ids if type(v) is int and v > 0})
        if not ids:
            raise ValueError("Job ID is required")
        status = payload.get("status")
        if status not in VALID_STATUSES:
            raise ValueError("Invalid application status")
        notes = payload.get("notes")
        if notes is not None and (type(notes) is not str or len(notes) > 5000):
            raise ValueError("Invalid notes")
        url = payload.get("application_url")
        if url is not None and (type(url) is not str or len(url) > 2000 or
                                (url and not url.startswith(("https://","http://")))):
            raise ValueError("Invalid application URL")
        for field in ("applied_at", "follow_up_at"):
            value = payload.get(field)
            if value is not None:
                if type(value) is not str or len(value) > 60:
                    raise ValueError("Invalid " + field)
                try:
                    dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError("Use ISO 8601 for " + field) from exc
        now = utc_now()
        with self.db._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = {}
            for job_id in ids:
                if not conn.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone():
                    raise LookupError("Job not found")
                old = conn.execute("SELECT * FROM applications WHERE job_id=?", (job_id,)).fetchone()
                old_status = old["status"] if old else "not_applied"
                if status != old_status and status not in APPLICATION_TRANSITIONS[old_status]:
                    raise ValueError("Invalid transition: " + old_status + " -> " + status)
                current[job_id] = old
            for job_id in ids:
                old = current[job_id]
                notes_value = notes if notes is not None else (old["notes"] if old else "")
                applied = payload.get("applied_at") or (old["applied_at"] if old else None)
                if status == "applied" and not applied:
                    applied = now
                followup = payload.get("follow_up_at") if "follow_up_at" in payload else (old["follow_up_at"] if old else None)
                link = url if "application_url" in payload else (old["application_url"] if old else None)
                conn.execute("""INSERT INTO applications(job_id,status,notes,applied_at,follow_up_at,application_url,updated_at)
                             VALUES(?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET
                             status=excluded.status,notes=excluded.notes,applied_at=excluded.applied_at,
                             follow_up_at=excluded.follow_up_at,application_url=excluded.application_url,
                             updated_at=excluded.updated_at""",
                             (job_id,status,notes_value,applied,followup,link,now))
        return {"status": status, "updated": len(ids)}

    def create_batch(self):
        with self.db._get_connection() as conn:
            return conn.execute("INSERT INTO run_batches(status,created_at) VALUES('queued',?)",
                                (utc_now(),)).lastrowid

    def update_batch(self, run_id, **kwargs):
        keys = {"status", "total_tasks", "processed_tasks", "jobs_found",
                "jobs_new", "jobs_recent", "filtered_old", "filtered_unknown",
                "filtered_future", "pages_fetched", "retry_count",
                "details_enriched", "duration_ms", "errors", "error_message",
                "started_at", "finished_at"}
        if not kwargs or set(kwargs) - keys:
            raise ValueError("Invalid batch update")
        with self.db._get_connection() as conn:
            conn.execute("UPDATE run_batches SET " + ",".join(k+"=?" for k in kwargs) + " WHERE id=?",
                         list(kwargs.values()) + [run_id])

    def get_batch(self, run_id):
        with self.db._get_connection() as conn:
            row = conn.execute("SELECT * FROM run_batches WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def latest_batch(self):
        with self.db._get_connection() as conn:
            row = conn.execute("SELECT * FROM run_batches ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def source_health(self):
        with self.db._get_connection() as conn:
            return [dict(row) for row in conn.execute("""
                SELECT r.* FROM job_runs r WHERE r.id =
                (SELECT MAX(sub.id) FROM job_runs sub WHERE sub.source=r.source)
                ORDER BY r.source
            """)]
