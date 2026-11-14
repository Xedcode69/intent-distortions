"use client";
import {financialNow,walletTransactionsEnabled} from "@/lib/api";
import { useState } from "react";
import {useQuery} from "@tanstack/react-query";
import {useWallet} from "./wallet-provider";
import {submitAuctionBid,type BidderStatus} from "@/lib/auction-bid";
import Link from "next/link";
import { ArrowUpRight, ArrowRight, Check, Circle, Fingerprint, LoaderCircle } from "lucide-react";
import { ResponsiveContainer, AreaChart, Area, XAxis, Tooltip } from "recharts";
import { useAPI, api, date, type Art, type Health, toYocto, yocto } from "@/lib/api";
import { contractAction, walletAccount } from "@/lib/wallet";
import { ArtCard, Countdown, Loading } from "./studio";
import { Button } from "./ui/button";
import { BidHistory,OwnerCuration } from "./auction-extras";
import {TransactionLinks,TransactionMessage} from "./transaction-links";
import {transactionLabel,type TransactionReceipt} from "@/lib/transactions";
import {units} from "@/lib/marketplace";

export function Gallery(){
 const {data:arts,error}=useAPI<Art[]>("/artworks");const [sort,setSort]=useState("newest"),[family,setFamily]=useState("all");
 if(!arts)return <Loading error={error}/>;
 const sorted=[...arts].filter(a=>family==="all"||a.composition===family).sort((a,b)=>sort==="newest"?b.number-a.number:a.number-b.number);
 return <div className="page-container"><div className="page-title"><span className="eyebrow">ONE WEEK. ONE ORIGINAL.</span><h1>Every distortion.<br/><em>Its own world.</em></h1><p>A collection shaped by the weeks that made it.</p></div><div className="gallery-toolbar"><div className="collection-count"><span>{arts.length} {arts.length===1?"artwork":"artworks"}</span><Link href="/my-collection" className="text-link">My collection <ArrowUpRight size={14}/></Link></div><div><label>Family<select value={family} onChange={e=>setFamily(e.target.value)}><option value="all">All families</option>{[...new Set(arts.map(a=>a.composition))].map(f=><option value={f} key={f}>{f.replaceAll("_"," ")}</option>)}</select></label><label>View<select value={sort} onChange={e=>setSort(e.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select></label></div></div><div className="gallery-grid">{sorted.map(a=><ArtCard art={a} key={a.id}/>)}</div>{!sorted.length&&<div className="empty-state"><h2>Nothing here just yet.</h2><p>Try another family, or come back for the next drop.</p><Link href="/drops" className="text-link">Next drop <ArrowUpRight size={15}/></Link></div>}</div>;
}

export { Drops } from "./drops";
export {EconomyDashboard as Treasury} from "./economy-dashboard";

type Auction={token_id:string;status:string;highest_bid:string;highest_bidder:string|null;min_bid:string;increment:string;end_ns:string;custody_verified:boolean};
export function AuctionPage({id}:{id:string}){
 const {data:a,error}=useAPI<Art>(`/artworks/${id}`);const {data:h}=useAPI<Health>("/health");
 const {data:auction,error:auctionError,isPending:auctionPending,refetch}=useAPI<Auction>(`/auctions/${id}`);
 const [amount,setAmount]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
 const [receipts,setReceipts]=useState<TransactionReceipt[]>([]);
 const wallet=useWallet(),account=wallet.account;
 const {data:bidder,error:bidderError,refetch:refreshBidder}=useQuery({queryKey:["auction-bidder",h?.network,h?.contracts.auction,account],queryFn:()=>api<BidderStatus>(`/auctions/bidders/${encodeURIComponent(account)}`),enabled:!!account&&!!h?.contracts.auction,refetchInterval:30000});
 async function action(method:string,args:Record<string,unknown>,deposit="0"){
  if(!h||!walletTransactionsEnabled(h)){setMessage("Wallet actions are temporarily unavailable.");return;}
  if(!account){await wallet.connect();return;}
  setBusy(true);setMessage("");setReceipts([]);
  try{
   if(await walletAccount(h.contracts.auction,h.network)!==account)throw new Error("Wallet account changed. Review the transaction again.");
   let reviewedNow=financialNow(h);
   const send=async(name:string,values:Record<string,unknown>,attached:string)=>{const sent=await contractAction(h.contracts.auction,h.network,name,values,attached,account);setReceipts(previous=>[...previous,{hash:sent.transaction.hash,network:h.network,label:transactionLabel(name)}]);return sent;};
   const result=method==="place_bid"?await submitAuctionBid({account,contract:h.contracts.auction,tokenId:auction!.token_id,amount:deposit},{
    currentAccount:()=>walletAccount(h.contracts.auction,h.network),
    readBidder:()=>api<BidderStatus>(`/auctions/bidders/${encodeURIComponent(account)}`),
    readAuction:async()=>{
     const [latest,health]=await Promise.all([api<Auction>(`/auctions/${id}`),api<Health>("/health")]);
     if(!walletTransactionsEnabled(health)||health.network!==h.network||health.contracts.auction!==h.contracts.auction)throw new Error("Auction connection changed. Review the bid again.");
     reviewedNow=financialNow(health);return latest;
    },now:()=>reviewedNow,
    submit:send,
    progress:phase=>setMessage(phase==="registration"?"Approve the one-time 0.01 NEAR registration (1 of 2).":"Approve your bid in the wallet."),
   }):await send(method,args,deposit);
   setMessage("Transaction confirmed.");await Promise.all([refetch(),refreshBidder()]);
  }catch(e){setMessage((e as Error).message);}finally{setBusy(false);void refreshBidder();}
 }
 if(!a)return <Loading error={error}/>;
 const active=auction?.status==="Active"&&financialNow(h)<Number(BigInt(auction.end_ns)/1000000n)&&walletTransactionsEnabled(h);
 const unavailable=!!auctionError&&(auctionError as Error & {status?:number}).status!==404;
 const pendingLabel=a.auction.status==="CreatorMinted"?"CREATOR EDITION · NO AUCTION":auctionPending?"READING AUCTION STATE":unavailable?"AUCTION STATE UNAVAILABLE":a.nft.status==="minted"?"AUCTION NOT CREATED":"MINT PENDING · NO AUCTION";
 const ended=!!auction&&financialNow(h)>=Number(BigInt(auction.end_ns)/1000000n);
 const sold=auction?.status==="Settled",unsold=auction?.status==="Unsold";
 const creator=a.auction.status==="CreatorMinted"&&!auction;
 return <div className="page-container auction-page"><div className="breadcrumb"><Link href={`/artwork/${id}`}>{a.edition}</Link><ArrowRight size={12}/>Auction</div>
 <div className="auction-layout"><div><img className="auction-image" src={a.image} alt={a.title}/><span className="overline">{a.edition} · ONE OF ONE</span><h2>{a.title}</h2></div>
 <section className="auction-panel"><span className="eyebrow">COLLECT A MOMENT IN HISTORY</span><h1>{sold?<>A new<br/>chapter.</>:unsold?<>The auction<br/>has closed.</>:creator?<>A creator<br/>edition.</>:auction?<>Make it<br/>yours.</>:<>Its next chapter<br/>is still ahead.</>}</h1>
 {auction?<><span className="pill">{sold?"Sold":unsold?"No bids":auction.status==="Active"&&ended?"Awaiting settlement":auction.status}</span>
 <div className="current-bid"><span className="overline">{sold?"WINNING BID":"HIGHEST BID"}</span><b>{units(auction.highest_bid,24)} <small>NEAR</small></b></div>
 {sold&&<p className="auction-outcome">Winning bidder: <strong>{auction.highest_bidder}</strong></p>}
 {unsold&&<p className="auction-outcome">No bids were placed. The artwork was sent to the team wallet.</p>}
 {auction.status==="Active"&&!ended&&<><Countdown target={Number(BigInt(auction.end_ns)/1000000000n)}/><p>Minimum next bid: {units(BigInt(auction.highest_bid)>0n?(BigInt(auction.highest_bid)+BigInt(auction.increment)).toString():auction.min_bid,24)} NEAR</p>
 {account&&bidder?.registered===false&&<p className="auction-registration-note">Your first bid includes 0.01 NEAR bidder registration. Approve setup, then the bid.</p>}
 {account&&!bidder&&!bidderError&&<p role="status">Checking bidder registration…</p>}
 {bidderError&&<p role="status">Registration could not be checked. <button className="text-link" onClick={()=>void refreshBidder()}>Try again</button></p>}
 <label className="bid-label">Your bid · NEAR<input value={amount} onChange={e=>setAmount(e.target.value)} inputMode="decimal" placeholder="0.00"/></label>
 <Button className="primary" disabled={!active||!auction.custody_verified||busy||!!account&&!amount} onClick={()=>{if(!account){void wallet.connect();return;}try{void action("place_bid",{token_id:auction.token_id},toYocto(amount));}catch(e){setMessage((e as Error).message);}}}>{account?"Place bid":"Connect wallet to bid"}<ArrowUpRight size={15}/></Button></>}
 {auction.status==="Active"&&ended&&<p>Bidding has ended. The artwork is awaiting settlement.</p>}
 {bidder&&BigInt(bidder.refund_yocto)>0n&&<Button className="subtle" disabled={busy||!walletTransactionsEnabled(h)} onClick={()=>void action("claim_refund",{},"1")}>Claim {units(bidder.refund_yocto,24)} NEAR refund</Button>}
 {["Active","RecoveryRequired"].includes(auction.status)&&ended&&<Button className="subtle" disabled={busy||!walletTransactionsEnabled(h)} onClick={()=>void action("finalize_auction",{token_id:auction.token_id})}>Settle ended auction</Button>}
 {(sold||unsold)&&<Link href={`/marketplace?token=${encodeURIComponent(auction.token_id)}`} className="button subtle">Artwork & ownership <ArrowUpRight size={15}/></Link>}
 </>:<><div className="unminted-mark"><Circle size={28} strokeWidth={1}/><span>{pendingLabel}</span></div><p>{creator?"This artwork was issued as a creator edition, without an auction.":unavailable?"Auction state could not be verified. Please try again shortly.":"Bidding opens once the artwork is minted and auction custody is verified."}</p>
 <Link href={creator?`/marketplace?token=${encodeURIComponent(a.edition)}`:`/artwork/${id}?view=dna`} className="button subtle">{creator?"Artwork & ownership":"Explore the artwork"}<ArrowUpRight size={15}/></Link></>}
 {message&&<TransactionMessage message={message} className="inline-message"/>}<TransactionLinks receipts={receipts}/>
 {auction&&<BidHistory id={id}/>}<OwnerCuration tokenId={a.edition}/>
 <details className="auction-rules"><summary>Auction rules</summary><p>24-hour auction · NEAR bids · losing bid principal is refunded. Successful sales allocate 20% to treasury and 80% to the edition wallet. Early withdrawal removes the artwork from its funded month's draw.</p></details>
 </section></div></div>;
}
