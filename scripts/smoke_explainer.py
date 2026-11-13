"""HTTP/asset integrity checks for the independent static educational demo."""
import hashlib
import json
import httpx

with httpx.Client(base_url="http://127.0.0.1:3001",timeout=15,trust_env=False) as client:
    page=client.get("/");page.raise_for_status()
    assert "EXPLANATORY DEMO" in page.text and "Synthetic educational data" in page.text
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert page.headers["x-content-type-options"]=="nosniff"
    for path in ("/styles.css","/app.mjs","/core.mjs","/assets/scene.json","/assets/artwork.svg","/assets/thumbnail.webp"):
        response=client.get(path);response.raise_for_status()
        if path.endswith(".mjs"):assert "javascript" in response.headers["content-type"]
    sample=client.get("/assets/example.json").json()
    assert sample["classification"]=="synthetic_educational_sample" and not sample["randomness_verified"]
    image=client.get("/assets/artwork.png");image.raise_for_status()
    assert hashlib.sha256(image.content).hexdigest()==sample["image_hash"]
    assert client.get("/api/v1/health").status_code==404
    assert client.get("/.env").status_code==404
    print(json.dumps({"demo_http":"passed","public_assets":"passed","image_hash":"passed","production_api":"absent","credentials":"not_required"}))
