import type {Metadata} from "next";
import {WalletCollection} from "@/components/wallet-collection";
export const metadata:Metadata={title:"My collection | NEAR ECHOES"};
export default function Page(){return <WalletCollection/>;}
