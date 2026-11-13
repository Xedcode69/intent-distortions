"use client";
import { useCallback, useEffect, useState } from "react";
import { ArrowDown, Check, Fingerprint, LoaderCircle, RotateCcw } from "lucide-react";
import { ReplayProgress } from "./replay-progress";
import { AnimatedArtwork } from "./animated-artwork";
import { ArtworkStory } from "./artwork-story";
import { NetworkMappingCoverage } from "./network-mapping-coverage";
import type { ArtworkScene as Scene, HistoricalDemoData as Demo } from "./historical-demo-types";

type Asset = {url:string;sha256:string};
const layers:Record<string,string>={routes:"Cross-chain routes",geometry:"Seeded geometry",particles:"Transaction moments",inheritance:"Genesis inheritance",signature:"Edition signature"};
const utc=(seconds:number)=>new Date(seconds*1000).toUTCString();
async function verifiedBytes(asset:Asset, signal?:AbortSignal){
  if(!/^\/historical-demo\/editions\/[a-f0-9]{64}\/(artwork\.png|artwork-manifest\.json)$/.test(asset.url))throw new Error("Invalid demo asset location.");
  const response=await fetch(asset.url,{signal,cache:"no-store"});
  if(!response.ok)throw new Error("A saved demo asset is unavailable.");
  const bytes=await response.arrayBuffer();
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),b=>b.toString(16).padStart(2,"0")).join("");
  if(hash!==asset.sha256)throw new Error("Demo file integrity mismatch.");
  return bytes;
}

