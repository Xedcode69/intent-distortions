"use client";
import {financialNow,walletTransactionsEnabled} from "@/lib/api";
import {useState} from "react";
import {useAPI,yocto,toYocto,type Health} from "@/lib/api";
import {contractAction} from "@/lib/wallet";
import {simulateEconomy,monthLabel,type Economy,type EditionWallet,type Month} from "@/lib/economy";
import {Button} from "./ui/button";
import {Loading} from "./studio";

export function EconomyExample(){
 const [sales,setSales]=useState(5),[exits,setExits]=useState(2),[price,setPrice]=useState("100");
 let example;try{example=simulateEconomy(sales,Math.min(exits,sales),BigInt(toYocto(price)));}catch{example=null;}
 return <section className="economy-section economy-example"><span className="eyebrow">INTERACTIVE EXPLANATION · SIMULATED FUNDS</span><h2>Follow every NEAR.</h2><p>This example explains the rules. It creates no accounts, bids, transfers or raffle entries.</p>
 <div className="economy-inputs"><label>Auction price per NFT (NEAR)<input inputMode="decimal" value={price} onChange={e=>setPrice(e.target.value)}/></label>
 <label>Successful sales: {sales}<input type="range" min="0" max="5" value={sales} onChange={e=>{const n=Number(e.target.value);setSales(n);setExits(Math.min(exits,n));}}/></label>
 <label>Early withdrawals: {Math.min(exits,sales)}<input type="range" min="0" max={sales} value={Math.min(exits,sales)} onChange={e=>setExits(Number(e.target.value))}/></label></div>
 {example?<><div className="economy-flow" aria-label="Auction proceeds distribution">{[["Treasury",example.treasury],["Early withdrawals",example.withdrawals],["Current pot",example.pot],["Next month",example.rollover]].map(([label,amount])=><div key={String(label)}><span>{String(label)}</span><strong>{yocto(String(amount))}</strong><small>NEAR</small></div>)}</div>
 <p role="status">{example.tickets} eligible NFT{example.tickets===1?"":"s"}{example.tickets>0?`, each with one of ${example.tickets} tickets`:"; the pot carries forward if there are no entries"}. Total allocated: {yocto(example.gross.toString())} NEAR.</p></>:<p role="alert">Enter a valid non-negative NEAR amount.</p>}
 </section>;
}

function WalletCard({d,enabled,busy,onAction}:{d:EditionWallet;enabled:boolean;busy:boolean;onAction:(method:string,args:Record<string,unknown>,deposit?:string)=>Promise<void>}){
 const [recipient,setRecipient]=useState("");
 const {data:detail}=useAPI<{current_owner:string|null;vault_state:{early:{status:string}|null;collection:{status:string}|null}|null}>(`/economy/wallets/${d.token_id}`);
 const {data:health}=useAPI<Health>("/health");
 const now=financialNow(health);const cycleEnd=d.cycle?Date.UTC(Math.floor(d.cycle/100)+(d.cycle%100===12?1:0),d.cycle%100===12?0:d.cycle%100,1):0;
 const canExit=enabled&&d.wallet_status==="Funded"&&!!d.cycle&&!d.exited&&!d.collected&&!d.transfer_pending&&now<cycleEnd;
 const exit=(BigInt(d.original)*2n/5n).toString();
 return <article className="edition-wallet"><div className="economy-row"><h3>{d.token_id}</h3><span className="pill">{d.exited?"EXIT USED":d.collected?"POOLED":d.cycle?"FUNDED":"UNFUNDED"}</span></div>
 <code className="economy-address">{d.account_id}</code><p>Account: {d.wallet_status}. {d.cycle?`Funded for ${monthLabel(d.cycle)}.`:"This edition has no funded raffle entry."}</p><p>Current NFT owner: {detail?.current_owner||"Reading contract…"}</p>
 <dl className="economy-balances"><div><dt>Original allocation</dt><dd>{yocto(d.original)} NEAR</dd></div><div><dt>Uncollected allocation</dt><dd>{yocto(d.remaining)} NEAR</dd></div><div><dt>Monthly beneficiary</dt><dd>{d.beneficiary}</dd></div></dl>
 {d.exited?<p>Withdrawal belongs to {d.exit_beneficiary}. Payment: {detail?.vault_state?.early?.status||"Awaiting vault registration"}. The remaining allocation funds a later pot and creates no new ticket.</p>:d.cycle?<p>One withdrawal pays {yocto(exit)} NEAR and removes this NFT from its funded cycle’s draw.</p>:null}
 <Button disabled={!canExit||busy} onClick={()=>onAction("withdraw_edition",{token_id:d.token_id},"1")}>Withdraw {yocto(exit)} NEAR · leave draw</Button>
 {d.exited&&<Button className="subtle" disabled={!enabled||busy} onClick={()=>onAction("dispatch_exit",{token_id:d.token_id})}>Check / retry withdrawal</Button>}
 <details><summary>Transfer this NFT</summary><p>Only the current owner can transfer. Unused rights follow the NFT before the cutoff; already fixed monthly entitlements stay with the recorded beneficiary.</p>
 <label className="bid-label">Recipient NEAR account<input value={recipient} onChange={e=>setRecipient(e.target.value)} placeholder="collector.near"/></label>
 <Button className="subtle" disabled={!enabled||busy||!recipient.trim()||d.transfer_pending} onClick={()=>onAction("nft_transfer",{receiver_id:recipient.trim(),token_id:d.token_id,approval_id:null,memo:null},"1")}>Authorize NFT transfer</Button></details>
 </article>;
}

