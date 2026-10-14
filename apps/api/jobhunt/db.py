import sqlite3
from contextlib import contextmanager
import datetime
import json
import os
from typing import Optional, List, Dict, Any, Tuple
from jobhunt.models import Job
from jobhunt.classifier import classify_job
from jobhunt.freshness import recent_posting, parse_posted_at

class Database:
    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Commit/rollback and ALWAYS close; 'with sqlite3.connect' alone does not close.

        This is important on Windows where an open SQLite file cannot be
        removed during test cleanup or application reset.
        """
        conn = sqlite3.connect(self.db_path, timeout=5)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    area TEXT NOT NULL DEFAULT 'all',
                    sources TEXT NOT NULL DEFAULT 'jobstreet,kalibrr,glints,dealls,karir,techinasia',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location_raw TEXT,
                    area TEXT NOT NULL,
                    url TEXT NOT NULL,
                    salary TEXT,
                    work_type TEXT,
                    is_remote INTEGER NOT NULL DEFAULT 0,
                    posted_at TEXT,
                    description TEXT,
                    experience_level TEXT DEFAULT 'unspecified',
                    min_years REAL,
                    max_years REAL,
                    experience_raw TEXT,
                    role_category TEXT DEFAULT 'other',
                    company_logo TEXT,
                    is_new INTEGER NOT NULL DEFAULT 1,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    UNIQUE(source, external_id)
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_source_ext ON jobs(source, external_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_area ON jobs(area);
                CREATE INDEX IF NOT EXISTS idx_jobs_is_new ON jobs(is_new);
                CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at);
                CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);

                CREATE TABLE IF NOT EXISTS job_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_id INTEGER,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
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
                    error_message TEXT,
                    ran_at TEXT NOT NULL,
                    FOREIGN KEY(search_id) REFERENCES searches(id) ON DELETE SET NULL
                );
            """)

            # Safe migration for existing databases
            existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            migrations = [
                ("description", "TEXT"),
                ("experience_level", "TEXT DEFAULT 'unspecified'"),
                ("min_years", "REAL"),
                ("max_years", "REAL"),
                ("experience_raw", "TEXT"),
                ("role_category", "TEXT DEFAULT 'other'"),
                ("company_logo", "TEXT"),
                ("work_mode", "TEXT DEFAULT 'unknown'"),
                ("description_status", "TEXT NOT NULL DEFAULT 'missing'"),
                ("description_source", "TEXT"),
                ("application_url", "TEXT"),
                ("application_evidence", "TEXT"),
                ("origin_url", "TEXT"),
            ]
            for col_name, col_def in migrations:
                if col_name not in existing_cols:
                    try:
                        conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_def}")
                    except sqlite3.OperationalError:
                        pass

            # Historical databases must retain their existing job/application data.
            run_cols = {row["name"] for row in conn.execute("PRAGMA table_info(job_runs)")}
            for name in ("jobs_recent", "filtered_old", "filtered_unknown", "filtered_future",
                         "pages_fetched", "retry_count", "details_enriched", "duration_ms"):
                if name not in run_cols:
                    conn.execute(f"ALTER TABLE job_runs ADD COLUMN {name} INTEGER NOT NULL DEFAULT 0")

            # Create indexes on migrated columns safely
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_exp_level ON jobs(experience_level);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_role_cat ON jobs(role_category);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);")

    # ---------------- Search Queries ----------------
    def create_search(self, keyword: str, area: str = "all", sources: Optional[List[str]] = None) -> int:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        src_str = ",".join(sources) if sources else "jobstreet,kalibrr,glints,dealls"
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO searches (keyword, area, sources, is_active, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
                (keyword.strip(), area.strip(), src_str, now, now),
            )
            return cursor.lastrowid

    def get_searches(self, active_only: bool = False) -> List[Dict[str, Any]]:
        query = "SELECT * FROM searches"
        params: List[Any] = []
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY id ASC"
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def set_search_active(self, search_id: int, active: bool):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE searches SET is_active = ?, updated_at = ? WHERE id = ?",
                (1 if active else 0, now, search_id),
            )

    def delete_search(self, search_id: int):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM searches WHERE id = ?", (search_id,))

    def reset_database(self):
        """
        Completely resets jobs and job_runs tables to clean slate.
        """
        with self._get_connection() as conn:
            conn.execute("DELETE FROM jobs")
            conn.execute("DELETE FROM job_runs")
            try:
                conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('jobs', 'job_runs')")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def seed_default_searches(self):
        """
        Seeds default technical searches if searches table is empty.
        """
        default_searches = [
            ("Backend Engineer", "all"),
            ("Frontend Engineer", "all"),
            ("Fullstack Developer", "all"),
            ("Mobile Developer", "all"),
            ("DevOps Engineer", "all"),
            ("Data Engineer", "all"),
            ("QA Engineer", "all"),
            ("Product Engineer", "all"),
        ]
        with self._get_connection() as conn:
            existing = conn.execute("SELECT count(*) FROM searches").fetchone()[0]
            if existing == 0:
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                conn.executemany(
                    "INSERT INTO searches(keyword, area, sources, is_active, created_at, updated_at) VALUES(?, ?, ?, 1, ?, ?)",
                    [(kw, area, "jobstreet,kalibrr,glints,dealls", now, now)
                     for kw, area in default_searches]
                )

    # ---------------- Job Queries & Upsert ----------------
    def upsert_jobs(self, jobs: List[Job]) -> Tuple[int, int]:
        """
        Inserts new jobs with is_new = 1.
        Strictly rejects any non-technical / excluded roles.
        If job already exists (source, external_id match):
        - updates last_seen_at
        - keeps previous is_new state
        Returns (new_jobs_count, total_jobs_processed)
        """
        if not jobs:
            return 0, 0

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        new_count = 0

        with self._get_connection() as conn:
            for job in jobs:
                # Classify role & experience
                cl = classify_job(job.title, job.description)
                
                # Strict firewall: Discard non-technical or excluded roles!
                if not cl["is_technical"] or cl["role_category"] in ("other", None):
                    continue

                job.experience_level = cl["experience_level"]
                job.min_years = cl["min_years"]
                job.max_years = cl["max_years"]
                job.experience_raw = cl["experience_raw"]
                job.role_category = cl["role_category"]

                # Check if exists
                existing = conn.execute(
                    "SELECT id, is_new, description_status FROM jobs WHERE source = ? AND external_id = ?",
                    (job.source, job.external_id),
                ).fetchone()

                preserve_complete = bool(
                    existing and existing["description_status"] == "complete"
                    and job.description_status != "complete"
                )
                if preserve_complete:
                    # The search-card snippet may still improve other metadata,
                    # but must not replace a verified full description.
                    job.description = None

                if existing:
                    # Update metadata & last_seen
                    conn.execute(
                        """
                        UPDATE jobs SET
                            title = ?,
                            company = ?,
                            location_raw = ?,
                            area = ?,
                            url = ?,
                            salary = COALESCE(?, salary),
                            work_type = COALESCE(?, work_type),
                            is_remote = ?,
                            work_mode = ?,
                            posted_at = COALESCE(?, posted_at),
                            description = COALESCE(?, description),
                            experience_level = COALESCE(?, experience_level),
                            min_years = COALESCE(?, min_years),
                            max_years = COALESCE(?, max_years),
                            experience_raw = COALESCE(?, experience_raw),
                            role_category = COALESCE(?, role_category),
                            company_logo = COALESCE(?, company_logo),
                            last_seen_at = ?
                        WHERE id = ?
                        """,
                        (
                            job.title,
                            job.company,
                            job.location_raw,
                            job.area,
                            job.url,
                            job.salary,
                            job.work_type,
                            1 if job.is_remote else 0,
                            job.work_mode or ("remote" if job.is_remote else "unknown"),
                            job.posted_at,
                            job.description,
                            job.experience_level,
                            job.min_years,
                            job.max_years,
                            job.experience_raw,
                            job.role_category,
                            job.company_logo,
                            now,
                            existing["id"],
                        ),
                    )
                else:
                    new_count += 1
                    conn.execute(
                        """
                        INSERT INTO jobs (
                            source, external_id, title, company, location_raw, area, url,
                            salary, work_type, is_remote, posted_at, description,
                            experience_level, min_years, max_years, experience_raw, role_category,
                            company_logo, work_mode, is_new, first_seen_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """,
                        (
                            job.source,
                            job.external_id,
                            job.title,
                            job.company,
                            job.location_raw,
                            job.area,
                            job.url,
                            job.salary,
                            job.work_type,
                            1 if job.is_remote else 0,
                            job.posted_at,
                            job.description,
                            job.experience_level,
                            job.min_years,
                            job.max_years,
                            job.experience_raw,
                            job.role_category,
                            job.company_logo,
                            job.work_mode or ("remote" if job.is_remote else "unknown"),
                            now,
                            now,
                        ),
                    )

                if not preserve_complete:
                    conn.execute(
                        """UPDATE jobs SET description_status = ?, description_source = ?,
                                  application_url = COALESCE(?, application_url),
                                  application_evidence = COALESCE(?, application_evidence),
                                  origin_url = COALESCE(?, origin_url)
                           WHERE source = ? AND external_id = ?""",
                        (job.description_status if job.description_status != "missing"
                         else ("partial" if job.description else "missing"),
                         job.description_source, job.application_url,
                         job.application_evidence, job.origin_url,
                         job.source, job.external_id),
                    )

        return new_count, len(jobs)

    def mark_job_seen(self, job_id: int):
        with self._get_connection() as conn:
            conn.execute("UPDATE jobs SET is_new = 0 WHERE id = ?", (job_id,))

    def mark_jobs_seen(self, job_ids: List[int]) -> int:
        ids = sorted({i for i in job_ids if type(i) is int and i > 0})
        if not ids:
            return 0
        with self._get_connection() as conn:
            q = ",".join("?" for _ in ids)
            cursor = conn.execute(f"UPDATE jobs SET is_new=0 WHERE id IN ({q})", ids)
            return cursor.rowcount

    def mark_all_seen(self):
        with self._get_connection() as conn:
            conn.execute("UPDATE jobs SET is_new = 0 WHERE is_new = 1")

    def get_jobs(
        self,
        area: Optional[str] = None,
        source: Optional[str] = None,
        is_new_only: bool = False,
        query_text: Optional[str] = None,
        experience_level: Optional[str] = None,
        role_category: Optional[str] = None,
        company: Optional[str] = None,
        limit: Optional[int] = 100,
        offset: int = 0,
        posted_within_days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM jobs WHERE 1=1"
        params: List[Any] = []

        if area and area != "all":
            sql += " AND area = ?"
            params.append(area)

        if source and source != "all":
            sql += " AND source = ?"
            params.append(source)

        if is_new_only:
            sql += " AND is_new = 1"

        if company and company != "all":
            sql += " AND (company = ? OR company LIKE ?)"
            params.extend([company.strip(), f"%{company.strip()}%"])

        if experience_level and experience_level != "all":
            if experience_level == "entry":
                sql += " AND experience_level = 'entry'"
            elif experience_level == "mid":
                sql += " AND experience_level = 'mid'"
            elif experience_level == "senior":
                sql += " AND experience_level = 'senior'"
            elif experience_level == "unspecified":
                sql += " AND (experience_level = 'unspecified' OR experience_level IS NULL)"

        if role_category and role_category != "all":
            sql += " AND role_category = ?"
            params.append(role_category)
        else:
            sql += " AND role_category != 'other'"

        if query_text:
            sql += " AND (title LIKE ? OR company LIKE ? OR location_raw LIKE ? OR description LIKE ?)"
            pat = f"%{query_text}%"
            params.extend([pat, pat, pat, pat])

        sql += " ORDER BY is_new DESC, COALESCE(posted_at, first_seen_at) DESC, id DESC"
        # Filter after loading when age gating is enabled: legacy DBs may
        # contain mixed provider date representations.
        if limit is not None and posted_within_days is None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([max(1, min(int(limit), 100000)), max(0, int(offset))])

        with self._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            jobs = [dict(r) for r in rows]
            if posted_within_days is not None:
                # Parse dates instead of relying on lexical SQL comparisons:
                # providers expose offset-aware ISO, date-only, and legacy formats.
                if posted_within_days != 14:
                    raise ValueError("Only the 14-day discovery window is supported")
                jobs = [job for job in jobs if recent_posting(job.get("posted_at"))]
                # Mixed pre-migration timestamp formats cannot be ordered by
                # lexical SQLite comparisons. Sort by actual publication time.
                jobs.sort(key=lambda job: (
                    int(bool(job.get("is_new"))),
                    parse_posted_at(job["posted_at"]).timestamp(),
                    job["id"],
                ), reverse=True)
                if limit is not None:
                    start = max(0, int(offset))
                    jobs = jobs[start:start + max(1, min(int(limit), 100000))]
            return jobs

    def get_companies(self, limit: int = 150, posted_within_days: Optional[int] = None) -> List[Dict[str, Any]]:
        if posted_within_days is not None:
            jobs = self.get_jobs(limit=None, posted_within_days=posted_within_days)
            counts: Dict[str, Dict[str, Any]] = {}
            for job in jobs:
                company = job.get("company")
                if not company or not company.strip():
                    continue
                item = counts.setdefault(company, {"company": company, "job_count": 0,
                                                   "company_logo": None})
                item["job_count"] += 1
                item["company_logo"] = item["company_logo"] or job.get("company_logo")
            return sorted(counts.values(), key=lambda row: (-row["job_count"], row["company"]))[:limit]
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT company, COUNT(*) as job_count, MAX(company_logo) as company_logo
                FROM jobs
                WHERE role_category != 'other' AND company IS NOT NULL AND TRIM(company) != ''
                GROUP BY company
                ORDER BY job_count DESC, company ASC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def record_run(
        self,
        source: str,
        status: str,
        jobs_found: int = 0,
        jobs_new: int = 0,
        error_message: Optional[str] = None,
        search_id: Optional[int] = None,
        jobs_recent: int = 0,
        filtered_old: int = 0,
        filtered_unknown: int = 0,
        filtered_future: int = 0,
        pages_fetched: int = 0,
        retry_count: int = 0,
        details_enriched: int = 0,
        duration_ms: int = 0,
    ):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO job_runs (
                    search_id, source, status, jobs_found, jobs_new, jobs_recent,
                    filtered_old, filtered_unknown, filtered_future,
                    pages_fetched, retry_count, details_enriched, duration_ms,
                    error_message, ran_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (search_id, source, status, jobs_found, jobs_new, jobs_recent,
                 filtered_old, filtered_unknown, filtered_future,
                 pages_fetched, retry_count, details_enriched, duration_ms,
                 error_message, now),
            )

    def get_latest_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM job_runs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
