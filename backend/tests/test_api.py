import pytest
from fastapi.testclient import TestClient

def test_api_reads_and_recomputes(monkeypatch,tmp_path):
    import app.main as main
    from app.database import init_db
    from app.services.storage import ContentStore
    monkeypatch.setattr(main.settings,"data_dir",tmp_path)
    monkeypatch.setattr(main,"factory",init_db(f"sqlite:///{tmp_path/'api.db'}"))
    monkeypatch.setattr(main,"store",ContentStore(tmp_path/"content"))
    with TestClient(main.app) as c:
        assert c.get("/api/v1/health").json()["mode"]=="demo"
        a=c.get("/api/v1/artworks/latest").json()
        assert c.get(a["image"]).headers["content-type"]=="image/png"
        assert c.get(f'/api/v1/artworks/{a["id"]}/verify').json()["valid"]
        main.verification_slots.acquire()
        try:
            busy=c.get(f'/api/v1/artworks/{a["id"]}/verify')
            assert busy.status_code==429 and busy.headers["retry-after"]=="5"
        finally:main.verification_slots.release()
        assert c.get("/api/v1/epochs/current").json()["selected_block"] is None
        assert c.get("/api/v1/auctions").json()==[]
        assert c.get("/api/v1/analytics/treasury").json()["earned_yocto"]=="0"
        assert c.get("/api/v1/admin/jobs").status_code==403
        assert c.post("/api/v1/demo/run-epoch",headers={"origin":"https://attacker.example"}).status_code==403
        assert c.post("/api/v1/demo/run-epoch",headers={"origin":"http://127.0.0.1:3000"}).json()["image_hash"]==a["image_hash"]
        monkeypatch.setattr(main.settings,"app_env","production")
        assert c.post("/api/v1/demo/run-epoch").status_code==404
        monkeypatch.setattr(main.settings,"storage_provider","s3")
        monkeypatch.setattr(main.settings,"artifact_public_url","https://art.example")
        redirect=c.get(a["image"],follow_redirects=False)
        assert redirect.status_code==307 and redirect.headers["location"]==f'https://art.example/sha256/{a["image_hash"]}'
