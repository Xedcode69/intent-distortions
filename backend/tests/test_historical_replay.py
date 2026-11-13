"""Network-mocked workflow tests; generated test captures never claim live acceptance."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.services.historical_replay import ReplayPlan, readiness, replay_week, replay_lock
from app.services.randomness import select_timestamp
from test_dataset import raw

NOW = datetime(2026, 11, 13, tzinfo=timezone.utc)
PLAN = ReplayPlan.build("2026-11-08", now=NOW)
BEACON = json.loads((Path(__file__).resolve().parents[2] / "fixtures/sample-epoch/verified-beacon.json").read_text())


class MockMainnet:
    def __init__(self): self.lookups = 0

    async def call(self, method, params):
        assert method == "status"
        return {"chain_id": "mainnet"}

    async def first_block_at(self, target):
        self.lookups += 1
        return {"height": 42, "hash": "11111111111111111111111111111111", "timestamp_ns": str(target * 10**9 + 200_000_000),
                "previous_timestamp_ns": str(target * 10**9 - 100_000_000), "rpc_network": "mainnet", "verified": True}

    async def verify_selected_block(self, block, target):
        assert int(block["previous_timestamp_ns"]) < target * 10**9 <= int(block["timestamp_ns"])
        return True


class MockExplorer:
    def __init__(self, complete=True): self.calls = 0; self.complete = complete

    async def collect(self, start, end, page_size):
        self.calls += 1
        records = [raw(i, start + i + 1) for i in range(5)] + [raw(6, start + 10, status="PROCESSING")]
        return records, {"complete": self.complete, "pages": 1, "query": {"start": start - 1, "end": end}, "source": "mock://unit-test"}


async def mock_beacon(timestamp):
    assert timestamp == BEACON["released_at"]
    return BEACON


def base_settings(**changes):
    return Settings(_env_file=None, near_intents_partner_jwt="unit-test-placeholder", near_ai_api_key="", near_ai_text_model="", **changes)


def test_latest_released_sunday_and_explicit_genesis():
    assert ReplayPlan.build(now=NOW).sunday == "2026-11-08"
    assert PLAN.sunday_start - PLAN.start == 7 * 86400
    before_release = datetime(2026, 11, 8, 17, tzinfo=timezone.utc)
    assert ReplayPlan.build(now=before_release).sunday == "2026-11-01"
    with pytest.raises(ValueError, match="Sunday"): ReplayPlan.build("2026-11-09", now=NOW)
    with pytest.raises(ValueError, match="completed"): ReplayPlan.build("2026-11-15", now=NOW)
    with pytest.raises(ValueError, match="precede"): ReplayPlan.build("2026-11-08", PLAN.sunday_start, now=NOW)


async def test_readiness_needs_no_network_or_production_state(tmp_path):
    base = Settings(_env_file=None, near_intents_partner_jwt="", near_ai_api_key="", near_ai_text_model="")
    result = await replay_week(PLAN, base, tmp_path, action="check")
    assert result["status"] == "blocked" and result["requirements"]["missing"] == ["NEAR_INTENTS_PARTNER_JWT"]
    assert not (tmp_path / "replay.db").exists() and not (tmp_path / "capture.raw.json").exists()
    assert not (tmp_path / "plan.json").exists()
    assert readiness(ReplayPlan(PLAN.sunday_start, PLAN.start, "required"), base)["missing"] == ["NEAR_INTENTS_PARTNER_JWT", "NEAR_AI_API_KEY", "NEAR_AI_TEXT_MODEL"]


async def test_ai_can_be_configured_after_readiness_and_public_preparation(tmp_path):
    plan = ReplayPlan(PLAN.sunday_start, PLAN.start, "required")
    base = Settings(_env_file=None, near_intents_partner_jwt="", near_ai_api_key="", near_ai_text_model="")
    assert (await replay_week(plan, base, tmp_path, action="check"))["status"] == "blocked"
    await replay_week(plan, base, tmp_path, action="prepare", rpc=MockMainnet(), beacon_fetch=mock_beacon)
    configured = Settings(_env_file=None, near_intents_partner_jwt="unit-test-placeholder",
                          near_ai_api_key="unit-test-ai-placeholder", near_ai_text_model="unit-test-model")
    ready = await replay_week(plan, configured, tmp_path, action="check")
    assert ready["status"] == "ready" and ready["plan"]["ai_model"] == "unit-test-model"
    prepared = await replay_week(plan, configured, tmp_path, action="prepare", rpc=MockMainnet(), beacon_fetch=mock_beacon)
    assert prepared["status"] == "checkpoint_prepared"
    assert json.loads((tmp_path / "plan.json").read_text())["ai_model"] == "unit-test-model"
    assert not (tmp_path / "replay.db").exists()


async def test_full_mocked_replay_caches_capture_verifies_art_and_detects_tampering(tmp_path,monkeypatch):
    rpc = MockMainnet(); collector = MockExplorer(); base = base_settings()
    first = await replay_week(PLAN, base, tmp_path, rpc=rpc, collector=collector, beacon_fetch=mock_beacon)
    assert first["status"] == "passed" and first["stages"]["capture"]["successful_records"] == 5
    assert all(first["tests"].values()) and first["full_live_acceptance"] is False
    assert first["stages"]["art_direction"]["provider"] == "deterministic_fallback"
    assert "unit-test-placeholder" not in (tmp_path / "report.json").read_text()
    assert "unit-test-placeholder" not in (tmp_path / "preview.env").read_text()
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.services.storage import ContentStore
    import app.main as api
    engine=create_engine(f"sqlite:///{tmp_path/'replay.db'}",connect_args={"check_same_thread":False})
    monkeypatch.setattr(api,"factory",sessionmaker(engine,expire_on_commit=False))
    monkeypatch.setattr(api,"store",ContentStore(tmp_path/"content"))
    monkeypatch.setattr(api.settings,"execution_mode","historical_replay")
    with TestClient(api.app) as client:
        assert client.get("/api/v1/health").json()["mode"]=="historical_replay"
        assert client.get("/api/v1/epochs/current").json()["selected_block"]["height"]==42
        assert client.get("/api/v1/artworks/latest").json()["image_hash"]==first["artwork"]["image_hash"]
        assert client.get("/api/v1/artworks/historical_replay-000001/dna").json()["shapes"]
        assert client.get("/api/v1/artworks/historical_replay-000001/verify").json()["valid"]
        assert client.post("/api/v1/demo/run-epoch").status_code==404
    engine.dispose()
    from app.services.demo_publication import publish_replay
    from app.services.canonical_data import sha
    public = tmp_path / "public-demo"
    published = publish_replay(tmp_path / "report.json", public)
    assert published["schema"] == "echo-historical-demo-v1" and published["statistics"]["total_swaps"] == 5
    assert published["artwork"]["image_hash"] == first["artwork"]["image_hash"]
    assert set(published["files"]) == {"artwork.png", "artwork-manifest.json"}
    assert len(list(public.rglob("*.*"))) == 3
    for item in published["files"].values():
        relative = item["url"].removeprefix("/historical-demo/")
        assert sha((public / relative).read_bytes()).hex() == item["sha256"]
    public_json = (public / "index.json").read_text()
    assert not any(value in public_json for value in ("unit-test-placeholder", "mock://", "depositAddress", "DATABASE_URL"))
    assert publish_replay(tmp_path / "report.json", public) == published
    invalid = json.loads((tmp_path / "report.json").read_text())
    invalid["status"] = "failed"
    (tmp_path / "rejected.json").write_text(json.dumps(invalid))
    with pytest.raises(ValueError, match="completed"):
        publish_replay(tmp_path / "rejected.json", public)
    second = await replay_week(PLAN, base, tmp_path, rpc=rpc, collector=collector, beacon_fetch=mock_beacon)
    assert second["artwork"] == first["artwork"] and collector.calls == 1 and rpc.lookups == 1
    private = tmp_path / "capture.raw.json"
    private.write_text(private.read_text().replace('"SUCCESS"', '"REFUNDED"', 1))
    failed = await replay_week(PLAN, base, tmp_path, rpc=rpc, collector=collector, beacon_fetch=mock_beacon)
    assert failed["status"] == "failed" and failed["stages"]["capture"]["error_type"] == "ValueError"
    assert (tmp_path / "export/artwork.png").exists()
    # Even a forged passed report cannot publish an altered original capture.
    (tmp_path / "report.json").write_text(json.dumps(first))
    with pytest.raises(ValueError, match="Raw capture hash"):
        publish_replay(tmp_path / "report.json", public)
    assert (public / "index.json").read_text() == public_json


async def test_public_checkpoint_preparation_is_separate_from_swap_capture(tmp_path):
    base = Settings(_env_file=None, near_intents_partner_jwt="")
    prepared = await replay_week(PLAN, base, tmp_path, action="prepare", rpc=MockMainnet(), beacon_fetch=mock_beacon)
    assert prepared["status"] == "checkpoint_prepared" and not (tmp_path / "capture.raw.json").exists()
    blocked = await replay_week(PLAN, base, tmp_path, rpc=MockMainnet(), beacon_fetch=mock_beacon)
    assert blocked["status"] == "blocked" and blocked["stages"]["capture"]["missing"] == ["NEAR_INTENTS_PARTNER_JWT"]
    assert not (tmp_path / "replay.db").exists()


async def test_incomplete_capture_cannot_generate_a_replay(tmp_path):
    report = await replay_week(PLAN, base_settings(), tmp_path, rpc=MockMainnet(), collector=MockExplorer(False), beacon_fetch=mock_beacon)
    assert report["status"] == "failed" and report["stages"]["capture"]["error_type"] == "ValueError"
    assert not (tmp_path / "replay.db").exists()


async def test_provider_failure_does_not_leak_credentials_or_fabricate_evidence(tmp_path):
    async def unavailable(timestamp): raise RuntimeError("sensitive-provider-token")
    report = await replay_week(PLAN, base_settings(), tmp_path, beacon_fetch=unavailable)
    assert report["status"] == "failed" and report["stages"]["beacon"]["error_type"] == "RuntimeError"
    assert "sensitive-provider-token" not in (tmp_path / "report.json").read_text()
    assert not (tmp_path / "evidence.json").exists() and not (tmp_path / "export/artwork.png").exists()


async def test_required_ai_cannot_silently_fall_back(tmp_path):
    plan = ReplayPlan(PLAN.sunday_start, PLAN.start, "required")
    report = await replay_week(plan, base_settings(), tmp_path, rpc=MockMainnet(), collector=MockExplorer(), beacon_fetch=mock_beacon)
    assert report["status"] == "blocked" and report["stages"]["art_direction"]["status"] == "blocked"
    assert not (tmp_path / "replay.db").exists()


def test_preview_does_not_inherit_operator_credentials_or_database(monkeypatch,tmp_path):
    import importlib.util
    path=Path(__file__).resolve().parents[2]/"scripts/serve_replay.py"
    spec=importlib.util.spec_from_file_location("serve_replay_test",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for key in ("NEAR_AI_API_KEY","NEAR_INTENTS_PARTNER_JWT","AWS_SECRET_ACCESS_KEY","GITHUB_TOKEN","OPENAI_API_KEY"):
        monkeypatch.setenv(key,"private-operator-credential")
    monkeypatch.setenv("DATABASE_URL","postgresql://operator:private@production/echoes")
    api,frontend=module.preview_environment(tmp_path,8001,3003)
    assert api["DATABASE_URL"].startswith("sqlite:///") and api["ENABLE_CHAIN_WRITES"]=="false"
    assert not any("private-operator-credential" in value for value in api.values())
    assert not any("private-operator-credential" in value for value in frontend.values())
    assert "DATABASE_URL" not in frontend and "ECHOES_ENV_FILE" not in frontend
    assert frontend["ECHOES_NEXT_DIST_DIR"]==".next-replay"


def test_replay_lock_prevents_parallel_collectors_and_releases_for_next_run(tmp_path):
    path=tmp_path/"collector.lock"
    with replay_lock(path):
        with pytest.raises(RuntimeError,match="Another historical test"):
            with replay_lock(path):pass
    with replay_lock(path):pass
