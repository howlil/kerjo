"""Selective detail enrichment: JSON-LD date evidence and SSRF boundaries."""
import datetime as dt
import unittest
from jobhunt.enrichment import (
    NoRedirect, allowed_detail_url, enrich_jobs,
    jobposting_metadata,
)
from jobhunt.freshness import utc_now
from jobhunt.models import Job


def make(url, date=None, description=None):
    return Job(source="jobstreet", external_id=url.rsplit("/",1)[-1],
               title="Backend Engineer",company="Acme",area="jakarta_selatan",
               location_raw="Jakarta Selatan",url=url,posted_at=date,
               description=description)


class TestEnrichment(unittest.TestCase):
    def test_jsonld_jobposting_extracts_date_and_full_description(self):
        html = """<script nonce="abc" type="application/ld+json">
        {"@context":"https://schema.org","@graph":[
          {"@type":"WebPage","dateModified":"2026-10-14"},
          {"@type":"JobPosting","title":"Backend Engineer",
           "datePosted":"2026-10-13T07:00:00+07:00",
           "description":"<p>Implement <b>reliable services</b> with SQL and Python.</p>"}
        ]}</script>"""
        metadata=jobposting_metadata(html,"Backend Engineer")
        self.assertEqual(metadata["posted_at"],"2026-10-13T07:00:00+07:00")
        self.assertIn("reliable services",metadata["description"])
        self.assertNotIn("<b>",metadata["description"])

    def test_never_uses_modified_date_or_unrelated_job(self):
        text='''<script type="application/ld+json">
           {"@type":"JobPosting","title":"Customer Service","datePosted":"2026-10-14",
            "dateModified":"2026-10-14"}</script>'''
        self.assertEqual(jobposting_metadata(text,"Backend Engineer"),{})
        page='<script type="application/ld+json">{"@type":"WebPage","dateModified":"2026-10-14"}</script>'
        self.assertEqual(jobposting_metadata(page,"Backend Engineer"),{})

    def test_strict_https_provider_host_and_no_redirects(self):
        self.assertTrue(allowed_detail_url("jobstreet","https://id.jobstreet.com/job/123"))
        for url in [
            "http://id.jobstreet.com/job/123",
            "https://id.jobstreet.com.evil.test/job/123",
            "https://127.0.0.1/private",
            "file:///etc/passwd",
            "https://user:pass@id.jobstreet.com/job/123",
            "https://id.jobstreet.com:8443/job/123",
            "https://id.jobstreet.com/"
        ]:
            self.assertFalse(allowed_detail_url("jobstreet",url),url)
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,"Moved",{},"https://evil.test"))

    def test_missing_date_requires_jobposting_evidence(self):
        recent=utc_now().isoformat()
        jobs=[
            make("https://id.jobstreet.com/job/1"),
            make("https://id.jobstreet.com/job/2"),
            make("https://evil.test/job/3"),
            make("https://id.jobstreet.com/job/4",date=recent,description="Short"),
        ]
        calls=[]
        def fetch(url):
            calls.append(url)
            if url.endswith("/1"):
                return ('<script type="application/ld+json">'
                        '{"@type":"JobPosting","title":"Backend Engineer",'
                        '"datePosted":"' + recent + '","description":"New full description of job posting."}'
                        '</script>')
            return "<html><body>No JobPosting structured data</body></html>"
        changed=enrich_jobs(jobs,"jobstreet",max_details=2,fetch_html=fetch)
        self.assertEqual(changed,1)
        self.assertEqual(len(calls),2)
        self.assertEqual(jobs[0].posted_at,recent)
        self.assertIsNone(jobs[1].posted_at)
        self.assertIsNone(jobs[2].posted_at)
        self.assertEqual(jobs[3].description,"Short")

    def test_older_jobs_not_enriched_or_republished(self):
        old=(utc_now()-dt.timedelta(days=30)).isoformat()
        entry=make("https://id.jobstreet.com/job/old",date=old)
        calls=[]
        self.assertEqual(enrich_jobs([entry],"jobstreet",max_details=5,
                                     fetch_html=lambda u:calls.append(u)),0)
        self.assertEqual(calls,[])
        self.assertEqual(entry.posted_at,old)


if __name__=="__main__":
    unittest.main()
