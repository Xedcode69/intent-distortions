"use client";
import {useAPI} from "@/lib/api";
import type {TraitBundle} from "@/lib/nft-traits";
export type {TraitBundle} from "@/lib/nft-traits";
export function TraitList({bundle}:{bundle:TraitBundle}){
 const all=[...bundle.attributes,...(bundle.edition_attributes||[])];
 const featured=all.filter(a=>["Art family","Material","Theme","Global edition"].includes(a.trait_type));
 return <section className="artwork-traits" aria-label="Artwork traits"><span className="eyebrow">THE ARTWORK'S CHARACTER</span><div className="primary-traits">{featured.map(a=><span key={a.trait_type}><b>{a.trait_type}</b>{a.value}</span>)}</div><details><summary>All traits & verification</summary><dl className="trait-grid">{all.map(a=><div key={a.trait_type}><dt>{a.trait_type}</dt><dd>{typeof a.value==="number"?a.value.toLocaleString("en-GB",{maximumFractionDigits:8}):a.value}</dd></div>)}</dl><p>{bundle.onchain_status==="published"?"Published in the NFT metadata.":"Recorded artwork traits; this artwork has not been confirmed as minted here."} Balances and draw eligibility are shown in Rewards.</p><p>Trait document SHA-256</p><code>{bundle.sha256}</code><p>Source provenance SHA-256</p><code>{bundle.source.provenance_sha256}</code></details></section>;
}
export function ArtworkTraits({id}:{id:string}){
 const {data,error}=useAPI<TraitBundle>(`/artworks/${id}/traits`);
 if(error)return <p role="alert">Artwork traits could not be verified or loaded.</p>;
 if(!data)return <p role="status">Loading recorded traits…</p>;
 return <TraitList bundle={data}/>;
}
