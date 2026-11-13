import base58
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
import app.wallet_api as module


@pytest.fixture
def wallet_client(monkeypatch):
    settings = Settings(_env_file=None, near_network="testnet", near_nft_contract="echo.testnet",
                        expected_nft_code_hash="ab" * 32)
    monkeypatch.setattr(module, "settings", settings)

    class RPC:
        calls = []
        chain = "testnet"
        code_hash = "ab" * 32
        owner = "collector.testnet"
        fail = False

        async def call(self, method, args):
            self.calls.append((method, args))
            if self.fail:
                raise RuntimeError("https://provider.example/private-credential")
            if method == "status":
                return {"chain_id": self.chain}
            assert args["account_id"] == "echo.testnet" and args["finality"] == "final"
            return {"code_hash": base58.b58encode(bytes.fromhex(self.code_hash)).decode()}

        async def view(self, contract, method, args):
            self.calls.append((method, args))
            assert contract == "echo.testnet" and args["account_id"] == "collector.testnet"
            if method == "nft_supply_for_owner":
                return "23"
            assert method == "nft_tokens_for_owner"
            return [{"token_id": "ECHO-000021", "owner_id": self.owner,
                     "metadata": {"title": "An echo", "media": "https://art.example/21.png"}}]

    rpc = RPC()
    monkeypatch.setattr(module, "rpc", lambda: rpc)
    app = FastAPI()
    app.include_router(module.router)
    with TestClient(app) as client:
        yield client, settings, rpc


def test_owned_collection_uses_owner_enumeration_and_does_not_require_market(wallet_client):
    client, settings, rpc = wallet_client
    assert not settings.near_market_contract
    response = client.get("/api/v1/wallets/collector.testnet/collection?offset=20&limit=20")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "onchain" and data["total"] == "23" and data["checked_at"]
    assert data["account_id"] == data["tokens"][0]["owner_id"] == "collector.testnet"
    assert ("nft_tokens_for_owner", {"account_id": "collector.testnet", "from_index": "20", "limit": 20}) in rpc.calls
    assert not any(method == "nft_tokens" for method, _ in rpc.calls)


@pytest.mark.parametrize("query", ["?offset=-1", "?limit=51", "?limit=0", "?offset=100001"])
def test_collection_rejects_invalid_pagination_before_rpc(wallet_client, query):
    client, _, rpc = wallet_client
    assert client.get("/api/v1/wallets/collector.testnet/collection" + query).status_code == 422
    assert not rpc.calls


def test_collection_rejects_invalid_account_and_distinguishes_unconfigured_contract(wallet_client):
    client, settings, rpc = wallet_client
    assert client.get("/api/v1/wallets/INVALID/collection").status_code == 422
    assert not rpc.calls
    settings.near_nft_contract = ""
    data = client.get("/api/v1/wallets/collector.testnet/collection").json()
    assert data["status"] == "not_deployed" and data["total"] is None and not data["tokens"]
    assert not rpc.calls


@pytest.mark.parametrize("change", ["missing_pin", "wrong_hash", "wrong_network", "wrong_owner", "provider_error"])
def test_collection_fails_closed_without_leaking_provider_details(wallet_client, change):
    client, settings, rpc = wallet_client
    if change == "missing_pin":
        settings.expected_nft_code_hash = ""
    elif change == "wrong_hash":
        rpc.code_hash = "cd" * 32
    elif change == "wrong_network":
        rpc.chain = "mainnet"
    elif change == "wrong_owner":
        rpc.owner = "someone-else.testnet"
    else:
        rpc.fail = True
    response = client.get("/api/v1/wallets/collector.testnet/collection")
    assert response.status_code == (409 if change == "missing_pin" else 503)
    assert "private-credential" not in response.text and "tokens" not in response.json()
    if change in ("wrong_hash", "wrong_network"):
        assert not any(method.startswith("nft_") for method, _ in rpc.calls)


def test_ownership_is_requeried_after_transfer(wallet_client):
    client, _, rpc = wallet_client
    assert client.get("/api/v1/wallets/collector.testnet/collection").status_code == 200
    rpc.owner = "buyer.testnet"
    assert client.get("/api/v1/wallets/collector.testnet/collection").status_code == 503
