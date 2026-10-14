"""Local Kerjo API: asynchronous collection, trustworthy discovery, job workflow."""
import http.server
import json
import mimetypes
import os
import pathlib
import threading
import urllib.parse
import logging

from jobhunt.db import Database
from jobhunt.features import FeatureStore, utc_now
from jobhunt.runner import JobRunner, RunnerLock, LockAcquireError, DEFAULT_SOURCES
from jobhunt.dedup import group_dedup_jobs
from jobhunt.sources.linkedin_posts import make_post_job
from jobhunt.html_details import enrich_job

logger = logging.getLogger(__name__)


class JobhuntRequestHandler(http.server.BaseHTTPRequestHandler):
    db = None
    features = None
    run_gate = None
    dist_dir = None

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store" if content_type == "application/json" else "public, max-age=300")
        origin = self.headers.get("Origin", "")
        if origin and self._allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _allowed_origin(self, origin):
        parsed = urllib.parse.urlparse(origin)
        return (parsed.scheme in ("http", "https") and
                parsed.hostname in ("localhost", "127.0.0.1") and
                parsed.port in (5173, self.server.server_port))

    def _guard_write(self):
        origin = self.headers.get("Origin")
        if origin and not self._allowed_origin(origin):
            self._send_json({"error": "Cross-origin writes are forbidden"}, 403)
            return False
        return True

    def do_OPTIONS(self):
        if not self._guard_write():
            return
        self._set_headers(204)

    def _send_json(self, payload, status=200):
        self._set_headers(status)
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length") from exc
        if length < 0 or length > 65536:
            raise ValueError("JSON body exceeds 64 KiB limit")
        if not length:
            return {}
        try:
            parsed = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON body") from exc
        if not isinstance(parsed, dict):
            raise ValueError("JSON body must be an object")
        return parsed

    def _integer(self, text, name, lower=0, upper=100000):
        try:
            n = int(text)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid " + name) from exc
        if not lower <= n <= upper:
            raise ValueError("Out of range " + name)
        return n

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/api/jobs":
                limit = self._integer(query.get("limit", ["100"])[0], "limit", 1, 500)
                offset = self._integer(query.get("offset", ["0"])[0], "offset", 0, 100000)
                should_dedup = query.get("dedup", ["1"])[0] not in ("0", "false")
                raw = self.db.get_jobs(
                    area=query.get("area", [None])[0],
                    source=query.get("source", [None])[0],
                    is_new_only=query.get("is_new", ["0"])[0] in ("1", "true"),
                    query_text=query.get("q", [None])[0],
                    experience_level=query.get("experience_level", [None])[0],
                    role_category=query.get("role_category", [None])[0],
                    company=query.get("company", [None])[0],
                    limit=None,
                    posted_within_days=14,
                )
                results = group_dedup_jobs(raw) if should_dedup else raw
                saved_only = query.get("saved", ["0"])[0] in ("1", "true")
                application_filter = query.get("application_status", [None])[0]
                sort_by_match = query.get("sort", ["recent"])[0] == "match"
                # Only rank and annotate the whole dataset when needed for
                # global filtering/sorting. Recent/default mode annotates one page.
                globally = saved_only or (application_filter and application_filter != "all") or sort_by_match
                if globally:
                    self.features.annotate(results)
                    if saved_only:
                        results = [j for j in results if j["is_saved"]]
                    if application_filter and application_filter != "all":
                        results = [j for j in results if j["application_status"] == application_filter]
                    if sort_by_match:
                        results.sort(key=lambda j: (j["match"]["eligibility"] != "mismatch",
                                                     j["match"]["score"],
                                                     j.get("first_seen_at") or ""), reverse=True)
                total = len(results)
                page = results[offset:offset + limit]
                if not globally:
                    self.features.annotate(page)
                self._send_json({"jobs": page, "total": total, "limit": limit, "offset": offset, "max_post_age_days": 14})
                return
            if path == "/api/companies":
                self._send_json({"companies": self.db.get_companies(limit=200, posted_within_days=14)})
                return
            if path == "/api/searches":
                self._send_json({"searches": self.db.get_searches()})
                return
            if path == "/api/runs":
                self._send_json({"runs": self.db.get_latest_runs(limit=30)})
                return
            if path == "/api/preferences":
                self._send_json({"preferences": self.features.get_preferences()})
                return
            if path == "/api/applications":
                self._send_json({"applications": self.features.applications(query.get("status", [None])[0])})
                return
            if path == "/api/source-health":
                self._send_json({"sources": self.features.source_health()})
                return
            if path == "/api/run/latest":
                batch = self.features.latest_batch()
                self._send_json({"run": batch})
                return
            if path.startswith("/api/run/"):
                run_id = self._integer(path.split("/")[-1], "run ID", 1)
                batch = self.features.get_batch(run_id)
                self._send_json({"run": batch} if batch else {"error": "Run not found"}, 200 if batch else 404)
                return
            if path.startswith("/api/"):
                self._send_json({"error": "Not found"}, 404)
                return
            self._serve_static(path)
        except (ValueError, TypeError) as exc:
            self._send_json({"error": str(exc)}, 400)

    def _serve_static(self, path):
        if self.dist_dir and self.dist_dir.is_dir():
            root = self.dist_dir.resolve()
            target = (root / path.lstrip("/")).resolve() if path != "/" else root / "index.html"
            if not target.is_relative_to(root):
                self._send_json({"error": "Forbidden"}, 403)
                return
            if target.is_file():
                mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                self._set_headers(200, mime)
                self.wfile.write(target.read_bytes())
                return
            index = root / "index.html"
            if index.is_file():
                self._set_headers(200, "text/html; charset=utf-8")
                self.wfile.write(index.read_bytes())
                return
        self._set_headers(200, "text/html; charset=utf-8")
        self.wfile.write(b"<h1>Kerjo API</h1><p>Frontend unavailable. Build apps/web first.</p>")

    def do_POST(self):
        if not self._guard_write():
            return
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/linkedin-posts":
                data = self._read_json_body()
                posts = data.get("posts")
                if posts is None:
                    posts = [data]
                if not isinstance(posts, list) or not 1 <= len(posts) <= 20:
                    raise ValueError("Provide 1-20 recruiter posts")
                accepted, rejected = [], []
                for index, post in enumerate(posts):
                    try:
                        candidate = make_post_job(post)
                        accepted.append(enrich_job(candidate))
                    except ValueError as exc:
                        rejected.append({"index": index, "reason": str(exc)})
                if not accepted:
                    self._send_json({"error": "No qualifying recruiter post", "rejected": rejected}, 400)
                    return
                new_count, _ = self.db.upsert_jobs(accepted)
                self._send_json({
                    "accepted": len(accepted), "new": new_count, "rejected": rejected,
                    "note": "Application URL evidence does not guarantee an open vacancy",
                }, 201)
                return
            if path == "/api/searches":
                data = self._read_json_body()
                keyword = data.get("keyword", "")
                area = data.get("area", "all")
                sources = data.get("sources", list(DEFAULT_SOURCES))
                if type(keyword) is not str or not keyword.strip() or len(keyword) > 120:
                    raise ValueError("Keyword is required (maximum 120 characters)")
                if type(area) is not str or area not in {"all", "jakarta_selatan", "jakarta_barat", "jakarta_pusat", "tangerang_selatan", "bsd", "alam_sutera", "unspecified"}:
                    raise ValueError("Invalid area")
                if not isinstance(sources, list) or not sources or any(type(src) is not str or src not in DEFAULT_SOURCES for src in sources):
                    raise ValueError("At least one valid source is required")
                sid = self.db.create_search(keyword, area, list(dict.fromkeys(sources)))
                self._send_json({"id": sid, "message": "Search created"}, 201)
                return
            if path == "/api/jobs/seen-all":
                data = self._read_json_body()
                ids = data.get("ids")
                if not isinstance(ids, list) or not ids or len(ids) > 3000 or any(type(i) is not int or i <= 0 for i in ids):
                    raise ValueError("Explicit job IDs are required; global mark-seen is not supported")
                count = self.db.mark_jobs_seen(ids)
                self._send_json({"success": True, "updated": count})
                return
            if path.startswith("/api/jobs/") and path.endswith("/seen"):
                job_id = self._integer(path.split("/")[3], "job ID", 1)
                count = self.db.mark_jobs_seen([job_id])
                self._send_json({"success": True} if count else {"error": "Job not found"}, 200 if count else 404)
                return
            if path.startswith("/api/jobs/") and path.endswith("/save"):
                job_id = self._integer(path.split("/")[3], "job ID", 1)
                payload = self._read_json_body()
                saved = payload.get("saved", True)
                if type(saved) is not bool:
                    raise ValueError("saved must be boolean")
                ids = payload.get("ids", [job_id])
                if not isinstance(ids, list) or not 0 < len(ids) <= 100 or job_id not in ids:
                    raise ValueError("Invalid job IDs")
                self._send_json(self.features.set_saved(ids, saved))
                return
            if path == "/api/run":
                payload = self._read_json_body()
                keyword = payload.get("keyword")
                sources = payload.get("sources")
                area = payload.get("area", "all")
                if keyword is not None and (type(keyword) is not str or not keyword.strip() or len(keyword) > 120):
                    raise ValueError("Invalid keyword")
                if sources is not None and (not isinstance(sources, list) or not sources or any(type(s) is not str or s not in DEFAULT_SOURCES for s in sources)):
                    raise ValueError("Invalid source selection")
                if type(area) is not str or area not in ("all","jakarta_selatan","jakarta_barat","jakarta_pusat","tangerang_selatan","bsd","alam_sutera","unspecified"):
                    raise ValueError("Invalid area")
                if not self.run_gate.acquire(blocking=False):
                    self._send_json({"error": "Another run is already in progress"}, 409)
                    return
                try:
                    run_id = self.features.create_batch()
                    worker = threading.Thread(
                        target=execute_batch,
                        args=(self.db, self.features, self.run_gate, run_id, keyword, area, sources),
                        daemon=True, name="kerjo-worker-" + str(run_id))
                    worker.start()
                except Exception:
                    self.run_gate.release()
                    raise
                self._send_json({"status": "queued", "run_id": run_id}, 202)
                return
            self._send_json({"error": "Not found"}, 404)
        except LookupError as exc:
            self._send_json({"error": str(exc)}, 404)
        except (ValueError, TypeError) as exc:
            self._send_json({"error": str(exc)}, 400)

    def do_PUT(self):
        if not self._guard_write():
            return
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/preferences":
                self._send_json({"preferences": self.features.set_preferences(self._read_json_body())})
                return
            if path.startswith("/api/jobs/") and path.endswith("/application"):
                job_id = self._integer(path.split("/")[3], "job ID", 1)
                payload = self._read_json_body()
                ids = payload.pop("ids", [job_id])
                if not isinstance(ids, list) or not 0 < len(ids) <= 100 or job_id not in ids:
                    raise ValueError("Invalid job IDs")
                self._send_json(self.features.update_application(ids, payload))
                return
            if path.startswith("/api/searches/") and path.endswith("/toggle"):
                search_id = self._integer(path.split("/")[3], "search ID", 1)
                found = next((s for s in self.db.get_searches() if s["id"] == search_id), None)
                if not found:
                    self._send_json({"error": "Search not found"}, 404)
                    return
                new_active = not bool(found["is_active"])
                self.db.set_search_active(search_id, new_active)
                self._send_json({"id": search_id, "is_active": int(new_active)})
                return
            self._send_json({"error": "Not found"}, 404)
        except LookupError as exc:
            self._send_json({"error": str(exc)}, 404)
        except (ValueError, TypeError) as exc:
            self._send_json({"error": str(exc)}, 400)

    def do_DELETE(self):
        if not self._guard_write():
            return
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/searches/"):
            try:
                search_id = self._integer(path.split("/")[3], "search ID", 1)
                found = any(s["id"] == search_id for s in self.db.get_searches())
                if not found:
                    self._send_json({"error": "Search not found"}, 404)
                    return
                self.db.delete_search(search_id)
                self._send_json({"success": True})
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 400)
            return
        self._send_json({"error": "Not found"}, 404)


