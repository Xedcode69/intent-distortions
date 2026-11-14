import type { Metadata } from "next";
import "./globals.css";
import "./gallery-design.css";
import "./wallet-collection.css";
import "./collection-market.css";
import "./rewards.css";
import "./demo/onchain/onchain.css";
import { Providers } from "@/components/providers";
import { Shell } from "@/components/shell";
export const metadata: Metadata = {title:"Intent Distortions — A week. A work of art.",applicationName:"Intent Distortions",description:"A week of real movement, transformed into one original artwork. Explore, collect and follow the next drop on NEAR.",openGraph:{title:"Intent Distortions",siteName:"Intent Distortions",description:"A week of real movement. One original artwork."}};
export default function Layout({ children }: {children: React.ReactNode}) {
  return <html lang="en"><body><Providers><Shell>{children}</Shell></Providers></body></html>;
}
