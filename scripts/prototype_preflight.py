"""Read-only testnet deployment and provider checks. Never signs."""
import argparse,asyncio,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))

async def check(online):
    from app.config import settings
    from app.services.protocol import policy
    from app.services.canonical_data import canonical,sha
    if settings.execution_mode!='live' or settings.near_network!='testnet':raise ValueError('Live testnet profile required')
    result={'network':'testnet','policy_sha256':sha(canonical(policy(settings))).hex(),
        'signing_enabled':settings.enable_chain_writes,'online_checks':'not_run'}
    if not Path(settings.onchain_renderer_binary).is_file():raise ValueError('Build the frozen SVG renderer first')
    if not online:return result
    from app.services.preflight import validate_contracts,validate_source_rpc
    print(json.dumps({'checking':'fresh_testnet_contracts'}),flush=True)
    result['contracts']=await validate_contracts(settings)
    print(json.dumps({'checking':'mainnet_source_rpc'}),flush=True)
    await validate_source_rpc(settings)
    from app.services.onchain_reader import snapshot
    from app.services.near_rpc import NearRPC
    print(json.dumps({'checking':'preserved_genesis'}),flush=True)
    await snapshot(settings,NearRPC(settings.near_rpc_url))
    result['genesis_contract']=settings.onchain_art_contract
    import httpx
    async with httpx.AsyncClient(timeout=60) as client:
        print(json.dumps({'checking':'explorer_authentication'}),flush=True)
        response=await client.get(settings.near_intents_explorer_url+'/transactions',
            params={'numberOfTransactions':1,'direction':'next','statuses':'SUCCESS',
                'startTimestampUnix':settings.genesis_checkpoint-1,'endTimestampUnix':settings.genesis_checkpoint+60},
            headers={'Authorization':'Bearer '+settings.near_intents_partner_jwt})
        response.raise_for_status()
        if not isinstance(response.json(),list):raise ValueError('Explorer schema mismatch')
        print(json.dumps({'checking':'near_ai_model_catalog'}),flush=True)
        response=await client.get(settings.near_ai_base_url+'/models',headers={'Authorization':'Bearer '+settings.near_ai_api_key})
        response.raise_for_status()
        if settings.near_ai_text_model not in {m['id'] for m in response.json()['data']}:raise ValueError('AI model unavailable')
    result['online_checks']='passed'
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--online',action='store_true');args=parser.parse_args()
    try:print(json.dumps(asyncio.run(check(args.online)),indent=2))
    except Exception as exc:
        print(json.dumps({'status':'failed','error_type':type(exc).__name__,'hint':'Check the private env and deployment guide; no signing attempted'}));raise SystemExit(1)
