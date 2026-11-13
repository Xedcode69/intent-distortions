import type { ArtworkScene,HistoricalDemoData } from "./historical-demo-types";

export function RenderControls({scene,demo}:{scene:ArtworkScene;demo:HistoricalDemoData}){
  if(!scene.controls)return null;
  const features=demo.statistics.visual_features,style=scene.controls.style;
  return <section className="network-coverage render-controls" aria-label="What shapes this artwork">
    <span className="eyebrow">THIS WEEK'S DRAWING RULES</span><h3>{style.material} · {style.theme} · {Math.round(style.complexity*100)}% detail</h3>
    {demo.family_selection&&<p>The <b>{demo.artwork.composition.replaceAll("_"," ")}</b> family was selected from the art seed with a verifiable draw among six families. AI supplied its styling. Curator styling cannot replace the selected family.</p>}
    {features&&<div className="network-counts">{[["Reciprocal cross-network routes",`${Math.round(features.reciprocity*100)}%`],["Activity burstiness",features.burstiness.toFixed(2)],["Network communities",features.community_count],["Asset diversity",features.asset_diversity.toFixed(2)],["Trade-size inequality",features.size_inequality.toFixed(2)]].map(([label,value])=><div key={label}><span>{label}</span><b>{value}</b></div>)}</div>}
    <details><summary>View family controls</summary><div className="network-counts">{Object.entries(scene.controls.family).map(([name,value])=><div key={name}><span>{name.replaceAll("_"," ")}</span><b>{typeof value==="number"?Number(value.toFixed(3)):value}</b></div>)}</div></details>
    {scene.visual_features_sha256&&<div className="hash-field"><span className="overline">Frozen visual measurements SHA-256</span><code>{scene.visual_features_sha256}</code></div>}
    {demo.family_selection&&<div className="hash-field"><span className="overline">Family draw digest · {demo.family_selection.policy}</span><code>{demo.family_selection.digest}</code></div>}
  </section>;
}
