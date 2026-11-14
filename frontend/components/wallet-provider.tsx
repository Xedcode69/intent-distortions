"use client";
import {createContext,useContext,useEffect,useState,useCallback} from "react";
import {useAPI,type Health} from "@/lib/api";
import {walletApprovalPending} from "@/lib/wallet-activity";
import {walletSession} from "@/lib/wallet";
import type {WalletNetwork} from "@/lib/wallet-session";

type Session = {
  account:string; accounts:string[]; network:WalletNetwork|undefined;
  ready:boolean; busy:boolean; error:string;
  connect:()=>Promise<void>; disconnect:()=>Promise<void>;
  selectAccount:(account:string)=>Promise<void>;
};
type WalletSelector=Awaited<ReturnType<typeof walletSession.get>>;
const Context=createContext<Session|null>(null);

export function WalletProvider({children}:{children:React.ReactNode}){
  const {data:health}=useAPI<Health>("/health");
  const network=health?.network;
  const [account,setAccount]=useState(""),[accounts,setAccounts]=useState<string[]>([]);
  const [ready,setReady]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const [attempt,setAttempt]=useState(0);

  const update=useCallback((selector:WalletSelector)=>{
    const rows=selector.isSignedIn()?selector.store.getState().accounts:[];
    setAccounts(rows.map(row=>row.accountId));
    setAccount((rows.find(row=>row.active)||rows[0])?.accountId||"");
  },[]);

  useEffect(()=>{
    let disposed=false,subscription:{unsubscribe:()=>void}|undefined,timer:ReturnType<typeof setInterval>|undefined;
    let refresh:(()=>void)|undefined;
    setReady(false);setAccount("");setAccounts([]);
    if(network)void walletSession.get(network).then(selector=>{
      if(disposed)return;
      update(selector);setReady(true);setError("");
      subscription=selector.store.observable.subscribe(()=>update(selector));
      refresh=()=>{if(!walletApprovalPending())void selector.refresh();};
      timer=setInterval(refresh,15000);window.addEventListener("focus",refresh);
    }).catch(()=>{if(!disposed)setError("Wallet session could not be restored. Try connecting again.");});
    return()=>{disposed=true;subscription?.unsubscribe();if(timer)clearInterval(timer);if(refresh)window.removeEventListener("focus",refresh);};
  },[network,update,attempt]);

  async function connect(){
    if(!network)return;
    setBusy(true);setError("");
    try{const selector=await walletSession.connect(network);update(selector);if(!ready)setAttempt(value=>value+1);}
    catch(reason){setError(reason instanceof Error?reason.message:"Wallet connection failed.");}
    finally{setBusy(false);}
  }
  async function disconnect(){
    if(!network)return;
    setBusy(true);setError("");
    try{await walletSession.disconnect(network);update(await walletSession.get(network));}
    catch{setError("Could not disconnect the wallet. Try again.");}
    finally{setBusy(false);}
  }
  async function selectAccount(accountId:string){
    if(!network)return;
    try{const selector=await walletSession.get(network);selector.setActiveAccount(accountId);update(selector);setError("");}
    catch{setError("Could not switch the active account.");}
  }
  return <Context.Provider value={{account,accounts,network,ready,busy,error,connect,disconnect,selectAccount}}>{children}</Context.Provider>;
}
export function useWallet(){
  const session=useContext(Context);
  if(!session)throw new Error("WalletProvider is required.");
  return session;
}
