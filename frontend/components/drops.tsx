"use client";
import Link from "next/link";
import {useState,useEffect} from "react";
import {useQuery} from "@tanstack/react-query";
import {ArrowUpRight,Clock,LoaderCircle} from "lucide-react";
import {api} from "@/lib/api";
import type {DropFeed,DropArtwork,ActiveDrop} from "@/lib/drops";
import type {ArtworkScene} from "./historical-demo-types";
import {Countdown} from "./studio";
import {ReplayProgress} from "./replay-progress";
import {AnimatedArtwork} from "./animated-artwork";

const utc=(seconds:number)=>new Intl.DateTimeFormat("en-GB",{dateStyle:"full",timeStyle:"short",timeZone:"UTC"}).format(seconds*1000)+" UTC";
const count=(n:number|undefined|null)=>n==null?"—":n.toLocaleString("en-GB");
const stages=[
 {key:"checkpoint",title:"Checkpoint",detail:"Verify the scheduled beacon and selected historical block."},
 {key:"collection",title:"Collect",detail:"Collect records for the exact interval; retain successful eligible swaps."},
 {key:"reconciliation",title:"Freeze",detail:"Reconcile complete observations before the fixed data freeze."},
 {key:"art_direction",title:"Direction",detail:"The seed selects the family; recorded AI styling defines its character."},
 {key:"rendering",title:"Create",detail:"Render geometry, materials and motion controls from the frozen inputs."},
 {key:"preparing_files",title:"Save",detail:"Store the canonical image, scene and provenance."},
 {key:"ready",title:"Artwork ready",detail:"Explore the saved artwork. NFT minting and auctions have separate statuses."},
];

function CreatedArtwork({art}:{art:DropArtwork}){
 const [animated,setAnimated]=useState(false);
 const {data:scene,error}=useQuery<ArtworkScene>({queryKey:["drop-scene",art.id],queryFn:()=>api(`/artworks/${art.id}/dna`),enabled:animated});
 return <div className="drop-created"><div className="tabs" role="group" aria-label="Drop artwork view"><button aria-pressed={!animated} className={!animated?"active":""} onClick={()=>setAnimated(false)}>Static image</button><button aria-pressed={animated} className={animated?"active":""} onClick={()=>setAnimated(true)}>Animated view</button></div>
 <div className="drop-artwork">{!animated?<img src={art.image} alt={art.title}/>:scene?<AnimatedArtwork key={art.id} scene={scene} seed={art.seed} title={art.title}/>:<div className="empty-state"><p role="status">{error?"The saved animation could not be loaded.":"Loading the recorded scene…"}</p></div>}</div>
 <div className="drop-artwork-caption"><div><span className="overline">{art.edition} · {art.composition.replaceAll("_"," ")}</span><h3>{art.title}</h3><details><summary>About this artwork</summary><p>{art.description}</p></details></div><Link href={`/artwork/${art.id}`} className="button primary">Artwork & traits <ArrowUpRight size={15}/></Link></div>
 <div className="drop-facts"><div><span>Contributing records</span><b>{count(art.records)}</b></div><div><span>Source networks</span><b>{count(art.source_networks)}</b></div><div><span>NFT</span><b>{art.nft_status.replaceAll("_"," ")}</b></div><div><span>Auction</span><b>{art.auction_status.replaceAll("_"," ")}</b></div></div>
 <details><summary>Canonical image commitment</summary><code>{art.image_hash}</code><p>The static image is canonical; animation is an interpretation of its saved scene.</p></details>
 {art.nft_status==="minted"&&art.delivery==="auction"&&<Link href={`/auction/${art.id}`} className="text-link">View the primary auction <ArrowUpRight size={14}/></Link>}
 </div>;
}

