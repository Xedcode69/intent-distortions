"use client";
import Link from "next/link";
import { useState, useEffect } from "react";
import { ArrowRight, ArrowUpRight, Fingerprint, Layers3, Check, Circle, ChevronRight, Copy, Download, LoaderCircle } from "lucide-react";
import { motion } from "motion/react";
import { useAPI, api, short, date, type Art } from "@/lib/api";
import { Button } from "./ui/button";
import { SceneSvg } from "./scene-svg";
import { AnimatedArtwork } from "./animated-artwork";
import type { ArtworkScene } from "./historical-demo-types";
import {ArtworkTraits} from "./artwork-traits";

export function Loading({error}:{error?:Error|null}) {
 const empty=(error as Error & {status?:number})?.status===404;
 return <div className="empty-state">{error?<><Circle size={30}/><h2>{empty?"The first distortion is still becoming.":"The studio is temporarily unavailable."}</h2><p>{empty?"Verified editions will appear after a weekly dataset is frozen, rendered, and published.":error.message}</p>{empty?<Link className="button primary" href="/drops">Follow the next drop <ArrowRight size={15}/></Link>:<Button onClick={()=>location.reload()}>Try again <ArrowRight size={15}/></Button>}</>:<><LoaderCircle className="spin" size={28}/><p>Opening the studio…</p></>}</div>;
}
export function Countdown({target}:{target:number}) {
 const [now,setNow]=useState<number>(); useEffect(()=>{setNow(Date.now());const t=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(t);},[]);
 const seconds=Math.max(0,Math.floor((target*1000-(now||target*1000))/1000));
 return <span className="countdown">{[Math.floor(seconds/86400),Math.floor(seconds%86400/3600),Math.floor(seconds%3600/60)].map((n,i)=><span key={i}>{now?String(n).padStart(2,"0"):"--"}<small>{["DAYS","HOURS","MINS"][i]}</small></span>)}</span>;
}
export { ProductionHome as Home } from "./production-home";
export function ArtCard({art:a}:{art:Art}) {return <Link href={`/artwork/${a.id}`} className="art-card"><div className="card-image"><img src={a.thumbnail} alt={a.title} loading="lazy"/><span className="card-badge">{a.mode==="live"?"ONE OF ONE":a.mode==="historical_replay"?"HISTORICAL STUDY":"DEMO STUDY"}</span><span className="card-arrow"><ArrowUpRight size={21}/></span></div><div className="card-caption"><span className="overline">{a.edition} · {date(a.end)}</span><h3>{a.title}</h3><p>{a.composition.replaceAll("_"," ")}<span>{a.nft.status==="minted"?"Onchain":"Artwork study"}</span></p></div></Link>;}

