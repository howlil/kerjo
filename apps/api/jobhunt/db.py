import sqlite3
import datetime
import json
from typing import Optional, List, Dict, Any, Tuple
from jobhunt.models import Job
from jobhunt.classifier import classify_job

class Database:
    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    area TEXT NOT NULL DEFAULT 'all',
                    sources TEXT NOT NULL DEFAULT 'jobstreet,kalibrr,linkedin,glints,dealls,karir,techinasia',
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
            ]
            for col_name, col_def in migrations:
                if col_name not in existing_cols:
                    try:
                        conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_def}")
                    except sqlite3.OperationalError:
                        pass

            # Create indexes on migrated columns safely
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_exp_level ON jobs(experience_level);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_role_cat ON jobs(role_category);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);")

    # ---------------- Search Queries ----------------
    def create_search(self, keyword: str, area: str = "all", sources: Optional[List[str]] = None) -> int:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        src_str = ",".join(sources) if sources else "jobstreet,kalibrr,linkedin,glints,dealls"
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
                for kw, area in default_searches:
                    self.create_search(keyword=kw, area=area)

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
                    "SELECT id, is_new FROM jobs WHERE source = ? AND external_id = ?",
                    (job.source, job.external_id),
                ).fetchone()

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
                            company_logo, is_new, first_seen_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
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
                            now,
                            now,
                        ),
                    )

        return new_count, len(jobs)

    def mark_job_seen(self, job_id: int):
        with self._get_connection() as conn:
            conn.execute("UPDATE jobs SET is_new = 0 WHERE id = ?", (job_id,))

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
        limit: int = 100,
        offset: int = 0,
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
                sql += " AND (experience_level = 'entry' OR (min_years IS NOT NULL AND min_years <= 1))"
            elif experience_level == "mid":
                sql += " AND (experience_level = 'mid' OR (min_years IS NOT NULL AND min_years >= 1 AND min_years <= 3))"
            elif experience_level == "senior":
                sql += " AND (experience_level = 'senior' OR (min_years IS NOT NULL AND min_years >= 3))"
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

        sql += " ORDER BY is_new DESC, COALESCE(posted_at, first_seen_at) DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_companies(self, limit: int = 150) -> List[Dict[str, Any]]:
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
    ):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO job_runs (search_id, source, status, jobs_found, jobs_new, error_message, ran_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (search_id, source, status, jobs_found, jobs_new, error_message, now),
            )

    def get_latest_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM job_runs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
