"""Read-only, code-pinned recovery of onchain artwork; no CAS/IPFS fallback."""
import asyncio
import base64
import hashlib
import json
import re
import base58

FORMAT="intent-distortions-onchain-v1"

async def snapshot(settings,rpc):
    account=settings.onchain_art_contract
    if not re.fullmatch(r"(?=.{2,64}$)[a-z0-9]+(?:[._-][a-z0-9]+)*",account):
        raise ValueError("Invalid onchain artwork account")
    if settings.near_network=="testnet" and not account.endswith('.testnet') or settings.near_network=="mainnet" and account.endswith('.testnet'):
        raise ValueError("Onchain artwork network mismatch")
    if not re.fullmatch(r"[a-f0-9]{64}",settings.expected_onchain_art_code_hash):
        raise ValueError("Reviewed onchain renderer code hash required")
    block=await rpc.block()
    async def view(method,args):
        result=await rpc.call("query",{"request_type":"call_function","block_id":block["hash"],"account_id":account,
            "method_name":method,"args_base64":base64.b64encode(json.dumps(args).encode()).decode()})
        return json.loads(bytes(result["result"]))
    status,code,keys,config,edition=await asyncio.gather(rpc.call("status",{}),
        rpc.call("query",{"request_type":"view_account","block_id":block["hash"],"account_id":account}),
        rpc.call("query",{"request_type":"view_access_key_list","block_id":block["hash"],"account_id":account}),
        view("get_config",{}),view("get_edition",{"token_id":settings.onchain_art_token_id}))
    if status["chain_id"]!=settings.near_network or base58.b58decode(code["code_hash"]).hex()!=settings.expected_onchain_art_code_hash:
        raise ValueError("Onchain renderer identity mismatch")
    if config.get("format")!=FORMAT or config.get("renderer")!="idart1-svg-1" or config.get("external_dependencies") is not False or config.get("upgrade_method") is not False:
        raise ValueError("Unsupported onchain renderer")
    if not isinstance(edition,dict) or edition.get("format")!=FORMAT or edition.get("token_id")!=settings.onchain_art_token_id or edition.get("sealed") is not True:
        raise ValueError("Edition is not sealed")
    if not 76<edition["recipe_bytes"]<=262144 or edition["uploaded_bytes"]!=edition["recipe_bytes"]:
        raise ValueError("Incomplete onchain recipe")
    if any(not re.fullmatch(r"[a-f0-9]{64}",edition.get(k) or "") for k in ("recipe_sha256","static_sha256","animated_sha256","artwork_commitment")):
        raise ValueError("Incomplete artwork commitments")
    return {"status":"sealed_onchain","network":settings.near_network,"contract":account,"code_sha256":settings.expected_onchain_art_code_hash,
            "keyless":keys.get("keys")==[],"block_height":block["height"],"block_hash":block["hash"],
            "storage_usage":code["storage_usage"],"edition":edition}


async def recover_asset(settings,rpc,state,kind):
    if kind not in ("static","animated","recipe"):
        raise ValueError("Unsupported onchain asset")
    async def view(method,args):
        result=await rpc.call("query",{"request_type":"call_function","block_id":state["block_hash"],"account_id":settings.onchain_art_contract,
            "method_name":method,"args_base64":base64.b64encode(json.dumps(args).encode()).decode()})
        return json.loads(bytes(result["result"]))
    token=settings.onchain_art_token_id
    if kind=="recipe":
        chunks=[]
        for offset in range(0,state["edition"]["recipe_bytes"],16384):
            chunk=base64.b64decode(await view("get_recipe_chunk",{"token_id":token,"offset":offset}),validate=True)
            if len(chunk)!=min(16384,state["edition"]["recipe_bytes"]-offset):raise ValueError("Incomplete onchain chunk")
            chunks.append(chunk)
        data=b''.join(chunks)
    else:
        value=await view("get_static_svg" if kind=="static" else "get_animated_svg",{"token_id":token})
        if not isinstance(value,str) or not value.startswith('<svg ') or len(value)>2_000_000:
            raise ValueError("Invalid onchain SVG")
        data=value.encode()
    if hashlib.sha256(data).hexdigest()!=state["edition"][kind+"_sha256"]:
        raise ValueError("Onchain artwork hash mismatch")
    return data
