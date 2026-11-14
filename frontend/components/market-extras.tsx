"use client";
import {useState,useEffect} from "react";
import {useQuery} from "@tanstack/react-query";
import {api,toYocto,yocto,type Health} from "@/lib/api";
import {units,type MarketListing,type RoyaltyMonth} from "@/lib/marketplace";
import {Button} from "./ui/button";

type Quote={quote_response:{quote:{depositAddress?:string;depositMemo?:string;amountIn:string;maxAmountIn?:string;deadline:string;amountOut:string};quoteRequest:Record<string,unknown>};funding_yocto:string;notice:string};
type Source={assetId:string;symbol:string;blockchain:string;decimals:number};
export function CrossChain({listing,tokenId,account,enabled,offer,network,onMessage}:{listing:MarketListing;tokenId:string;account:string;enabled:boolean;offer:string;network:Health["network"];onMessage:(s:string)=>void}){
 const [source,setSource]=useState(""),[refund,setRefund]=useState(""),[quote,setQuote]=useState<Quote|null>(null),[status,setStatus]=useState(""),[busy,setBusy]=useState(false);
 const {data:sources}=useQuery({queryKey:["swap-sources"],queryFn:()=>api<Source[]>("/marketplace/crosschain/tokens"),enabled});
 useEffect(()=>{setQuote(null);setStatus("");},[source,refund,account,listing.nonce,offer,tokenId]);
 async function request(dry:boolean){setBusy(true);setQuote(null);try{
  const q=await api<Quote>("/marketplace/crosschain/quote",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({token_id:tokenId,listing_nonce:listing.nonce,buyer:account,origin_asset:source,refund_to:refund,dry,offer_amount:offer?toYocto(offer):null})});setQuote(q);
 }catch(e){onMessage((e as Error).message);}finally{setBusy(false);}}
 async function poll(){if(!quote?.quote_response.quote.depositAddress)return;setBusy(true);try{
  const q=quote.quote_response.quote,params=new URLSearchParams({deposit_address:q.depositAddress!});if(q.depositMemo!=null)params.set("deposit_memo",q.depositMemo);
  const value=await api<{status:string}>(`/marketplace/crosschain/status?${params}`);setStatus(value.status);
 }catch(e){onMessage((e as Error).message);}finally{setBusy(false);}}
 const selected=sources?.find(t=>t.assetId===source),q=quote?.quote_response.quote;
 return <details className="market-crosschain"><summary>Pay from another chain with NEAR Intents</summary>
 {!enabled?<p>Cross-chain checkout becomes available with an enabled, reviewed mainnet marketplace. Testnet and this replay do not accept deposits.</p>:<>
 <p>Swap into your connected NEAR account, then approve Buy or Make offer. This does not reserve the artwork. If it sells meanwhile, your funds stay in your wallet. Funding includes an extra 0.1 NEAR for registration, offer storage and gas; unused funds are yours.</p>
 <label>Source asset<select value={source} onChange={e=>setSource(e.target.value)}><option value="">Choose network and token</option>{sources?.map(t=><option key={t.assetId} value={t.assetId}>{t.blockchain} · {t.symbol}</option>)}</select></label>
 <label>Refund address on the source chain<input value={refund} onChange={e=>setRefund(e.target.value)} placeholder="Your source wallet address"/></label>
 <p>Receiving NEAR account: <code>{account||"Connect a NEAR wallet first"}</code>. {offer?`Funding an offer of ${offer} NEAR.`:"Funding the fixed listing price."}</p>
 <Button disabled={!account||!source||!refund||busy} onClick={()=>request(true)}>Preview funding quote</Button>
 {q&&<div className="market-quote"><p>Quoted input: {selected?units(q.maxAmountIn||q.amountIn,selected.decimals):q.amountIn} {selected?.symbol} (maximum, including input-side slippage). Output: {units(q.amountOut,24)} NEAR. Provider fees are included in the quote; marketplace royalty is deducted from the sale price.</p><p>Deadline: {q.deadline}</p>
 {q.depositAddress?<><p>Send the quoted source asset on <b>{selected?.blockchain}</b> to:</p><code>{q.depositAddress}</code>{q.depositMemo!=null&&<p className="notice">Required deposit memo: <code>{q.depositMemo}</code></p>}<p>Use your source wallet to send. Include the exact memo when provided; never send after the deadline.</p><Button disabled={busy} onClick={poll}>Check swap status</Button>{status&&<p role="status">Swap: {status}. NFT ownership is checked separately.</p>}</>:<Button disabled={busy} onClick={()=>request(false)}>Create deposit instructions</Button>}
 </div>}
 </>}
 </details>;
}

export function RoyaltyCycle({m,enabled,act}:{m:RoyaltyMonth;enabled:boolean;act:(method:string,args:Record<string,unknown>,deposit?:string)=>Promise<void>}){
 const [offset,setOffset]=useState(0);
 const {data:shares,refetch}=useQuery({queryKey:["royalty-shares",m.cycle,offset,m.paid,m.processed],queryFn:()=>api<{index:number;token_id:string;owner_id:string;status:string;amount:string}[]>(`/marketplace/royalties/${m.cycle}/shares?offset=${offset}&limit=25`),enabled:m.ready,refetchInterval:15000});
 return <article className="market-royalty"><h3>{m.cycle.toString().slice(0,4)} / {m.cycle%100}</h3><p>Royalties earned: {yocto(m.earned)} NEAR · Held unpaid: {yocto(m.pot)} NEAR</p><p>{m.ready?`${m.eligible} eligible artworks · ${yocto(m.share)} NEAR per artwork · ${m.paid} payments delivered`:`Ownership snapshot: ${m.processed} / ${m.snapshot_total??"pending"}; ${m.pending_sales} sales awaiting resolution.`}</p>
 {shares?.map(s=><div className="market-share" key={s.index}><span>{s.token_id} → {s.owner_id} · {s.status}</span><Button className="subtle" disabled={!enabled||BigInt(s.amount)===0n||!["Claimable","Retryable"].includes(s.status)} onClick={async()=>{await act("pay_royalty",{cycle:m.cycle,index:String(s.index)},"1");await refetch();}}>Deliver payment</Button></div>)}
 {m.ready&&<div className="market-actions"><Button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-25))}>Previous shares</Button><Button disabled={!shares||shares.length<25} onClick={()=>setOffset(offset+25)}>Next shares</Button></div>}
 </article>;
}

