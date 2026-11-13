import copy
import pytest
from app.services.canonical_data import snapshot, normalize,canonical,record_hash
from app.services.merkle import root,proof,verify

def raw(i=0,t=100,**extra):
    return {"depositAddress":f"deposit-{i}","depositMemo":None,"createdAtTimestamp":t,"originAsset":"nep141:eth-usdc","destinationAsset":"nep141:wrap.near","status":"SUCCESS","amountInUsd":"2.00",**extra}

def test_duplicates_and_half_open_boundaries():
    a,b,c=raw(0,100),raw(1,199),raw(2,200)
    assert len(snapshot([a,a,b,c,raw(3,99)],100,200))==2

def test_pending_not_eligible_and_delayed_success():
    a=raw(status="PROCESSING")
    assert snapshot([a],100,200)==[]
    a["status"]="SUCCESS"
    assert len(snapshot([a],100,200))==1

def test_shared_optional_hash_does_not_merge():
    assert len(snapshot([raw(1,intentHashes="same"),raw(2,intentHashes="same")],100,200))==2

def test_conflicting_identity_blocks_freeze():
    with pytest.raises(ValueError,match="Conflicting"):
        snapshot([raw(),raw(amountInUsd="3.00")],100,200)

def test_missing_hash_is_acceptable_missing_identity_is_not():
    assert normalize(raw())["public_record_identifier"]
    with pytest.raises(ValueError,match="Ambiguous"): normalize(raw(depositAddress=None))

@pytest.mark.parametrize("value",[1.1,"NaN","-1","Infinity",False])
def test_invalid_money(value):
    with pytest.raises(ValueError): normalize(raw(amountInUsd=value))

@pytest.mark.parametrize("value",[1.2,"100",None,False])
def test_invalid_timestamp(value):
    with pytest.raises(ValueError): normalize(raw(createdAtTimestamp=value))

def test_tie_breaking_and_input_order_independence():
    data=[raw(4),raw(1),raw(2)]
    assert snapshot(data,100,200)==snapshot(data[::-1],100,200)
    assert canonical({"b":None,"a":"2.00"})==b'{"a":"2.00","b":null}'

@pytest.mark.parametrize("count",[1,2,3,7,16])
def test_merkle_proofs_odd_leaf_and_tamper(count):
    records=snapshot([raw(i) for i in range(count)],100,200)
    for i,r in enumerate(records):
        assert verify(r,proof(records,i),root(records))
        changed={**r,"amount_in_usd":"999"}
        assert not verify(changed,proof(records,i),root(records))

def test_empty_tree_has_domain_separated_root():
    assert len(root([]))==64
    assert root([])!=root(snapshot([raw()],100,200))

def test_nanosecond_cutoff_is_not_rounded():
    assert len(snapshot([raw(1,100)],99,101,end_ns=100_000_000_001))==1
    assert len(snapshot([raw(1,100)],99,101,end_ns=100_000_000_000))==0
