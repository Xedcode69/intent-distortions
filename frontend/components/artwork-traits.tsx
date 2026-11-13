"use client";
import {useAPI} from "@/lib/api";
import type {TraitBundle} from "@/lib/nft-traits";
export type {TraitBundle} from "@/lib/nft-traits";
export function TraitList({bundle}:{bundle:TraitBundle}){
 return <section className="artwork-traits" aria-label="Artwork traits"><span className="eyebrow">FROZEN ARTWORK TRAITS</span><h2>The character of this echo.</h2>
 <p>Derived from the saved scene and committed inputs. Ownership, wallet balances and draw eligibility are shown separately in the Economy.</p>
 <dl className="trait-grid">{[...bundle.attributes,...(bundle.edition_attributes||[])].map(a=><div key={a.trait_type}><dt>{a.trait_type}</dt><dd>{typeof a.value==="number"?a.value.toLocaleString("en-GB",{maximumFractionDigits:8}):a.value}</dd></div>)}</dl>
 <details><summary>Trait integrity and mint status</summary><p>{bundle.onchain_status==="published"?"Published in the NFT metadata.":"Recorded artwork traits. This view does not claim they have been minted."}</p>
 <p>Trait document SHA-256</p><code>{bundle.sha256}</code><p>Source provenance SHA-256</p><code>{bundle.source.provenance_sha256}</code></details></section>;
}
export function ArtworkTraits({id}:{id:string}){
 const {data,error}=useAPI<TraitBundle>(`/artworks/${id}/traits`);
 if(error)return <p role="alert">Artwork traits could not be verified or loaded.</p>;
 if(!data)return <p role="status">Loading recorded traits…</p>;
 return <TraitList bundle={data}/>;
}
