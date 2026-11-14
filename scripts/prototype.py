"""One testnet prototype: configure, review/deploy fresh contracts, or serve locally.

Credentials stay in .env / OS keychain. Raw data and signed journals stay in data/.
"""
import argparse,asyncio,base64,hashlib,json,os,re,shutil,subprocess,sys,time
from contextlib import contextmanager
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"));sys.path.insert(0,str(ROOT))
os.environ.setdefault("ECHOES_ENV_FILE",str(ROOT/".env"))

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8");tmp.replace(path)
def digest(value):
    from app.services.canonical_data import canonical
    return hashlib.sha256(canonical(value)).hexdigest()

@contextmanager
def operator_lock(directory):
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/"operator.lock").open("a+b") as lock:
        lock.seek(0);lock.write(b"0");lock.flush();lock.seek(0)
        try:
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise ValueError("Another prototype operator holds the workspace lock") from None
        try:yield
        finally:
            lock.seek(0)
            if os.name=="nt":msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)

async def recover(settings,role):
    from app.services.near_rpc import NearRPC
    from app.services.signed_call import inspect_signed_bootstrap
    path=settings.data_dir/"deployment-journal.json";journal=json.loads(path.read_text())
    if role not in journal:raise ValueError("No saved deployment for that role")
    row=journal[role];expected=next(o for o in plan(settings)["operations"] if o["role"]==role)
    if row["expected"]!=expected:raise ValueError("Saved deployment differs from the current plan")
    info=inspect_signed_bootstrap(row["signed_transaction"],expected)
    if info["transaction_hash"]!=row["transaction_hash"]:raise ValueError("Saved transaction hash differs")
    rpc=NearRPC(settings.near_rpc_url)
    if (await rpc.call("status",{}))["chain_id"]!="testnet":raise ValueError("Testnet RPC required")
    # Read only: unavailable/expired transactions remain unknown, never re-signed.
    receipt=await rpc.call("tx",{"tx_hash":info["transaction_hash"],"sender_account_id":expected["signer"],"wait_until":"FINAL"})
    if receipt.get("final_execution_status")!="FINAL":raise ValueError("Exact transaction is not FINAL yet")
    row["status"]="succeeded" if "SuccessValue" in receipt.get("status",{}) and not any("Failure" in r["outcome"]["status"] for r in receipt.get("receipts_outcome",[])) else "failed"
    write(path,journal);write(settings.data_dir/("receipt-"+info["transaction_hash"]+".json"),receipt)
    print(json.dumps({"role":role,"status":row["status"],"transaction_url":"https://testnet.nearblocks.io/txns/"+info["transaction_hash"]}))

