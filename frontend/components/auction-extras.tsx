"use client";
import {walletTransactionsEnabled} from "@/lib/api";
import {useState} from "react";
import {useAPI,type Health,yocto,short} from "@/lib/api";
import {contractAction} from "@/lib/wallet";
import {Button} from "./ui/button";
import {TransactionLinks,TransactionMessage} from "./transaction-links";
import type {TransactionReceipt} from "@/lib/transactions";
export function BidHistory({id}:{id:string}){
 const {data}=useAPI<{bids:{transaction_hash:string;bidder:string;amount:string;block_height:number}[];coverage:string}>(`/auctions/${id}/bids`);
 return <div className="auction-rules"><span className="overline">VERIFIED BID RECEIPTS</span>{data?.bids.length?data.bids.map((b,i)=><div className="stat-pair" key={`${b.transaction_hash}-${i}`}><span>{short(b.bidder,10)}</span><b>{yocto(b.amount)} NEAR</b></div>):<p>No verified bid receipts have been indexed yet.</p>}<p>Indexed history may lag. The highest bid above is queried directly from the contract.</p></div>;
}
export function OwnerCuration({tokenId}:{tokenId?:string}={}){
 const {data:h}=useAPI<Health>("/health");
 const {data:c,refetch}=useAPI<{theme:string;locked:boolean;deadline_ns:string;token_id:string|null}>("/analytics/curation");
 const [theme,setTheme]=useState("celestial"),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
 const [receipts,setReceipts]=useState<TransactionReceipt[]>([]);
 async function choose(){if(!h||!walletTransactionsEnabled(h))return;setBusy(true);setReceipts([]);try{const result=await contractAction(h.contracts.auction,h.network,"choose_theme",{theme});setReceipts([{hash:result.transaction.hash,network:h.network,label:"Theme selection"}]);setMessage("Theme transaction confirmed.");await refetch();}catch(e){setMessage((e as Error).message);}finally{setBusy(false);}}
 if(!c?.token_id||tokenId&&c.token_id!==tokenId)return null;
 return <div className="auction-rules"><span className="overline">OWNER CURATORIAL CHOICE</span><p>The current owner of {c.token_id} can choose one permitted style before the onchain deadline. The contract verifies ownership.</p><label className="bid-label">Theme<select value={theme} onChange={e=>setTheme(e.target.value)} disabled={c.locked}><option value="celestial">Celestial</option><option value="organic">Organic</option><option value="crystalline">Crystalline</option></select></label><Button className="subtle" onClick={choose} disabled={busy||c.locked||!walletTransactionsEnabled(h)}>{c.locked?"Choice locked":"Submit owner’s choice"}</Button>{message&&<TransactionMessage message={message} className="inline-message"/>}<TransactionLinks receipts={receipts}/></div>;
}
