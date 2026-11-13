"use client";
import Link from "next/link";
import {useEffect,useRef} from "react";
import {Wallet,ArrowUpRight,LogOut} from "lucide-react";
import {short} from "@/lib/api";
import {useWallet} from "./wallet-provider";

export function WalletControl(){
  const wallet=useWallet(),menu=useRef<HTMLDetailsElement>(null);
  useEffect(()=>{
    const close=(event:KeyboardEvent)=>{if(event.key==="Escape"&&menu.current)menu.current.open=false;};
    const outside=(event:PointerEvent)=>{if(menu.current&&!menu.current.contains(event.target as Node))menu.current.open=false;};
    document.addEventListener("keydown",close);document.addEventListener("pointerdown",outside);
    return()=>{document.removeEventListener("keydown",close);document.removeEventListener("pointerdown",outside);};
  },[]);
  if(!wallet.account)return <button className="wallet" aria-label="Connect wallet" disabled={!wallet.network||wallet.busy} onClick={()=>void wallet.connect()}><Wallet size={14}/><span>{wallet.busy?"Connecting…":"Connect wallet"}</span></button>;
  return <details className="wallet-menu" ref={menu}><summary className="wallet" aria-label={`Wallet ${wallet.account}`}><Wallet size={14}/><span>{short(wallet.account,7)}</span></summary><div className="wallet-menu-panel"><span className="eyebrow">{wallet.network} WALLET</span><p>{wallet.account}</p>{wallet.accounts.length>1&&<label>Active account<select value={wallet.account} onChange={event=>void wallet.selectAccount(event.target.value)}>{wallet.accounts.map(account=><option key={account}>{account}</option>)}</select></label>}<Link href="/my-collection" onClick={()=>{if(menu.current)menu.current.open=false;}}>My collection <ArrowUpRight size={16}/></Link><button disabled={wallet.busy} onClick={()=>void wallet.disconnect()}>Disconnect <LogOut size={15}/></button></div></details>;
}
