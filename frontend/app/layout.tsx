import type { Metadata } from "next";
import "./globals.css";
import "./gallery-design.css";
import { Providers } from "@/components/providers";
import { Shell } from "@/components/shell";
export const metadata: Metadata = {title:"NEAR ECHOES — A week. A work of art.",description:"A week of real movement, transformed into one original artwork. Explore, collect and follow the next drop on NEAR."};
export default function Layout({ children }: {children: React.ReactNode}) {
  return <html lang="en"><body><Providers><Shell>{children}</Shell></Providers></body></html>;
}
