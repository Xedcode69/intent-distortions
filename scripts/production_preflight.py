"""Validate deployment configuration and optionally read live dependencies. Never signs."""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))

async def check(online):
    from app.config import settings
    from app.services.protocol import policy
    from app.services.canonical_data import canonical,sha
    if settings.app_env!="production" or settings.execution_mode!="live":raise ValueError("Production/live profile required")
    value=policy(settings)
    report={"configuration":"valid","policy_commitment":sha(canonical(value)).hex(),"network":settings.near_network,
        "chain_writes_enabled":settings.enable_chain_writes,"online_checks":"not_run","ready_for_mainnet":False}
    if not online:return report
    from app.database import init_db,Epoch
    from sqlalchemy import select,text
    factory=init_db(create_schema=False)
    with factory() as db:
        if db.scalar(text("SELECT version_num FROM alembic_version"))!="0002":raise ValueError("Database migrations are not current")
        first=db.scalar(select(Epoch.id).where(Epoch.mode=="live").limit(1))
    if not first and value["first_sunday"]+18*3600+settings.reconciliation_delay_seconds<=time.time():
        raise ValueError("Initial freeze has passed; choose a future first Sunday before committing a new protocol")
    from app.services.preflight import validate_contracts
    report["chain"]=await validate_contracts(settings)
    from app.services.near_rpc import NearRPC
    if (await NearRPC(settings.near_mainnet_rpc_url).call("status",{}))["chain_id"]!="mainnet":raise ValueError("Source block RPC must be mainnet")
    from app.services.storage import content_store
    store=content_store(settings)
    versioning=store.client.get_bucket_versioning(Bucket=settings.s3_bucket)
    lock=store.client.get_object_lock_configuration(Bucket=settings.s3_bucket)
    if versioning.get("Status")!="Enabled" or lock.get("ObjectLockConfiguration",{}).get("ObjectLockEnabled")!="Enabled":
        raise ValueError("S3 versioning and Object Lock required")
    retention=lock.get("ObjectLockConfiguration",{}).get("Rule",{}).get("DefaultRetention",{})
    if retention.get("Mode")!="COMPLIANCE" or retention.get("Days",0)<3650:raise ValueError("Published ten-year compliance retention required")
    report["storage"]="versioning_and_object_lock_enabled"
    if settings.service_role=="worker":
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            explorer=await client.get(settings.near_intents_explorer_url+"/transactions",params={"numberOfTransactions":1,"direction":"prev","statuses":"SUCCESS","showTestTxs":"false"},headers={"Authorization":f"Bearer {settings.near_intents_partner_jwt}"})
            explorer.raise_for_status()
            if not isinstance(explorer.json(),list):raise ValueError("Explorer response schema mismatch")
            models=await client.get(settings.near_ai_base_url+"/models",headers={"Authorization":f"Bearer {settings.near_ai_api_key}"})
            models.raise_for_status()
            if settings.near_ai_text_model not in {m["id"] for m in models.json()["data"]}:raise ValueError("Configured AI model is not in the live catalog")
        report["integrations"]="Explorer authentication and AI model catalog verified; no generation requested"
    report["online_checks"]="passed"
    report["release_gates"]="Still requires recorded end-to-end testnet lifecycle and independent contract/security review"
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--online",action="store_true");args=parser.parse_args()
    try:print(json.dumps(asyncio.run(check(args.online)),indent=2))
    except Exception as exc:
        # Do not print exception bodies: provider errors can include authentication-bearing URLs.
        print(json.dumps({"configuration_or_dependency":"failed","error_type":type(exc).__name__,"hint":"Check the service-scoped production environment and deployment guide; no signing was attempted."}));raise SystemExit(1)
