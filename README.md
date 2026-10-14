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

The collector uses bounded pagination (default 2 pages, hard cap 5),
separate provider workers (default 3, hard cap 4), and one active fetch per
provider. SQLite inserts and run logs are committed on the coordinator thread.
Identical provider/keyword requests are network-shared across saved searches.

Transient 429/5xx/timeouts use up to three attempts with bounded exponential
backoff, small jitter, and `Retry-After` when provided. HTTP 401/403, CAPTCHA,
and blocked pages are not bypassed. Repeated pages, an explicit `has_more=false`,
or raw unfiltered page count zero terminate collection early; location-filtered
empty pages do not.

For eligible or undated results, optional detail enrichment reads public
`JobPosting` JSON-LD from allowlisted source HTTPS hosts only. It never follows
redirects, sends credentials, or treats `dateModified` as `datePosted`.
When no trustworthy date is available, the strict rolling 14-day gate still
excludes the listing. It is an explicit best-effort step, not proof that all
sources expose dates. Source health includes page/retry/enrichment/duration
counts, including partial errors.

| Environment variable | Default | Bounds | Meaning |
|---|---:|---:|---|
| `KERJO_MAX_PAGES` | 2 | 1–5 | Page budget per provider / keyword |
| `KERJO_MAX_WORKERS` | 3 | 1–4 | Parallel provider workers; never parallel on one provider |
| `KERJO_REQUEST_GAP_SECONDS` | 0.4 | 0–3 | Inter-page polite delay |
| `KERJO_DETAIL_ENRICH_LIMIT` | 3 | 0–10 | Detail-page requests per provider / keyword; 0 disables |
| `KERJO_RUN_DETAIL_BUDGET` | 8 | 0–16 | Maximum total detail-page requests per provider per manual run |

The LinkedIn adapter additionally asks for a 14-day server-side filter.
Local publication-date checking is authoritative. The window rolls forward
over time, including for previously collected local rows.

See [Scraper V3 execution design](docs/SCRAPER_DESIGN.md) for shapes,
concurrency, failure policies, security boundaries, and verification.

`POST /api/run` starts a manual run; `GET /api/run/{id}` reports
`queued`, `running`, `completed`, `partial`, `failed`, or `skipped`.


## Full descriptions and recruiter-post ingestion

On each manual run, Kerjo can enrich job cards with public JobPosting JSON-LD
or targeted description HTML. Description confidence and provenance are
persisted. Public Greenhouse, Lever and Ashby company boards are opt-in via
KERJO_ATS_BOARDS, and the per-source detail request budget is bounded.

LinkedIn guest scraping is retired. Use **Impor post HR** in Discover for
dated recruiter posts containing a real-looking direct careers/apply link,
or configure authorized LinkedIn Posts API access for approved authors.
A link is **not** proof that the vacancy is still accepting applicants.

See [Job Ingestion V2](docs/job-ingestion-v2.md) for supported sources,
environment variables, limitations, and verification protocol.

## Main API routes

| Route | Methods | Purpose |
|---|---|---|
| /api/jobs | GET | Filter jobs; sort=recent or match; saved=1; offset and limit; returns accurate total after dedup |
| /api/searches | GET, POST | Saved search rules |
| /api/searches/{id}/toggle | PUT | Toggle active search |
| /api/searches/{id} | DELETE | Delete saved search |
| /api/run | POST | Enqueue manual scrape worker |
| /api/linkedin-posts | POST | Import 1–20 dated recruiter posts with application-link evidence |
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
