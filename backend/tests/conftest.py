import sys
from pathlib import Path
import os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

# Unit tests must never initialize the operator's configured production database
# or inherit live integration keys during collection/import of app.main.
os.environ.update(APP_ENV="test",EXECUTION_MODE="demo",DATABASE_URL="sqlite:///:memory:",
    DATA_DIR=str(Path(__file__).resolve().parents[2]/".tools/pytest-runtime"),
    STORAGE_PROVIDER="local_content_addressed",SCHEDULER_ENABLED="false",ENABLE_CHAIN_WRITES="false",
    MAINNET_WRITES_APPROVED="false",NEAR_INTENTS_PARTNER_JWT="",NEAR_AI_API_KEY="",NEAR_AI_TEXT_MODEL="",
    NEAR_NFT_CONTRACT="",NEAR_AUCTION_CONTRACT="",NEAR_MARKET_CONTRACT="",ADMIN_TOKEN="",SIGNER_KEY_FILE="",
    ALLOW_AI_FALLBACK="true",NEAR_NETWORK="testnet",ONCHAIN_ART_CONTRACT="")
