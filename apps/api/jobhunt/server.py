import http.server
import json
import urllib.parse
import os
import pathlib
import mimetypes
import logging
from typing import Optional
from jobhunt.db import Database
from jobhunt.runner import JobRunner, RunnerLock, LockAcquireError
from jobhunt.dedup import group_dedup_jobs

logger = logging.getLogger(__name__)

class JobhuntRequestHandler(http.server.BaseHTTPRequestHandler):
    db: Database
    dist_dir: Optional[pathlib.Path] = None

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def _send_json(self, data: dict, status: int = 200):
        self._set_headers(status, "application/json")
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/jobs":
            area = query.get("area", [None])[0]
            source = query.get("source", [None])[0]
            is_new = query.get("is_new", ["0"])[0] in ("1", "true")
            q = query.get("q", [None])[0]
            limit = int(query.get("limit", ["100"])[0])
            offset = int(query.get("offset", ["0"])[0])
            dedup_param = query.get("dedup", ["1"])[0]
            should_dedup = dedup_param not in ("0", "false")

            fetch_limit = limit * 2 if should_dedup else limit
            jobs = self.db.get_jobs(
                area=area,
                source=source,
                is_new_only=is_new,
                query_text=q,
                limit=fetch_limit,
                offset=offset,
            )
            if should_dedup:
                jobs = group_dedup_jobs(jobs)[:limit]
            self._send_json({"jobs": jobs, "total": len(jobs)})
            return

        if path == "/api/searches":
            searches = self.db.get_searches()
            self._send_json({"searches": searches})
            return

        if path == "/api/runs":
            runs = self.db.get_latest_runs(limit=30)
            self._send_json({"runs": runs})
            return

        # Serve static build from dist_dir if present
        if self.dist_dir and self.dist_dir.exists():
            rel_path = path.lstrip("/") or "index.html"
            target_file = (self.dist_dir / rel_path).resolve()
            if not str(target_file).startswith(str(self.dist_dir.resolve())):
                self.send_error(403)
                return

            if target_file.is_file():
                mime, _ = mimetypes.guess_type(str(target_file))
                self._set_headers(200, mime or "application/octet-stream")
                self.wfile.write(target_file.read_bytes())
                return
            else:
                # SPA fallback: return index.html
                index_file = self.dist_dir / "index.html"
                if index_file.is_file():
                    self._set_headers(200, "text/html")
                    self.wfile.write(index_file.read_bytes())
                    return

        # Fallback welcome page
        self._set_headers(200, "text/html")
        html_msg = b"""
        <!DOCTYPE html>
        <html>
        <head><title>Jobhunt API Server</title></head>
        <body style="font-family: sans-serif; padding: 40px; line-height: 1.6;">
            <h2>Jobhunt API Server is Running!</h2>
            <p>API endpoints:</p>
            <ul>
                <li><a href="/api/jobs">/api/jobs</a></li>
                <li><a href="/api/searches">/api/searches</a></li>
                <li><a href="/api/runs">/api/runs</a></li>
            </ul>
            <p>To run the frontend, start the Vite dev server in <code>apps/web</code> or run <code>npm run build</code>.</p>
        </body>
        </html>
        """
        self.wfile.write(html_msg)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/searches":
            data = self._read_json_body()
            keyword = data.get("keyword", "").strip()
            if not keyword:
                self._send_json({"error": "Keyword is required"}, 400)
                return
            area = data.get("area", "all")
            sources = data.get("sources")
            sid = self.db.create_search(keyword=keyword, area=area, sources=sources)
            self._send_json({"id": sid, "message": "Search created"}, 201)
            return

        if path.startswith("/api/jobs/") and path.endswith("/seen"):
            parts = path.split("/")
            try:
                job_id = int(parts[3])
                self.db.mark_job_seen(job_id)
                self._send_json({"success": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
            return

        if path == "/api/jobs/seen-all":
            self.db.mark_all_seen()
            self._send_json({"success": True})
            return

        if path == "/api/run":
            runner = JobRunner(db=self.db)
            try:
                with RunnerLock():
                    data = self._read_json_body()
                    keyword = data.get("keyword")
                    if keyword:
                        results = runner.run_single(
                            keyword=keyword,
                            area_filter=data.get("area", "all"),
                            source_names=data.get("sources"),
                        )
                    else:
                        results = runner.run_all_active()
                    self._send_json({"status": "completed", "results": results})
            except LockAcquireError:
                self._send_json({"status": "skipped", "message": "Run already in progress"}, 409)
            return

        self._send_json({"error": "Not found"}, 404)

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/searches/") and path.endswith("/toggle"):
            parts = path.split("/")
            try:
                search_id = int(parts[3])
                searches = self.db.get_searches()
                match = [s for s in searches if s["id"] == search_id]
                if not match:
                    self._send_json({"error": "Search not found"}, 404)
                    return
                new_state = not bool(match[0]["is_active"])
                self.db.set_search_active(search_id, new_state)
                self._send_json({"id": search_id, "is_active": 1 if new_state else 0})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
            return

        self._send_json({"error": "Not found"}, 404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/searches/"):
            parts = path.split("/")
            try:
                search_id = int(parts[3])
                self.db.delete_search(search_id)
                self._send_json({"success": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
            return

        self._send_json({"error": "Not found"}, 404)

def create_server(host: str = "127.0.0.1", port: int = 8000, db: Optional[Database] = None) -> http.server.HTTPServer:
    class CustomHandler(JobhuntRequestHandler):
        pass

    CustomHandler.db = db or Database()
    dist = pathlib.Path("apps/web/dist")
    if dist.exists():
        CustomHandler.dist_dir = dist

    server = http.server.HTTPServer((host, port), CustomHandler)
    return server

def run_server(host: str = "127.0.0.1", port: int = 8000):
    server = create_server(host, port)
    print(f"[*] Jobhunt server running at http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server.")
        server.shutdown()
        server.server_close()
