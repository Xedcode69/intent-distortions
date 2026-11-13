import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import Settings
from app.database import Base,Artwork
from app.services.epoch_manager import run_demo,run_epoch,sunday_schedule
from app.services.provenance import verify_artwork
from app.services.storage import ContentStore
from app.services.art_seed import master_seed,GENESIS_HASH
from app.services.art_renderer import scene,render
from app.services.art_statistics import statistics
from app.services.near_ai import fallback,Direction
from app.services.canonical_data import snapshot
from test_dataset import raw

async def test_end_to_end_offline_and_idempotent(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'test.db'}");Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    settings=Settings(data_dir=tmp_path,execution_mode="demo",near_ai_api_key="",near_ai_text_model="")
    first=await run_demo(factory,settings);second=await run_demo(factory,settings)
    assert first==second
    store=ContentStore(tmp_path/"content")
    assert verify_artwork(store,first,True)["valid"]
    changed={**first,"seed":"ff"*32}
    assert not verify_artwork(store,changed)["valid"]
    assert first["nft"]["status"]=="not_minted"
    path=store.directory/first["image_hash"];path.write_bytes(b"tampered")
    with pytest.raises(ValueError,match="mismatch"):verify_artwork(store,first)

async def test_incomplete_live_dataset_is_rejected(tmp_path):
    with pytest.raises(ValueError,match="Incomplete"):
        await run_epoch(None,Settings(execution_mode="live",data_dir=tmp_path),number=1,mode="live",raw=[],start=1,end=2,block={},beacon={},selection={},source={})

def test_scene_changes_with_data_and_epoch_signature():
    records=snapshot([raw(i,100+i) for i in range(6)],100,200)
    stats=statistics(records,100,200);seed="01"*32;direction=fallback(seed,stats).model_dump()
    a=scene(seed,records,stats,direction,100,200,GENESIS_HASH,1)
    assert a==scene(seed,records,stats,direction,100,200,GENESIS_HASH,1)
    b=scene(seed,records,stats,direction,100,200,GENESIS_HASH,2)
    assert [s for s in a["shapes"] if s["layer"]=="signature"]!=[s for s in b["shapes"] if s["layer"]=="signature"]
    assert a!=scene("02"*32,records,stats,direction,100,200,GENESIS_HASH,1)

def test_statistics_missing_values_and_single_chain():
    records=snapshot([raw(0,100,amountInUsd=None)],100,200)
    s=statistics(records,100,200)
    assert s["chain_diversity_score"]==0 and s["volume_coverage"]==0 and s["public_volume_usd"]=="0"

def test_direction_rejects_untrusted_extra_rules():
    d=fallback("01"*32,{"chain_diversity_score":0}).model_dump()
    with pytest.raises(ValueError):Direction.validate_output({**d,"auction_minimum":"0"})
    with pytest.raises(ValueError):Direction.validate_output({**d,"palette":["red"]*3})

def test_utc_sunday_schedule():
    from datetime import datetime,timezone
    s=sunday_schedule(datetime(2026,11,12,tzinfo=timezone.utc))
    assert datetime.fromtimestamp(s["beacon_at"],timezone.utc)==datetime(2026,11,15,18,tzinfo=timezone.utc)
