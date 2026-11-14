"""Build the vault first, then embed those exact bytes in the NFT factory."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def wasm_exports(data):
    """Read the actual export section, rather than matching debug/name strings."""
    def integer(offset):
        value = shift = 0
        while True:
            byte = data[offset]; offset += 1
            value |= (byte & 127) << shift
            if byte < 128: return value, offset
            shift += 7
    offset = 8
    while offset < len(data):
        section = data[offset]; size, offset = integer(offset + 1)
        end = offset + size
        if section == 7:
            count, offset = integer(offset); names = set()
            for _ in range(count):
                length, offset = integer(offset)
                names.add(data[offset:offset+length].decode("utf-8")); offset += length + 1
                _, offset = integer(offset)
            return names
        offset = end
    return set()


def verify_build_profile(out, lab):
    for name in ("echo_nft.wasm", "echo_auction.wasm", "echo_market.wasm"):
        exports = wasm_exports((out / name).read_bytes())
        for method in ("lab_set_time", "new_testnet_lab"):
            if (method in exports) != lab:
                raise RuntimeError(f"Unexpected lab exports in {name}; refusing to publish build hashes")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--optimizer-js",type=Path,help="Verified Binaryen 125 wasm-opt.js")
    parser.add_argument("--testnet-lab", action="store_true", help="Separate clock-controlled testnet artifacts; never deploy these to mainnet")
    args = parser.parse_args()
    cargo = ["cargo", "+1.95.0"]
    manifest = str(ROOT / "contracts/Cargo.toml")
    target = ROOT / ("contracts/target/testnet-lab" if args.testnet_lab else "contracts/target")
    common = ["--manifest-path", manifest, "--target-dir", str(target)]
    features = ["--features", "echo-nft/testnet-lab,echo-auction/testnet-lab,echo-market/testnet-lab"] if args.testnet_lab else []
    subprocess.run([*cargo,"build","--locked","--release","--target","wasm32-unknown-unknown",*common,"-p","echo-vault"],check=True,cwd=ROOT)
    out = target / "wasm32-unknown-unknown/release"
    embedded = ROOT / ("contracts/artifacts/testnet-lab" if args.testnet_lab else "contracts/artifacts")
    embedded.mkdir(parents=True, exist_ok=True)
    node=shutil.which("node") or next((str(p) for p in (ROOT/".tools").glob("node-*/node.exe")),None)
    def optimize(path):
        if args.optimizer_js:
            if not node:raise RuntimeError("Node 22 required")
            version=subprocess.run([node,str(args.optimizer_js),"--version"],capture_output=True,text=True,check=True)
            if version.stdout.strip()!="wasm-opt version 125 (version_125)":raise RuntimeError("Binaryen 125 required")
            subprocess.run([node,str(args.optimizer_js),str(path),"-Oz","--enable-bulk-memory","--enable-sign-ext",
                "--enable-nontrapping-float-to-int","--enable-mutable-globals","-o",str(path)],check=True)
    optimize(out/"echo_vault.wasm")
    shutil.copyfile(out / "echo_vault.wasm",embedded / "echo_vault.wasm")
    if args.test:
        subprocess.run([*cargo,"test","--locked",*common,"--workspace",*features],check=True,cwd=ROOT)
    subprocess.run([*cargo,"build","--locked","--release","--target","wasm32-unknown-unknown",*common,"--workspace",*features],check=True,cwd=ROOT)
    shutil.copyfile(embedded/"echo_vault.wasm",out/"echo_vault.wasm")
    verify_build_profile(out, args.testnet_lab)
    for name in ("echo_nft.wasm","echo_auction.wasm","echo_market.wasm"):optimize(out/name)
    hashes = {name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ("echo_vault.wasm","echo_nft.wasm","echo_auction.wasm","echo_market.wasm")}
    (embedded/"hashes.json").write_text(json.dumps(hashes,indent=2)+"\n",encoding="utf-8")
    if not args.testnet_lab:
        destination=ROOT/"contracts/artifacts/testnet";destination.mkdir(parents=True,exist_ok=True)
        for name in hashes:shutil.copyfile(out/name,destination/name)
        binary=destination/("render_recipe.exe" if __import__('os').name=="nt" else "render_recipe")
        subprocess.run(["rustc","+1.95.0","--edition=2021","-O",str(ROOT/"contracts/onchain-art/examples/render_recipe.rs"),"-o",str(binary)],check=True)
        (destination/"build.json").write_text(json.dumps({"network":"testnet","format":"intent-distortions-weekly-onchain-v1",
            "clock":"real_block_timestamp","artifacts":{name:{"sha256":digest,"bytes":(destination/name).stat().st_size} for name,digest in hashes.items()}},indent=2)+"\n")
    print(json.dumps(hashes,indent=2))

if __name__ == "__main__": main()
