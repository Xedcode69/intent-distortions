"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, Menu, X, Wallet, Activity } from "lucide-react";
import { useState } from "react";
import { useAPI, type Health } from "@/lib/api";
import { connectWallet } from "@/lib/wallet";
const links=[["/","Studio"],["/genesis","Live genesis"],["/gallery","Collection"],["/demo","Demo"],["/treasury","Treasury"]];
export function Mark(){return <svg width="34" height="34" viewBox="0 0 40 40" fill="none" aria-hidden="true"><path d="M7 30V10l26 20V10M14 10v20M26 10v20" stroke="currentColor" strokeWidth="2"/><circle cx="20" cy="20" r="18" stroke="currentColor" opacity=".35"/></svg>;}
export function Shell({children}:{children:React.ReactNode}) {
 const path=usePathname(), [open,setOpen]=useState(false),[message,setMessage]=useState("");
 const {data:health}=useAPI<Health>("/health");
 const demoSection=path==="/demo", readOnly=demoSection||health?.mode==="historical_replay";
 async function wallet(){try{await connectWallet(health?.contracts.auction||"",health?.network||"testnet");setMessage("");}catch(e){setMessage((e as Error).message);}}
 return <><header className="header"><Link href="/" className="brand" aria-label="NEAR ECHOES home"><Mark/><span>NEAR <b>ECHOES</b></span></Link><nav aria-label="Main navigation" className={open?"nav open":"nav"}>{links.map(([href,label])=><Link key={href} href={href} onClick={()=>setOpen(false)} className={path===href?"selected":""}>{label}{href==="/genesis"&&<span className="live-dot"/>}</Link>)}</nav><div className="nav-actions"><span className="network"><span/> {demoSection?"read-only demo":health?.network||"testnet"}</span><button className="wallet" disabled={readOnly} onClick={wallet}><Wallet size={15}/><span>{readOnly?"Read-only replay":"Connect wallet"}</span></button><button className="mobile-menu" aria-label={open?"Close navigation":"Open navigation"} onClick={()=>setOpen(!open)}>{open?<X/>:<Menu/>}</button></div></header>
 {message&&<div className="notice" role="status">{message}<button aria-label="Dismiss notification" onClick={()=>setMessage("")}><X size={16}/></button></div>}
 <div className="mode-strip"><span><Activity size={12}/>{demoSection?"DEMO · HISTORICAL REPLAY":health?.mode==="demo"?"DEMO STUDIO · SYNTHETIC DATA":health?.mode==="historical_replay"?"HISTORICAL REPLAY · READ-ONLY":health?health.mode.toUpperCase():"CONNECTING TO STUDIO"}</span><span>{demoSection?"A saved real-data demonstration. Availability and evidence are shown below.":health?.mode==="demo"?"A reproducible preview. No real swaps, mints, or bids.":health?.mode==="historical_replay"?"Past swap records observed at capture time. No live auction.":"One canonical edition per weekly checkpoint."}<ArrowUpRight size={12}/></span></div>
 <main>{children}</main><footer><Link className="brand" href="/"><Mark/><span>NEAR <b>ECHOES</b></span></Link><p>One week. One block. One artwork. Never repeated.</p><span>BUILT ON NEAR <ArrowUpRight size={13}/></span></footer></>;
}
