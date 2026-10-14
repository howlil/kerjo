import urllib.request, re, json, pathlib

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
url = "https://glints.com/id/opportunities/jobs/explore?keyword=backend%20engineer&country=ID"
req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")
        print("Glints fetched, bytes:", len(html))
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if m:
            nd = json.loads(m.group(1))
            props = nd.get("props", {}).get("pageProps", {})
            print("Glints pageProps keys:", list(props.keys()))
            # Look for job list
            for k in ["jobs", "data", "initialReduxState", "apolloState"]:
                if k in props:
                    val = props[k]
                    print(f"Key {k} type: {type(val)}", str(val)[:300])
            # If Apollo / Relay / redux
            pathlib.Path("data/glints_next_data.json").write_text(json.dumps(nd, indent=1), encoding="utf-8")
            print("Saved glints_next_data.json")
except Exception as e:
    print("Glints error:", e)
