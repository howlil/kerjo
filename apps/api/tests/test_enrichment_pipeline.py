"""Job description completeness, recruiter post validation and API regression tests."""
import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from jobhunt.db import Database
from jobhunt.dedup import group_dedup_jobs
from jobhunt.enrichment import (
    allowed_detail_url, clean_text, enrich_job, parse_job_detail, Detail,
)
from jobhunt.freshness import utc_now
from jobhunt.models import Job
from jobhunt.sources.ats import configured_boards, parse_ats_board
from jobhunt.sources.linkedin_posts import (
    application_link, make_post_job, parse_official_post, pick_apply_link,
)


DETAIL = " ".join(["Responsibilities: design backend APIs, maintain databases, " +
                   "write tests, monitor availability and investigate incidents."] * 5)
POST_URL = "https://www.linkedin.com/posts/example_backend-engineer-activity-123"
APPLY_URL = "https://jobs.ashbyhq.com/acme/123"


class TestDetailParsing(unittest.TestCase):
    def test_jsonld_jobposting_is_complete(self):
        payload = {"@context": "https://schema.org", "@type": "JobPosting",
                   "title": "Backend Engineer", "description": "<p>" + DETAIL + "</p>",
                   "datePosted": "2026-10-14"}
        result = parse_job_detail('<html><script type="application/ld+json">' +
                                  json.dumps(payload) + '</script></html>')
        self.assertEqual(result.status, "complete")
        self.assertIn("Responsibilities:", result.description)
        self.assertEqual(result.provenance, "jsonld")
        self.assertEqual(result.posted_at, "2026-10-14")

    def test_nested_html_section_excludes_footer(self):
        html = '<main><section class="job-description"><h2>Responsibilities</h2><p>' + DETAIL + '</p><br></section></main><footer>' + "noise"*500 + '</footer>'
        result = parse_job_detail(html)
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.provenance, "html-section")
        self.assertNotIn("noise", result.description)

    def test_short_snippet_not_marked_complete(self):
        result = parse_job_detail('<div class="job-description">Build APIs</div>')
        self.assertEqual(result.status, "partial")

    def test_no_whole_page_fallback(self):
        result = parse_job_detail("<main>" + "irrelevant navigation" * 100 + "</main>")
        self.assertEqual(result.status, "missing")
        self.assertFalse(result.description)

    def test_no_arbitrary_or_linkedin_detail_fetch(self):
        self.assertFalse(allowed_detail_url("http://127.0.0.1/admin"))
        self.assertFalse(allowed_detail_url("https://boards.greenhouse.io.evil.test/jobs/1"))
        self.assertFalse(allowed_detail_url("https://linkedin.com/posts/1"))
        self.assertTrue(allowed_detail_url(APPLY_URL))

    def test_missing_date_is_enriched_from_jsonld(self):
        job = Job(source="ats", external_id="1", title="Backend Engineer",
                  company="Acme", area="unspecified", location_raw="",
                  url=APPLY_URL, description="tiny card")
        def fake(url):
            return Detail(DETAIL, "complete", "jsonld", utc_now().isoformat())
        enrich_job(job, fetcher=fake)
        self.assertEqual(job.description, DETAIL)
        self.assertEqual(job.description_status, "complete")
        self.assertTrue(job.posted_at)


class TestATSPublicBoards(unittest.TestCase):
    def test_only_valid_configured_company_names(self):
        self.assertEqual(configured_boards("ashby:acme,greenhouse:team-a,lever:foo,ashby:acme,evil:x,lever:../private"),
                         [("ashby", "acme"), ("greenhouse", "team-a"), ("lever", "foo")])

    def test_ashby_published_at_description_and_apply_url(self):
        payload = {"jobs": [{"title": "Backend Engineer", "isListed": True,
                             "location": "Jakarta Selatan",
                             "descriptionPlain": DETAIL,
                             "publishedAt": utc_now().isoformat(),
                             "jobUrl": "https://jobs.ashbyhq.com/acme/123",
                             "applyUrl": APPLY_URL,
                             "workplaceType": "Hybrid"}]}
        jobs = parse_ats_board("ashby", "acme", payload)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].description_status, "complete")
        self.assertEqual(jobs[0].application_url, APPLY_URL)
        self.assertEqual(jobs[0].posted_at, payload["jobs"][0]["publishedAt"])

    def test_greenhouse_updated_at_not_used_as_date_posted(self):
        payload = {"jobs": [{"id": 25, "title": "Software Engineer",
                             "location": {"name": "Jakarta Selatan"},
                             "absolute_url": "https://boards.greenhouse.io/acme/jobs/25",
                             "updated_at": utc_now().isoformat(), "content": DETAIL}]}
        jobs = parse_ats_board("greenhouse", "acme", payload)
        self.assertIsNone(jobs[0].posted_at)
        self.assertEqual(jobs[0].description_status, "complete")


