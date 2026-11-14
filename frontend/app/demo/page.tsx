import Link from "next/link";
import type {Metadata} from "next";
export const metadata:Metadata={title:"How it works | Intent Distortions"};
export default function Page(){return <div className="page-container">
 <div className="page-title"><span className="eyebrow">REAL MOVEMENT. LASTING ART.</span><h1>A week.<br/><em>Made permanent.</em></h1><p>Successful NEAR Intents swaps become a one-of-one artwork, stored entirely on NEAR testnet.</p></div>
 <section className="discover-how-steps">{[
  ["01","The network leaves a trace.","A weekly snapshot captures successful swaps. Routes, networks, sizes and activity shape the piece."],
  ["02","A character emerges.","A verifiable seed selects an art family. NEAR AI directs its palette, material and composition."],
  ["03","The artwork becomes final.","Frozen geometry and its renderer live onchain. The still and animated views retain their original hashes."],
  ["04","A collector writes the next chapter.","A 24-hour auction begins every Sunday from November 15. The NFT carries its dedicated edition account into future sales."],
 ].map(([n,title,copy])=><article key={n}><span>{n}</span><div><h3>{title}</h3><p>{copy}</p></div></article>)}</section>
 <section className="discover-how"><div><span className="eyebrow">THE COLLECTION ECONOMY</span><h2>Collect.<br/><em>Participate.</em></h2></div><div><p>Twenty percent of a successful auction supports the treasury. Eighty percent funds the edition account. Its owner can withdraw forty percent of that allocation before the month closes, leaving the remainder for the next month's pot and forfeiting that edition's draw entry.</p><p>Eligible editions enter a monthly draw verified by the contract. Marketplace sales contribute a five-percent fee, shared equally per eligible artwork among holders at month end, excluding the team.</p><p>All purchases and rewards use test NEAR. The genesis is preserved as a separate first edition, with no auction-funded rewards.</p><Link href="/artwork/genesis" className="button primary">Explore the genesis ↗</Link> <Link href="/drops" className="button subtle">Next drop ↗</Link></div></section>
 </div>;}
