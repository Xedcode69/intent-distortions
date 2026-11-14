"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
import {ArrowUpRight,Download,LockKeyhole,LoaderCircle} from "lucide-react";
import {api} from "@/lib/api";

type Study={network:"testnet"|"mainnet";contract:string;code_sha256:string;keyless:boolean;block_height:number;
 edition:{token_id:string;owner_id:string;sealed:boolean;recipe_bytes:number;recipe_sha256:string;static_sha256:string;animated_sha256:string;artwork_commitment:string;
 metadata:{title:string;description:string;family:string;ai_model:string;direction:string;motion:string;record_count:number;source_start:string;source_end:string;prototype:boolean}}};
const hash=async(bytes:ArrayBuffer)=>Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),b=>b.toString(16).padStart(2,"0")).join("");

export function OnchainStudy(){
 const [study,setStudy]=useState<Study|null>(null),[animated,setAnimated]=useState(false),[image,setImage]=useState(""),[error,setError]=useState(""),[loading,setLoading]=useState(true);
 useEffect(()=>{const abort=new AbortController();void api<Study>("/onchain/prototype",{signal:abort.signal}).then(setStudy).catch(()=>{if(!abort.signal.aborted){setError("The onchain study is not available for verification yet.");setLoading(false);}});return()=>abort.abort();},[]);
 useEffect(()=>{
  if(!study)return;const abort=new AbortController();let objectURL="";setLoading(true);setError("");
  void (async()=>{try{
   const response=await fetch(`/api/v1/onchain/prototype/${animated?"animated":"static"}.svg`,{signal:abort.signal,cache:"no-store"});
   if(!response.ok)throw new Error("The artwork could not be recovered from NEAR.");
   const bytes=await response.arrayBuffer();
   if(await hash(bytes)!==(animated?study.edition.animated_sha256:study.edition.static_sha256))throw new Error("The recovered artwork does not match its sealed hash.");
   if(abort.signal.aborted)return;objectURL=URL.createObjectURL(new Blob([bytes],{type:"image/svg+xml"}));setImage(objectURL);setLoading(false);
  }catch(e){if(!abort.signal.aborted){setError(e instanceof Error?e.message:"Verification failed.");setLoading(false);}}})();
  return()=>{abort.abort();if(objectURL)URL.revokeObjectURL(objectURL);};
 },[study,animated]);
 const explorer=study?`https://${study.network==="testnet"?"testnet.":""}nearblocks.io/address/${study.contract}`:"";
 const direction=study?JSON.parse(study.edition.metadata.direction):null;
 const motion=study?JSON.parse(study.edition.metadata.motion):null;
 return <div className="page-container onchain-study"><div className="onchain-intro"><Link href="/demo" className="eyebrow">← BACK TO THE HISTORICAL DEMO</Link><h1>A moment.<br/><em>Made permanent.</em></h1><p>One frozen composition. Two ways to experience it.</p></div>
 {error&&<div className="data-warning" role="alert">{error}</div>}
 {!study&&loading&&<div className="onchain-loading" role="status"><LoaderCircle className="spin"/> Reading the onchain study…</div>}
 {study&&<><div className="onchain-layout"><div><div className="onchain-viewbar"><div className="tabs" role="group" aria-label="Artwork view"><button aria-pressed={!animated} className={!animated?"active":""} onClick={()=>setAnimated(false)}>Still</button><button aria-pressed={animated} className={animated?"active":""} onClick={()=>setAnimated(true)}>In motion</button></div><span><LockKeyhole size={13}/>{study.keyless?"Sealed · keyless contract":"Sealed · account locking pending"}</span></div><div className="onchain-canvas">{loading?<div className="onchain-loading" role="status"><LoaderCircle className="spin"/> Verifying artwork…</div>:image&&!error&&<img src={image} alt={study.edition.metadata.title}/>}</div><div className="onchain-downloads">{image&&!loading&&!error&&<a href={image} download={`${study.edition.token_id}-${animated?"animated":"static"}.svg`}><Download size={14}/> Save this view</a>}<a href="/api/v1/onchain/prototype/recipe.bin"><Download size={14}/> Download onchain recipe</a></div></div>
 <aside className="onchain-details"><span className="eyebrow">ONCHAIN STUDY 01 · {study.network}</span><h2>{study.edition.metadata.title}</h2><p>{study.edition.metadata.description}</p><div className="palette">{direction.palette.map((c:string)=><span key={c} style={{background:c}} title={c}/>)}</div><dl><div><dt>Family</dt><dd>{study.edition.metadata.family.replaceAll("_"," ")}</dd></div><div><dt>Artistic director</dt><dd>NEAR AI</dd></div><div><dt>Contributing swaps</dt><dd>{study.edition.metadata.record_count.toLocaleString()}</dd></div><div><dt>Frozen recipe</dt><dd>{(study.edition.recipe_bytes/1024).toFixed(1)} KiB</dd></div><div><dt>Owner</dt><dd>{study.edition.owner_id}</dd></div></dl><p className="onchain-caption">Derived from the saved historical artwork. This separate prototype has no auction or reward allocation.</p><a className="button subtle" href={explorer} target="_blank" rel="noreferrer">View on NEAR <ArrowUpRight size={15}/></a></aside></div>
 <details className="onchain-evidence"><summary>What makes it permanent?</summary><p>The geometry, accepted AI direction, motion controls and renderer are stored on NEAR. Both views are checked against their sealed SHA-256 hashes. No artwork files are fetched from IPFS or a media host.</p><p>{study.keyless?"The contract has no access keys. Its pinned code has no upgrade or artwork replacement method.":"An access key still exists. Permanent account locking has not been verified."} Ownership can change; the artwork cannot.</p><p>Motion uses the frozen week’s activity rhythm, route weights and flow imbalance. It does not consume new transactions. Variant {motion.variant+1}; {(motion.route_period_ms/1000).toFixed(2)}-second base route cycle. Browser rasterization can differ slightly.</p>{[["Artwork commitment",study.edition.artwork_commitment],["Recipe SHA-256",study.edition.recipe_sha256],["Static SVG SHA-256",study.edition.static_sha256],["Animated SVG SHA-256",study.edition.animated_sha256],["Renderer code SHA-256",study.code_sha256]].map(([label,value])=><div className="hash-field" key={label}><span className="overline">{label}</span><code>{value}</code></div>)}<p>Checked at finalized block {study.block_height.toLocaleString()}. AI model: {study.edition.metadata.ai_model}. Original transaction records are committed by provenance; the complete raw dataset is not stored in this art contract.</p></details></>}
 </div>;
}
