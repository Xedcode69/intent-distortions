"""HTTP smoke check of the single testnet API and chain-recovered media."""
import argparse,hashlib,json,httpx
parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8000');args=parser.parse_args()
def get(path):
    with httpx.Client(timeout=90,trust_env=False) as client:
        response=client.get(args.url+path);response.raise_for_status();return response.content
health=json.loads(get('/api/v1/health'));assert health['network']=='testnet' and health['mode']=='live'
for path in ['/readyz','/api/v1/artworks','/api/v1/drops','/api/v1/epochs/current','/api/v1/marketplace','/api/v1/economy']:
    get(path);print('OK '+path,flush=True)
art=json.loads(get('/api/v1/artworks/latest'));image=get(art['image'])
assert image.startswith(b'<svg ') and hashlib.sha256(image).hexdigest()==art['image_hash']
if art['id']=='genesis':
    state=json.loads(get('/api/v1/onchain/prototype'));motion=get('/api/v1/onchain/prototype/animated.svg')
    assert state['keyless'] and hashlib.sha256(motion).hexdigest()==state['edition']['animated_sha256']
else:
    motion=get(art['onchain_art']['animated_url'])
    assert hashlib.sha256(motion).hexdigest()==art['onchain_art']['animated_sha256']
print('OK chain-recovered still and animation match sealed hashes',flush=True)
