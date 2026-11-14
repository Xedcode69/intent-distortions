"""Monthly totals from canonical allocations; no per-NFT public response."""
import asyncio
import base64
import json
from datetime import datetime,timezone
import base58

def next_cycle(cycle):
    year,month=divmod(cycle,100)
    return (year+1)*100+1 if month==12 else cycle+1

def cutoff_ns(cycle):
    year,month=divmod(next_cycle(cycle),100)
    return str(int(datetime(year,month,1,tzinfo=timezone.utc).timestamp())*10**9)

def summarize_cycles(wallets,months,now_ns):
    by_cycle={m["cycle"]:m for m in months}
    funded=[d for d in wallets if d.get("cycle") is not None and int(d["original"])>0]
    cycles=set(by_cycle)|{d["cycle"] for d in funded}|{next_cycle(d["cycle"]) for d in funded if d["exited"]}
    rows=[]
    for cycle in sorted(cycles,reverse=True):
        m=by_cycle.get(cycle,{"cycle":cycle,"status":"Upcoming","pot":"0","rollover_received":"0","entries":[],"prize":"0","winner":None,"payout":None})
        own=[d for d in funded if d["cycle"]==cycle]
        exits=[d for d in own if d["exited"]]
        eligible=[d for d in own if not d["exited"] and d["wallet_status"]=="Funded"]
        pending=[d for d in own if not d["exited"] and d["wallet_status"]!="Funded"]
        incoming=[d for d in funded if d["exited"] and next_cycle(d["cycle"])==cycle and not d["collected"]]
        incoming_pending=sum(int(d["remaining"]) for d in incoming)
        uncollected=sum(int(d["remaining"]) for d in eligible if not d["collected"])
        exit_amount=sum(int(d["original"])*2//5 for d in exits)
        exit_rollover=sum(int(d["original"])-int(d["original"])*2//5 for d in exits)
        # An empty draw carries its whole received pool. Early-exit remainders
        # bypass that source pool, so these two outgoing amounts are disjoint.
        carried=int(m["rollover_received"]) if m["status"]=="Carried" else 0
        amount=int(m["prize"]) if m["status"]=="Drawn" else 0 if m["status"]=="Carried" else int(m["pot"])+uncollected+incoming_pending
        count=len(m["entries"]) if m["status"] in ("Collecting","Drawn","Carried") else len(eligible)
        rows.append({"cycle":cycle,"recorded":cycle in by_cycle,"status":m["status"],"cutoff_ns":m.get("cutoff_ns",cutoff_ns(cycle)),
            "draw_amount":str(amount),"eligible_nfts":count,"early_withdrawals":len(exits),"early_exit_amount":str(exit_amount),
            "incoming_rollover":str(int(m["rollover_received"])+incoming_pending),"incoming_pending":str(incoming_pending),
            "next_month_rollover":str(exit_rollover+carried),"next_cycle":next_cycle(cycle),
            "pooled_amount":m["pot"],"awaiting_collection":str(uncollected+incoming_pending),
            "pending_funding":len(pending),"pending_funding_amount":str(sum(int(d["remaining"]) for d in pending)),
            "winner":m.get("winner"),"payout":m.get("payout"),"prize":m.get("prize","0"),
            "awaiting_close":m["status"]=="Open" and now_ns>=int(m.get("cutoff_ns",cutoff_ns(cycle)))})
    date=datetime.fromtimestamp(now_ns//10**9,timezone.utc);current=date.year*100+date.month
    rows.sort(key=lambda row:(0 if row["cycle"]==current else 1 if row["cycle"]>current else 2,row["cycle"] if row["cycle"]>current else -row["cycle"]))
    return rows

async def reward_snapshot(settings,rpc):
    from .testnet_profile import validate_clock_build
    block=await rpc.block()
    async def view(method,args):
        response=await rpc.call("query",{"request_type":"call_function","account_id":settings.near_nft_contract,"block_id":block["hash"],
            "method_name":method,"args_base64":base64.b64encode(json.dumps(args).encode()).decode()})
        return json.loads(bytes(response["result"]))
    async def pages(method):
        rows=[]
        for offset in range(0,10100,100):
            page=await view(method,{"from_index":offset,"limit":100})
            if not isinstance(page,list) or len(page)>100 or len(rows)+len(page)>10000:raise ValueError("Reward enumeration exceeded bounds")
            rows.extend(page)
            if len(page)<100:return rows
        raise ValueError("Incomplete reward enumeration")
    status,code,config,wallets,months=await asyncio.gather(rpc.call("status",{}),
        rpc.call("query",{"request_type":"view_account","account_id":settings.near_nft_contract,"block_id":block["hash"]}),
        view("get_config",{}),pages("get_edition_wallets"),pages("get_months"))
    if status["chain_id"]!=settings.near_network or base58.b58decode(code["code_hash"]).hex()!=settings.expected_nft_code_hash:raise ValueError("Reward contract identity mismatch")
    if config.get("version")!="echo-nft-3":raise ValueError("Unsupported reward contract")
    validate_clock_build(settings,config)
    if len({d["token_id"] for d in wallets})!=len(wallets) or len({m["cycle"] for m in months})!=len(months):raise ValueError("Duplicated reward enumeration")
    now=int(config.get("clock_ns") or block["timestamp_nanosec"])
    return {"status":"onchain","network":settings.near_network,"block_height":block["height"],"as_of_ns":str(now),"months":summarize_cycles(wallets,months,now)}
