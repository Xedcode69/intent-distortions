export type TransactionReceipt={hash:string;network:"mainnet"|"testnet";label?:string};
export function transactionUrl(hash:string,network:"mainnet"|"testnet"){
 if(!/^[1-9A-HJ-NP-Za-km-z]{40,44}$/.test(hash)||!["mainnet","testnet"].includes(network))throw new Error("Invalid transaction reference");
 return `https://${network==="testnet"?"testnet.":""}nearblocks.io/txns/${hash}`;
}
export function transactionLabel(method:string){
 return ({storage_deposit:"Storage setup",register_bidder:"Bidder registration",place_bid:"Bid",buy:"Purchase",make_offer:"Offer",accept_offer:"Offer accepted",cancel_offer:"Offer cancellation",nft_approve:"Listing",cancel_listing:"Listing cancellation",nft_revoke:"Approval removal",withdraw_edition:"Early withdrawal",dispatch_exit:"Withdrawal delivery",nft_transfer:"Artwork transfer",withdraw_credit:"Credit withdrawal",withdraw_storage:"Storage withdrawal",near_withdraw:"Unwrap NEAR",finalize_auction:"Auction settlement",choose_theme:"Theme selection",pay_month:"Prize delivery"} as Record<string,string>)[method]||"Transaction";
}
export function assertTransactionConfirmed(result:unknown,network:"mainnet"|"testnet"){
 const value=result as {status?:unknown;transaction?:{hash?:unknown}}|null;
 const status=value?.status;
 if(status&&typeof status==="object"&&("SuccessValue" in status||"SuccessReceiptId" in status))return;
 let url="";try{if(typeof value?.transaction?.hash==="string")url=transactionUrl(value.transaction.hash,network);}catch{}
 const failed=!!status&&typeof status==="object"&&"Failure" in status;
 throw new Error(`${failed?"Transaction failed.":"Transaction was not confirmed."} ${url?`Inspect ${url} before retrying.`:"Check your wallet history before retrying."}`);
}
