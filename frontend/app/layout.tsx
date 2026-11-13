import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Shell } from "@/components/shell";
export const metadata: Metadata = {title:"NEAR ECHOES — The Weekly Genesis",description:"One week. One block. One artwork. Never repeated. An auditable generative art studio on NEAR."};
export default function Layout({ children }: {children: React.ReactNode}) {
  return <html lang="en"><body><Providers><Shell>{children}</Shell></Providers></body></html>;
}