def configure():
    from dotenv import dotenv_values
    import secrets
    old={}
    for name in (".env",".env.replay"):
        for key,value in dotenv_values(ROOT/name).items():
            if value:old[key]=value
    prior=ROOT/"data/testnet-rehearsals/full-lab/profile.env"
    if prior.is_file():
        for key,value in dotenv_values(prior).items():
            if key=="NEAR_RPC_URL" and value:old[key]=value
    values={key:old[key] for key in ("NEAR_INTENTS_PARTNER_JWT","NEAR_AI_API_KEY","NEAR_AI_TEXT_MODEL","NEAR_RPC_URL","NEAR_MAINNET_RPC_URL","NEAR_AI_BASE_URL") if key in old}
    directory=ROOT/"data/prototype";directory.mkdir(parents=True,exist_ok=True)
    values.update(APP_ENV="development",EXECUTION_MODE="live",SERVICE_ROLE="api",ECHOES_ROOT=str(ROOT),
        DATA_DIR=str(directory),DATABASE_URL=f"sqlite:///{(directory/'prototype.db').as_posix()}",
        STORAGE_PROVIDER="local_content_addressed",NEAR_NETWORK="testnet",SCHEDULER_ENABLED="false",ENABLE_CHAIN_WRITES="false",
        PROTOCOL_ID="intent-distortions-testnet-weekly-v1",FIRST_RELEASE_SUNDAY="2026-11-15",GENESIS_CHECKPOINT="1794097030",
        GENESIS_CHECKPOINT_NS="1794097030218994184",GENESIS_IMAGE_HASH="b870866d3f2eded46854edaf3f941ddd8f8bdf3d820ca5a413aa253893b2424b",
        ONCHAIN_ART_CONTRACT="art-v1.id-operator.testnet",ONCHAIN_ART_TOKEN_ID="ONCHAIN-PROTOTYPE-000001",
        EXPECTED_ONCHAIN_ART_CODE_HASH="d9bac8e086fc4a43851abec3d954cf77f1cf7e04a101f369ae085d916e347d6a",
        NEAR_MINTER_ACCOUNT="id-operator.testnet",NEAR_CREATOR_ACCOUNT="id-team.testnet",NEAR_TREASURY_ACCOUNT="id-treasury.testnet",
        NEAR_NFT_CONTRACT="weekly-nft.id-operator.testnet",NEAR_AUCTION_CONTRACT="weekly-auction.id-operator.testnet",
        NEAR_MARKET_CONTRACT="weekly-market.id-operator.testnet",ALLOW_AI_FALLBACK="false",MARKETPLACE_CROSSCHAIN_ENABLED="false",
        PUBLIC_ORIGIN="http://127.0.0.1:3000",CORS_ORIGIN="http://127.0.0.1:3000",ADMIN_TOKEN=old.get("ADMIN_TOKEN") or secrets.token_hex(32),
        ONCHAIN_RENDERER_BINARY=str(ROOT/"contracts/artifacts/testnet"/("render_recipe.exe" if os.name=="nt" else "render_recipe")))
    build=ROOT/"contracts/artifacts/testnet/build.json"
    if build.is_file():
        info=json.loads(build.read_text())
        values.update({f"EXPECTED_{role.upper()}_CODE_HASH":info["artifacts"][f"echo_{role}.wasm"]["sha256"] for role in ("nft","auction","market","vault")})
    # Complete replacement intentionally drops Cloudflare/artifact/S3 credentials.
    (ROOT/".env").write_text("# Intent Distortions - testnet prototype only. Never commit.\n"+
        "\n".join(key+"="+json.dumps(value) for key,value in values.items())+"\n",encoding="utf-8")
    print(json.dumps({"configured":".env","network":"testnet","credentials_preserved":[key for key in ("NEAR_INTENTS_PARTNER_JWT","NEAR_AI_API_KEY","NEAR_AI_TEXT_MODEL") if values.get(key)],"signing":"disabled until explicitly configured"}))

def plan(settings):
    directory=ROOT/"contracts/artifacts/testnet";build=json.loads((directory/"build.json").read_text())
    if build.get("network")!="testnet" or build.get("clock")!="real_block_timestamp":raise ValueError("Build the real-clock testnet contracts first")
    operations=[]
    for role in ("nft","auction","market"):
        account=getattr(settings,f"near_{role}_contract")
        if not account.endswith("."+settings.near_minter_account) or account in ("id-nft.testnet","id-auction.testnet","id-marketplace.testnet"):
            raise ValueError("Use fresh direct operator subaccounts; old rehearsal accounts are preserved")
        name=f"echo_{role}.wasm";code=directory/name;expected=build["artifacts"][name]
        if hashlib.sha256(code.read_bytes()).hexdigest()!=expected["sha256"] or getattr(settings,f"expected_{role}_code_hash")!=expected["sha256"]:
            raise ValueError("Build and environment code pins differ; configure the fresh profile")
        if role=="nft":method="new_economy";args={"owner_id":settings.near_minter_account,"minter":settings.near_minter_account,
            "auction_contract":settings.near_auction_contract,"creator":settings.near_creator_account,"treasury":settings.near_treasury_account}
        elif role=="auction":method="new_economy";args={"owner":settings.near_minter_account,"nft_contract":settings.near_nft_contract,
            "creator":settings.near_creator_account,"treasury":settings.near_treasury_account,"min_bid":str(10**24),"increment":str(10**23)}
        else:method="new";args={"nft_contract":settings.near_nft_contract,"primary_auction":settings.near_auction_contract,"creator":settings.near_creator_account}
        operations.append({"role":role,"signer":settings.near_minter_account,"contract":account,"code_sha256":expected["sha256"],
            "wasm":name,"deposit_yocto":str((expected["bytes"]+5000)*10**19),"method":method,"args":args,"gas":60*10**12})
    return {"schema":"intent-distortions-testnet-deployment-v1","network":"testnet","keys_added":0,"operations":operations}

