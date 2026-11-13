import json

from fastapi.testclient import TestClient

from app.services.replay_progress import ProgressWriter, read_progress


def test_progress_has_no_invented_total_and_distinguishes_complete_capture(tmp_path):
    clock=[100]
    writer=ProgressWriter(tmp_path,sunday="2026-11-08",start=1793491200,clock=lambda:clock[0])
    writer.update(stage="capture",received_rows=123000,pages=123)
    initial=read_progress(tmp_path,clock=lambda:130)
    assert initial["total_records"] is None and initial["collection_percent"] is None
    assert initial["elapsed_seconds"]==30 and not initial["stale"]
    assert read_progress(tmp_path,clock=lambda:221)["stale"]
    clock[0]=240
    writer.update(stage="art_direction",received_rows=123100,total_records=123099,eligible_records=120000,
                  collection_complete=True,total_source="complete_capture")
    complete=read_progress(tmp_path,clock=lambda:240)
    assert complete["collection_percent"]==100 and complete["total_records"]==123099
    assert complete["status"]=="running" and complete["stage"]=="art_direction"
    writer.update(status="passed",stage="complete")
    assert read_progress(tmp_path,clock=lambda:999)["elapsed_seconds"]==140


def test_progress_endpoint_is_read_only_and_excludes_extra_fields(monkeypatch,tmp_path):
    import app.main as main
    writer=ProgressWriter(tmp_path,sunday="2026-11-08",start=1793491200)
    writer.update(stage="capture",received_rows=300000,pages=300)
    payload=json.loads(writer.path.read_text())
    payload["credentials"]="must-not-be-returned"
    writer.path.write_text(json.dumps(payload))
    monkeypatch.setattr(main.settings,"execution_mode","historical_replay")
    monkeypatch.setattr(main.settings,"data_dir",tmp_path)
    with TestClient(main.app) as client:
        response=client.get("/api/v1/replay/progress")
        assert response.status_code==200 and response.json()["received_rows"]==300000
        assert "must-not-be-returned" not in response.text
        assert client.post("/api/v1/replay/progress").status_code==405
        monkeypatch.setattr(main.settings,"execution_mode","live")
        assert client.get("/api/v1/replay/progress").status_code==404
        monkeypatch.setattr(main.settings,"execution_mode","historical_replay")
        monkeypatch.setattr(main.settings,"app_env","production")
        assert client.get("/api/v1/replay/progress").status_code==404
