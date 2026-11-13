"""Build the vault first, then embed those exact bytes in the NFT factory."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    cargo = ["cargo", "+1.95.0"]
    manifest = str(ROOT / "contracts/Cargo.toml")
    subprocess.run([*cargo,"build","--locked","--release","--target","wasm32-unknown-unknown","--manifest-path",manifest,"-p","echo-vault"],check=True,cwd=ROOT)
    out = ROOT / "contracts/target/wasm32-unknown-unknown/release"
    embedded = ROOT / "contracts/artifacts"
    embedded.mkdir(exist_ok=True)
    shutil.copyfile(out / "echo_vault.wasm",embedded / "echo_vault.wasm")
    if args.test:
        subprocess.run([*cargo,"test","--locked","--manifest-path",manifest,"--workspace"],check=True,cwd=ROOT)
    subprocess.run([*cargo,"build","--locked","--release","--target","wasm32-unknown-unknown","--manifest-path",manifest,"--workspace"],check=True,cwd=ROOT)
    hashes = {name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ("echo_vault.wasm","echo_nft.wasm","echo_auction.wasm")}
    (embedded/"hashes.json").write_text(json.dumps(hashes,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(hashes,indent=2))

if __name__ == "__main__": main()
