"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

type Progress = {status:string;stage:string;sunday:string|null;start:number|null;end_ns:string|null;
  received_rows:number;pages:number;total_records:number|null;eligible_records:number|null;
  collection_complete:boolean;elapsed_seconds:number;updated_at:number|null;stale:boolean};
const names:Record<string,string>={waiting:"Waiting to start",beacon:"Verifying randomness",checkpoint:"Verifying the historical block",capture:"Collecting historical records",art_direction:"Generating artwork",verification:"Verifying artwork",export:"Preparing the result",complete:"Replay verified"};
const elapsed=(seconds:number)=>`${Math.floor(seconds/3600)}h ${Math.floor(seconds%3600/60)}m ${seconds%60}s`;

export function ReplayProgress(){
  const {data,error}=useQuery<Progress>({queryKey:["replay-progress"],queryFn:()=>api<Progress>("/replay/progress"),refetchInterval:5000,retry:false});
  if(!data||data.status==="idle")return null;
  const title=names[data.stage]||"Preparing historical replay";
  return <section className="replay-progress" aria-label="Historical replay progress">
    <div className="replay-progress-heading"><div><span className="eyebrow">HISTORICAL RUN {data.sunday}</span><h2>{title}</h2></div><span className="pill">{data.status.replaceAll("_"," ")}</span></div>
    <div className="replay-progress-track" role="progressbar" aria-label="Historical record collection" aria-valuemin={0} aria-valuemax={100} aria-valuenow={data.collection_complete?100:undefined} aria-valuetext={data.collection_complete?"Collection complete":`${data.received_rows.toLocaleString()} rows received; total not yet available`}><span className={data.collection_complete?"replay-progress-fill complete":"replay-progress-fill indeterminate"}/></div>
    <div className="replay-progress-numbers" aria-live="polite"><span><b>{data.received_rows.toLocaleString()}</b> rows received</span><span>{data.pages.toLocaleString()} pages</span><span>{elapsed(data.elapsed_seconds)} elapsed</span></div>
    <p>{data.total_records===null?"Explorer does not provide a total count in advance. The bar stays indeterminate until the final page is received.":`${data.total_records.toLocaleString()} unique records found; ${data.eligible_records?.toLocaleString()??"—"} successful eligible records contribute to the artwork.`}</p>
    {data.start!==null&&<p className="demo-note">UTC interval: {new Date(data.start*1000).toUTCString()} → {data.end_ns?new Date(Number(BigInt(data.end_ns)/1000000n)).toUTCString():"verifying endpoint"} (end exclusive).</p>}
    {(data.stale||error)&&<p role="status" className="demo-note">Progress has not refreshed recently. The last reported count is shown above.</p>}
    {data.status==="failed"&&<p role="status">The run stopped before completion. Saved inputs are retained for diagnosis and retry.</p>}
  </section>;
}
