"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, Pause, Play, SkipForward } from "lucide-react";
import { useReducedAnimation } from "./animated-artwork";
import type { HistoricalDemoData } from "./historical-demo-types";

const STEP_MS=4000,TOTAL_MS=STEP_MS*5;
const labels=["Completion","Activity","Routes","Commitment","The artwork"];
const ease=(value:number)=>1-Math.pow(1-Math.max(0,Math.min(1,value)),3);
const format=(value:number)=>Math.round(value).toLocaleString("en-US");
const routeName=(value:string)=>value.replace(/\u00e2\u2020\u2019/g,"\u2192").replaceAll("Unmapped","Unmapped assets");

export function ArtworkStory({demo,image,onComplete}:{demo:HistoricalDemoData;image:string;onComplete:()=>void}){
  const reduced=useReducedAnimation(),[playing,setPlaying]=useState(false),[elapsed,setElapsed]=useState(0);
  const section=useRef<HTMLElement>(null),visible=useRef(false);
  useEffect(()=>{
    if(!section.current)return;
    const observer=new IntersectionObserver(entries=>{visible.current=(entries[0]?.intersectionRatio??0)>=.2;},{threshold:.2});
    observer.observe(section.current);return()=>observer.disconnect();
  },[]);
  useEffect(()=>setPlaying(!reduced),[reduced]);
  useEffect(()=>{
    if(!playing)return;
    let frame=0,last=0,published=0,clock=elapsed;
    function tick(now:number){
      if(last&&visible.current&&!document.hidden)clock=Math.min(TOTAL_MS,clock+Math.min(now-last,80));
      last=now;
      if(now-published>32||clock>=TOTAL_MS){setElapsed(clock);published=now;}
      if(clock<TOTAL_MS)frame=requestAnimationFrame(tick);
    }
    frame=requestAnimationFrame(tick);return()=>cancelAnimationFrame(frame);
    // Restart the clock only when playback changes; elapsed is sampled on start.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[playing]);
  useEffect(()=>{if(elapsed>=TOTAL_MS)onComplete();},[elapsed,onComplete]);
  const stage=Math.min(4,Math.floor(elapsed/STEP_MS)),progress=reduced?1:ease((elapsed-stage*STEP_MS)/STEP_MS);
  const activity=demo.statistics.activity||[],peak=Math.max(1,...activity);
  const routes=Object.entries(demo.statistics.dominant_routes||{}).sort((a,b)=>b[1]-a[1]).slice(0,6);
  const routePeak=Math.max(1,...routes.map(([,count])=>count));
  const recognized=Object.keys(demo.statistics.chains||{}).filter(name=>name!=="Unmapped").length;
  const headings=["Completed journeys. Shared momentum.","A week has its own rhythm.","Movement leaves a network.","Many records. One fixed fingerprint.",demo.artwork.title];
  function selectStep(index:number){setPlaying(false);setElapsed(index*STEP_MS);}
  return <section ref={section} className="artwork-story" aria-label="How this artwork came to be">
    <header className="story-top"><span className="eyebrow">THE MAKING OF A DISTORTION</span><button className="text-link" onClick={onComplete}>View artwork <SkipForward size={14}/></button></header>
    <div className="story-stage" key={stage}>
      <div className="story-copy"><span className="story-index">0{stage+1} / 05</span><h2 aria-live="polite">{headings[stage]}</h2>
        {stage===0&&<><div className="story-big" aria-label={`${demo.statistics.total_swaps.toLocaleString()} successful records`}><span aria-hidden="true">{format(demo.statistics.total_swaps*progress)}</span></div><p>Unique, successful swap records in the selected interval. Test records and unsuccessful attempts are excluded.</p><span className="story-footnote">Each eligible record contributes to the dataset commitment and seed.</span></>}
        {stage===1&&<><div className="story-big">24 <small>time slices</small></div><p>Activity rises and falls across the captured week. Record timestamps place the visible sample; aggregate activity records the full rhythm.</p><span className="story-footnote">Equal time intervals across the entire capture, not hours of one day.</span></>}
        {stage===2&&<><div className="story-big">{recognized||demo.statistics.unique_chains} <small>{recognized?"recognized source chains":"source categories"}</small></div><p>Route frequencies shape the network of lines and their intensity. Source categories guide the palette; reported USD amounts influence particle prominence.</p><span className="story-footnote">{demo.statistics.network_mapping&&`${demo.statistics.network_mapping.resolved_assets} of ${demo.statistics.network_mapping.total_assets} asset IDs are resolved using the saved registry. `}Top routes shown. “Unmapped assets” is an unresolved category.</span></>}
        {stage===3&&<><div className="story-seed">{demo.artwork.seed.slice(0,32)}</div><p>The dataset commitment, {demo.statistics.network_mapping&&"frozen network mapping, "}selected block, drand beacon, edition number and genesis image hash determine the art seed. {demo.family_selection?"The family is verifiably selected from the seed; recorded NEAR AI styling supplies palette, material and detail.":"Recorded NEAR AI direction supplies the composition and palette."}</p><span className="story-footnote">The seed drives geometry. The saved direction makes the finished image replayable.</span></>}
        {stage===4&&<><p>{demo.artwork.description}</p><div className="story-result"><span>{demo.statistics.total_swaps.toLocaleString()} contributing records</span><span>{demo.statistics.particle_count.toLocaleString()} visible sample particles</span></div><span className="story-footnote">The full dataset contributes even though the visible particle sample is bounded.</span></>}
      </div>
      <div className={`story-visual story-visual-${stage}`}>
        {stage===0&&<svg viewBox="0 0 500 440" role="img" aria-label="A symbolic field of completed swap records"><circle className="story-orbit" cx="250" cy="220" r="165" fill="none"/><circle className="story-orbit" cx="250" cy="220" r="105" fill="none"/>{Array.from({length:96},(_,i)=>{const angle=i*2.399963,radius=25+Math.sqrt(i/96)*175;return <circle className="story-record" key={i} cx={250+Math.cos(angle)*radius} cy={220+Math.sin(angle)*radius*.86} r={i%9===0?4:2} style={{animationDelay:`${i*18}ms`}}/>;})}</svg>}
        {stage===1&&<div className="story-activity" role="img" aria-label={`Activity in ${activity.length||24} equal intervals across the capture; peak ${peak.toLocaleString()} records`}><p className="story-chart-caption">Peak interval · {peak.toLocaleString()} records</p><div className="story-bars">{activity.map((count,i)=><div key={i} title={`${count.toLocaleString()} records`}><span style={{height:`${Math.max(2,count/peak*100)*progress}%`}}/></div>)}</div><div className="story-chart-labels"><span>{new Date(demo.interval.start*1000).toLocaleDateString("en-GB",{day:"numeric",month:"short",timeZone:"UTC"})} · UTC</span><span>{new Date(demo.interval.end*1000).toLocaleDateString("en-GB",{day:"numeric",month:"short",timeZone:"UTC"})} · CHECKPOINT</span></div></div>}
        {stage===2&&<div className="story-routes">{routes.map(([route,count],i)=><div className="story-route" key={route}><div><span>{routeName(route)}</span><b>{format(count*progress)}</b></div><div className="story-route-track"><span style={{width:`${count/routePeak*100*progress}%`,opacity:1-i*.1}}/></div></div>)}</div>}
        {stage===3&&<div className="story-commitment"><div className="commitment-ring"/><div className="commitment-ring inner"/><span className="eyebrow">VERIFIED INPUTS</span><strong>{demo.checkpoint.height.toLocaleString()}</strong><span>selected mainnet block</span><code>DRAND {demo.beacon.round}</code><code>MERKLE {demo.artwork.merkle_root.slice(0,16)}…</code></div>}
        {stage===4&&<img className="story-reveal" src={image} alt={demo.artwork.title}/>}
      </div>
    </div>
    <footer className="story-bottom"><div className="story-steps" aria-label="Presentation chapters">{labels.map((label,i)=><button key={label} className={i===stage?"active":""} aria-current={i===stage?"step":undefined} onClick={()=>selectStep(i)}><span>0{i+1}</span>{label}</button>)}</div><div className="story-controls"><button className="button subtle" onClick={()=>setPlaying(!playing)}>{playing?<Pause size={14}/>:<Play size={14}/>} {playing?"Pause":"Play"}</button><button className="button subtle" onClick={()=>selectStep(stage+1)}>{stage===4?"Explore":"Next"}<ArrowRight size={14}/></button></div></footer>
    <div className="story-timeline" role="progressbar" aria-label="Artwork presentation" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(elapsed/TOTAL_MS*100)}><span style={{width:`${elapsed/TOTAL_MS*100}%`}}/></div>
    {reduced&&<p className="story-motion-note">Automatic motion is paused for your reduced-motion preference. Use Next to explore each chapter.</p>}
  </section>;
}
