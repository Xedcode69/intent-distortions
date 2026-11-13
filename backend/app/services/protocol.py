"""Published immutable policy. Never include credentials in a commitment."""
from datetime import datetime,timezone
from sqlalchemy import select
from ..database import Protocol,Epoch
from .canonical_data import canonical,sha
from .visual_features import RENDERER_VERSION,FEATURE_VERSION
from .asset_networks import POLICY
from .family_selection import POLICY as FAMILY_POLICY
from .randomness import CHAIN_HASH

def policy(settings):
    sunday=datetime.strptime(settings.first_release_sunday,"%Y-%m-%d").replace(tzinfo=timezone.utc)
    if sunday.weekday()!=6 or settings.genesis_checkpoint>=int(sunday.timestamp()):
        raise ValueError("First release must be a Sunday after the genesis checkpoint")
    return {"protocol_id":settings.protocol_id,"network":settings.near_network,"nft_contract":settings.near_nft_contract,
        "auction_contract":settings.near_auction_contract,"genesis_checkpoint":settings.genesis_checkpoint,
        "nft_code_hash":settings.expected_nft_code_hash,"auction_code_hash":settings.expected_auction_code_hash,
        "economy_policy":"dedicated-accounts-calendar-month-v1" if settings.economy_enabled else "legacy",
        "vault_code_hash":settings.expected_vault_code_hash,"creator":settings.near_creator_account,"treasury":settings.near_treasury_account,
        "first_sunday":int(sunday.timestamp()),"window_seconds":61200,"beacon_hour_utc":18,
        "drand_chain_hash":CHAIN_HASH,"reconciliation_delay_seconds":settings.reconciliation_delay_seconds,
        "max_observation_age_seconds":settings.freeze_observation_max_age_seconds,
        "renderer_version":RENDERER_VERSION,"visual_features_version":FEATURE_VERSION,"family_policy":FAMILY_POLICY,
        "asset_mapping_policy":POLICY,"art_seed_policy":"registry-bound-v1",
        "canonical_schema":"echo-record-v1","odd_leaf_policy":"duplicate_last",
        "ai_policy":"first-valid-v1","ai_model":settings.near_ai_text_model,"allow_ai_fallback":settings.allow_ai_fallback,
        "freeze_policy":"latest complete consistent observation finished before fixed freeze; no late observations"}

def ensure_protocol(factory,settings):
    value=policy(settings);commitment=sha(canonical(value)).hex()
    with factory.begin() as db:
        if settings.app_env=="production" and db.scalar(select(Epoch.id).where(Epoch.mode!="live").limit(1)):
            raise ValueError("Production cannot share a database containing demo or replay epochs")
        row=db.get(Protocol,"active",with_for_update=True)
        if row is None:db.add(Protocol(id="active",commitment=commitment,payload=value))
        elif row.commitment!=commitment:raise ValueError("Published protocol configuration changed; use a new protocol/database")
    return commitment,value