class TestRecruiterPosts(unittest.TestCase):
    def valid_payload(self):
        return {"post_url": POST_URL, "text": "Hiring a backend engineer. Apply: " + APPLY_URL,
                "company": "Acme", "location": "Jakarta Selatan",
                "posted_at": utc_now().isoformat()}

    def test_import_real_linked_post_as_candidate(self):
        job = make_post_job(self.valid_payload())
        self.assertEqual(job.source, "linkedin_posts")
        self.assertEqual(job.application_url, APPLY_URL)
        self.assertEqual(job.origin_url, POST_URL)
        self.assertEqual(job.application_evidence, "ats-link")

    def test_reject_comment_interested_without_application(self):
        data = self.valid_payload()
        data["text"] = "Hiring Backend Engineer! Comment interested and DM me."
        with self.assertRaisesRegex(ValueError, "No direct careers/application link"):
            make_post_job(data)

    def test_reject_old_undated_or_fake_application(self):
        data = self.valid_payload()
        data["posted_at"] = "2020-01-01"
        with self.assertRaises(ValueError):
            make_post_job(data)
        data = self.valid_payload()
        data["apply_url"] = "https://forms.gle/fake"
        data["text"] = "Hiring Backend Engineer; send your CV by DM"
        with self.assertRaises(ValueError):
            make_post_job(data)

    def test_social_media_link_is_not_a_direct_application(self):
        self.assertIsNone(application_link("https://www.linkedin.com/posts/p/123"))
        self.assertIsNone(application_link("https://example.com/"))
        self.assertEqual(application_link("https://acme.id/careers/backend-engineer"),
                         "https://acme.id/careers/backend-engineer")

    def test_official_api_post_requires_source_link_and_valid_date(self):
        post = {"id": "urn:li:share:12345", "lifecycleState": "PUBLISHED",
                "publishedAt": int(utc_now().timestamp() * 1000),
                "commentary": "We're hiring Backend Engineer https://jobs.ashbyhq.com/acme/123"}
        parsed = parse_official_post(post, "Acme")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.company, "Acme")
        post["commentary"] = "Backend Engineer, comment interested"
        self.assertIsNone(parse_official_post(post, "Acme"))


class TestDatabaseProvenance(unittest.TestCase):
    def test_full_description_survives_later_snippet(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(os.path.join(directory, "data.db"))
            def create(description, status):
                return Job(source="ats", external_id="same", title="Backend Engineer",
                           company="Acme", area="unspecified", location_raw="Jakarta",
                           url=APPLY_URL, posted_at=utc_now().isoformat(),
                           description=description, description_status=status,
                           description_source="jsonld" if status == "complete" else "search-result")
            db.upsert_jobs([create(DETAIL, "complete")])
            db.upsert_jobs([create("small preview", "partial")])
            job = db.get_jobs()[0]
            self.assertEqual(job["description"], DETAIL)
            self.assertEqual(job["description_status"], "complete")

    def test_dedup_retains_full_even_if_snippet_is_longer(self):
        records = [
            {"id": 1, "source": "ats", "external_id": "1", "company": "Acme",
             "title": "Backend Engineer", "area": "unspecified",
             "url": APPLY_URL, "work_mode": "unknown", "description": DETAIL,
             "description_status": "complete"},
            {"id": 2, "source": "linkedin_posts", "external_id": "2",
             "company": "Acme", "title": "Backend Engineer", "area": "unspecified",
             "url": APPLY_URL, "work_mode": "unknown", "description": "x"*2000,
             "description_status": "partial", "origin_url": POST_URL}
        ]
        merged = group_dedup_jobs(records)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["description"], DETAIL)
        self.assertEqual(merged[0]["origin_url"], POST_URL)


if __name__ == "__main__":
    unittest.main()