export function EconomyDashboard(){
 const {data:e,error,refetch}=useAPI<Economy>("/economy");const {data:h}=useAPI<Health>("/health");
 const [offset,setOffset]=useState(0),[monthOffset,setMonthOffset]=useState(0),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
 const {data:wallets,refetch:refreshWallets,error:walletError}=useAPI<EditionWallet[]>(`/economy/wallets?offset=${offset}&limit=50`);
 const {data:months,refetch:refreshMonths,error:monthError}=useAPI<Month[]>(`/economy/months?offset=${monthOffset}&limit=24`);
 const enabled=walletTransactionsEnabled(h)&&e?.status==="onchain"&&!!h.contracts.nft;
 async function action(method:string,args:Record<string,unknown>,deposit="0"){
  if(!enabled||!h)return;setBusy(true);setMessage("");
  try{const result=await contractAction(h.contracts.nft,h.network,method,args,deposit);setMessage(`Transaction confirmed: ${result.transaction.hash}. Delivery status is verified separately.`);await Promise.all([refetch(),refreshWallets(),refreshMonths()]);}
  catch(err){setMessage((err as Error).message);}finally{setBusy(false);}
 }
 if(!e)return <Loading error={error}/>;
 return <div className="page-container"><div className="page-title"><span className="eyebrow">THE COLLECTION ECONOMY</span><h1>Art that comes<br/><em>full circle.</em></h1><p>Every edition has a story. And an account of its own.</p></div>
 <div className="notice">{e.status==="onchain"?`Contract state on ${h?.network||"the configured network"}.`:"Preview · No live funds or draws. Explore the rules below."}</div>
 <section className="economy-flow economy-policy">{[["Treasury","20%","Reserved for development"],["Edition vault","80%","Funded by its primary auction"],["Optional withdrawal","40%","Of the original vault allocation"],["Monthly prize","1 winner","One ticket per eligible NFT"]].map(([label,value,note])=><div key={label}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>)}</section>
 <p className="economy-disclosure">This distributes auction proceeds and generates no external yield. An early withdrawal removes the edition from its funded cycle. Otherwise its allocation enters the pot and is consumed when the prize is awarded, including for non-winning NFTs. The artwork remains owned by its holder.</p>
 <details><summary>Launch schedule & treasury</summary> <section className="economy-section"><span className="eyebrow">LAUNCH SCHEDULE · UTC</span><h2>Three creator editions, then auctions.</h2><p>November 15, 22 and 29, 2026: editions 1–3 go to the team. December 6 starts the 24-hour weekly auctions. An auction without bids returns the edition to the team and creates no funded raffle entry.</p><code className="economy-address">december2026-edition-1.&lt;nft-contract-account&gt;</code><p>The number resets every calendar month. Every account is controlled by the NFT contract; owning the NFT grants only its published rights.</p></section>
 <section className="economy-section"><div className="economy-row"><div><span className="eyebrow">ONCHAIN TREASURY</span><h2>{yocto(e.treasury_earned)} NEAR allocated</h2></div><span className="pill">20% OF SUCCESSFUL AUCTIONS</span></div><code className="economy-address">{e.treasury||"Treasury account pending deployment"}</code><p>Awaiting transfer: {yocto(e.treasury_credit)} NEAR. Gas and account storage are funded separately.</p></section>
</details>
 <section className="economy-section"><span className="eyebrow">THE EDITION ACCOUNTS</span><h2>Art with something in it.</h2>
 {walletError?<p role="alert">Edition accounts could not be queried.</p>:wallets?.length?<div className="economy-wallet-grid">{wallets.map(d=><WalletCard key={d.token_id} d={d} enabled={!!enabled} busy={busy} onAction={action}/>)}</div>:<p>No edition accounts have been recorded on the configured contract.</p>}
 <div className="economy-pagination"><Button className="subtle" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-50))}>Previous editions</Button><Button className="subtle" disabled={!wallets||wallets.length<50} onClick={()=>setOffset(offset+50)}>Next editions</Button></div></section>
 <section className="economy-section"><span className="eyebrow">MONTHLY DRAWS</span><h2>A new chapter, every month.</h2>
 {monthError?<p role="alert">Monthly pots could not be queried.</p>:months?.length?months.map(m=><article className="economy-month" key={m.cycle}><div className="economy-row"><h3>{monthLabel(m.cycle)}</h3><span className="pill">{m.status}</span></div><div className="economy-flow"><div><span>Unawarded pot</span><strong>{yocto(m.pot)}</strong><small>NEAR</small></div><div><span>Incoming rollover</span><strong>{yocto(m.rollover_received)}</strong><small>NEAR</small></div><div><span>Frozen tickets</span><strong>{m.entries.length}</strong><small>One per eligible NFT</small></div><div><span>Receipts received</span><strong>{m.received_receipts} / {m.expected_receipts}</strong><small>{m.pending_sources} source wallets pending</small></div></div>
 <p>Cutoff: {new Date(Number(BigInt(m.cutoff_ns)/1_000_000n)).toISOString()}. Fixed drand round: {m.entropy_round}.</p>
 {m.winner&&<p>Winner: <b>{m.winner.token_id}</b> · {m.winner.beneficiary}. Prize: {yocto(m.prize)} NEAR. Payment: {m.payout?.status}.</p>}
 {m.payout?.status==="Retryable"&&<Button disabled={!enabled||busy} onClick={()=>action("pay_month",{cycle:m.cycle})}>Retry prize delivery</Button>}
 <details><summary>Entries and randomness</summary>{m.entries.map(t=><p key={t.token_id}>{t.token_id} → {t.beneficiary}</p>)}<code className="economy-address">{m.randomness||"No randomness recorded. Empty pots carry forward; one-ticket outcomes need no random selection."}</code></details></article>):<p>No monthly pot has been opened yet.</p>}
 <div className="economy-pagination"><Button className="subtle" disabled={monthOffset===0} onClick={()=>setMonthOffset(Math.max(0,monthOffset-24))}>Previous cycles</Button><Button className="subtle" disabled={!months||months.length<24} onClick={()=>setMonthOffset(monthOffset+24)}>Next cycles</Button></div></section>
 {message&&<p className="notice" role="status">{message}</p>}<details><summary>Try the auction economy simulator</summary><EconomyExample/></details>
 </div>;
}
