"use client";
import {useState} from "react";
import {yocto,toYocto} from "@/lib/api";
import {simulateEconomy} from "@/lib/economy";
export function EconomyExample(){
 const [sales,setSales]=useState(5),[exits,setExits]=useState(2),[price,setPrice]=useState("100");
 let example;try{example=simulateEconomy(sales,Math.min(exits,sales),BigInt(toYocto(price)));}catch{example=null;}
 return <section className="economy-section economy-example"><span className="eyebrow">INTERACTIVE EXPLANATION · SIMULATED FUNDS</span><h2>Follow every NEAR.</h2><p>This example explains the rules. It creates no accounts, bids, transfers or raffle entries.</p>
 <div className="economy-inputs"><label>Auction price per NFT (NEAR)<input inputMode="decimal" value={price} onChange={e=>setPrice(e.target.value)}/></label>
 <label>Successful sales: {sales}<input type="range" min="0" max="5" value={sales} onChange={e=>{const n=Number(e.target.value);setSales(n);setExits(Math.min(exits,n));}}/></label>
 <label>Early withdrawals: {Math.min(exits,sales)}<input type="range" min="0" max={sales} value={Math.min(exits,sales)} onChange={e=>setExits(Number(e.target.value))}/></label></div>
 {example?<><div className="economy-flow" aria-label="Auction proceeds distribution">{[["Treasury",example.treasury],["Early withdrawals",example.withdrawals],["Current pot",example.pot],["Next month",example.rollover]].map(([label,amount])=><div key={String(label)}><span>{String(label)}</span><strong>{yocto(String(amount))}</strong><small>NEAR</small></div>)}</div>
 <p role="status">{example.tickets} eligible NFT{example.tickets===1?"":"s"}{example.tickets>0?`, each with one of ${example.tickets} tickets`:"; the pot carries forward if there are no entries"}. Total allocated: {yocto(example.gross.toString())} NEAR.</p></>:<p role="alert">Enter a valid non-negative NEAR amount.</p>}
 </section>;
}


export {RewardsOverview as EconomyDashboard} from "./rewards-overview";