async def deploy(settings,value,send):
    from app.services.near_rpc import NearRPC
    from app.services.signed_call import inspect_signed_bootstrap
    import base58
    directory=settings.data_dir;directory.mkdir(parents=True,exist_ok=True)
    journal_path=directory/"deployment-journal.json";journal=json.loads(journal_path.read_text()) if journal_path.exists() else {}
    rpc=NearRPC(settings.near_rpc_url,budget_seconds=45)
    if (await rpc.call("status",{}))["chain_id"]!="testnet":raise ValueError("Testnet RPC required")
    near=shutil.which("near") or (str(Path(os.environ.get("PROGRAMFILES","C:/Program Files"))/"near-cli-rs/bin/near.exe") if os.name=="nt" else None)
    for op in value["operations"]:
        account=None
        try:account=await rpc.call("query",{"request_type":"view_account","finality":"final","account_id":op["contract"]})
        except RuntimeError as exc:
            if "UNKNOWN_ACCOUNT" not in str(exc):raise
        if account:
            if base58.b58decode(account["code_hash"]).hex()!=op["code_sha256"]:raise ValueError("Existing account has different code; refusing upgrade")
            keys=await rpc.call("query",{"request_type":"view_access_key_list","finality":"final","account_id":op["contract"]})
            if keys.get("keys")!=[]:raise ValueError("Deployed contracts must be keyless")
            continue
        if not send:continue
        if any(row["status"]=="unknown" for row in journal.values()):raise ValueError("Reconcile the exact pending transaction before new signing")
        if op["role"] in journal:raise ValueError("Inspect the prior failed deployment; do not sign it again")
        command=[near,"transaction","construct-transaction",op["signer"],"receiver-id",op["contract"],"add-action","create-account",
            "add-action","transfer",op["deposit_yocto"]+" yoctoNEAR","add-action","deploy-contract","use-file",str(ROOT/"contracts/artifacts/testnet"/op["wasm"]),
            "with-init-call",op["method"],"json-args",json.dumps(op["args"]),"prepaid-gas","60 Tgas","attached-deposit","0 NEAR",
            "skip","network-config","testnet","sign-with-keychain","display"]
        result=subprocess.run(command,capture_output=True,text=True,timeout=180)
        if result.returncode:raise ValueError("NEAR CLI keychain signing failed before broadcast")
        candidates=re.findall(r"(?m)^[A-Za-z0-9+/]{100,}={0,2}$",result.stdout+"\n"+result.stderr)
        if len(candidates)!=1:raise ValueError("Expected one signed transaction; nothing broadcast")
        encoded=candidates[0];info=inspect_signed_bootstrap(encoded,op)
        journal[op["role"]]={"status":"unknown","expected":op,"signed_transaction":encoded,**info};write(journal_path,journal)
        await rpc.call("broadcast_tx_commit",[encoded])
        receipt=await rpc.call("tx",{"tx_hash":info["transaction_hash"],"sender_account_id":op["signer"],"wait_until":"FINAL"})
        ok=receipt.get("final_execution_status")=="FINAL" and "SuccessValue" in receipt.get("status",{}) and not any("Failure" in r["outcome"]["status"] for r in receipt.get("receipts_outcome",[]))
        journal[op["role"]]["status"]="succeeded" if ok else "failed";write(journal_path,journal)
        write(directory/("receipt-"+info["transaction_hash"]+".json"),receipt)
        print(json.dumps({"contract":op["contract"],"success":ok,"transaction_url":"https://testnet.nearblocks.io/txns/"+info["transaction_hash"]}),flush=True)
        if not ok:raise ValueError("Deployment finalized with failure; inspect the saved receipt")
    if send:
        from app.services.preflight import validate_contracts
        await validate_contracts(settings,rpc)
        write(directory/"deployment-verified.json",{"network":"testnet","plan_sha256":digest(value),"verified":True})

