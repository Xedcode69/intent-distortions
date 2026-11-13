"use client";
import { useEffect, useRef, useState } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import type { ArtworkScene, SceneShape } from "./historical-demo-types";
import { ExpressiveArtwork } from "./expressive-artwork";

export function useReducedAnimation(){
  const [reduced,setReduced]=useState(true);
  useEffect(()=>{
    const query=window.matchMedia("(prefers-reduced-motion: reduce)");
    const update=()=>setReduced(query.matches);update();
    query.addEventListener("change",update);return()=>query.removeEventListener("change",update);
  },[]);
  return reduced;
}

function drawShape(ctx:CanvasRenderingContext2D,shape:SceneShape){
  ctx.globalAlpha=shape.alpha/255;ctx.fillStyle=ctx.strokeStyle=shape.color;
  ctx.beginPath();
  if(shape.kind==="dot"&&shape.center){ctx.arc(shape.center[0],shape.center[1],shape.radius||1,0,Math.PI*2);ctx.fill();}
  else if(shape.points?.length){ctx.lineWidth=shape.width||1;shape.points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.stroke();}
}

export function AnimatedArtwork(props:{scene:ArtworkScene;seed:string;title:string}){
  return props.scene.animation?.version==="data-motion-v2"?<ExpressiveArtwork {...props}/>:<LegacyAnimatedArtwork {...props}/>;
}

function LegacyAnimatedArtwork({scene,seed,title}:{scene:ArtworkScene;seed:string;title:string}){
  const canvas=useRef<HTMLCanvasElement>(null),time=useRef(0);
  const reduced=useReducedAnimation();
  const [playing,setPlaying]=useState(false),[restart,setRestart]=useState(0),[available,setAvailable]=useState(true);
  useEffect(()=>setPlaying(!reduced),[reduced]);
  useEffect(()=>{
    const target=canvas.current,ctx=target?.getContext("2d");
    if(!target||!ctx){setAvailable(false);return;}
    const resolution=Math.min(1440,Math.max(720,Math.round(target.clientWidth*(window.devicePixelRatio||1))));
    target.width=target.height=resolution;
    const scale=resolution/scene.width;
    const layers=new Map<string,HTMLCanvasElement>();
    for(const shape of scene.shapes){
      if(!layers.has(shape.layer)){
        const layer=document.createElement("canvas");layer.width=layer.height=resolution;
        const painter=layer.getContext("2d");if(!painter)continue;painter.scale(scale,scale);layers.set(shape.layer,layer);
      }
      const painter=layers.get(shape.layer)?.getContext("2d");if(painter)drawShape(painter,shape);
    }
    const routes=scene.shapes.filter(shape=>shape.layer==="routes"&&shape.points?.length);
    const lights=scene.shapes.filter(shape=>shape.layer==="particles"&&shape.kind==="dot").filter((_,i)=>i%19===0);
    const phase=parseInt(seed.slice(0,8),16)/0xffffffff;
    let frame=0,last=0,painted=0,visible=true;
    const observer=new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting??false;});observer.observe(target);
    function render(t:number){
      ctx!.globalAlpha=1;ctx!.fillStyle=scene.background;ctx!.fillRect(0,0,resolution,resolution);
      for(const [name,layer] of layers){
        ctx!.save();
        if(name==="geometry"||name==="particles"){
          ctx!.translate(resolution/2,resolution/2);
          const breathe=1+Math.sin(t*.28+phase*6)*.008;
          ctx!.scale(breathe,breathe);ctx!.rotate(Math.sin(t*.08+phase*6)*(name==="geometry"?.012:-.008));
          ctx!.translate(-resolution/2,-resolution/2);
        }
        ctx!.globalAlpha=name==="routes"?.85+.15*Math.sin(t*.5):1;ctx!.drawImage(layer,0,0);ctx!.restore();
      }
      ctx!.save();ctx!.scale(scale,scale);ctx!.globalCompositeOperation="screen";
      routes.forEach((route,i)=>{
        const points=route.points!,position=((t*.055+phase+i*.117)%1)*(points.length-1),index=Math.floor(position),fraction=position-index;
        const a=points[index],b=points[Math.min(index+1,points.length-1)];
        ctx!.globalAlpha=.65;ctx!.fillStyle=route.color;ctx!.shadowColor=route.color;ctx!.shadowBlur=12;
        ctx!.beginPath();ctx!.arc(a[0]+(b[0]-a[0])*fraction,a[1]+(b[1]-a[1])*fraction,2.4,0,Math.PI*2);ctx!.fill();
      });
      ctx!.shadowBlur=8;
      lights.forEach((light,i)=>{
        const pulse=Math.pow((Math.sin(t*.8+i*2.399+phase*6)+1)/2,5);
        if(pulse<.1)return;ctx!.globalAlpha=pulse*.55;ctx!.fillStyle=ctx!.shadowColor=light.color;
        ctx!.beginPath();ctx!.arc(light.center![0],light.center![1],(light.radius||1)+pulse*1.8,0,Math.PI*2);ctx!.fill();
      });ctx!.restore();
    }
    render(time.current);
    function tick(now:number){
      if(playing&&visible&&!document.hidden){
        if(last)time.current+=Math.min(now-last,80)/1000;
        if(now-painted>=1000/30){render(time.current);painted=now;}
      }
      last=now;frame=requestAnimationFrame(tick);
    }
    if(playing)frame=requestAnimationFrame(tick);
    return()=>{cancelAnimationFrame(frame);observer.disconnect();};
  },[scene,seed,playing,restart]);
  return <div className="animated-artwork">
    <canvas ref={canvas} role="img" aria-label={`Animated interpretation of ${title}: light follows recorded routes and particles pulse.`}/>
    {!available&&<p role="status">Animation is unavailable in this browser. Select Static image to see the artwork.</p>}
    <div className="art-motion-controls"><button className="button subtle" disabled={!available} onClick={()=>setPlaying(!playing)}>{playing?<Pause size={14}/>:<Play size={14}/>} {playing?"Pause":"Play"}</button><button className="button subtle" disabled={!available} onClick={()=>{time.current=0;setRestart(value=>value+1);}}><RotateCcw size={14}/> Restart</button><span>{reduced?"Motion starts paused for your preference.":"Light follows the saved scene."}</span></div>
  </div>;
}