function Creation({drop,asOf}:{drop:ActiveDrop;asOf:number}){
 const index=stages.findIndex(s=>s.key===drop.phase),p=drop.progress;
 const stale=drop.phase!=="ready"&&p.updated_at!=null&&asOf-p.updated_at>120;
 return <section className="drop-creation" aria-labelledby="creation-title"><div className="drop-section-heading"><div><span className="eyebrow">{drop.artwork?"LATEST DROP":"CREATING THE NEXT DROP"} · {drop.edition}</span><h2 id="creation-title">{drop.artwork?"The week has taken shape.":drop.last_error_type?"The drop is delayed.":drop.phase==="awaiting_worker"?"Waiting for creation to begin.":"An echo is taking shape."}</h2></div><span className="pill">{drop.state.replaceAll("_"," ")}</span></div>
 {!drop.artwork&&<p className="drop-phase-description" role="status">{index>=0?stages[index].detail:"Waiting for the studio to report this scheduled release. The artwork will appear here after creation."}</p>}
 <ol className="drop-stages" aria-label="Artwork creation stages">{stages.map((stage,i)=><li key={stage.key} className={drop.artwork||index>i?"done":index===i?"current":""} aria-current={index===i?"step":undefined}><span>{String(i+1).padStart(2,"0")}</span><strong>{stage.title}</strong></li>)}</ol>
 {!drop.artwork&&<><div className="replay-progress-track" role="progressbar" aria-label="Artwork creation" aria-valuemin={0} aria-valuemax={100} aria-valuetext={drop.last_error_type?"Creation delayed":index>=0?`Stage ${index+1} of ${stages.length}: ${stages[index].title}`:"Waiting for the creation run"}><span className={`replay-progress-fill ${drop.last_error_type||drop.phase==="awaiting_worker"?"drop-progress-waiting":"indeterminate"}`}/></div><details><summary>About progress</summary><p>Stages reflect saved creation updates. Collection totals are known only after the final page. Rendering has no estimated percentage.</p></details></>}
 {p.pass_number>0&&<div className="drop-collection"><div className="drop-section-heading"><h3>Collection pass {p.pass_number}</h3><span className="pill">{p.collection_complete?"PASS COMPLETE":"COLLECTING"}</span></div><div className="drop-facts"><div><span>Rows received</span><b>{count(p.received_rows)}</b></div><div><span>Pages received</span><b>{count(p.pages)}</b></div><div><span>Unique received records</span><b>{count(p.total_records)}</b></div><div><span>Successful eligible records</span><b>{count(p.eligible_records)}</b></div></div>
 <div className="replay-progress-track" role="progressbar" aria-label="Current record collection pass" aria-valuemin={0} aria-valuemax={100} aria-valuenow={p.collection_complete?100:undefined} aria-valuetext={p.collection_complete?"Latest collection pass complete":"Receiving records; total is not yet known"}><span className={`replay-progress-fill ${p.collection_complete?"complete":drop.last_error_type?"drop-progress-waiting":"indeterminate"}`}/></div><details><summary>What these counts mean</summary><p>Each reconciliation pass starts fresh. Received rows may include other statuses or boundary overlaps; only successful exact-interval records contribute.</p></details></div>}
 {drop.last_error_type&&<p className="data-warning" role="status">Last reported issue: {drop.last_error_type}. Committed inputs are preserved; the artwork appears here when creation succeeds.</p>}
 {stale&&<p className="data-warning" role="status">The studio has not reported a new stage recently. The last saved state is shown; this is not a completion estimate.</p>}
 {p.updated_at&&<p className="demo-note">Last creation update: {utc(p.updated_at)}. This page checks for updates every five seconds.</p>}
 {drop.selected_block&&<details><summary>Selected historical block</summary><p>Block {drop.selected_block.height.toLocaleString("en-GB")}</p><code>{drop.selected_block.hash}</code></details>}
 {drop.artwork?<CreatedArtwork key={drop.artwork.id} art={drop.artwork}/>:<div className="drop-awaiting-art"><LoaderCircle size={30} className={drop.last_error_type||drop.phase==="awaiting_worker"?"":"spin"}/><h3>The artwork will appear here.</h3><p>Follow along. The finished artwork appears automatically.</p></div>}
 </section>;
}

