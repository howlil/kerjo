# Kerjo: Job Ingestion V2 — research and implementation

## Design thinking: problem, evidence, and tradeoffs

Recruiting search cards contain snippets rather than complete job descriptions. LinkedIn
formal Jobs and recruiter feed posts are distinct. User needs verifiable links,
publication dates no older than 14 days, and low false-positive rates.

Flow: discover -> enrich -> validate publication -> classify -> deduplicate -> persist.

- Prefer public structured APIs (Ashby, Lever, Greenhouse) over brittle DOM.
- Use JSON-LD JobPosting or targeted job-description HTML for other portals.
- Store description_status = complete / partial / missing and description_source.
- Preserve previously complete descriptions when new results contain only snippets.
- Treat a careers URL as a candidate, not proof a requisition is still open.
- Reject undated posts and CTA-only posts asking for "comment interested".
- Never bypass authentication, CAPTCHA, rate limits or LinkedIn's API permissions.
- Keep all runs manual with configured per-source request budgets.

## Source strategy

| Source | Existing discovery | Enrichment | Publish date |
|---|---|---|---|
| JobStreet | API | public HTML/JSON-LD detail | listingDate |
| Kalibrr | API | public HTML/JSON-LD detail | activation_date / published_at |
| Glints | embedded JSON | public HTML/JSON-LD detail | publishedAt |
| Dealls | API | public HTML/JSON-LD detail | publishedAt |
| Karir.com | API | public HTML/JSON-LD detail | posted_at |
| Tech in Asia | API | public HTML/JSON-LD detail | published_at |
| Greenhouse | public board API, content=true | full HTML body | published if available, else detail datePosted |
| Lever | public postings API | descriptionPlain + lists + additionalPlain | published if available; never updatedAt |
| Ashby | public posting API | descriptionPlain/Html | publishedAt |
| LinkedIn Jobs | original guest adapter retired | not scraped | n/a |
| LinkedIn Posts | manual import or approved Posts API | ATS detail if available | supplied or authorized API publishedAt |

Official references:
- https://docs.greenhouse.io/job-board.html
- https://github.com/lever/postings-api
- https://developers.ashbyhq.com/docs/public-job-posting-api
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
- https://www.linkedin.com/help/linkedin/answer/a1341387/prohibition-of-scraping-software

## Configure and run

Python 3.12+; no new pip dependencies. Example on PowerShell:

~~~powershell
$env:KERJO_ATS_BOARDS = "ashby:company,greenhouse:company,lever:company"
$env:KERJO_ENRICH_LIMIT = "12"
$env:PYTHONPATH = "apps/api"
python -m jobhunt serve
~~~

Enable source 'ats' in a saved search. ATS board slugs refer to real public company
boards; this is not a global ATS search. Only the designated company boards are
queried. The detail fetcher allows HTTPS to known job board hosts only, limits
redirects by host, 2 MB response size, and 9s timeout. Default enrichment cap is
12 detailed pages per provider/search (maximum 30); cache spans searches in
one manual run. Set limit 0 to disable. Increase it only after measuring failures.

## LinkedIn recruiter posts

The UI action 'Impor post HR' accepts post URL, text, employer, location, date,
optional role and apply URL. Local endpoint: POST /api/linkedin-posts; accept
one post object or an object with posts array (maximum 20). Only posts with a
recognizable software engineering role, employer, 14-day date and real-looking
HTTPS jobs/careers link are accepted. DM-only and comment-only CTAs are rejected.
Links to social sites, forms, opaque shorteners, homepages and arbitrary URLs
without a job path are rejected. Valid syntax is not a guarantee of a live job.

For the approved official Posts API, set:

~~~powershell
$env:KERJO_LINKEDIN_ACCESS_TOKEN = "<authorized token>"
$env:KERJO_LINKEDIN_AUTHORS = "urn:li:organization:12345|Company Name"
$env:KERJO_LINKEDIN_VERSION = "202609"
~~~

Enable source 'linkedin_posts'. Only explicitly configured authors for whom
the app has r_organization_social or approved r_member_social permission can be
read. No generic recruiter search or all-feed capture is possible with this
interface. No guest scraping, login cookie reuse or proxy/captcha bypass.
Do not commit secrets; keep token only in environment. Unconfigured mode is not
proof that no recruiter posts exist.

## Precision, security and verification

Publication timestamp remains authoritative: updatedAt, firstSeen and lastSeen
are not substituted for missing posted_at. Unknown, future, and older records
are excluded from Discover without deleting tracked applications.
The complete status reports an extracted targeted section; short or unstructured
content remains partial or missing.

Tests cover HTML/JSON-LD, ATS fields, URL allowlisting, fake CTA posts,
old/undated posts, dedup precedence and persistence. CI tests parsers and
Svelte build, not live provider availability. After deployment, manually
spot-check representative results, link reachability and completeness per
source before increasing collection budgets.