"""Reviewed, journaled deployment of a separate keyless testnet art study.

No production contract, treasury, collector wallet or existing NFT is changed.
The account is created without keys; there is no later destructive lock step.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
import shutil
import sys
import httpx

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import testnet_rehearsal as cli
from scripts.build_onchain_art import ALLOWED
from scripts.build_contracts import wasm_exports
from app.services import testnet_rehearsal as lab,testnet_lab
from app.services.near_rpc import NearRPC
from app.services.onchain_reader import snapshot,recover_asset
from app.services.signed_call import inspect_signed_call

def sha(data):return hashlib.sha256(data).hexdigest()
def emit(value):print(json.dumps(value),flush=True)

async def account_state(rpc,account):
    async with httpx.AsyncClient(timeout=25) as client:
        response=await client.post(rpc.url,json={'jsonrpc':'2.0','id':'account-exists','method':'query','params':{
            'request_type':'view_account','finality':'final','account_id':account}})
        response.raise_for_status();body=response.json()
        if 'result' in body:return body['result']
        error=body.get('error',{})
        if error.get('cause',{}).get('name')=='UNKNOWN_ACCOUNT':return None
        raise lab.RehearsalError('Could not establish account existence; nothing signed')

def local_files(directory):
    directory=directory.resolve()
    root=(ROOT/'data/onchain-prototypes').resolve()
    if not directory.is_relative_to(root) or directory==root:raise lab.RehearsalError('Use an isolated data/onchain-prototypes workspace')
    document=json.loads((directory/'prototype.json').read_text())
    recipe=(directory/'recipe.bin').read_bytes()
    wasm=ROOT/'contracts/artifacts/onchain-v1/intent_onchain_art.wasm'
    build=json.loads(wasm.with_name('build.json').read_text())
    if sha(recipe)!=document['recipe_sha256'] or len(recipe)!=document['recipe_bytes'] or sha(wasm.read_bytes())!=build['sha256']:
        raise lab.RehearsalError('Prepared recipe or reviewed WASM changed')
    if not wasm_exports(wasm.read_bytes())<=ALLOWED:raise lab.RehearsalError('Unreviewed contract exports')
    return document,recipe,wasm,build

async def make_plan(cfg,rpc,directory,account):
    document,recipe,wasm,build=local_files(directory)
    if not account.endswith('.'+cfg.near_minter_account) or len(account)>64:
        raise lab.RehearsalError('Prototype must be a separate child of the testnet operator')
    await lab._network(rpc)
    protocol=await rpc.call('EXPERIMENTAL_protocol_config',{'finality':'final'})
    byte_cost=int(protocol['runtime_config']['storage_amount_per_byte'])
    value={'schema':'intent-distortions-onchain-deploy-v1','network':'testnet','contract':account,
        'minter':cfg.near_minter_account,'receiver':cfg.near_creator_account,'token_id':document['token_id'],
        'wasm_sha256':build['sha256'],'wasm_bytes':build['bytes'],'recipe_sha256':sha(recipe),
        'prototype_sha256':sha((directory/'prototype.json').read_bytes()),
        'static_sha256':sha((directory/'static.svg').read_bytes()),'animated_sha256':sha((directory/'animated.svg').read_bytes()),
        'bootstrap_yocto':str((build['bytes']+6000)*byte_cost+5*10**22),
        'upload_deposit_yocto':str((len(recipe)+24000)*byte_cost),'storage_byte_cost':str(byte_cost),
        'keys_added':0,'source_edition_unchanged':True}
    return value

async def verify_bootstrap(rpc,tx_hash,expected):
    receipt=await rpc.call('tx',{'tx_hash':tx_hash,'sender_account_id':expected['signer'],'wait_until':'FINAL'})
    tx=receipt.get('transaction',{});actions=tx.get('actions',[])
    if receipt.get('final_execution_status')!='FINAL' or tx.get('signer_id')!=expected['signer'] or tx.get('receiver_id')!=expected['contract'] or len(actions)!=4:
        raise lab.RehearsalError('Bootstrap receipt identity/action count mismatch')
    if actions[0]!='CreateAccount' or actions[1].get('Transfer',{}).get('deposit')!=expected['deposit_yocto']:
        raise lab.RehearsalError('Bootstrap account/funding mismatch')
    deployed=base64.b64decode(actions[2].get('DeployContract',{}).get('code',''),validate=True)
    # nearcore ActionView intentionally returns SHA-256(code), not the WASM
    # itself. Accept full-code RPCs too, while binding both to the reviewed hash.
    deployed_hash=deployed.hex() if len(deployed)==32 else sha(deployed)
    if deployed_hash!=expected['code_sha256']:
        raise lab.RehearsalError('Bootstrap code mismatch')
    call=actions[3].get('FunctionCall',{})
    if call.get('method_name')!='new' or json.loads(base64.b64decode(call['args']))!={'minter':expected['signer']} or str(call.get('deposit'))!='0':
        raise lab.RehearsalError('Bootstrap initializer mismatch')
    ok='SuccessValue' in receipt.get('status',{}) and not any('Failure' in row.get('outcome',{}).get('status',{}) for row in receipt.get('receipts_outcome',[]))
    receipt['transaction_hash']=tx_hash
    return receipt,ok

async def signed_call(d,cfg,rpc,account,method,args,deposit='0',nonce=None,allowed_pending=None):
    """Journal exact signed bytes before their sole broadcast; unknown IDs cannot occur."""
    journal=lab._journal(d)
    if any(v['status']=='outcome_unknown' and k!=allowed_pending for k,v in journal.items()):
        raise lab.RehearsalError('Reconcile the unresolved operator action before signing')
    gas=300 if method=='seal_and_mint' else 80
    expected={'signer':cfg.near_minter_account,'contract':account,'method':method,'args':args,'deposit_yocto':deposit,'gas':gas*10**12}
    command=lab._call_command(account,method,args,cfg.near_minter_account,deposit+' yoctoNEAR');command.remove('--quiet')
    command[command.index('prepaid-gas')+1]=str(gas)+' Tgas';command[-1]='display'
    if nonce is not None:command[-1:-1]=['--nonce',str(nonce)]
    # DISPLAY signs locally but cannot submit; failure here creates no unknown write.
    result=subprocess.run(command,check=False,capture_output=True,text=True,timeout=180)
    if result.returncode:raise lab.RehearsalError('CLI signing failed before broadcast; no transaction submitted')
    candidates=re.findall(r'(?m)^[A-Za-z0-9+/]{100,}={0,2}$',(result.stdout or '')+'\n'+(result.stderr or ''))
    if len(candidates)!=1:raise lab.RehearsalError('Expected one signed transaction; nothing broadcast')
    encoded=candidates[0];info=inspect_signed_call(encoded,expected)
    if nonce is not None and info['nonce']!=nonce:raise lab.RehearsalError('Nonce differs; nothing broadcast')
    key=f'onchain:{len(journal):06d}:{method}'
    journal[key]={'status':'outcome_unknown','started_at':int(time.time()),'expected':expected,
                  **info,'signed_transaction_base64':encoded}
    lab.write_json(d/'operator-journal.json',journal)
    await rpc.call('broadcast_tx_commit',[encoded])
    receipt,ok=await testnet_lab.finalized(rpc,info['transaction_hash'],expected)
    journal=lab._journal(d);journal[key]['status']='verified_onchain' if ok else 'verified_failed';lab.write_json(d/'operator-journal.json',journal)
    if not ok:raise lab.RehearsalError('Prototype action finalized with failure; inspect exact receipt')
    return receipt

async def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['plan','send','verify','recover','invalidate-pending'])
    p.add_argument('workspace',type=Path);p.add_argument('prototype',type=Path)
    p.add_argument('--account');p.add_argument('--send',action='store_true');p.add_argument('--plan-sha256');p.add_argument('--tx-hash')
    p.add_argument('--rebroadcast-exact',action='store_true',help='Recovery only: send the identical journaled bytes, never a new nonce')
    args=p.parse_args();d=lab.workspace(args.workspace);directory=args.prototype.resolve();cfg=testnet_lab.require_lab(d)
    near=shutil.which('near')
    if not near and os.name=='nt':
        candidate=Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'near-cli-rs/bin'
        os.environ['PATH']=str(candidate)+os.pathsep+os.environ['PATH'];near=shutil.which('near')
    if not near:raise lab.RehearsalError('Official near-cli-rs required')
    rpc=NearRPC(cfg.near_rpc_url,budget_seconds=30);account=args.account or 'art-v1.'+cfg.near_minter_account
    if cfg.near_network!='testnet':raise lab.RehearsalError('Testnet only')
    plan=await make_plan(cfg,rpc,directory,account);digest=sha(lab.canonical(plan));plan_path=directory/'chain-plan.json'
    document,recipe,wasm,build=local_files(directory)
    if args.command=='plan':
        if plan_path.exists() and json.loads(plan_path.read_text())!=plan:raise lab.RehearsalError('Existing reviewed plan changed; use a separate prototype workspace')
        lab.write_json(plan_path,plan)
        balance=await lab._account_view(rpc,cfg.near_minter_account)
        required=int(plan['bootstrap_yocto'])+int(plan['upload_deposit_yocto'])+3*10**23+int(balance['storage_usage'])*int(plan['storage_byte_cost'])
        emit({'plan':plan,'sha256':digest,'operator_balance':balance['amount'],'required_with_gas_reserve':str(required),'funded':int(balance['amount'])>=required,'signed':False});return
    if not plan_path.exists() or json.loads(plan_path.read_text())!=plan or args.plan_sha256!=digest:
        raise lab.RehearsalError('Supply the reviewed, unchanged --plan-sha256')
    if args.command=='recover':
        if not args.tx_hash:raise lab.RehearsalError('Exact transaction hash required')
        with lab.operator_lock(d):
            journal=lab._journal(d);pending=[(k,v) for k,v in journal.items() if v['status']=='outcome_unknown']
            if len(pending)!=1 or pending[0][1]['expected']['contract']!=account:raise lab.RehearsalError('Expected one unresolved prototype action')
            key,value=pending[0]
            if args.rebroadcast_exact:
                if not args.send or not value.get('signed_transaction_base64'):raise lab.RehearsalError('Exact-byte rebroadcast requires --send and journaled signed bytes')
                decoded=inspect_signed_call(value['signed_transaction_base64'],value['expected'])
                if decoded['transaction_hash']!=args.tx_hash or value.get('transaction_hash')!=args.tx_hash:
                    raise lab.RehearsalError('Saved transaction hash differs; nothing broadcast')
                await rpc.call('broadcast_tx_commit',[value['signed_transaction_base64']])
            receipt,ok=await (verify_bootstrap(rpc,args.tx_hash,value['expected']) if value['expected'].get('kind')=='onchain-bootstrap' else testnet_lab.finalized(rpc,args.tx_hash,value['expected']))
            journal[key].update(status='verified_onchain' if ok else 'verified_failed',transaction_hash=args.tx_hash)
            lab.write_json(d/'operator-journal.json',journal)
            lab.write_json(directory/('receipt-'+args.tx_hash+'.json'),receipt)
            action_file=directory/'chain-actions.json'
            actions=json.loads(action_file.read_text()) if action_file.exists() else []
            if not any(a['transaction_hash']==args.tx_hash for a in actions):
                actions.append({'method':'create_keyless_deploy_initialize' if value['expected'].get('kind')=='onchain-bootstrap' else value['expected']['method'],'transaction_hash':args.tx_hash})
                lab.write_json(action_file,actions)
            emit({'reconciled':True,'success':ok,'transaction_hash':args.tx_hash});return
    if args.command in ('send','invalidate-pending') and not args.send:raise lab.RehearsalError('Explicit --send required')
    if args.command=='invalidate-pending':
        # Recovery only for the old CLI's no-hash first preparation call. Consume
        # its sole possible nonce with a zero-value read transaction before any
        # balance change, making the old call permanently unexecutable.
        with lab.operator_lock(d):
            journal=lab._journal(d);pending=[(k,v) for k,v in journal.items() if v['status']=='outcome_unknown']
            if len(pending)!=1:raise lab.RehearsalError('Expected exactly one pending preparation')
            key,old=pending[0];e=old['expected']
            if old.get('transaction_hash') or old.get('cli_exit_code')!=1 or e.get('contract')!=account or e.get('method')!='begin_edition':
                raise lab.RehearsalError('Only a legacy no-hash preparation may use this recovery')
            bootstrap=next(v for v in journal.values() if v.get('expected',{}).get('kind')=='onchain-bootstrap' and v['expected']['contract']==account)
            tx=await rpc.call('tx',{'tx_hash':bootstrap['transaction_hash'],'sender_account_id':cfg.near_minter_account,'wait_until':'FINAL'})
            prior=tx['transaction'];public_key=prior['public_key']
            access=await rpc.call('query',{'request_type':'view_access_key','finality':'final','account_id':cfg.near_minter_account,'public_key':public_key})
            if access['nonce']!=prior['nonce'] or await rpc.view(account,'get_edition',{'token_id':document['token_id']}) is not None:
                raise lab.RehearsalError('Nonce or edition changed; manual receipt reconciliation required')
            receipt=await signed_call(d,cfg,rpc,account,'get_config',{},nonce=prior['nonce']+1,allowed_pending=key)
            if receipt['transaction']['public_key']!=public_key or receipt['transaction']['nonce']!=prior['nonce']+1:
                raise lab.RehearsalError('Recovery signer/nonce mismatch')
            if await rpc.view(account,'get_edition',{'token_id':document['token_id']}) is not None:raise lab.RehearsalError('Edition changed during recovery')
            journal=lab._journal(d);journal[key].update(status='verified_nonce_invalidated',recovery_transaction=receipt['transaction_hash'],
                reason='Exact next nonce consumed by zero-deposit get_config; unsubmitted/pending preparation can no longer execute')
            lab.write_json(d/'operator-journal.json',journal);lab.write_json(directory/('receipt-'+receipt['transaction_hash']+'.json'),receipt)
            emit({'status':'legacy_pending_nonce_invalidated','transaction_hash':receipt['transaction_hash'],'deposit':'0'});return
    read_config=cfg.model_copy(update={'onchain_art_contract':account,'onchain_art_token_id':document['token_id'],'expected_onchain_art_code_hash':build['sha256']})
    receipts_path=directory/'chain-actions.json';receipts=json.loads(receipts_path.read_text()) if receipts_path.exists() else []
    async def save(receipt,method):
        lab.write_json(directory/('receipt-'+receipt['transaction_hash']+'.json'),receipt)
        receipts.append({'method':method,'transaction_hash':receipt['transaction_hash']});lab.write_json(receipts_path,receipts);emit(receipts[-1])
    if args.command=='send':
        with lab.operator_lock(d):
            if any(v['status']=='outcome_unknown' for v in lab._journal(d).values()):raise lab.RehearsalError('Resolve unknown operator outcome before signing')
            existing=await account_state(rpc,account)
            if existing is None:
                balance=await lab._account_view(rpc,cfg.near_minter_account)
                required=int(plan['bootstrap_yocto'])+int(plan['upload_deposit_yocto'])+3*10**23+int(balance['storage_usage'])*int(plan['storage_byte_cost'])
                if int(balance['amount'])<required:raise lab.RehearsalError('Fund the operator before this reviewed prototype deployment')
                key='onchain:'+digest+':bootstrap'
                expected={'kind':'onchain-bootstrap','signer':cfg.near_minter_account,'contract':account,'deposit_yocto':plan['bootstrap_yocto'],'code_sha256':build['sha256']}
                command=[near,'transaction','construct-transaction',cfg.near_minter_account,'receiver-id',account,'add-action','create-account',
                    'add-action','transfer',plan['bootstrap_yocto']+' yoctoNEAR','add-action','deploy-contract','use-file',str(wasm),
                    'with-init-call','new','json-args',json.dumps({'minter':cfg.near_minter_account}),'prepaid-gas','30 Tgas',
                    'attached-deposit','0 NEAR','skip','network-config','testnet','sign-with-keychain','send']
                lab._run_cli(d,key,command,expected);row=lab._journal(d)[key]
                if not row.get('transaction_hash'):raise lab.RehearsalError('Bootstrap outcome unknown; recover exact transaction before retrying')
                receipt,ok=await verify_bootstrap(rpc,row['transaction_hash'],expected)
                journal=lab._journal(d);journal[key]['status']='verified_onchain' if ok else 'verified_failed';lab.write_json(d/'operator-journal.json',journal)
                if not ok:raise lab.RehearsalError('Bootstrap finalized with failure; inspect receipts')
                await save(receipt,'create_keyless_deploy_initialize')
            code=await lab._account_view(rpc,account)
            keys=await rpc.call('query',{'request_type':'view_access_key_list','finality':'final','account_id':account})
            import base58
            if base58.b58decode(code['code_hash']).hex()!=build['sha256'] or keys['keys']!=[]:
                raise lab.RehearsalError('Expected pinned code and a keyless account; no mint submitted')
            config=await rpc.view(account,'get_config',{})
            if config.get('format')!='intent-distortions-onchain-v1':raise lab.RehearsalError('Wrong format')
            if config.get('minter')!=cfg.near_minter_account:raise lab.RehearsalError('Wrong minter')
            # Reuse only this exact token's committed metadata and recipe hash.
            # The seal validates the complete uploaded bytes before minting.
            edition=await rpc.view(account,'get_edition',{'token_id':document['token_id']})
            if edition is None:
                if await rpc.view(account,'nft_total_supply',{})!='0':raise lab.RehearsalError('Existing collection requires inspection')
                receipt=await signed_call(d,cfg,rpc,account,'begin_edition',{
                    'token_id':document['token_id'],'metadata':document['metadata'],'receiver_id':cfg.near_creator_account,
                    'recipe_sha256':document['recipe_sha256'],'recipe_bytes':len(recipe)},plan['upload_deposit_yocto'])
                await save(receipt,'begin_edition');edition=await rpc.view(account,'get_edition',{'token_id':document['token_id']})
            if edition['metadata']!=document['metadata'] or edition['recipe_sha256']!=sha(recipe):raise lab.RehearsalError('Prepared onchain edition conflicts with local frozen inputs')
            if not edition['sealed']:
                preparations=[v.get('expected',{}) for v in lab._journal(d).values() if v['status']=='verified_onchain'
                    and v.get('expected',{}).get('contract')==account and v.get('expected',{}).get('method')=='begin_edition']
                if not any(e.get('args',{}).get('token_id')==document['token_id'] and e['args'].get('receiver_id')==cfg.near_creator_account
                           and e['args'].get('metadata')==document['metadata'] and e['args'].get('recipe_sha256')==sha(recipe) for e in preparations):
                    raise lab.RehearsalError('Existing draft needs its verified preparation receipt and fixed team recipient')
                for offset in range(edition['uploaded_bytes'],len(recipe),16384):
                    receipt=await signed_call(d,cfg,rpc,account,'append_recipe',{'token_id':document['token_id'],
                        'offset':offset,'data':base64.b64encode(recipe[offset:offset+16384]).decode()})
                    await save(receipt,'append_recipe')
                receipt=await signed_call(d,cfg,rpc,account,'seal_and_mint',{'token_id':document['token_id']})
                await save(receipt,'seal_and_mint')
    state=await snapshot(read_config,rpc)
    if not state['keyless'] or state['edition']['owner_id']!=cfg.near_creator_account:raise lab.RehearsalError('Keylessness or initial ownership mismatch')
    for kind,name in [('recipe','recipe.bin'),('static','static.svg'),('animated','animated.svg')]:
        recovered=await recover_asset(read_config,rpc,state,kind)
        if recovered!=(directory/name).read_bytes():raise lab.RehearsalError('Chain-only recovery differs from prepared artwork')
        (directory/('recovered-'+name)).write_bytes(recovered)
    lab.write_json(directory/'chain-verified.json',state)
    emit({'status':'keyless_onchain_study_verified','contract':account,'token_id':document['token_id'],
          'owner':state['edition']['owner_id'],'recipe_bytes':len(recipe),'static_sha256':state['edition']['static_sha256'],
          'animated_sha256':state['edition']['animated_sha256'],'code_sha256':build['sha256'],'block_height':state['block_height']})

if __name__=='__main__':
    try:asyncio.run(main())
    except lab.RehearsalError as exc:
        emit({'status':'blocked','reason':str(exc),'automatic_retry':False});raise SystemExit(2)
    except Exception as exc:
        emit({'status':'blocked','error_type':type(exc).__name__,'automatic_retry':False});raise SystemExit(1)
