"""HTTP verification of standalone HTML/assets; does not replace browser QA."""
import urllib.request
from html.parser import HTMLParser

class Assets(HTMLParser):
    def __init__(self):super().__init__();self.urls=set()
    def handle_starttag(self,tag,attrs):
        for name,value in attrs:
            if name in ("src","href") and value and value.startswith("/_next/"):self.urls.add(value)

base="http://127.0.0.1:3000"
with urllib.request.urlopen(base,timeout=20) as r:
    assert r.status==200;page=r.read().decode()
assert "Intent Distortions" in page
parser=Assets();parser.feed(page)
assert parser.urls,"No Next.js assets found"
for path in sorted(parser.urls):
    with urllib.request.urlopen(base+path,timeout=20) as r:
        assert r.status==200 and len(r.read())>0
print(f"Standalone homepage and {len(parser.urls)} linked assets return HTTP 200. Browser visual QA remains unverified.")
