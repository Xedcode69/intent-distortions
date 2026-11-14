"""Package separate source and static-demo deliverables, excluding secrets and runtime state."""
import hashlib
import json
import os
import yaml
from pathlib import Path
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"dist";OUT.mkdir(exist_ok=True)
EXCLUDED={"node_modules",".next",".next-replay",".next-testnet","target","__pycache__",".pytest_cache",".venv",".git",".tools",".vendor","data","tests",".aws",".codex",".agents"}

def digest(data):return hashlib.sha256(data).hexdigest()

def package(name,files,kind):
    manifest={"schema":"echo-release-bundle-v1","kind":kind,"release_status":"educational_demo" if kind=="static_educational_demo" else "candidate_pending_live_acceptance",
        "secrets_included":False,"mainnet_ready":False,"files":{name:{"sha256":digest(data),"bytes":len(data)} for name,data in sorted(files.items())}}
    encoded=(json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode()
    with ZipFile(OUT/name,"w",compression=ZIP_DEFLATED,compresslevel=9) as archive:
        for relative,data in sorted({**files,"release-manifest.json":encoded}.items()):
            info=ZipInfo(relative,date_time=(1980,1,1,0,0,0));info.compress_type=ZIP_DEFLATED
            info.external_attr=0o644<<16;archive.writestr(info,data)
    (OUT/(name.removesuffix(".zip")+".manifest.json")).write_bytes(encoded)
    print(f"{name}: {len(files)} files; SHA-256 {digest((OUT/name).read_bytes())}")

demo_names=["index.html","styles.css","app.mjs","core.mjs","assets/artwork.png","assets/artwork.svg","assets/thumbnail.webp","assets/scene.json","assets/example.json"]
demo={name:(ROOT/"demo"/name).read_bytes() for name in demo_names}
demo["README.txt"]=b"Standalone educational demo. Serve this directory on localhost or HTTPS. All records and blockchain evidence are synthetic; no credentials, wallet or API required. See the repository's demo/README.md for verification instructions.\n"
package("intent-distortions-demo.zip",demo,"static_educational_demo")

files={}
for folder in ["backend","frontend","signer","contracts","deploy","docs"]:
    for directory,dirs,names in os.walk(ROOT/folder):
        dirs[:]=sorted(d for d in dirs if d not in EXCLUDED and not d.startswith(".next-") and not d.endswith(".egg-info"))
        if folder=="contracts":dirs[:]=[d for d in dirs if d!="artifacts"]
        for name in sorted(names):
            if name.startswith(".env") or name.endswith((".pyc",".tsbuildinfo")) or (name.endswith(".test.mjs") and folder!="contracts") or name in ("AGENTS.md","next-env.d.ts"):continue
            path=Path(directory)/name;files[path.relative_to(ROOT).as_posix()]=path.read_bytes()
            if folder=="signer" and name not in ("sign.mjs","package.json","package-lock.json"):
                del files[path.relative_to(ROOT).as_posix()]
for name in ["render.yaml","pyproject.toml","uv.lock",".python-version",".dockerignore",".env.production.example",".env.replay.example","LICENSE"]:
    path=ROOT/name
    if path.is_file():files[name]=path.read_bytes()
blueprint=yaml.safe_load(files["render.yaml"])
blueprint["services"]=[service for service in blueprint["services"] if service["name"]!="intent-distortions-explainer"]
files["render.yaml"]=yaml.safe_dump(blueprint,sort_keys=False).encode()
for name in ["production_preflight.py","verify_epoch.py","export_artwork.py","validate_deployment.py","test_historical_week.py","serve_replay.py","publish_replay_demo.py","build_contracts.py","build_onchain_art.py","prepare_onchain_art.py","onchain_art_testnet.py","test_economy_sandbox.ps1","testnet_rehearsal.py","serve_testnet.py"]:
    files[f"scripts/{name}"]=(ROOT/"scripts"/name).read_bytes()
for name in ("verified-beacon.json", "transactions.json", "evidence.json"):
    files[f"fixtures/sample-epoch/{name}"]=(ROOT/f"fixtures/sample-epoch/{name}").read_bytes()
for name in ["echo_nft.wasm","echo_auction.wasm","echo_vault.wasm","echo_market.wasm"]:
    path=ROOT/"contracts/target/wasm32-unknown-unknown/release"/name
    if not path.exists():raise SystemExit("Build both current contract WASM artifacts before packaging")
    files[f"artifacts/{name}"]=path.read_bytes()
onchain_files={}
onchain_dir=ROOT/"contracts/artifacts/onchain-v1"
if (onchain_dir/"build.json").is_file():
    build=json.loads((onchain_dir/"build.json").read_bytes())
    artifact=(onchain_dir/"intent_onchain_art.wasm").read_bytes()
    if digest(artifact)!=build["sha256"] or len(artifact)!=build["bytes"]:raise SystemExit("Onchain study artifact differs from its reviewed build manifest")
    onchain_files={"artifacts/onchain-v1/intent_onchain_art.wasm":artifact,"artifacts/onchain-v1/build.json":(onchain_dir/"build.json").read_bytes()}
    files.update(onchain_files)
files["README.md"]=b"# Intent Distortions managed-cloud release candidate\n\nRead docs/managed-cloud.md and docs/VALIDATION.md before deployment. Source, lockfiles, contract WASM candidates, environment template and deployment definitions are included. No credentials or runtime data are packaged. The educational demo is distributed separately; this archive's Render Blueprint contains only production services. This archive has not passed live credentialed acceptance or independent security review and is not mainnet-ready.\n"
package("intent-distortions-managed-cloud.zip",files,"managed_cloud_source_and_wasm")

# Never mix the clock-controlled binaries into the production artifact set.
lab_files={name:data for name,data in files.items() if not name.startswith("artifacts/")}
lab_files.update(onchain_files)
for name in ("echo_nft.wasm","echo_auction.wasm","echo_vault.wasm","echo_market.wasm"):
    path=ROOT/"contracts/target/testnet-lab/wasm32-unknown-unknown/release"/name
    if not path.is_file():raise SystemExit("Build --testnet-lab before packaging the testnet release")
    lab_files[f"artifacts/testnet-lab/{name}"]=path.read_bytes()
lab_files["README.md"]=b"# Intent Distortions testnet lab\n\nRead docs/TESTNET_LAB.md and docs/reports/testnet-deployment-2026-11-14.md. Initial testnet deployment, genesis mint and synthetic auction setup are verified; full financial and browser wallet acceptance remain pending. Separate testnet accounts, controlled clock and known historical drand entropy. These binaries must never be deployed to mainnet. No credentials, prepared private workspace or raw historical capture are included.\n"
package("intent-distortions-testnet-lab.zip",lab_files,"testnet_lab_source_and_wasm")
