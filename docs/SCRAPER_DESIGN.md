# Kerjo Scraper V3 — Implementation Graph

## Requirement

Manual-only job discovery. Never schedule provider requests. Include only postings whose verified publication timestamp is within the past 14 × 24 hours. Saved jobs and historical applications remain in SQLite.

## Shapes

- SourceResult: jobs, success, error_message, raw_count, has_more, http_status, retry_after_seconds, pages_fetched, retry_count, enriched_count, elapsed_ms.
- Job: provider-specific (source, external_id), posted_at from explicit publication / activation metadata; never from record updated_at or first_seen_at.
- Job runs and batches: durable metrics for pages, retries, enriched details, duration, old/unknown/future exclusions.

## Success flow

Manual button / CLI
→ process-wide RunnerLock and API run gate
→ normalized saved-search tasks
→ ThreadPoolExecutor with maximum three provider workers by default, maximum four configurable
→ per-provider lock serializes each source's requests
→ bounded page collection, retries, HTTP rate policy
→ selective JobPosting JSON-LD date/description extraction from allowlisted detail pages
→ coordinator thread applies area and publication cutoff
→ coordinator thread upserts SQLite and writes source/run metadata
→ UI polls status and renders source health + 14-day Discover.

Identical provider/keyword requests share one network fetch, then each saved search evaluates its own area.

## Cardinality / ordering / concurrency

At most one active manual batch; at most one active collection per provider; max four sources in parallel. SQLite writes never run on provider workers. Progress increases after each persisted result. Returned results preserve original task order. Paged collection stops on genuine raw_count=0, explicit has_more=false, a repeated page, or max five pages. Parsed-empty pages may still have raw listings filtered by location and must not force early termination.

## Failure / recovery

429/500/502/503/504 and timeouts retry up to two times with bounded exponential backoff, jitter and Retry-After. 401/403/CAPTCHA are not retried or bypassed. Cooldown prevents repeated calls to blocked providers during the same batch. A partial page failure remains partial and carries an error. Missing/old/future posted_at stays excluded; optional detail enrichment may recover publication date only from explicit JobPosting.datePosted. A crashed worker leaves no re-scheduled scraping, and kernel releases process lock.

## Trust boundaries and resource scope

Public HTTPS detail host must match the source's exact allowlist. No userinfo, custom ports, redirects, or unrestricted arbitrary URLs. Maximum response 300 KiB, timeout six seconds, max ten details per search (default three). No credential/session automation, proxy rotation, captcha evasion, external cloud queue, Scrapy rewrite, or recurring schedule. Respect provider access/rate limitations.

## Invariants / verification

1. Two distinct providers run concurrently; the same provider never overlaps.
2. Every DB write and progress callback runs on the coordinating thread.
3. Old/unknown/future publication does not enter Discover or appear newly eligible.
4. Every partial rate-limited run reports an error; HTTP 403 never retries.
5. Empty filtered page is not evidence of empty raw provider page.
6. Repeated result pages stop before exhausting the page cap.
7. JobPosting title must match the intended vacancy; dateModified is never datePosted.
8. Untrusted detail URLs cannot fetch private/internal targets or follow redirects.
9. Existing saved/application rows survive additive SQLite migrations.
10. Offline parser/contract, concurrency, Windows/Linux backend and Svelte production build tests must pass on merged SHA.

## Intentional limitations

No live provider availability is implied by fixture tests. Detail enrichment is best effort: authenticated, JavaScript-only, and CAPTCHA-protected pages may have unavailable dates/descriptions. The hard per-provider concurrency ceiling plus delay is a conservative alternative to Scrapy's full latency-feedback AutoThrottle.
