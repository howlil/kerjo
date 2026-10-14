# Kerjo

Local-first multi-source job discovery and application tracking: Python standard library API, SQLite, Svelte 5 and Vite.

## Architecture

Seven source adapters -> normalization and technical role classification -> SQLite (exact source/external-ID identity) -> conservative cross-provider dedup -> relevance ranking -> Svelte dashboard.

No external queue, hosted service or LLM is required. SQLite stores job discovery, saved status, application stages, preferences and worker-run history.

## Quick start

Requires Python 3.12+, Node.js 22+, npm.

From the repository root:

~~~powershell
$env:PYTHONPATH = "apps/api"
python -m unittest discover -s apps/api/tests -p "test_*.py"
cd apps/web
npm ci
npm run build
cd ../..
python -m jobhunt serve --host 127.0.0.1 --port 8000
~~~

Open http://127.0.0.1:8000. The DB directory is created automatically. For hot reload use 'task dev'; 'task serve' rebuilds the UI and starts API. Run 'task verify' to test and build.

## Collection and background runs

POST /api/run accepts optional keyword, sources and area. It returns HTTP 202 with run_id. GET /api/run/{id} reports queued, running, completed, partial or failed, including processed_tasks, total_tasks, jobs_found, jobs_new and errors.

Set KERJO_MAX_PAGES to adjust bounded pagination (default 2, cap 5). Provider errors including malformed payloads and known HTML challenge cases are visible in run/source health rather than silently treated as successful collection.

On Windows, install the hourly schedule with:

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/schedule.ps1 install
powershell -ExecutionPolicy Bypass -File scripts/schedule.ps1 status
~~~

The UI deliberately does not claim the scheduler is active. Confirm installation in Task Scheduler.

## Main API routes

| Route | Methods | Purpose |
|---|---|---|
| /api/jobs | GET | Filter jobs; sort=recent or match; saved=1; offset and limit; returns accurate total after dedup |
| /api/searches | GET, POST | Saved search rules |
| /api/searches/{id}/toggle | PUT | Toggle active search |
| /api/searches/{id} | DELETE | Delete saved search |
| /api/run | POST | Enqueue background scrape |
| /api/run/{id} | GET | Inspect run progress |
| /api/runs | GET | Per-source execution history |
| /api/source-health | GET | Last result by adapter |
| /api/preferences | GET, PUT | Role, location, work mode, keywords and experience cap |
| /api/jobs/seen-all | POST | Explicit JSON ids array; never change jobs outside those IDs |
| /api/jobs/{id}/save | POST | JSON saved and optional group ids |
| /api/jobs/{id}/application | PUT | JSON status, notes, follow_up_at, application_url, group ids |
| /api/applications | GET | Current application pipeline |

Application state: not_applied -> applied -> screening -> interview -> offer. Rejected and withdrawn can follow in-progress applications; both can reopen into applied. Invalid transitions return HTTP 400. Applications are not submitted to portals automatically.

Ranking is deterministic, with score, eligibility, reasons, blockers and unknowns. Unspecified experience or location is never assumed to meet a constraint.

## Trust and reliability

By default server binds to 127.0.0.1, refuses arbitrary cross-origin writes, validates input size, and uses verified TLS. Remote binding requires KERJO_ALLOW_REMOTE=1 and an authenticated reverse proxy. Do not publish the raw HTTP server to the Internet.

The availability label 'recently_seen' means last observed by the scraper; it does not verify an open requisition. Stale and unverified jobs remain identifiable.

## Tests

GitHub Actions compiles Svelte and runs all Python unit/HTTP integration tests. Fixtures are version-controlled under apps/api/tests/fixtures. Provider availability is external and is not implied by parser fixture success.

## Limitations

This is a single-user local application without built-in multi-account auth, cloud synchronization, direct application submission, or verified closing statuses. Cross-provider dedup is conservative and may leave similar listings separate to avoid erroneous merges.
