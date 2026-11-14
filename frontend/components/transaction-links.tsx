import {ArrowUpRight} from "lucide-react";
import {transactionUrl,type TransactionReceipt} from "@/lib/transactions";
export function TransactionLinks({receipts}:{receipts:TransactionReceipt[]}){
 if(!receipts.length)return null;
 return <div className="transaction-links" aria-label="Transaction confirmations">{receipts.map((tx,i)=><div key={`${tx.hash}:${i}`}><span>{tx.label||"Transaction confirmed"}</span><a href={transactionUrl(tx.hash,tx.network)} target="_blank" rel="noopener noreferrer">{transactionUrl(tx.hash,tx.network)} <ArrowUpRight size={13}/></a></div>)}</div>;
}
export function TransactionMessage({message,className}:{message:string;className?:string}){
 const parts=message.split(/(https:\/\/(?:testnet\.)?nearblocks\.io\/txns\/[1-9A-HJ-NP-Za-km-z]{40,44})/g);
 return <p role="status" className={className}>{parts.map((part,i)=>/^https:\/\/(?:testnet\.)?nearblocks\.io\/txns\//.test(part)?<a key={i} href={part} target="_blank" rel="noopener noreferrer">{part}</a>:part)}</p>;
}
