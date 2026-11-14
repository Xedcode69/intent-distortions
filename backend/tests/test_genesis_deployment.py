"""Genesis remains readable when app code is installed in site-packages."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.services import collection_art


@pytest.fixture
def installed_layout(monkeypatch, tmp_path):
    repository = Path(__file__).resolve().parents[2]
    content = (repository / "fixtures/collection/genesis.json").read_bytes()
    deployment = tmp_path / "app"
    fixture = deployment / "fixtures/collection/genesis.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(content)
    # A non-editable Docker install places Python code away from /app/fixtures.
    package_file = deployment / ".venv/lib/python3.12/site-packages/app/services/collection_art.py"
    monkeypatch.setattr(collection_art, "__file__", str(package_file))
    monkeypatch.setattr(collection_art, "ROOT", deployment, raising=False)
    settings = Settings(_env_file=None, app_env="test", execution_mode="live",
                        onchain_art_contract="art-v1.id-operator.testnet",
                        data_dir=tmp_path / "data")
    return settings, json.loads(content)


def test_installed_genesis_uses_deployment_root_and_preserves_identity(installed_layout):
    settings, expected = installed_layout
    assert collection_art.genesis(settings) == expected
    settings.onchain_art_contract = "different.testnet"
    with pytest.raises(ValueError, match="Genesis account must match"):
        collection_art.genesis(settings)


def test_installed_collection_api_exposes_preserved_genesis(monkeypatch, tmp_path, installed_layout):
    import app.main as main
    from app.database import init_db

    settings, expected = installed_layout
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "factory", init_db(f"sqlite:///{(tmp_path / 'collection.db').as_posix()}"))
    with TestClient(main.app) as client:
        response = client.get("/api/v1/artworks")
        assert response.status_code == 200
        assert response.json() == [expected]
        assert client.get("/api/v1/artworks/latest").json() == expected
        detail = client.get("/api/v1/artworks/genesis")
        assert detail.status_code == 200 and detail.json() == expected
