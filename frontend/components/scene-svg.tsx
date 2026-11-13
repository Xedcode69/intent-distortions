"use client";
import { useId } from "react";
import type { ArtworkScene } from "./historical-demo-types";

export function SceneSvg({scene,visible}:{scene:ArtworkScene;visible:Record<string,boolean>}){
  const id="scene-"+useId().replaceAll(":","_");
  return <svg viewBox={`0 0 ${scene.width} ${scene.height}`} role="img" aria-label="Interactive layers of the recorded artwork">
    {scene.background_style&&<defs><linearGradient id={id} x2="0" y2="1"><stop stopColor={scene.background_style.top}/><stop offset="1" stopColor={scene.background_style.bottom}/></linearGradient></defs>}
    <rect width={scene.width} height={scene.height} fill={scene.background_style?`url(#${id})`:scene.background}/>
    {scene.shapes.filter(shape=>visible[shape.layer]!==false).map((shape,index)=>{
      const common={opacity:shape.alpha/255};
      if(shape.kind==="dot")return <circle key={index} {...common} cx={shape.center![0]} cy={shape.center![1]} r={shape.radius} fill={shape.color}/>;
      if(shape.kind==="polygon")return <polygon key={index} {...common} points={shape.points!.map(point=>point.join(",")).join(" ")} fill={shape.color} stroke={shape.stroke||shape.color} strokeWidth={shape.width}/>;
      if(shape.kind==="curve"){
        const [a,b,c,d]=shape.points!;return <path key={index} {...common} d={`M ${a[0]} ${a[1]} C ${b[0]} ${b[1]} ${c[0]} ${c[1]} ${d[0]} ${d[1]}`} fill="none" stroke={shape.color} strokeWidth={shape.width}/>;
      }
      return <polyline key={index} {...common} points={shape.points!.map(point=>point.join(",")).join(" ")} fill="none" stroke={shape.color} strokeWidth={shape.width}/>;
    })}
  </svg>;
}