def serve():
    from scripts.serve_replay import stop_process
    import socket
    for port in (8000,3000):
        with socket.socket() as probe:
            try:probe.bind(("127.0.0.1",port))
            except OSError:raise ValueError(f"Port {port} is already in use") from None
    node=shutil.which("node") or next((str(p) for p in (ROOT/".tools").glob("node-*/node.exe")),None)
    if not node:raise ValueError("Install Node 22")
    env={**os.environ,"ECHOES_ENV_FILE":str(ROOT/".env"),"SERVICE_ROLE":"api","SCHEDULER_ENABLED":"false","ENABLE_CHAIN_WRITES":"false"}
    keep={"PATH","PATHEXT","SYSTEMROOT","WINDIR","COMSPEC","TEMP","TMP","HOME","USERPROFILE","APPDATA","LOCALAPPDATA","NODE_EXTRA_CA_CERTS"}
    web_env={k:v for k,v in os.environ.items() if k.upper() in keep};web_env.update(BACKEND_URL="http://127.0.0.1:8000",APP_PROFILE="testnet",NEXT_TELEMETRY_DISABLED="1")
    flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
    logs=ROOT/"data/prototype/logs";logs.mkdir(parents=True,exist_ok=True)
    api_log=(logs/"api.log").open("a",encoding="utf-8");web_log=(logs/"web.log").open("a",encoding="utf-8")
    api=web=None
    try:
        api=subprocess.Popen([sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000"],cwd=ROOT,env=env,creationflags=flags,start_new_session=os.name!="nt",stdout=api_log,stderr=subprocess.STDOUT)
        web=subprocess.Popen([node,"node_modules/next/dist/bin/next","dev","--hostname","127.0.0.1","--port","3000"],cwd=ROOT/"frontend",env=web_env,creationflags=flags,start_new_session=os.name!="nt",stdout=web_log,stderr=subprocess.STDOUT)
        write(ROOT/"data/prototype/servers.json",{"launcher":os.getpid(),"api":api.pid,"web":web.pid})
        print("Intent Distortions testnet: http://127.0.0.1:3000 - Ctrl+C stops both servers",flush=True)
        while api.poll() is None and web.poll() is None:time.sleep(.5)
    except KeyboardInterrupt:pass
    finally:
        for child in (web,api):stop_process(child)
        api_log.close();web_log.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("command",choices=("configure","plan","deploy","recover","serve"));p.add_argument("--send",action="store_true");p.add_argument("--plan-sha256");p.add_argument("--role",choices=("nft","auction","market"))
    a=p.parse_args()
    if a.command=="configure":return configure()
    if a.command=="serve":return serve()
    from app.config import settings
    if a.command=="recover":
        if not a.role:raise ValueError("Choose the saved --role")
        with operator_lock(settings.data_dir):asyncio.run(recover(settings,a.role))
        return
    value=plan(settings);sha=digest(value)
    if a.command=="plan":
        write(settings.data_dir/"deployment-plan.json",value)
        print(json.dumps({"plan":value,"plan_sha256":sha,"estimated_setup_yocto":str(sum(int(o['deposit_yocto']) for o in value['operations'])),"signed":False},indent=2));return
    if not a.send or a.plan_sha256!=sha:raise ValueError("Review plan and supply --send --plan-sha256")
    with operator_lock(settings.data_dir):asyncio.run(deploy(settings,value,True))

if __name__=="__main__":
    try:main()
    except Exception as exc:
        # Provider errors and CLI output can contain secrets; no raw exception dump.
        print(json.dumps({"status":"stopped","error_type":type(exc).__name__,"reason":str(exc) if type(exc) is ValueError else "Inspect local configuration and operator journal"}));raise SystemExit(1)
