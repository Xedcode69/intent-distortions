"use client";
import {useState} from "react";
import Link from "next/link";
import {RefreshCw,ArrowUpRight} from "lucide-react";
import {useQueryClient} from "@tanstack/react-query";
import {api,useAPI,walletTransactionsEnabled,type Health} from "@/lib/api";
import {monthLabel} from "@/lib/economy";
import {units} from "@/lib/marketplace";
import {contractAction} from "@/lib/wallet";
import type {TransactionReceipt} from "@/lib/transactions";
import {useWallet} from "./wallet-provider";
import {TransactionLinks,TransactionMessage} from "./transaction-links";
import {Button} from "./ui/button";
type Cycle={cycle:number;status:string;recorded:boolean;cutoff_ns:string;draw_amount:string;eligible_nfts:number;early_withdrawals:number;early_exit_amount:string;incoming_rollover:string;incoming_pending:string;next_month_rollover:string;next_cycle:number;awaiting_collection:string;pending_funding:number;pending_funding_amount:string;winner:{beneficiary:string;token_id:string}|null;payout:{status:string;amount:string}|null;prize:string;awaiting_close:boolean};
type Rewards={status:"onchain"|"not_deployed";network:string;months:Cycle[];total:number;block_height:number|null;as_of_ns:string|null};
const stateLabel=(m:Cycle)=>m.awaiting_close?"Awaiting close":({Open:"In progress",Upcoming:"Upcoming",Collecting:"Preparing draw",Drawn:m.payout?.status==="Paid"?"Prize paid":"Prize pending",Carried:"Rolled over"} as Record<string,string>)[m.status]||m.status;
export function RewardsOverview(){
 const [offset,setOffset]=useState(0),[busy,setBusy]=useState(false),[message,setMessage]=useState(""),[receipts,setReceipts]=useState<TransactionReceipt[]>([]);
 const path=`/economy/cycles?offset=${offset}&limit=12`;
 const [refreshing,setRefreshing]=useState(false);
 const {data,error,isFetching,dataUpdatedAt}=useAPI<Rewards>(path);
 const {data:health}=useAPI<Health>("/health"),wallet=useWallet(),cache=useQueryClient();
 async function refresh(){setRefreshing(true);try{const value=await api<Rewards>(`${path}&fresh=true`);cache.setQueryData([path],value);}catch{setMessage("The latest monthly totals could not be verified. Please try again shortly.");}finally{setRefreshing(false);}}
 async function retry(cycle:number){
  if(!health||!walletTransactionsEnabled(health)||!wallet.account)return;
  setBusy(true);setMessage("");setReceipts([]);try{const result=await contractAction(health.contracts.nft,health.network,"pay_month",{cycle},"0",wallet.account);setReceipts([{hash:result.transaction.hash,network:health.network,label:"Prize delivery"}]);await cache.invalidateQueries();}catch(e){setMessage((e as Error).message);}finally{setBusy(false);}
 }
 return <div className="page-container rewards-page"><div className="rewards-heading"><div><span className="eyebrow">THE COLLECTION ECONOMY</span><h1>Monthly<br/><em>rewards.</em></h1><p>Live pools, eligibility and rollovers.</p></div><Link href="/my-collection" className="button subtle">Manage my artworks <ArrowUpRight size={16}/></Link></div>
 <div className="rewards-toolbar"><span>{data?.status==="onchain"?`${data.network} · Live monthly totals`:"Monthly draw overview"}</span><Button className="subtle" disabled={isFetching||refreshing} onClick={()=>void refresh()}><RefreshCw size={14} className={isFetching||refreshing?"spin":""}/>Refresh</Button></div>
 {error&&<p role="alert" className="data-warning">Monthly totals could not be verified.{data?" Showing the last checked snapshot.":" Please try again shortly."}</p>}
 {!data&&!error&&<div className="empty-state" role="status"><p>Checking monthly rewards…</p></div>}
 {data&&!data.months.length&&<div className="empty-state"><h2>No funded cycles yet.</h2><p>Monthly totals appear after successful auctions fund the edition wallets.</p></div>}
 <div className="rewards-cycles">{data?.months.map((m,index)=><article className={`reward-cycle ${index===0&&offset===0?"reward-cycle-featured":""}`} key={m.cycle}><header><div><span className="eyebrow">MONTHLY DRAW</span><h2>{monthLabel(m.cycle)}</h2></div><span className="pill">{stateLabel(m)}</span></header>
 <div className="reward-pool"><span>{m.status==="Drawn"?"Final prize pool":"Eligible draw pool"}</span><strong>{units(m.draw_amount,24)} <small>NEAR</small></strong></div>
 <dl className="reward-metrics"><div><dt>Eligible artworks</dt><dd>{m.eligible_nfts}</dd></div><div><dt>Early withdrawals</dt><dd>{m.early_withdrawals}</dd></div><div><dt>Incoming rollover</dt><dd>{units(m.incoming_rollover,24)} <small>NEAR</small></dd></div><div><dt>Rollover to {monthLabel(m.next_cycle)}</dt><dd>{units(m.next_month_rollover,24)} <small>NEAR</small></dd></div></dl>
 <footer><span>Cutoff · {new Date(Number(BigInt(m.cutoff_ns)/1000000n)).toLocaleString("en-GB",{day:"numeric",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit",timeZone:"UTC"})} UTC</span>{BigInt(m.awaiting_collection)>0n&&<span>{units(m.awaiting_collection,24)} NEAR held in edition wallets</span>}{BigInt(m.incoming_pending)>0n&&<span>{units(m.incoming_pending,24)} NEAR incoming rollover awaits transfer</span>}{m.pending_funding>0&&<span>{m.pending_funding} allocation{m.pending_funding===1?"":"s"} awaiting funding · {units(m.pending_funding_amount,24)} NEAR</span>}</footer>
 {m.winner&&<div className="reward-winner"><span>Winner</span><strong>{m.winner.beneficiary}</strong><small>{m.payout?.status==="Paid"?"Prize delivered":m.payout?.status==="Pending"?"Delivery in progress":"Awaiting delivery"}</small>{m.payout?.status==="Retryable"&&<Button disabled={busy||!walletTransactionsEnabled(health)} onClick={()=>wallet.account?void retry(m.cycle):void wallet.connect()}>{wallet.account?"Retry prize delivery":"Connect wallet"}</Button>}</div>}
 </article>)}</div>
 {data&&data.total>12&&<div className="owned-pagination"><Button disabled={!offset||isFetching} onClick={()=>setOffset(Math.max(0,offset-12))}>Newer cycles</Button><Button disabled={offset+12>=data.total||isFetching} onClick={()=>setOffset(offset+12)}>Older cycles</Button></div>}
 {message&&<TransactionMessage message={message} className="data-warning"/>}<TransactionLinks receipts={receipts}/>
 <p className="rewards-note">One ticket per eligible artwork. An early withdrawal removes its ticket and reserves the remaining funds for next month. Rollovers add funds, not tickets. Totals can change until cutoff; the draw waits for funding and collection to finish.</p>
 {dataUpdatedAt>0&&<p className="rewards-updated">Checked {new Date(dataUpdatedAt).toLocaleTimeString()} · Updates every 30 seconds.</p>}
 </div>;
}
