"use client";
import { QueryClient, QueryClientProvider,focusManager } from "@tanstack/react-query";
import { useState,useEffect } from "react";
import { WalletProvider } from "./wallet-provider";
import {subscribeWalletActivity,walletApprovalPending} from "@/lib/wallet-activity";
export function Providers({ children }: {children: React.ReactNode}) {
  const [client] = useState(() => new QueryClient({defaultOptions:{queries:{retry:1,staleTime:30000,refetchOnWindowFocus:false}}}));
  useEffect(()=>{
    // All query interval observers honor this, including custom artwork queries.
    // Explicit pre-signature reads still use api() and always read fresh state.
    focusManager.setEventListener(handleFocus=>{
      const update=()=>handleFocus(!walletApprovalPending()&&document.visibilityState!=="hidden");
      const unsubscribe=subscribeWalletActivity(update);
      document.addEventListener("visibilitychange",update);update();
      return()=>{unsubscribe();document.removeEventListener("visibilitychange",update);};
    });
    return()=>{focusManager.setEventListener(()=>()=>{});focusManager.setFocused(undefined);};
  },[]);
  return <QueryClientProvider client={client}><WalletProvider>{children}</WalletProvider></QueryClientProvider>;
}
