"use client";
import { useState } from "react";
import Link from "next/link";
import { ArrowUpRight, ArrowRight, Check, Circle, Fingerprint, LoaderCircle } from "lucide-react";
import { ResponsiveContainer, AreaChart, Area, XAxis, Tooltip } from "recharts";
import { useAPI, api, date, type Art, type Health, toYocto, yocto } from "@/lib/api";
import { contractAction } from "@/lib/wallet";
import { ArtCard, Countdown, Loading } from "./studio";
import { Button } from "./ui/button";
import { BidHistory,OwnerCuration } from "./auction-extras";

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
 async function action(method:string,args:Record<string,unknown>,deposit="0"){
  if(!h||h.mode!=="live"){setMessage("This preview is read-only.");return;}setBusy(true);try{const result=await contractAction(h.contracts.auction,h.network,method,args,deposit);setMessage(`Transaction confirmed: ${result.transaction.hash}`);await refetch();}catch(e){setMessage((e as Error).message);}finally{setBusy(false);}
 }
 if(!a)return <Loading error={error}/>;
 const active=auction?.status==="Active"&&h?.mode==="live";
 const unavailable=!!auctionError&&(auctionError as Error & {status?:number}).status!==404;
 const pendingLabel=a.auction.status==="CreatorMinted"?"CREATOR EDITION · NO AUCTION":auctionPending?"READING AUCTION STATE":unavailable?"AUCTION STATE UNAVAILABLE":a.nft.status==="minted"?"AUCTION NOT CREATED":"MINT PENDING · NO AUCTION";
 return <div className="page-container"><div className="breadcrumb"><Link href={`/artwork/${id}`}>{a.edition}</Link><ArrowRight size={12}/>Auction</div><div className="auction-layout"><div><img className="auction-image" src={a.image} alt={a.title}/><span className="overline">{a.edition} · ONE OF ONE</span><h2>{a.title}</h2></div><section className="auction-panel"><span className="eyebrow">COLLECT A MOMENT IN HISTORY</span><h1>{auction?"Make it yours.":"Its next chapter<br/>is still ahead."}</h1>{auction?<><span className="pill">{auction.status}</span><div className="current-bid"><span className="overline">HIGHEST BID</span><b>{yocto(auction.highest_bid)} <small>NEAR</small></b></div><Countdown target={Number(BigInt(auction.end_ns)/1_000_000_000n)}/><p>Minimum next bid: {yocto(BigInt(auction.highest_bid)>0n?(BigInt(auction.highest_bid)+BigInt(auction.increment)).toString():auction.min_bid)} NEAR</p><label className="bid-label">Your bid (NEAR)<input value={amount} onChange={e=>setAmount(e.target.value)} inputMode="decimal" placeholder="0.00"/></label><Button className="primary" disabled={!active||busy||!amount} onClick={()=>{try{void action("place_bid",{token_id:auction.token_id},toYocto(amount));}catch(e){setMessage((e as Error).message);}}}>Place wallet-authorized bid <ArrowUpRight size={15}/></Button><Button className="subtle" disabled={busy} onClick={()=>action("register_bidder",{},"10000000000000000000000")}>Register bidder storage · 0.01 NEAR</Button><Button className="subtle" disabled={busy} onClick={()=>action("claim_refund",{},"1")}>Claim available refund</Button><Button className="subtle" disabled={busy||!auction||!["Active","RecoveryRequired"].includes(auction.status)||Date.now()<Number(BigInt(auction.end_ns)/1_000_000n)} onClick={()=>action("finalize_auction",{token_id:auction.token_id})}>Settle ended auction</Button></>:<><div className="unminted-mark"><Circle size={34} strokeWidth={1}/><span>{pendingLabel}</span></div><p>{unavailable?"The contract could not be queried. Its ownership and auction state have not been inferred.":"Bidding opens after this edition is minted and its auction contract has verified NFT custody."}</p><div className="data-warning">Auction values are read from the configured NEAR network. Until custody is verified, bidding remains unavailable.</div><Link href={`/artwork/${id}?view=dna`} className="button primary">Explore the artwork’s DNA <Fingerprint size={16}/></Link></>}{message&&<p role="status" className="inline-message">{message}</p> }{auction&&<BidHistory id={id}/>}<OwnerCuration/><div className="auction-rules"><span className="overline">THE PUBLISHED RULES</span><p>24-hour auction · native NEAR bids · automatic losing-bid refunds with retryable claims · 20% treasury and 80% edition vault after confirmed NFT delivery. Monthly participation consumes the contributed balance; early withdrawal removes this edition from its funded draw.</p></div></section></div></div>;
}
