import type {Metadata} from "next";
import {OnchainStudy} from "@/components/onchain-study";
import "./onchain.css";
export const metadata:Metadata={title:"Onchain study | Intent Distortions",description:"An immutable vector edition recovered directly from NEAR, in stillness and motion."};
export default function Page(){return <OnchainStudy/>;}
