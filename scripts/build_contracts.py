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
    shutil.copyfile(out / "echo_vault.wasm",embedded / "echo_vault.wasm")
    if args.test:
        subprocess.run([*cargo,"test","--locked",*common,"--workspace",*features],check=True,cwd=ROOT)
    subprocess.run([*cargo,"build","--locked","--release","--target","wasm32-unknown-unknown",*common,"--workspace",*features],check=True,cwd=ROOT)
    verify_build_profile(out, args.testnet_lab)
    hashes = {name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ("echo_vault.wasm","echo_nft.wasm","echo_auction.wasm","echo_market.wasm")}
    (embedded/"hashes.json").write_text(json.dumps(hashes,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(hashes,indent=2))

if __name__ == "__main__": main()