type Manifest=ArtworkScene & {mapping:Record<string,unknown>};
function EditionAnimation({art}:{art:Art}){
 const {data:scene,error}=useAPI<ArtworkScene>(`/artworks/${art.id}/dna`);
 if(!scene)return <Loading error={error}/>;
 return <AnimatedArtwork scene={scene} seed={art.seed} title={art.title}/>;
}
export function DNA({art:a}:{art:Art}) {
 const {data:m,error}=useAPI<Manifest>(`/artworks/${a.id}/dna`);
 const [visible,setVisible]=useState<Record<string,boolean>>({routes:true,geometry:true,particles:true,inheritance:true,signature:true,surfaces:true,textures:true,lighting:true});
 const labels:Record<string,string>={routes:"Cross-chain routes",geometry:"Deterministic geometry",particles:"Transaction moments",inheritance:"Previous edition’s orbit",signature:"Unique edition signature",surfaces:"Filled surfaces and ribbons",textures:"Procedural textures",lighting:"Light and glow"};
 if(!m)return <Loading error={error}/>;
 return <div className="dna-layout"><div className="dna-canvas"><SceneSvg scene={m} visible={visible}/><span className="overline">INTERACTIVE SVG · CANONICAL PNG REMAINS FIXED</span></div><div className="dna-controls"><div className="eyebrow">REVEAL ITS DNA</div><h2>Every mark has<br/>a beginning.</h2><p>Explore the exact scene that produced this edition. Toggle a layer to discover what the data left behind.</p>{Object.keys(labels).map(key=><label key={key} className="toggle-row"><span>{labels[key]}</span><input type="checkbox" checked={visible[key]} onChange={e=>setVisible({...visible,[key]:e.target.checked})}/></label>)}<div className="dna-note"><Layers3 size={18}/><p>Timing sets angles. Public USD values set prominence. Source chains choose colors. Diversity deforms the geometry.</p></div><p className="muted">Creative direction: {a.ai_provider==="near_ai_cloud"?"NEAR AI Cloud":"deterministic fallback (AI not configured)"}.</p><a href={a.manifest.uri} target="_blank" rel="noreferrer" className="text-link">Inspect the scene manifest <ArrowUpRight size={14}/></a></div></div>;
}
export function ArtworkPage({id}:{id:string}){
 const {data:a,error}=useAPI<Art>(`/artworks/${id}`);
 const [tab,setTab]=useState("artwork"),[verification,setVerification]=useState<{valid:boolean;scope:string;checks:Record<string,boolean>}|null>(null),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
 useEffect(()=>{if(new URLSearchParams(location.search).get("view")==="dna")setTab("dna");},[]);
 async function verify(){setBusy(true);try{setVerification(await api(`/artworks/${id}/verify`));}catch(e){setMessage((e as Error).message);}finally{setBusy(false);}}
 if(!a)return <Loading error={error}/>;
 return <div className="page-container"><div className="breadcrumb"><Link href="/gallery">Collection</Link><ChevronRight size={12}/>{a.edition}</div><div className="detail-header"><div><div className="eyebrow">{a.edition} · ONE OF ONE · {a.mode.toUpperCase()}</div><h1>{a.title}</h1><p>{a.description}</p></div><a className="button subtle" href={a.image} download={`${a.edition}.png`}><Download size={15}/> Canonical image</a></div><div className="tabs">{["artwork","animated","dna","provenance"].map(t=><button key={t} onClick={()=>setTab(t)} className={tab===t?"active":""}>{t==="dna"?<><Fingerprint size={15}/>Reveal its DNA</>:t[0].toUpperCase()+t.slice(1)}</button>)}</div>
 {tab==="artwork"&&<div className="detail-layout"><div className="detail-image"><img src={a.image} alt={a.title}/></div><aside className="detail-sidebar"><span className="overline">A MOMENT MADE PERMANENT</span><h2>{a.edition}</h2><p>{date(a.start)} — {date(a.end)} UTC</p><div className="stat-pair"><span>Contributing records</span><b>{a.stats.total_swaps}</b></div><div className="stat-pair"><span>Source chains</span><b>{a.stats.unique_chains}</b></div><div className="stat-pair"><span>Composition</span><b>{a.composition.replaceAll("_"," ")}</b></div><div className="stat-pair"><span>Creative direction</span><b>{a.ai_provider==="near_ai_cloud"?"NEAR AI Cloud":"Deterministic fallback"}</b></div><div className="palette">{a.palette.map(c=><span key={c} style={{background:c}} title={c}/>)}</div><div className="auction-teaser"><span className="overline">COLLECT THIS DISTORTION</span><h3>{a.nft.status==="minted"?"Explore the auction":"Awaiting its onchain debut."}</h3><p>{a.nft.status==="minted"?"View contract state and bid with your wallet.":"This edition is awaiting a verified onchain mint and auction custody."}</p><Link href={`/auction/${a.id}`} className="button subtle">View auction status <ArrowUpRight size={15}/></Link></div></aside></div>}
 {tab==="artwork"&&<ArtworkTraits id={a.id}/>}
 {tab==="animated"&&<div className="dna-layout"><div className="dna-canvas"><EditionAnimation art={a}/></div><aside className="dna-controls"><h2>The week in motion.</h2><p>Explore the recorded scene with travelling route lights, activity-driven pulses and a chronological reveal. These are artistic encodings, not measurements of settlement speed. The canonical image and its hash remain fixed.</p></aside></div>}{tab==="dna"&&<DNA art={a}/>}{tab==="provenance"&&<div className="provenance-layout"><div><h2>A history you can verify.</h2><p>Recompute the snapshot, Merkle tree, seed, and file commitments. Source completeness and ownership require separate verification.</p>{[["Master art seed",a.seed],["Dataset Merkle root",a.merkle_root],["Canonical image SHA-256",a.image_hash],["Provenance SHA-256",a.provenance.sha256]].map(([label,value])=><div className="hash-field" key={label}><span className="overline">{label}</span><code>{value}</code><button aria-label={`Copy ${label}`} onClick={()=>{navigator.clipboard.writeText(value).then(()=>setMessage(`${label} copied`)).catch(()=>setMessage("Clipboard access unavailable"));}}><Copy size={15}/></button></div>)}<a href={a.provenance.uri} target="_blank" rel="noreferrer" className="text-link">Open full provenance JSON <ArrowUpRight size={15}/></a></div><div className="verification-panel"><Fingerprint size={32}/><h3>Trust the evidence.</h3><p>Verification reads the stored bytes and recomputes commitments. It does not rely on a saved verification flag.</p><Button className="primary" disabled={busy} onClick={verify}>{busy?<LoaderCircle size={16} className="spin"/>:<Check size={16}/>} Verify this artwork</Button>{verification&&<div className="verification-results" role="status"><b>{verification.valid?"All integrity checks passed":"Integrity mismatch detected"}</b>{Object.entries(verification.checks).map(([k,v])=><span key={k}>{v?<Check size={12}/>:<XIcon/>}{k.replaceAll("_"," ")}</span>)}<small>{verification.scope}</small></div>}<div className="data-warning">Source: {a.mode==="demo"?"synthetic fixture — not historical swap data":"recorded Explorer snapshot"}. Block evidence: {a.block.verified?"verified historical block":"unverified demo input"}. NFT: {a.nft.status.replaceAll("_"," ")}.</div></div></div>}{message&&<p className="inline-message" role="status">{message}</p>}</div>;
}
function XIcon(){return <Circle size={12}/>;}
