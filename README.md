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

## Manual collection: last 14 days

**Kerjo never schedules scraping.** Click **Scrape sekarang** in the dashboard, or run:

~~~powershell
task scrape
# or directly:
$env:PYTHONPATH = "apps/api"
python -m jobhunt run
~~~

A manual API/UI request starts a background **worker for that request only**, so the
dashboard remains responsive. No timer, cron job, or Windows Task Scheduler is
registered by Kerjo.

**Important for existing installations:** An old Windows Task Scheduler task may
still be installed even after pulling this revision. Remove it manually, once:

~~~powershell
schtasks.exe /Delete /TN KerjoHourlyScraper /F
~~~

The saved search **active** switch determines which queries are included when
you click Scrape; it does **not** schedule or trigger a scrape automatically.

**Strict freshness contract:** Only job postings with verifiable `posted_at`
within the previous **14 × 24 hours** are collected into the new discovery batch
and shown in Discover. Source first-seen and last-seen timestamps, or record
`updated_at`, are not substitutes for a publication date. Undated, future-dated,
and older postings are excluded from Discover. Old local records and tracked
applications remain in SQLite; this update does **not** erase them.

The per-run and per-source reports include `jobs_recent`, `filtered_old`,
`filtered_unknown`, and `filtered_future` alongside scraper errors. A zero-job
result with filtered unknown dates is not proof that no suitable positions exist.
A source that omits publication timestamps may therefore yield zero eligible jobs.

The default pagination budget is 2 pages per provider/keyword, adjustable with
`KERJO_MAX_PAGES` (hard cap: 5). The LinkedIn source additionally requests
a two-week date filter; the local date gate is authoritative when a remote site
ignores filters. The two-week cutoff rolls forward over time and is applied to
existing local records at query time as well.

`POST /api/run` starts a manual run; `GET /api/run/{id}` reports
`queued`, `running`, `completed`, `partial`, `failed`, or `skipped`.


## Job-description enrichment and recruiter posts

Kerjo enriches public job cards with full descriptions from embedded JobPosting
JSON-LD or targeted HTML sections, with missing/partial/complete indicators.
Official public company ATS boards (Greenhouse, Lever, Ashby) are supported
when KERJO_ATS_BOARDS lists their real company slugs. The default enrichment
budget is KERJO_ENRICH_LIMIT=12 detail pages per source/search. Collection
remains manual.

LinkedIn guest scraping is retired. Recruiter posts can be imported manually
from the Discover toolbar (must have a dated post, company, software role and
direct careers/application link). Authorized LinkedIn Posts API access is
optional, restricted to permitted authors. It cannot fetch every HR post.

See [Job ingestion V2 design and setup](docs/job-ingestion-v2.md) for
configuration, API examples, limitations, and security constraints.

## Main API routes

| Route | Methods | Purpose |
|---|---|---|
| /api/jobs | GET | Filter jobs; sort=recent or match; saved=1; offset and limit; returns accurate total after dedup |
| /api/searches | GET, POST | Saved search rules |
| /api/searches/{id}/toggle | PUT | Toggle active search |
| /api/searches/{id} | DELETE | Delete saved search |
| /api/run | POST | Enqueue manual scrape worker |
| /api/linkedin-posts | POST | Import 1–20 recruiter posts with verifiable direct application links |
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

Last observed does not verify that a vacancy remains open. Only published-within-14-days records are visible in Discover; existing application records are preserved.

## Tests

GitHub Actions compiles Svelte and runs all Python unit/HTTP integration tests. Fixtures are version-controlled under apps/api/tests/fixtures. Provider availability is external and is not implied by parser fixture success.

## Limitations

This is a single-user local application without built-in multi-account auth, cloud synchronization, direct application submission, or verified closing statuses. Cross-provider dedup is conservative and may leave similar listings separate to avoid erroneous merges.
