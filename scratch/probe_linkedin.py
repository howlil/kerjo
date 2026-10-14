import urllib.request, re, json, sys, pathlib

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=backend%20engineer&location=Jakarta%2C%20Indonesia&start=0"
req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")
        pathlib.Path("data/linkedin_sample.html").write_text(html, encoding="utf-8")
        print("LinkedIn fetched, bytes:", len(html))
        # Look for job cards
        cards = re.findall(r'<div[^>]*base-search-card[^>]*>.*?</div>\s*</li>', html, re.S)
        print("Cards found regex:", len(cards))
        if cards:
            c = cards[0]
            print("Sample card:", c[:800].replace("\n", " "))
            title = re.search(r'<h3[^>]*base-search-card__title[^>]*>\s*(.*?)\s*</h3>', c, re.S)
            comp = re.search(r'<h4[^>]*base-search-card__subtitle[^>]*>.*?<a[^>]*>\s*(.*?)\s*</a>', c, re.S)
            loc = re.search(r'<span[^>]*job-search-card__location[^>]*>\s*(.*?)\s*</span>', c, re.S)
            link = re.search(r'<a[^>]*base-card__full-link[^>]*href="([^"]+)"', c, re.S)
            urn = re.search(r'data-entity-urn="urn:li:jobPosting:(\d+)"', c, re.S)
            time_el = re.search(r'<time[^>]*datetime="([^"]+)"', c, re.S)
            print("Extracted:")
            print("  urn:", urn.group(1) if urn else None)
            print("  title:", title.group(1) if title else None)
            print("  comp:", comp.group(1) if comp else None)
            print("  loc:", loc.group(1) if loc else None)
            print("  link:", (link.group(1).split("?")[0]) if link else None)
            print("  time:", time_el.group(1) if time_el else None)
except Exception as e:
    print("LinkedIn error:", e)
