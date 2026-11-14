from pathlib import Path
import os
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(os.environ.get("ECHOES_ROOT",Path(__file__).resolve().parents[2]))

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=os.environ.get("ECHOES_ENV_FILE", ROOT / ".env"), extra="ignore",hide_input_in_errors=True)
    app_env: Literal["development", "production", "test"] = "development"
    execution_mode: Literal["demo", "live", "historical_replay", "testnet_rehearsal"] = "demo"
    testnet_rehearsal_dir: Path = Field(default=Path("data/testnet-rehearsals/unprepared"),repr=False)
    testnet_governance_account: str = ""
    testnet_artifact_base_url: str = ""
    database_url: str = Field(default="sqlite:///./data/echoes-demo.db",repr=False)
    data_dir: Path = ROOT / "data"
    admin_token: str = Field(default="",repr=False)
    near_network: Literal["testnet"] = "testnet"
    near_rpc_url: str = "https://rpc.testnet.near.org"
    near_mainnet_rpc_url: str = "https://archival-rpc.mainnet.near.org"
    near_nft_contract: str = ""
    near_auction_contract: str = ""
    near_market_contract: str = ""
    expected_market_code_hash: str = ""
    onchain_art_contract: str = ""
    onchain_art_token_id: str = "ONCHAIN-PROTOTYPE-000001"
    expected_onchain_art_code_hash: str = ""
    onchain_renderer_binary: str = ""
    genesis_image_hash: str = "b870866d3f2eded46854edaf3f941ddd8f8bdf3d820ca5a413aa253893b2424b"
    genesis_checkpoint_ns: str = "1794097030218994184"
    near_intents_1click_jwt: str = Field(default="",repr=False)
    marketplace_crosschain_enabled: bool = False
    near_intents_explorer_url: str = "https://explorer.near-intents.org/api/v0"
    near_intents_partner_jwt: str = Field(default="",repr=False)
    near_ai_api_key: str = Field(default="",repr=False)
    near_ai_base_url: str = "https://cloud-api.near.ai/v1"
    near_ai_text_model: str = ""
    reconciliation_delay_seconds: int = 3600
    genesis_checkpoint: int = 1794097030
    scheduler_enabled: bool = False
    cors_origin: str = "http://localhost:3000"
    service_role: Literal["api","worker","operator","combined"] = "api"
    public_origin: str = "http://localhost:3000"
    allowed_hosts: list[str] = ["localhost","127.0.0.1","testserver"]
    storage_provider: Literal["local_content_addressed"] = "local_content_addressed"
    protocol_id: str = "near-echoes-local"
    first_release_sunday: str = "2026-11-15"
    freeze_observation_max_age_seconds: int = Field(default=3600,ge=30,le=7200)
    allow_ai_fallback: bool = True
    worker_poll_seconds: int = Field(default=30,ge=5,le=300)
    index_poll_seconds: int = Field(default=600,ge=60,le=3600)
    near_minter_account: str = ""
    signer_key_file: str = ""
    enable_chain_writes: bool = False
    mainnet_writes_approved: bool = False
    expected_nft_code_hash: str = ""
    expected_auction_code_hash: str = ""
    expected_vault_code_hash: str = ""
    near_creator_account: str = ""
    near_treasury_account: str = ""
    economy_enabled: bool = True
    max_request_bytes: int = Field(default=262144,ge=1024,le=1048576)
    verification_concurrency: int = Field(default=1,ge=1,le=4)
    rpc_timeout_seconds: int = Field(default=30,ge=5,le=60)
    collector_page_size: int = Field(default=1000,ge=1,le=1000)

    @model_validator(mode="after")
    def production_boundary(self):
        if self.execution_mode=="testnet_rehearsal":
            from .services.testnet_profile import validate_boundary
            validate_boundary(self)
        if self.app_env!="production":
            return self
        issues=[]
        if self.execution_mode!="live": issues.append("production requires EXECUTION_MODE=live")
        if not self.database_url.startswith(("postgresql://","postgresql+psycopg://")):
            issues.append("production requires PostgreSQL")
        if not self.public_origin.startswith("https://"): issues.append("PUBLIC_ORIGIN must use HTTPS")
        if self.protocol_id in ("", "near-echoes-local"): issues.append("a distinct PROTOCOL_ID is required")
        if self.storage_provider!="local_content_addressed":
            issues.append("the testnet prototype uses a persistent local DATA_DIR")
        if not self.onchain_renderer_binary:issues.append("ONCHAIN_RENDERER_BINARY is required")
        if len(self.admin_token)<32: issues.append("ADMIN_TOKEN must contain at least 32 characters")
        if "*" in self.allowed_hosts: issues.append("explicit ALLOWED_HOSTS are required")
        if not self.allowed_hosts: issues.append("ALLOWED_HOSTS cannot be empty")
        if not 600<=self.reconciliation_delay_seconds<=7200: issues.append("reconciliation delay must be between 600 and 7200 seconds")
        if not self.near_nft_contract or not self.near_auction_contract:
            issues.append("deployed NFT and auction account IDs are required")
        if self.near_market_contract:
            if self.near_market_contract in (self.near_nft_contract,self.near_auction_contract,self.near_minter_account,self.near_creator_account):issues.append("marketplace requires a separate account")
            if len(self.expected_market_code_hash)!=64 or any(c not in "0123456789abcdef" for c in self.expected_market_code_hash):issues.append("reviewed marketplace WASM hash required")
        if self.marketplace_crosschain_enabled:issues.append("1Click checkout is unavailable for testnet NEAR")
        if not self.near_minter_account:issues.append("NEAR_MINTER_ACCOUNT is required")
        if not self.economy_enabled:issues.append("production requires the dedicated-account economy")
        if not self.near_creator_account or not self.near_treasury_account:issues.append("NEAR_CREATOR_ACCOUNT and NEAR_TREASURY_ACCOUNT are required")
        if len(self.expected_vault_code_hash)!=64 or any(c not in "0123456789abcdef" for c in self.expected_vault_code_hash):issues.append("reviewed vault WASM SHA-256 must be pinned")
        if self.first_release_sunday!="2026-11-15":issues.append("economy launch requires FIRST_RELEASE_SUNDAY=2026-11-15")
        if len({self.near_minter_account,self.near_nft_contract,self.near_auction_contract})!=3:issues.append("minter, NFT and auction must be separate accounts")
        if any(len(h)!=64 or any(c not in "0123456789abcdef" for c in h) for h in (self.expected_nft_code_hash,self.expected_auction_code_hash)):
            issues.append("both reviewed WASM SHA-256 hashes must be pinned before protocol initialization")
        if any(not url.startswith("https://") for url in (self.near_rpc_url,self.near_mainnet_rpc_url,self.near_ai_base_url,self.near_intents_explorer_url)):
            issues.append("production provider endpoints must use HTTPS")
        if self.allow_ai_fallback: issues.append("production must explicitly disable AI fallback")
        if not self.near_ai_text_model: issues.append("the published AI model ID is required")
        if self.service_role in ("worker","combined"):
            if not self.near_intents_partner_jwt: issues.append("worker requires Explorer partner JWT")
            if not self.near_ai_api_key or not self.near_ai_text_model: issues.append("worker requires NEAR AI key/model")
            if self.enable_chain_writes and (not self.near_minter_account or not self.signer_key_file):
                issues.append("enabled signing requires a minter account and mounted SIGNER_KEY_FILE")
        if issues: raise ValueError("; ".join(issues))
        return self

settings = Settings()
