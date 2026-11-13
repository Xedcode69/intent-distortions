import copy
import json
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import Settings
from app.database import Base,Epoch
from app.services.asset_networks import (REGISTRY_URL,build_asset_mapping,validate_asset_mapping,
    fetch_asset_mapping,network_label,mapping_summary,mapped_seed)
from app.services.canonical_data import snapshot,canonical,sha
from app.services.art_statistics import statistics
from app.services.epoch_manager import run_epoch
from app.services.provenance import verify_artwork
from app.services.storage import ContentStore
from test_dataset import raw

TOKENS=[{"assetId":"nep141:sol.omft.near","blockchain":"sol"},
        {"assetId":"1cs_v1:btc:native:coin","blockchain":"btc"},
        {"assetId":"nep141:eth.omft.near","blockchain":"eth"}]


def dataset():
    return snapshot([raw(1,101,originAsset="nep141:sol.omft.near",destinationAsset="1cs_v1:btc:native:coin"),
                     raw(2,102,originAsset="nep141:eth.omft.near",destinationAsset="nep141:delisted.near")],100,200)


def test_exact_registry_lookup_and_explicit_unresolved_coverage():
    records=dataset();mapping=build_asset_mapping(TOKENS,records,observed_at=1)
    assert network_label("nep141:sol.omft.near",mapping)=="Solana"
    assert network_label("1cs_v1:btc:native:coin",mapping)=="Bitcoin"
    assert network_label("nep141:delisted.near",mapping)=="Unmapped"
    with pytest.raises(ValueError,match="absent"):
        network_label("nep141:eth-lookalike",mapping)
    coverage=mapping_summary(mapping,records)
    assert (coverage["resolved_assets"],coverage["unresolved_assets"])==(3,1)
    assert (coverage["source_records_mapped"],coverage["destination_records_mapped"])==(2,1)
    stats=statistics(records,100,200,mapping)
    assert stats["chains"]=={"Ethereum":1,"Solana":1}
    assert stats["unique_chains"]==2 and stats["chain_diversity_score"]==1
    assert stats["dominant_routes"]=={"Solana → Bitcoin":1,"Ethereum → Unmapped":1}


def test_unknown_bucket_does_not_count_as_a_recognized_chain():
    records=dataset();mapping=build_asset_mapping(TOKENS[1:],records,observed_at=1)
    stats=statistics(records,100,200,mapping)
    assert stats["unique_chains"]==1 and stats["chain_diversity_score"]==0
    assert stats["chains"]["Unmapped"]==1


def test_mapping_binds_seed_without_retrieval_time_or_unrelated_tokens_rerolls():
    records=dataset();first=build_asset_mapping(TOKENS,records,observed_at=1)
    later=build_asset_mapping(TOKENS+[{"assetId":"unused","blockchain":"near"}],records,observed_at=2)
    assert mapped_seed("01"*32,first)==mapped_seed("01"*32,later)
    changed=copy.deepcopy(TOKENS);changed[0]["blockchain"]="eth"
    assert mapped_seed("01"*32,first)!=mapped_seed("01"*32,build_asset_mapping(changed,records,observed_at=1))


def test_ambiguous_and_forged_registry_mappings_are_rejected():
    records=dataset()
    with pytest.raises(ValueError,match="Duplicate"):
        build_asset_mapping(TOKENS+[TOKENS[0]],records)
    mapping=build_asset_mapping(TOKENS,records,observed_at=1)
    mapping["assets"]["nep141:sol.omft.near"]="eth"
    with pytest.raises(ValueError,match="disagrees"):
        validate_asset_mapping(mapping,records)
    mapping=build_asset_mapping(TOKENS,records,observed_at=1)
    with pytest.raises(ValueError,match="disagrees"):
        validate_asset_mapping(mapping,records[:1])


async def test_fetch_freezes_identity_metadata_without_prices_or_authentication():
    def handler(request):
        assert str(request.url)==REGISTRY_URL and "Authorization" not in request.headers
        return httpx.Response(200,json=[{**token,"price":99,"symbol":"SAME"} for token in TOKENS])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        mapping=await fetch_asset_mapping(dataset(),client=client)
    assert all(set(row)=={"asset_id","blockchain"} for row in mapping["registry"])


async def test_mapped_artwork_replays_offline_and_refuses_frozen_mapping_changes(tmp_path):
    records=dataset();mapping=build_asset_mapping(TOKENS,records,observed_at=1)
    engine=create_engine(f"sqlite:///{tmp_path/'test.db'}");Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
    settings=Settings(_env_file=None,data_dir=tmp_path,execution_mode="demo",near_ai_api_key="",near_ai_text_model="")
    raw_rows=[raw(1,101,originAsset="nep141:sol.omft.near",destinationAsset="1cs_v1:btc:native:coin"),
              raw(2,102,originAsset="nep141:eth.omft.near",destinationAsset="nep141:delisted.near")]
    args=dict(number=1,mode="demo",raw=raw_rows,start=100,end=200,
              block={"hash":"11111111111111111111111111111111"},beacon={"randomness":"01"*32},
              selection={},source={"classification":"synthetic_fixture"},asset_mapping=mapping)
    artwork=await run_epoch(factory,settings,**args)
    store=ContentStore(tmp_path/'content')
    assert verify_artwork(store,artwork,True)["valid"]
    assert await run_epoch(factory,settings,**args)==artwork
    provenance=json.loads(store.get(artwork['provenance']['sha256']))
    wrong_proof=copy.deepcopy(provenance);wrong_proof['family_selection']['counter']+=1
    forged_proof={**artwork,'provenance':store.put(canonical(wrong_proof))}
    assert not verify_artwork(store,forged_proof,True)['checks']['verifiable_family_selection']
    forged=copy.deepcopy(artwork);forged["stats"]["network_mapping"]["resolved_assets"]=0
    assert not verify_artwork(store,forged,True)["valid"]
    changed=copy.deepcopy(mapping);changed["observed_at"]=2
    with pytest.raises(ValueError,match="Frozen network"):
        await run_epoch(factory,settings,**{**args,"asset_mapping":changed})
    engine.dispose()


async def test_failed_generation_cannot_resume_with_edited_network_mapping(tmp_path,monkeypatch):
    from app.services import epoch_manager
    async def unavailable(*args):
        raise RuntimeError("mock AI unavailable")
    monkeypatch.setattr(epoch_manager,"creative_direction",unavailable)
    records=dataset();mapping=build_asset_mapping(TOKENS,records,observed_at=1)
    engine=create_engine(f"sqlite:///{tmp_path/'retry.db'}");Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
    settings=Settings(_env_file=None,data_dir=tmp_path,execution_mode="demo",near_ai_api_key="",near_ai_text_model="")
    args=dict(number=1,mode="demo",raw=[],sealed_records=records,start=100,end=200,
              block={"hash":"11111111111111111111111111111111"},beacon={"randomness":"01"*32},selection={},
              source={"classification":"synthetic_fixture","snapshot_hash":sha(canonical(records)).hex()})
    with pytest.raises(RuntimeError,match="mock AI"):
        await run_epoch(factory,settings,**args,asset_mapping=mapping)
    with factory.begin() as db:
        epoch=db.get(Epoch,"demo-000001");edited=copy.deepcopy(epoch.payload)
        edited["asset_mapping"]["observed_at"]=2;epoch.payload=edited
    with pytest.raises(ValueError,match="mapping hash mismatch"):
        await run_epoch(factory,settings,**args)
    engine.dispose()
