import type { ArtworkScene,SceneShape } from "./historical-demo-types";

export function drawSceneShape(ctx:CanvasRenderingContext2D,shape:SceneShape){
  ctx.save();ctx.globalAlpha=shape.alpha/255;ctx.fillStyle=ctx.strokeStyle=shape.color;ctx.lineWidth=shape.width||1;ctx.beginPath();
  if(shape.kind==="dot"&&shape.center){ctx.arc(shape.center[0],shape.center[1],shape.radius||1,0,Math.PI*2);ctx.fill();}
  else if(shape.points?.length){
    const points=shape.points;ctx.moveTo(points[0][0],points[0][1]);
    if(shape.kind==="curve"&&points.length===4)ctx.bezierCurveTo(points[1][0],points[1][1],points[2][0],points[2][1],points[3][0],points[3][1]);
    else points.slice(1).forEach(([x,y])=>ctx.lineTo(x,y));
    if(shape.kind==="polygon"){
      ctx.closePath();ctx.fill();ctx.strokeStyle=shape.stroke||shape.color;ctx.globalAlpha=Math.min(1,(shape.alpha+30)/255);ctx.stroke();
    }else ctx.stroke();
  }
  ctx.restore();
}

export function drawSceneBackground(ctx:CanvasRenderingContext2D,scene:ArtworkScene){
  ctx.save();ctx.globalAlpha=1;
  if(scene.background_style){
    const gradient=ctx.createLinearGradient(0,0,0,scene.height);
    gradient.addColorStop(0,scene.background_style.top);gradient.addColorStop(1,scene.background_style.bottom);ctx.fillStyle=gradient;
  }else ctx.fillStyle=scene.background;
  ctx.fillRect(0,0,scene.width,scene.height);
  if(scene.background_style){
    const [x,y]=scene.background_style.light,light=ctx.createRadialGradient(x,y,0,x,y,800);
    light.addColorStop(0,`rgba(180,205,220,${scene.background_style.intensity*.1})`);light.addColorStop(1,"rgba(180,205,220,0)");
    ctx.fillStyle=light;ctx.fillRect(0,0,scene.width,scene.height);
  }
  ctx.restore();
}

export function routePoint(shape:SceneShape,t:number):number[]{
  const points=shape.points!;
  if(shape.kind==="curve"&&points.length===4)return [0,1].map(k=>(1-t)**3*points[0][k]+3*(1-t)**2*t*points[1][k]+3*(1-t)*t*t*points[2][k]+t**3*points[3][k]);
  const position=t*(points.length-1),index=Math.floor(position),fraction=position-index,a=points[index],b=points[Math.min(index+1,points.length-1)];
  return [a[0]+(b[0]-a[0])*fraction,a[1]+(b[1]-a[1])*fraction];
}
