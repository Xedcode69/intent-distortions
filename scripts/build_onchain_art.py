"""Build the separate immutable-art contract; optionally optimize with Binaryen 125."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.build_contracts import wasm_exports
ALLOWED={"append_recipe","begin_edition","contract_source_metadata","get_animated_svg","get_config","get_edition",
         "get_recipe_chunk","get_static_svg","new","nft_metadata","nft_resolve_transfer","nft_supply_for_owner","nft_token",
         "nft_tokens","nft_tokens_for_owner","nft_total_supply","nft_transfer","nft_transfer_call","seal_and_mint","memory","__data_end","__heap_base"}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test',action='store_true')
    parser.add_argument('--optimizer-js',type=Path,help='Official Binaryen 125 wasm-opt.js; do not use an unpinned optimizer')
    parser.add_argument('--target-dir',type=Path,default=ROOT/'contracts/target/testnet-lab')
    args=parser.parse_args()
    common=['--locked','--manifest-path',str(ROOT/'contracts/Cargo.toml'),'--target-dir',str(args.target_dir),'-p','intent-onchain-art']
    if args.test:subprocess.run(['cargo','+1.95.0','test',*common,'--lib'],check=True)
    subprocess.run(['cargo','+1.95.0','build',*common,'--release','--target','wasm32-unknown-unknown'],check=True)
    source=args.target_dir/'wasm32-unknown-unknown/release/intent_onchain_art.wasm'
    output=ROOT/'contracts/artifacts/onchain-v1';output.mkdir(parents=True,exist_ok=True)
    target=output/'intent_onchain_art.wasm'
    if args.optimizer_js:
        # These are the two files in the checksum-pinned official Node release.
        node=shutil.which('node') or next((str(p) for p in (ROOT/'.tools').glob('node-*/node.exe')),None)
        if not node:raise ValueError('Node 22 is required for the Binaryen Node optimizer')
        optimizer=args.optimizer_js.resolve()
        result=subprocess.run([node,str(optimizer),'--version'],check=True,capture_output=True,text=True)
        if result.stdout.strip()!='wasm-opt version 125 (version_125)':raise ValueError('Expected Binaryen version 125')
        subprocess.run([node,str(optimizer),str(source),'-Oz','--enable-bulk-memory','--enable-sign-ext',
            '--enable-nontrapping-float-to-int','--enable-mutable-globals','-o',str(target)],check=True)
    else:shutil.copyfile(source,target)
    data=target.read_bytes();exports=wasm_exports(data)
    if not exports<=ALLOWED or not {'seal_and_mint','get_static_svg','get_animated_svg'}<=exports:
        raise ValueError('Unexpected contract exports; refusing immutable deployment artifact')
    manifest={'format':'intent-distortions-onchain-v1','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),
              'unoptimized_bytes':source.stat().st_size,'optimizer':'binaryen-125-Oz' if args.optimizer_js else None,
              'exports':sorted(exports)}
    (output/'build.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
