"use client";
import { useCallback, useEffect, useState } from "react";
import { ArrowDown, Check, Fingerprint, LoaderCircle } from "lucide-react";
import { ReplayProgress } from "./replay-progress";
import { AnimatedArtwork } from "./animated-artwork";
import { ArtworkStory } from "./artwork-story";
import { NetworkMappingCoverage } from "./network-mapping-coverage";
import { SceneSvg } from "./scene-svg";
import { RenderControls } from "./render-controls";
import {TraitList} from "./artwork-traits";
import { EconomyExample } from "./economy-dashboard";
import {RoyaltyExample} from "./royalty-example";
import { verifyFamilySelection } from "@/lib/family-selection";
import {verifyTraitDocument} from "@/lib/nft-traits";
import type { ArtworkScene as Scene, HistoricalDemoData as Demo } from "./historical-demo-types";

type Asset = {url:string;sha256:string};
const layers:Record<string,string>={routes:"Cross-chain routes",geometry:"Seeded geometry",particles:"Transaction moments",inheritance:"Genesis inheritance",signature:"Edition signature",surfaces:"Filled surfaces and ribbons",textures:"Procedural texture",lighting:"Light and glow"};
const utc=(seconds:number)=>new Date(seconds*1000).toUTCString();
async function verifiedBytes(asset:Asset, signal?:AbortSignal){
  if(!/^\/historical-demo\/editions\/[a-f0-9]{64}\/(artwork\.png|artwork-manifest\.json|nft-traits\.json)$/.test(asset.url))throw new Error("Invalid demo asset location.");
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
  const [visible,setVisible]=useState<Record<string,boolean>>({routes:true,geometry:true,particles:true,inheritance:true,signature:true,surfaces:true,textures:true,lighting:true});
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
        if(value.traits){
          const traitFile=value.files["nft-traits.json"];
          if(!traitFile||traitFile.sha256!==value.traits.sha256||value.traits.source.image_sha256!==value.artwork.image_hash||value.traits.source.manifest_sha256!==value.files["artwork-manifest.json"].sha256||value.traits.source.provenance_sha256!==value.provenance_sha256||!await verifyTraitDocument(value.traits,await verifiedBytes(traitFile,controller.signal)))throw new Error("The recorded NFT traits could not be verified.");
        }
        if(controller.signal.aborted)return;
        objectURL=URL.createObjectURL(new Blob([png],{type:"image/png"}));
        const parsed:Scene=JSON.parse(new TextDecoder().decode(manifest));
        if(parsed.version==="echo-renderer-4"&&(!value.family_selection||parsed.family!==value.artwork.composition))throw new Error("The publication is missing its required family proof.");
        if(value.family_selection&&(!await verifyFamilySelection(value.artwork.seed,value.artwork.composition,value.family_selection)||JSON.stringify(parsed.family_selection)!==JSON.stringify(value.family_selection)))throw new Error("The recorded family draw could not be verified.");
        setScene(parsed);setImage(objectURL);setDemo(value);setState("ready");
      }catch(reason){if(!controller.signal.aborted){setError(reason instanceof Error?reason.message:"Could not load the historical demo.");setState("error");}}
    }
    void load();return()=>{controller.abort();if(retry)clearTimeout(retry);if(objectURL)URL.revokeObjectURL(objectURL);};
  },[]);
  async function verify(){
    if(!demo)return;setVerification("Checking saved bytes…");
    try{await Promise.all(Object.values(demo.files).map(asset=>verifiedBytes(asset)));if(demo.family_selection&&!await verifyFamilySelection(demo.artwork.seed,demo.artwork.composition,demo.family_selection))throw new Error("Family selection mismatch.");setVerification(demo.family_selection?"Image, scene and verifiable family draw match the published commitments.":"Image and scene SHA-256 match the published commitments.");}
    catch(reason){setVerification(reason instanceof Error?reason.message:"Verification failed.");}
  }
  return <div className="page-container historical-demo"><div className="page-title"><span className="eyebrow">REAL ACTIVITY. ORIGINAL ART.</span><h1>A week,<br/><em>made visible.</em></h1><p>Explore a real historical run. Then see how it came to life.</p></div>
    <ReplayProgress compact/>
    {state==="loading"&&<div className="demo-placeholder" role="status"><LoaderCircle className="spin"/><p>Opening the artwork…</p></div>}
    {state==="empty"&&<div className="demo-placeholder"><Fingerprint size={35}/><h2>A new study is on its way.</h2><p>The historical artwork will appear when its replay is ready.</p></div>}
    {state==="error"&&<div className="demo-placeholder" role="alert"><h2>This artwork could not be verified.</h2><p>{error}</p><button className="button subtle" onClick={()=>location.reload()}>Try again</button></div>}
    {demo&&scene&&state==="ready"&&!storyComplete&&<ArtworkStory key={storyKey} demo={demo} image={image} onComplete={finishStory}/>}
    {demo&&scene&&state==="ready"&&storyComplete&&<><div className="demo-overview"><div className="demo-quick-stats"><div><b>{demo.statistics.total_swaps.toLocaleString()}</b><span>Successful swaps</span></div><div><b>{demo.statistics.unique_chains}</b><span>Source networks</span></div></div><button className="button primary" onClick={()=>{setStoryComplete(false);setStoryKey(v=>v+1);}}>Watch the story <ArrowDown size={15}/></button></div>
      <div className="tabs" role="group" aria-label="Historical artwork view">{["artwork","animated","layers"].map(value=><button key={value} aria-pressed={tab===value} className={tab===value?"active":""} onClick={()=>setTab(value)}>{value==="artwork"?"Still":value==="animated"?"In motion":"Layers"}</button>)}</div>
      <div className="dna-layout"><div className="dna-canvas">{tab==="artwork"?<img src={image} alt={demo.artwork.title}/>:tab==="animated"?<AnimatedArtwork scene={scene} seed={demo.artwork.seed} title={demo.artwork.title}/>:<SceneSvg scene={scene} visible={visible}/>}</div><aside className="dna-controls"><span className="overline">HISTORICAL STUDY · {demo.sunday}</span><h2>{demo.artwork.title}</h2><p>{demo.artwork.composition.replaceAll("_"," ")}. {scene.controls?.style.material||"Generative geometry"}. One original.</p><div className="palette">{scene.controls?.style.palette.map(color=><span key={color} style={{background:color}} title={color}/>)}</div><div className="stat-pair"><span>Edition</span><b>1 / 1</b></div><div className="stat-pair"><span>Creative direction</span><b>{demo.artwork.ai_provider==="near_ai_cloud"?"NEAR AI":"Recorded fallback"}</b></div><p className="demo-note">A read-only replay. No NFT mint or auction was performed.</p>{tab==="layers"&&Object.entries(layers).map(([key,label])=><label className="toggle-row" key={key}><span>{label}</span><input type="checkbox" checked={visible[key]} onChange={e=>setVisible({...visible,[key]:e.target.checked})}/></label>)}<details><summary>About this artwork</summary><p>{demo.artwork.description}</p><p>All eligible records contribute to the seed. The visible particle sample is bounded; motion is an artistic interpretation.</p></details></aside></div>
      {demo.traits&&<TraitList bundle={demo.traits}/>}
      <details className="demo-evidence"><summary>Data, process & verification</summary><p>Captured {utc(demo.captured_at)}. Statuses reflect capture time. The result has not been minted or auctioned.</p><NetworkMappingCoverage demo={demo}/><RenderControls scene={scene} demo={demo}/><h2>Check the original.</h2><p>Verify the saved image, scene and family draw against their commitments.</p><button className="button primary" onClick={verify}><Check size={15}/> Verify artwork</button>{verification&&<p role="status">{verification}</p>}<details><summary>Recorded pipeline checks</summary><div className="demo-checks">{Object.entries(demo.verification.checks).map(([name,passed])=><span key={name}><Check size={12}/>{name.replaceAll("_"," ")}: {passed?"passed":"failed"}</span>)}</div></details>{[["Image SHA-256",demo.artwork.image_hash],["Dataset Merkle root",demo.artwork.merkle_root],["Art seed",demo.artwork.seed],["Recorded mainnet block",demo.checkpoint.hash],["Source snapshot SHA-256",demo.snapshot_sha256],["Provenance SHA-256",demo.provenance_sha256]].map(([label,value])=><div className="hash-field" key={label}><span className="overline">{label}</span><code>{value}</code></div>)}<p className="demo-note">These checks establish integrity and reproducibility. They do not prove provider completeness, historical as-of-freeze statuses, private-shard contents or NFT ownership.</p></details>
    </>}
    <details className="demo-economy-details"><summary>Explore the collection economy</summary><EconomyExample/><RoyaltyExample/></details>
  </div>;
}
