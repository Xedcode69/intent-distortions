import type { Metadata } from "next";
import { HistoricalDemo } from "@/components/historical-demo";

export const metadata: Metadata = {title:"Historical demo | NEAR ECHOES", description:"Follow recorded swap data through a verified historical artwork."};
export default function Page(){return <HistoricalDemo/>;}
