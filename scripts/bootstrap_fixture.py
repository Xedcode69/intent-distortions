"""Create the published fixed synthetic fixture; never call this a live capture."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]

def main():
    start,end=1793577600,1794132000
    assets=["nep141:eth-usdc.omft.near","nep141:base-usdc.omft.near","nep141:sol-sol.omft.near","nep141:wrap.near","nep141:btc-btc.omft.near","nep141:arb-eth.omft.near"]
    records=[]
    for i in range(36):
        records.append({"originAsset":assets[i%6],"destinationAsset":assets[(i*3+1)%6],
            "depositAddress":f"SYNTHETIC-ONLY-{i:04d}","depositMemo":None,"status":"SUCCESS",
            "createdAtTimestamp":start+(i*15401+211)% (end-start),"intentHashes":None,
            "amountInUsd":None if i%9==0 else f"{(i*137+53)%8000}.{i*17%100:02d}","amountOutUsd":None})
    directory=ROOT/"fixtures/sample-epoch"; directory.mkdir(parents=True,exist_ok=True)
    fixture={"start":start,"end":end,"source":{"classification":"synthetic_fixture","complete":False,"reconciled":False,
        "description":"36 explicitly fabricated swap-shaped records for local engineering demonstration. Not historical swaps.","origin":"scripts/bootstrap_fixture.py"},"records":records}
    (directory/"transactions.json").write_text(json.dumps(fixture,indent=2)+"\n",encoding="utf-8")
    evidence={"block":{"height":0,"hash":"11111111111111111111111111111111","timestamp_ns":str(end*10**9),"timestamp_seconds":end,"rpc_network":"fixture","verified":False},
        "beacon":{"round":0,"randomness":hashlib.sha256(b"NEAR_ECHOES_SYNTHETIC_DEMO_V1").hexdigest(),"signature":"","verified":False,"network":"synthetic_fixture"},
        "selection":{"algorithm":"predetermined-demo-fixture","selected_timestamp":end,"verified":False}}
    # Never replace subsequently captured real evidence.
    if not (directory/"evidence.json").exists():
        (directory/"evidence.json").write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__": main()
