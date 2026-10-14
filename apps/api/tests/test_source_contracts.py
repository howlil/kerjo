"""Offline adapter contract: raw vs parsed page count and HTTP metadata."""
import json
import unittest
import urllib.error
from unittest.mock import patch

from jobhunt.sources.jobstreet import fetch_jobstreet
from jobhunt.sources.kalibrr import fetch_kalibrr
from jobhunt.sources.linkedin import fetch_linkedin
from jobhunt.sources.glints import fetch_glints
from jobhunt.sources.dealls import fetch_dealls
from jobhunt.sources.karir import fetch_karir
from jobhunt.sources.techinasia import fetch_techinasia


class Response:
    status = 200
    headers = {"Content-Type":"application/json"}
    def __init__(self, body):
        self.body=body.encode()
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def read(self):
        return self.body


class TestProviderContracts(unittest.TestCase):
    def test_all_adapters_distinguish_real_empty_raw_page(self):
        payloads=[
            (fetch_jobstreet, {"data":[]}),
            (fetch_kalibrr, {"jobs":[]}),
            (fetch_linkedin, "<html><body>No jobs</body></html>"),
            (fetch_glints, '<script id="__NEXT_DATA__">{"props":{"pageProps":{"initialJobs":[]}}}</script>'),
            (fetch_dealls, {"data":{"docs":[]}}),
            (fetch_karir, {"data":{"opportunities":[]}}),
            (fetch_techinasia, {"data":[]})
        ]
        for adapter,payload in payloads:
            with self.subTest(adapter=adapter.__name__):
                body=payload if isinstance(payload,str) else json.dumps(payload)
                with patch("urllib.request.urlopen",return_value=Response(body)):
                    result=adapter("backend")
                self.assertTrue(result.success,result.error_message)
                self.assertEqual(result.raw_count,0)
                self.assertEqual(result.pages_fetched,1)

    def test_retry_after_status_exposed_on_http_429(self):
        adapters=[fetch_jobstreet,fetch_kalibrr,fetch_linkedin,fetch_glints,
                  fetch_dealls,fetch_karir,fetch_techinasia]
        for adapter in adapters:
            with self.subTest(adapter=adapter.__name__):
                err=urllib.error.HTTPError(
                    url="https://example.test", code=429, msg="Too Many Requests",
                    hdrs={"Retry-After":"5"}, fp=None)
                with patch("urllib.request.urlopen",side_effect=err):
                    result=adapter("backend")
                self.assertFalse(result.success)
                self.assertEqual(result.http_status,429)
                self.assertEqual(result.retry_after_seconds,5)
