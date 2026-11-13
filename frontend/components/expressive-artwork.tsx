"use client";
import { useEffect,useRef,useState } from "react";
import { Pause,Play,RotateCcw,Sparkles } from "lucide-react";
import type { ArtworkScene } from "./historical-demo-types";
import { drawSceneShape,drawSceneBackground,routePoint } from "./scene-drawing";
import { useReducedAnimation } from "./reduced-motion";

export function ExpressiveArtwork({scene,seed,title}:{scene:ArtworkScene;seed:string;title:string}){
  const canvas=useRef<HTMLCanvasElement>(null),time=useRef(0),reduced=useReducedAnimation();
  const [playing,setPlaying]=useState(false),[restart,setRestart]=useState(0),[available,setAvailable]=useState(true);
  const [growth,setGrowth]=useState(false),[progress,setProgress]=useState(100);
  useEffect(()=>{setPlaying(!reduced);setGrowth(!reduced);},[reduced]);
  useEffect(()=>{
    const target=canvas.current,ctx=target?.getContext("2d");
    if(!target||!ctx){setAvailable(false);return;}
    const resolution=Math.min(1200,Math.max(640,Math.round(target.clientWidth*(window.devicePixelRatio||1))));
    target.width=target.height=resolution;const scale=resolution/scene.width;
    const makeLayer=()=>{const layer=document.createElement("canvas");layer.width=layer.height=resolution;return layer;};
    const full=makeLayer(),reveal=makeLayer(),background=makeLayer();
    const fullCtx=full.getContext("2d")!,revealCtx=reveal.getContext("2d")!,bgCtx=background.getContext("2d")!;
    for(const painter of [fullCtx,revealCtx,bgCtx])painter.scale(scale,scale);
    drawSceneBackground(bgCtx,scene);
    for(const shape of scene.shapes){drawSceneShape(fullCtx,shape);if(shape.time===undefined)drawSceneShape(revealCtx,shape);}
    const pending=scene.shapes.filter(shape=>shape.time!==undefined).sort((a,b)=>(a.time||0)-(b.time||0));
    let revealed=0;
    const routes=scene.shapes.filter(shape=>shape.layer==="routes"&&shape.points?.length).sort((a,b)=>(b.weight||0)-(a.weight||0)).slice(0,80);
    const lights=scene.shapes.filter(shape=>shape.layer==="particles"&&shape.kind==="dot").filter((_,i)=>i%19===0);
    const phase=parseInt(seed.slice(0,8),16)/0xffffffff;
    let frame=0,last=0,painted=0,visible=true,lastProgress=-1;
    const observer=new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting??false;});observer.observe(target);
    function render(t:number){
      const fraction=growth?Math.min(1,t/(scene.animation?.reveal_seconds||24)):1;
      while(revealed<pending.length&&(pending[revealed].time||0)<=fraction){drawSceneShape(revealCtx,pending[revealed]);revealed++;}
      const percent=Math.floor(fraction*100);if(percent!==lastProgress){setProgress(percent);lastProgress=percent;}
      ctx!.globalAlpha=1;ctx!.drawImage(background,0,0);ctx!.save();ctx!.translate(resolution/2,resolution/2);
      const angle=scene.family==="orbital_network"?t*.008*(scene.animation?.direction||1):Math.sin(t*.08+phase*6)*.005;
      const breathe=1+Math.sin(t*.28+phase*6)*.004;ctx!.rotate(angle);ctx!.scale(breathe,breathe);ctx!.translate(-resolution/2,-resolution/2);
      ctx!.drawImage(fraction<1?reveal:full,0,0);ctx!.restore();
      const activity=scene.animation?.activity_profile,period=scene.animation?.period_seconds||32;
      const signal=activity?.[Math.min(activity.length-1,Math.floor((t%period)/period*activity.length))]??.5;
      ctx!.save();ctx!.scale(scale,scale);ctx!.translate(scene.width/2,scene.height/2);ctx!.rotate(angle);ctx!.scale(breathe,breathe);ctx!.translate(-scene.width/2,-scene.height/2);ctx!.globalCompositeOperation=scene.controls?.style.dark===false?"source-over":"screen";
      routes.forEach((route,i)=>{
        if((route.time||0)>fraction)return;
        const speed=route.motion_rate||.055,comets=1+Math.floor((route.weight||0)*2);
        for(let comet=0;comet<comets;comet++){
          const position=(t*speed+phase+i*.117+comet/comets)%1,[x,y]=routePoint(route,position);
          ctx!.globalAlpha=.35+.5*signal;ctx!.fillStyle=route.color;ctx!.shadowColor=route.color;ctx!.shadowBlur=10;
          ctx!.beginPath();ctx!.arc(x,y,1.6+(route.weight||0)*1.7,0,Math.PI*2);ctx!.fill();
        }
      });
      ctx!.shadowBlur=8;
      lights.forEach((light,i)=>{
        if((light.time||0)>fraction)return;
        const pulse=Math.pow((Math.sin(t*(scene.animation?.pulse_hz||.127)*Math.PI*2+i*2.399+phase*6)+1)/2,5);
        if(pulse<.1)return;ctx!.globalAlpha=pulse*(.2+.4*signal);ctx!.fillStyle=ctx!.shadowColor=light.color;
        ctx!.beginPath();ctx!.arc(light.center![0],light.center![1],(light.radius||1)+pulse*1.8,0,Math.PI*2);ctx!.fill();
      });ctx!.restore();
    }
    render(time.current);
    function tick(now:number){
      if(playing&&visible&&!document.hidden){if(last)time.current+=Math.min(now-last,80)/1000;if(now-painted>=1000/30){render(time.current);painted=now;}}
      last=now;frame=requestAnimationFrame(tick);
    }
    if(playing)frame=requestAnimationFrame(tick);
    return()=>{cancelAnimationFrame(frame);observer.disconnect();};
  },[scene,seed,playing,restart,growth]);
  return <div className="animated-artwork"><canvas ref={canvas} role="img" aria-label={`Animated interpretation of ${title}: activity-driven pulses, frequency-weighted route lights and a chronological week reveal.`}/>
    {!available&&<p role="status">Animation is unavailable in this browser. Select Static image to see the artwork.</p>}
    <div className="art-motion-controls"><button className="button subtle" disabled={!available} onClick={()=>setPlaying(!playing)}>{playing?<Pause size={14}/>:<Play size={14}/>} {playing?"Pause":"Play"}</button><button className="button subtle" disabled={!available} onClick={()=>{time.current=0;setRestart(value=>value+1);}}><RotateCcw size={14}/> Restart</button><button className="button subtle" disabled={!available} onClick={()=>{time.current=0;setGrowth(!growth);setRestart(value=>value+1);}}><Sparkles size={14}/>{growth?"Show full scene":"Reveal the week"}</button><span>{growth?`Week reveal ${progress}% · `:""}{reduced?"Motion starts paused for your preference.":"Activity and route-frequency encodings; not settlement speed."}</span></div>
  </div>;
}
