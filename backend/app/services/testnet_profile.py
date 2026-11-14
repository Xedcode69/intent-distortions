"""Boundary between frozen historical art and an isolated testnet rehearsal."""
import json
from pathlib import Path

SCHEMA = "intent-distortions-testnet-rehearsal-v1"
REHEARSAL_ROOT = Path(__file__).resolve().parents[3] / "data/testnet-rehearsals"


def data_mode(settings):
    return "historical_replay" if settings.execution_mode == "testnet_rehearsal" else settings.execution_mode


def data_modes(settings):
    return ("historical_replay", "demo") if settings.execution_mode == "testnet_rehearsal" else (settings.execution_mode,)


def is_lab(settings):
    if settings.execution_mode != "testnet_rehearsal":
        return False
    return json.loads((settings.testnet_rehearsal_dir / "prepared.json").read_text(encoding="utf-8")).get("contract_flavor") == "testnet-lab"


def validate_clock_build(settings, config):
    lab = config.get("testnet_lab") is True
    if lab and (settings.near_network != "testnet" or not is_lab(settings)):
        raise ValueError("Test-only WASM is forbidden outside an isolated testnet lab")
    if is_lab(settings) and (not lab or config.get("clock_initialized") is not True):
        raise ValueError("Expected an initialized testnet lab contract")
    if is_lab(settings) and config.get("clock_authority") != settings.near_minter_account:
        raise ValueError("Lab clock authority must match the configured operator")


def validate_boundary(settings):
    if settings.execution_mode != "testnet_rehearsal":
        return
    directory = Path(settings.testnet_rehearsal_dir).resolve()
    root = REHEARSAL_ROOT.resolve()
    if not directory.is_relative_to(root) or directory == root:
        raise ValueError("Testnet rehearsal must use its prepared isolated workspace")
    manifest = json.loads((directory / "prepared.json").read_text(encoding="utf-8"))
    expected = f"sqlite:///{(directory / 'rehearsal.db').as_posix()}"
    if (manifest.get("schema") != SCHEMA or manifest.get("source_mode") != "historical_replay"
            or settings.database_url != expected or settings.data_dir.resolve() != directory):
        raise ValueError("Testnet rehearsal profile does not match its isolated workspace")
    if (settings.app_env != "development" or settings.near_network != "testnet"
            or settings.storage_provider != "local_content_addressed" or settings.service_role != "api"
            or settings.enable_chain_writes or settings.mainnet_writes_approved or settings.scheduler_enabled
            or settings.marketplace_crosschain_enabled or settings.signer_key_file):
        raise ValueError("Testnet rehearsal requires testnet, local storage and disabled background signing")
