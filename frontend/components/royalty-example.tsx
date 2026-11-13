"use client";
import {useState} from "react";
import {toYocto} from "@/lib/api";
import {royaltyFee,units} from "@/lib/marketplace";
export function RoyaltyExample(){
 const [sales,setSales]=useState("100"),[total,setTotal]=useState(10),[team,setTeam]=useState(2),[owned,setOwned]=useState(2);
 let pool=0n,seller=0n,valid=true;try{const gross=BigInt(toYocto(sales));pool=royaltyFee(String(gross));seller=gross-pool;}catch{valid=false;}
 const eligible=Math.max(0,total-Math.min(team,total)),per=eligible?pool/BigInt(eligible):0n,yours=per*BigInt(Math.min(owned,eligible));
 return <section className="economy-section"><span className="eyebrow">ILLUSTRATIVE ROYALTY SIMULATOR · NO REAL FUNDS</span><h2>Sales support the collection.</h2><p>A 5% fee on secondary marketplace sales funds a separate monthly pool. Each artwork held outside the creator and protocol custody wallets at UTC month-end earns one equal share. This does not change the primary auction’s 20/80 split or the raffle.</p>
 <div className="economy-inputs"><label>Example secondary sale · NEAR<input inputMode="decimal" value={sales} onChange={e=>setSales(e.target.value)}/></label><label>Artworks in the collection · {total}<input type="range" min="1" max="100" value={total} onChange={e=>setTotal(Number(e.target.value))}/></label><label>Team-held artworks · {Math.min(team,total)}<input type="range" min="0" max={total} value={Math.min(team,total)} onChange={e=>setTeam(Number(e.target.value))}/></label><label>Your eligible artworks · {Math.min(owned,eligible)}<input type="range" min="0" max={eligible} value={Math.min(owned,eligible)} onChange={e=>setOwned(Number(e.target.value))}/></label></div>
 {valid?<div className="economy-flow"><div><span>Seller receives</span><strong>{units(String(seller),24)}</strong><small>NEAR · 95%</small></div><div><span>Holder pool</span><strong>{units(String(pool),24)}</strong><small>NEAR · 5%</small></div><div><span>Per eligible artwork</span><strong>{units(String(per),24)}</strong><small>NEAR · {eligible} eligible artworks</small></div><div><span>Your example share</span><strong>{units(String(yours),24)}</strong><small>NEAR · creator receives zero</small></div></div>:<p role="alert">Enter a valid NEAR sale amount.</p>}
 <p>Multiple artworks earn multiple shares. A later sale does not redirect a payment fixed at an earlier cutoff. With no eligible artworks, the entire pool rolls forward. Integer rounding dust also rolls forward. This example uses one sale; fees are rounded per completed sale in the contract.</p></section>;
}
