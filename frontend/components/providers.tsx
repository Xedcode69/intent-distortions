"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { WalletProvider } from "./wallet-provider";
export function Providers({ children }: {children: React.ReactNode}) {
  const [client] = useState(() => new QueryClient({defaultOptions:{queries:{retry:1,staleTime:30000}}}));
  return <QueryClientProvider client={client}><WalletProvider>{children}</WalletProvider></QueryClientProvider>;
}