def execute_batch(db, features, gate, run_id, keyword=None, area="all", sources=None):
    stats = {"total_tasks": 0, "processed_tasks": 0, "jobs_found": 0, "jobs_new": 0, "errors": 0,
             "jobs_recent": 0, "filtered_old": 0, "filtered_unknown": 0, "filtered_future": 0,
             "pages_fetched": 0, "retry_count": 0, "details_enriched": 0, "duration_ms": 0}
    task_outcomes = []
    try:
        features.update_batch(run_id, status="running", started_at=utc_now())
        def progress(result, done, total):
            stats["total_tasks"] = total
            stats["processed_tasks"] = done
            if result:
                task_outcomes.append(result["status"])
                stats["jobs_found"] += result["found_count"]
                stats["jobs_new"] += result["new_count"]
                stats["jobs_recent"] += result.get("recent_count", 0)
                stats["filtered_old"] += result.get("filtered_old", 0)
                stats["filtered_unknown"] += result.get("filtered_unknown", 0)
                stats["filtered_future"] += result.get("filtered_future", 0)
                stats["pages_fetched"] += result.get("pages_fetched", 0)
                stats["retry_count"] += result.get("retry_count", 0)
                stats["details_enriched"] += result.get("details_enriched", 0)
                stats["duration_ms"] += result.get("duration_ms", 0)
                if result["status"] != "success":
                    stats["errors"] += 1
            features.update_batch(run_id, **stats)
        with RunnerLock():
            runner = JobRunner(db=db)
            if keyword:
                runner.run_single(keyword, area_filter=area, source_names=sources, on_progress=progress)
            else:
                runner.run_all_active(on_progress=progress)
        status = (
            "skipped" if stats["total_tasks"] == 0 else
            "completed" if not stats["errors"] else
            "failed" if task_outcomes and all(outcome == "error" for outcome in task_outcomes) else
            "partial"
        )
        features.update_batch(run_id, status=status, finished_at=utc_now())
    except Exception as exc:
        logger.exception("Collection run %s failed", run_id)
        features.update_batch(run_id, status="failed", error_message=str(exc)[:2000],
                              finished_at=utc_now())
    finally:
        gate.release()


def create_server(host="127.0.0.1", port=8000, db=None):
    if host not in ("127.0.0.1", "localhost", "::1") and os.getenv("KERJO_ALLOW_REMOTE") != "1":
        raise ValueError("Remote binding is disabled; set KERJO_ALLOW_REMOTE=1 only behind an authenticated reverse proxy")
    class Handler(JobhuntRequestHandler):
        pass
    Handler.db = db if db is not None else Database()
    Handler.features = FeatureStore(Handler.db)
    Handler.run_gate = threading.Lock()
    dist = pathlib.Path("apps/web/dist")
    Handler.dist_dir = dist if dist.is_dir() else None
    return http.server.ThreadingHTTPServer((host, port), Handler)


def run_server(host="127.0.0.1", port=8000):
    server = create_server(host, port)
    print("[*] Kerjo API running at http://%s:%s" % (host, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[*] Stopping Kerjo")
    finally:
        server.shutdown()
        server.server_close()