export function Drops(){
 const [offset,setOffset]=useState(0),[zone,setZone]=useState<string|null>(null);
 useEffect(()=>setZone(Intl.DateTimeFormat().resolvedOptions().timeZone),[]);
 const {data:d,error,isFetching}=useQuery<DropFeed>({queryKey:["drops",offset],queryFn:()=>api(`/drops?offset=${offset}&limit=12`),refetchInterval:5000});
 const next=d?.upcoming;
 return <div className="page-container drops-page"><div className="page-title"><span className="eyebrow">THE WEEKLY DROP</span><h1>Good things<br/><em>take a week.</em></h1><p>The next original. The moment it becomes.</p></div>
 {!d?<div className="empty-state"><h2>{error?"Drop details are unavailable.":"Opening the next chapter…"}</h2></div>:<>
 {d.preview&&<div className="data-warning">{d.mode==="historical_replay"?"Historical replay":"Synthetic demo"} · Read-only. Upcoming dates preview the production schedule.</div>}
 {error&&<p className="data-warning" role="status">Updates are unavailable. Showing the last saved state.</p>}
 {next&&<section className="drop-upcoming"><div><span className="eyebrow"><Clock size={13}/>{d.preview?"PLANNED NEXT DROP":"NEXT DROP"} · {next.edition}</span><h2>{new Intl.DateTimeFormat("en-GB",{day:"numeric",month:"long",year:"numeric",timeZone:"UTC"}).format(next.sunday*1000)}</h2><p>One original, revealed after creation.</p><div className="drop-delivery"><span className="pill">1 / 1 EDITION</span><span className="pill">{next.delivery==="creator"?"CREATOR / TEAM MINT":"24-HOUR AUCTION"}</span></div></div><aside><span className="overline">{d.as_of<next.freeze_at?"UNTIL CREATION OPENS":"CREATION WINDOW OPEN"}</span>{d.as_of<next.freeze_at&&<Countdown target={next.freeze_at}/>}<p>Creation from {utc(next.freeze_at)}</p><details><summary>Schedule & drop details</summary><dl className="drop-schedule"><div><dt>Randomness beacon</dt><dd>{utc(next.beacon_at)}</dd></div><div><dt>Data freeze / earliest creation</dt><dd>{utc(next.freeze_at)}</dd></div><div><dt>Checkpoint selection window</dt><dd>Sunday 00:00–17:00 UTC</dd></div>{zone&&<div><dt>Your time · {zone}</dt><dd>{new Intl.DateTimeFormat("en-GB",{dateStyle:"medium",timeStyle:"short",timeZone:zone}).format(next.freeze_at*1000)}</dd></div>}</dl><p className="demo-note">Completion follows the freeze once generation succeeds. The next artwork is not selected in advance.</p></details></aside></section>}
 {d.active&&<Creation drop={d.active} asOf={d.as_of}/>}
 {d.mode==="historical_replay"&&<section className="drop-replay"><ReplayProgress compact/><Link href="/demo" className="text-link">The story behind the artwork <ArrowUpRight size={15}/></Link></section>}
 <section className="drop-history"><div className="drop-section-heading"><div><span className="eyebrow">THE ARCHIVE</span><h2>Past echoes.</h2></div><span className="overline">{count(d.total_previous)} {d.preview?"STUDIES":"DROPS"}{isFetching?" · UPDATING":""}</span></div><div className="drop-history-grid">{d.previous.map(art=><article className="drop-history-card" key={art.id}><Link href={`/artwork/${art.id}`} className="drop-history-image"><img src={art.thumbnail} alt={art.title} loading="lazy"/><span className="pill">{art.mode==="live"?art.edition:art.mode==="historical_replay"?"HISTORICAL STUDY":"DEMO STUDY"}</span></Link><div><span className="overline">{art.edition} · {new Intl.DateTimeFormat("en-GB",{dateStyle:"medium",timeZone:"UTC"}).format(art.sunday*1000)}</span><h3>{art.title}</h3><p>{art.composition.replaceAll("_"," ")} · {count(art.records)} swaps</p><details><summary>Edition details</summary><dl><div><dt>Source networks</dt><dd>{count(art.source_networks)}</dd></div><div><dt>NFT</dt><dd>{art.nft_status.replaceAll("_"," ")}</dd></div><div><dt>Auction</dt><dd>{art.auction_status.replaceAll("_"," ")}</dd></div></dl></details><Link href={`/artwork/${art.id}`} className="text-link">Explore the artwork <ArrowUpRight size={15}/></Link></div></article>)}</div>{!d.previous.length&&<div className="empty-state"><h3>{offset?"You've reached the beginning.":"A little history, on its way."}</h3><p>Finished artworks join the archive here.</p></div>}{(offset>0||d.total_previous>12)&&<div className="drop-pagination"><button className="button subtle" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-12))}>Newer</button><button className="button subtle" disabled={offset+12>=d.total_previous} onClick={()=>setOffset(offset+12)}>Older</button></div>}</section>
 </>}
 </div>;
}