export function HistoricalDemo(){
  const [demo,setDemo]=useState<Demo|null>(null),[scene,setScene]=useState<Scene|null>(null),[image,setImage]=useState("");
  const [state,setState]=useState("loading"),[error,setError]=useState(""),[tab,setTab]=useState("artwork"),[verification,setVerification]=useState("");
  const [storyComplete,setStoryComplete]=useState(false),[storyKey,setStoryKey]=useState(0);
  const finishStory=useCallback(()=>setStoryComplete(true),[]);
  const [visible,setVisible]=useState<Record<string,boolean>>({routes:true,geometry:true,particles:true,inheritance:true,signature:true});
  useEffect(()=>{
    const controller=new AbortController();let objectURL="",retry:ReturnType<typeof setTimeout>|undefined;
    async function load(){
      try{
        const response=await fetch("/historical-demo/index.json",{signal:controller.signal,cache:"no-store"});
        if(response.status===404){setState("empty");retry=setTimeout(()=>{void load();},5000);return;}
        if(!response.ok)throw new Error("The historical demo is temporarily unavailable.");
        const value:Demo=await response.json();
        if(value.schema!=="echo-historical-demo-v1"||!value.verification.rerendered_before_publication||!Object.values(value.verification.checks).every(Boolean)||value.files["artwork.png"].sha256!==value.artwork.image_hash)throw new Error("The demo publication is incomplete.");
        const [png,manifest]=await Promise.all([verifiedBytes(value.files["artwork.png"],controller.signal),verifiedBytes(value.files["artwork-manifest.json"],controller.signal)]);
        if(controller.signal.aborted)return;
        objectURL=URL.createObjectURL(new Blob([png],{type:"image/png"}));
        setScene(JSON.parse(new TextDecoder().decode(manifest)));setImage(objectURL);setDemo(value);setState("ready");
      }catch(reason){if(!controller.signal.aborted){setError(reason instanceof Error?reason.message:"Could not load the historical demo.");setState("error");}}
    }
    void load();return()=>{controller.abort();if(retry)clearTimeout(retry);if(objectURL)URL.revokeObjectURL(objectURL);};
  },[]);
  async function verify(){
    if(!demo)return;setVerification("Checking saved bytes…");
    try{await Promise.all(Object.values(demo.files).map(asset=>verifiedBytes(asset)));setVerification("Image and scene SHA-256 match the published commitments.");}
    catch(reason){setVerification(reason instanceof Error?reason.message:"Verification failed.");}
  }
  return <div className="page-container historical-demo"><div className="page-title"><div className="eyebrow">THE PROCESS, MADE VISIBLE</div><h1>Past movement.<br/><em>A real echo.</em></h1><p>A read-only demonstration of recorded swap data becoming a reproducible artwork.</p></div>
    <ReplayProgress/>
    {state==="loading"&&<div className="demo-placeholder" role="status"><LoaderCircle className="spin"/><p>Opening the historical demonstration…</p></div>}
    {state==="empty"&&<div className="demo-placeholder"><Fingerprint size={38}/><h2>The first historical demo is being prepared.</h2><p>No completed real-data replay has been published here yet. Once available, its artwork, capture date and verification evidence will appear below.</p></div>}
    {state==="error"&&<div className="demo-placeholder" role="alert"><h2>The saved demo could not be verified.</h2><p>{error}</p><button className="button subtle" onClick={()=>location.reload()}>Try again</button></div>}
    {demo&&scene&&state==="ready"&&!storyComplete&&<ArtworkStory key={storyKey} demo={demo} image={image} onComplete={finishStory}/>}
    {demo&&scene&&state==="ready"&&storyComplete&&<><div className="data-warning">Historical release: {demo.sunday} · Captured {utc(demo.captured_at)}. Statuses reflect capture time. No NFT mint or auction was performed.</div>
      <NetworkMappingCoverage demo={demo}/>
      <button className="button subtle story-replay" onClick={()=>{setStoryComplete(false);setStoryKey(value=>value+1);setTab("artwork");}}><RotateCcw size={14}/> Replay the story</button>
      <div className="tabs" role="group" aria-label="Historical artwork view">{["artwork","animated","layers"].map(value=><button key={value} aria-pressed={tab===value} className={tab===value?"active":""} onClick={()=>setTab(value)}>{value==="artwork"?"Static image":value==="animated"?"Animated view":"Explore the layers"}</button>)}</div>
      <div className="dna-layout"><div className="dna-canvas">{tab==="artwork"?<img src={image} alt={demo.artwork.title}/>:tab==="animated"?<AnimatedArtwork scene={scene} seed={demo.artwork.seed} title={demo.artwork.title}/>:<svg viewBox={`0 0 ${scene.width} ${scene.height}`} role="img" aria-label="Interactive layers of the recorded artwork"><rect width={scene.width} height={scene.height} fill={scene.background}/>{scene.shapes.filter(shape=>visible[shape.layer]).map((shape,index)=>shape.kind==="dot"?<circle key={index} cx={shape.center![0]} cy={shape.center![1]} r={shape.radius} fill={shape.color} opacity={shape.alpha/255}/>:<polyline key={index} points={shape.points!.map(point=>point.join(",")).join(" ")} fill="none" stroke={shape.color} strokeWidth={shape.width} opacity={shape.alpha/255}/>)}</svg>}<span className="overline">{tab==="animated"?"ANIMATED INTERPRETATION · SAVED SCENE":tab==="artwork"?"CANONICAL PNG · HASH CHECKED IN YOUR BROWSER":"INTERACTIVE PRESENTATION · ORIGINAL ARTWORK STAYS FIXED"}</span></div>
      <aside className="dna-controls"><div className="eyebrow">RECORDED HISTORICAL RESULT</div><h2>{demo.artwork.title}</h2><p>{demo.artwork.description}</p><div className="stat-pair"><span>Successful contributing records</span><b>{demo.statistics.total_swaps.toLocaleString()}</b></div><div className="stat-pair"><span>Recognized source chains</span><b>{demo.statistics.chains?Object.keys(demo.statistics.chains).filter(name=>name!=="Unmapped").length:demo.statistics.unique_chains}</b></div><div className="stat-pair"><span>Visible transaction sample</span><b>{demo.statistics.particle_count.toLocaleString()} particles</b></div><div className="stat-pair"><span>Composition</span><b>{demo.artwork.composition.replaceAll("_"," ")}</b></div><div className="stat-pair"><span>Creative direction</span><b>{demo.artwork.ai_provider==="near_ai_cloud"?"NEAR AI Cloud":"Deterministic fallback"}</b></div>{tab==="layers"&&Object.entries(layers).map(([key,label])=><label className="toggle-row" key={key}><span>{label}</span><input type="checkbox" checked={visible[key]} onChange={event=>setVisible({...visible,[key]:event.target.checked})}/></label>)}<p className="demo-note">{tab==="animated"&&"Motion is a presentation of the recorded scene; the canonical image and its hash stay fixed. "}Every eligible record affects the dataset commitment and seed. The renderer uses aggregate routes and a bounded transaction sample.</p></aside></div>
      <section className="demo-evidence" aria-label="Recorded evidence"><div className="section-heading"><div><span className="eyebrow">FOLLOW THIS RUN</span><h2>From records to a fixed image.</h2></div></div><ol className="demo-steps">{[
        ["Collect",`${demo.statistics.total_swaps.toLocaleString()} successful eligible records. Interval: ${utc(demo.interval.start)} to ${utc(demo.interval.end)}; the exact endpoint is stored in nanoseconds.`],
        ["Select",`Verified drand round ${demo.beacon.round} selected a checkpoint on ${demo.sunday}. Saved mainnet block: ${demo.checkpoint.height.toLocaleString()}.`],
        ["Commit",`Canonical records form a Merkle root. That root, ${demo.statistics.network_mapping?"the frozen asset-to-network mapping, ":""}the block hash, beacon, edition number and genesis image hash determine the art seed.`],
        ["Render",`${demo.artwork.ai_provider==="near_ai_cloud"?"Recorded NEAR AI direction":"Explicit deterministic fallback direction"} and seeded mathematical geometry produce the image and its exact scene.`],
        ["Verify","Before publication, the runner rebuilt the scene and PNG, checked memberships and commitments, repeated the run, and tested tamper rejection."],
      ].map(([title,description],index)=><li key={title}><span className="step-number">0{index+1}</span><div><h3>{title}</h3><p>{description}</p></div>{index<4&&<ArrowDown size={14}/>}</li>)}</ol></section>
      <section className="demo-evidence"><h2>Check the evidence.</h2><p>Browser verification checks the published image and scene bytes. The recorded full-pipeline checks below were performed before publication.</p><button className="button primary" onClick={verify}><Check size={15}/> Verify image and scene</button>{verification&&<p role="status">{verification}</p>}<div className="demo-checks">{Object.entries(demo.verification.checks).map(([name,passed])=><span key={name}><Check size={12}/>{name.replaceAll("_"," ")}: {passed?"passed":"failed"}</span>)}</div>{[["Image SHA-256",demo.artwork.image_hash],["Dataset Merkle root",demo.artwork.merkle_root],["Art seed",demo.artwork.seed],["Recorded mainnet block",demo.checkpoint.hash],["Source snapshot SHA-256",demo.snapshot_sha256],["Provenance SHA-256",demo.provenance_sha256]].map(([label,value])=><div className="hash-field" key={label}><span className="overline">{label}</span><code>{value}</code></div>)}<p className="demo-note">These checks establish content integrity and reproducibility. They do not prove provider completeness, original as-of-freeze statuses, private-shard contents, NFT ownership or auction execution. Raw captures and credentials are never included in this presentation.</p></section>
    </>}
    <section className="demo-evidence"><div className="eyebrow">WHAT THIS DEMONSTRATES</div><h2>The same artwork pipeline, replayed from history.</h2><p>The historical demo uses the collection, checkpoint, commitment and rendering code used by the weekly process. A real-time release also observes its published schedule and performs separately verified onchain publication and auction operations.</p></section>
  </div>;
}
