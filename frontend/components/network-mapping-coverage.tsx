import type { HistoricalDemoData } from "./historical-demo-types";

export function NetworkMappingCoverage({demo}:{demo:HistoricalDemoData}){
  const mapping=demo.statistics.network_mapping;
  if(!mapping)return null;
  return <section className="network-coverage" aria-label="Asset network mapping coverage">
    <div><span className="eyebrow">FROZEN NETWORK LOOKUP</span><h3>{mapping.resolved_assets} / {mapping.total_assets} asset IDs resolved</h3></div>
    <p>The saved token registry identifies source networks for <b>{mapping.source_records_mapped.toLocaleString()}</b> records and destination networks for <b>{mapping.destination_records_mapped.toLocaleString()}</b>, out of {mapping.total_records.toLocaleString()} successful records. {mapping.unresolved_assets>0?`${mapping.unresolved_assets} historical asset IDs are absent from the saved registry and remain labelled Unmapped assets.`:"Every captured asset ID is resolved."} The artwork uses this saved lookup, so later registry changes cannot alter its replay.</p>
    <details><summary>View source networks and contributing record counts</summary><div className="network-counts">{Object.entries(demo.statistics.chains||{}).sort((a,b)=>b[1]-a[1]).map(([name,count])=><div key={name}><span>{name==="Unmapped"?"Unresolved assets":name}</span><b>{count.toLocaleString()}</b></div>)}</div></details>
    <div className="hash-field"><span className="overline">Frozen network mapping SHA-256</span><code>{mapping.sha256}</code></div>
  </section>;
}
