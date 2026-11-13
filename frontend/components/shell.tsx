"use client";
import Link from "next/link";
import {usePathname} from "next/navigation";
import {ArrowUpRight,Menu,X} from "lucide-react";
import {useState,useEffect} from "react";
import {useAPI,type Health} from "@/lib/api";
import {WalletControl} from "./wallet-control";
import {useWallet} from "./wallet-provider";
const links=[["/drops","Drops"],["/gallery","Collection"],["/marketplace","Market"],["/demo","The story"],["/economy","Rewards"]];
export function Mark(){return <svg width="32" height="32" viewBox="0 0 40 40" fill="none" aria-hidden="true"><path d="M6 29V11L34 29V11M14 11V29M26 11V29" stroke="currentColor" strokeWidth="2.5"/><path d="M1 1H39V39H1Z" stroke="currentColor" strokeWidth="1.5"/></svg>;}
export function Shell({children}:{children:React.ReactNode}){
 const path=usePathname(),[open,setOpen]=useState(false);
 const {error:message}=useWallet();
 const {data:health}=useAPI<Health>("/health");
 const readOnly=path==="/demo"||health?.mode!=="live";
 useEffect(()=>{if(!open)return;const close=(e:KeyboardEvent)=>{if(e.key==="Escape")setOpen(false);};document.addEventListener("keydown",close);return()=>document.removeEventListener("keydown",close);},[open]);
 return <><a href="#main-content" className="skip-link">Skip to content</a><header className="header"><Link href="/" className="brand" aria-label="NEAR ECHOES home"><Mark/><span>NEAR<span className="brand-echoes">ECHOES</span></span></Link><nav id="site-navigation" aria-label="Main navigation" className={open?"nav open":"nav"}>{links.map(([href,label])=><Link key={href} href={href} onClick={()=>setOpen(false)} aria-current={path===href?"page":undefined} className={path===href?"selected":""}>{label}{href==="/drops"&&<span className="nav-dot"/>}</Link>)}</nav><div className="nav-actions"><span className="site-status"><i/>{readOnly?"Preview":health?.network||"Connecting"}</span><WalletControl/><button className="mobile-menu" aria-label={open?"Close navigation":"Open navigation"} aria-controls="site-navigation" aria-expanded={open} onClick={()=>setOpen(!open)}>{open?<X/>:<Menu/>}</button></div></header>
 {message&&<div className="notice" role="status">{message}</div>}
 <main id="main-content">{children}</main><footer className="site-footer"><div className="footer-top"><p>A little history.<br/>A lasting impression.</p><div><Link href="/drops">Next drop <ArrowUpRight size={15}/></Link><Link href="/demo">How it works <ArrowUpRight size={15}/></Link><Link href="/marketplace">Collect an echo <ArrowUpRight size={15}/></Link></div></div><Link href="/" className="footer-wordmark" aria-label="NEAR ECHOES home">ECHOES<span>↗</span></Link><div className="footer-bottom"><span>ONE WEEK. ONE ORIGINAL.</span><span>BUILT ON NEAR · {health?.mode==="live"?health.network:"READ-ONLY PREVIEW"}</span></div></footer></>;
}
