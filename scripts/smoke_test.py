import argparse
import urllib.request
import json
parser=argparse.ArgumentParser();parser.add_argument("--url",default="http://127.0.0.1:8000");args=parser.parse_args()
def get(path):
    with urllib.request.urlopen(args.url+path,timeout=30) as r:return r.status,r.read()
for path in ["/api/v1/health","/api/v1/artworks","/api/v1/epochs/current","/api/v1/analytics/treasury"]:
    status,body=get(path);assert status==200;print(f"OK {path}")
_,body=get("/api/v1/artworks/latest");a=json.loads(body)
_,verified=get(f'/api/v1/artworks/{a["id"]}/verify');assert json.loads(verified)["valid"]
status,image=get(a["image"]);assert image.startswith(b"\x89PNG")
print("OK canonical image and recomputed provenance")
