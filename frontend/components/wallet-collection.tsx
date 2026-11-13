"use client";
import Link from "next/link";
import {useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {ArrowUpRight,RefreshCw,Wallet} from "lucide-react";
import {api} from "@/lib/api";
import type {MarketToken} from "@/lib/marketplace";
import {useWallet} from "./wallet-provider";

type Collection = {
  status:"onchain"|"not_deployed"; network:string; contract:string;
  account_id:string; tokens:MarketToken[]; total:string|null; checked_at:number|null;
};

function OwnedArtworks({account,network}:{account:string;network:string}){
  const [offset,setOffset]=useState(0),limit=20;
  const {data,error,isFetching,refetch}=useQuery<Collection>({
    queryKey:["wallet-collection",network,account,offset],
    queryFn:()=>api(`/wallets/${encodeURIComponent(account)}/collection?offset=${offset}&limit=${limit}`),
    staleTime:0,refetchInterval:15000,
  });
  if(error)return <div className="empty-state" role="alert"><h2>Collection unavailable.</h2><p>Your current ownership could not be verified.</p><button className="button subtle" onClick={()=>void refetch()}>Try again</button></div>;
  if(!data)return <div className="empty-state" role="status"><p>Checking your collection…</p></div>;
  if(data.status==="not_deployed")return <div className="empty-state"><h2>The collection is on its way.</h2><p>No live NFT contract is configured for this site. Historical artwork studies do not appear as owned NFTs.</p><Link href="/gallery" className="button subtle">Explore the artwork <ArrowUpRight size={15}/></Link></div>;
  // Refuse ownership claims if the backend response does not match this wallet.
  if(data.account_id!==account||data.network!==network)return <p role="alert">The collection response does not match your wallet network.</p>;
  return <><div className="owned-toolbar"><div><strong>{data.total}</strong><span> {data.total==="1"?"artwork":"artworks"} owned</span></div><button className="button subtle" disabled={isFetching} onClick={()=>void refetch()}><RefreshCw size={14} className={isFetching?"spin":""}/>Refresh</button></div>
    <div className="gallery-grid owned-grid">{data.tokens.map(token=><article key={token.token_id} className="art-card"><Link href={`/marketplace?token=${encodeURIComponent(token.token_id)}`} className="card-image">{token.metadata?.media?<img src={token.metadata.media} alt={token.metadata.title||token.token_id} loading="lazy"/>:<span className="owned-no-image">INTENT DISTORTIONS</span>}<span className="card-badge">OWNED ON CHAIN</span><span className="card-arrow"><ArrowUpRight size={21}/></span></Link><div className="card-caption"><span className="overline">{token.token_id}</span><h3>{token.metadata?.title||token.token_id}</h3><Link href={`/marketplace?token=${encodeURIComponent(token.token_id)}`} className="text-link">View in market <ArrowUpRight size={14}/></Link></div></article>)}</div>
    {!data.tokens.length&&<div className="empty-state"><h2>{offset?"No artworks on this page.":"Your next distortion awaits."}</h2><p>{offset?"Ownership may have changed. Return to the first page or refresh.":"This wallet holds no NFTs from the configured Intent Distortions collection."}</p><Link href="/marketplace" className="button primary">Explore the market <ArrowUpRight size={15}/></Link></div>}
    {(offset>0||BigInt(data.total||"0")>BigInt(limit))&&<div className="owned-pagination"><button className="button subtle" disabled={offset===0||isFetching} onClick={()=>setOffset(Math.max(0,offset-limit))}>Previous</button><button className="button subtle" disabled={BigInt(offset+limit)>=BigInt(data.total||"0")||isFetching} onClick={()=>setOffset(offset+limit)}>Next</button></div>}
    <p className="demo-note">{data.network} · {data.contract} · Checked {new Date((data.checked_at||0)*1000).toLocaleTimeString()}. Ownership refreshes every 15 seconds.</p></>;
}

export function WalletCollection(){
  const wallet=useWallet();
  return <div className="page-container owned-page"><div className="page-title"><span className="eyebrow">YOUR INTENT DISTORTIONS</span><h1>A collection.<br/><em>Yours to keep.</em></h1><p>{wallet.account?wallet.account:"Connect your NEAR wallet to see your artworks."}</p></div>
    {wallet.account&&wallet.network?<OwnedArtworks key={`${wallet.network}:${wallet.account}`} account={wallet.account} network={wallet.network}/>:<div className="empty-state"><Wallet size={30} strokeWidth={1}/><h2>Your distortions live here.</h2><p>Connect an account to view its Intent Distortions NFTs.</p><button className="button primary" disabled={!wallet.network||wallet.busy} onClick={()=>void wallet.connect()}>Connect wallet <ArrowUpRight size={15}/></button></div>}
  </div>;
}
