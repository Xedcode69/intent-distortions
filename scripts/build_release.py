"""Package separate source and static-demo deliverables, excluding secrets and runtime state."""
import hashlib
import json
import os
import yaml
from pathlib import Path
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"dist";OUT.mkdir(exist_ok=True)
EXCLUDED={"node_modules",".next","target","__pycache__",".pytest_cache",".venv",".git",".tools",".vendor","data","tests",".aws",".codex",".agents"}

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
package("near-echoes-demo.zip",demo,"static_educational_demo")

files={}
for folder in ["backend","frontend","signer","contracts","deploy","docs"]:
    for directory,dirs,names in os.walk(ROOT/folder):
        dirs[:]=sorted(d for d in dirs if d not in EXCLUDED and not d.endswith(".egg-info"))
        for name in sorted(names):
            if name.startswith(".env") or name.endswith((".pyc",".tsbuildinfo",".test.mjs")) or name in ("AGENTS.md","next-env.d.ts"):continue
            path=Path(directory)/name;files[path.relative_to(ROOT).as_posix()]=path.read_bytes()
            if folder=="signer" and name not in ("sign.mjs","package.json","package-lock.json"):
                del files[path.relative_to(ROOT).as_posix()]
for name in ["render.yaml","pyproject.toml","uv.lock",".python-version",".dockerignore",".env.production.example","LICENSE"]:
    path=ROOT/name
    if path.is_file():files[name]=path.read_bytes()
blueprint=yaml.safe_load(files["render.yaml"])
blueprint["services"]=[service for service in blueprint["services"] if service["name"]!="near-echoes-explainer"]
files["render.yaml"]=yaml.safe_dump(blueprint,sort_keys=False).encode()
for name in ["production_preflight.py","verify_epoch.py","export_artwork.py","validate_deployment.py"]:
    files[f"scripts/{name}"]=(ROOT/"scripts"/name).read_bytes()
for name in ["echo_nft.wasm","echo_auction.wasm"]:
    path=ROOT/"contracts/target/wasm32-unknown-unknown/release"/name
    if not path.exists():raise SystemExit("Build both current contract WASM artifacts before packaging")
    files[f"artifacts/{name}"]=path.read_bytes()
files["README.md"]=b"# NEAR ECHOES managed-cloud release candidate\n\nRead docs/managed-cloud.md and docs/VALIDATION.md before deployment. Source, lockfiles, contract WASM candidates, environment template and deployment definitions are included. No credentials or runtime data are packaged. The educational demo is distributed separately; this archive's Render Blueprint contains only production services. This archive has not passed live credentialed acceptance or independent security review and is not mainnet-ready.\n"
package("near-echoes-managed-cloud.zip",files,"managed_cloud_source_and_wasm")
