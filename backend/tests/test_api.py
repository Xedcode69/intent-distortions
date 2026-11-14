import pytest
from fastapi.testclient import TestClient

def test_api_reads_and_recomputes(monkeypatch,tmp_path):
    import app.main as main
    from app.database import init_db
    from app.services.storage import ContentStore
    monkeypatch.setattr(main.settings,"app_env","development")
    monkeypatch.setattr(main.settings,"data_dir",tmp_path)
    monkeypatch.setattr(main,"factory",init_db(f"sqlite:///{tmp_path/'api.db'}"))
    monkeypatch.setattr(main,"store",ContentStore(tmp_path/"content"))
    with TestClient(main.app) as c:
        assert c.get("/api/v1/health").json()["mode"]=="demo"
        a=c.get("/api/v1/artworks/latest").json()
        feed=c.get('/api/v1/drops').json()
        assert feed['preview'] and feed['mode']=='demo' and feed['previous'][0]['id']==a['id']
        assert feed['previous'][0]['records']==a['stats']['total_swaps']
        assert c.get('/api/v1/drops?limit=1000').status_code==422
        traits=c.get(f'/api/v1/artworks/{a["id"]}/traits').json()
        assert traits["source"]["image_sha256"]==a["image_hash"] and traits["onchain_status"]=="not_published"
        assert traits["edition_attributes"]==[]
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
        from app.database import Job
        with main.factory.begin() as db:
            db.add(Job(key="historical-replay-summary",kind="historical_replay",status="succeeded",attempts=1,
                payload={"mode":"historical_replay","status":"replay_complete","indexed_records":36,"selected_block":{"height":42}}))
        monkeypatch.setattr(main.settings,"execution_mode","historical_replay")
        replay=c.get("/api/v1/epochs/current").json()
        assert replay["status"]=="replay_complete" and replay["selected_block"]["height"]==42
        assert c.get("/api/v1/health").json()["integrations"]["near_ai"]=="recorded_direction"
        monkeypatch.setattr(main.settings,"execution_mode","demo")
        monkeypatch.setattr(main.settings,"app_env","production")
        assert c.post("/api/v1/demo/run-epoch").status_code==404
