"""Package the single testnet build from allowlisted Git source and reviewed WASM."""
import hashlib,json,subprocess
from pathlib import Path
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'
sha=lambda data:hashlib.sha256(data).hexdigest()

def main():
    git=subprocess.run(['git','-c','safe.directory='+ROOT.as_posix(),'ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT,capture_output=True,check=True)
    folders={'backend','frontend','signer','contracts','scripts','deploy','fixtures','docs','.github'}
    roots={'README.md','project.json','render.yaml','pyproject.toml','uv.lock','.python-version','.dockerignore','.env.example','LICENSE','AGENTS.md'}
    forbidden={'data','.tools','.git','.aws','.codex','.agents','.venv','node_modules','target','artifacts','__pycache__'}
    files={}
    for name in git.stdout.decode().split('\0'):
        if not name:continue
        path=Path(name)
        if name not in roots and path.parts[0] not in folders:continue
        if forbidden.intersection(path.parts) or any(part.startswith('.next') for part in path.parts):continue
        if path.name.startswith('.env') and path.name!='.env.example':continue
        if path.suffix in ('.db','.pem','.key','.pyc','.tsbuildinfo','.log','.wasm'):continue
        source=ROOT/path
        if source.is_file():files[name]=source.read_bytes()
    directory=ROOT/'contracts/artifacts/testnet';build=json.loads((directory/'build.json').read_text())
    if build['network']!='testnet' or build['clock']!='real_block_timestamp':raise ValueError('Real-clock testnet build required')
    files['contracts/artifacts/testnet/build.json']=(directory/'build.json').read_bytes()
    for name,expected in build['artifacts'].items():
        if name not in {'echo_nft.wasm','echo_auction.wasm','echo_market.wasm','echo_vault.wasm'}:raise ValueError('Unexpected artifact')
        data=(directory/name).read_bytes()
        if sha(data)!=expected['sha256']:raise ValueError('Artifact hash mismatch')
        files['contracts/artifacts/testnet/'+name]=data
    manifest={'schema':'intent-distortions-testnet-release-v1','network':'testnet','kind':'single-prototype-source-and-wasm',
        'secrets_included':False,'runtime_state_included':False,'files':{name:{'sha256':sha(data),'bytes':len(data)} for name,data in sorted(files.items())}}
    encoded=(json.dumps(manifest,indent=2)+'\n').encode();OUT.mkdir(exist_ok=True)
    output=OUT/'intent-distortions-testnet.zip'
    with ZipFile(output,'w',compression=ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted({**files,'release-manifest.json':encoded}.items()):
            info=ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=ZIP_DEFLATED;info.external_attr=0o644<<16
            archive.writestr(info,data)
    (OUT/'intent-distortions-testnet.manifest.json').write_bytes(encoded)
    print(json.dumps({'bundle':str(output.relative_to(ROOT)),'files':len(files),'sha256':sha(output.read_bytes())}))

if __name__=='__main__':main()
