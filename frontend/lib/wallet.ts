import type { WalletSelector } from "@near-wallet-selector/core";
import { actionCreators } from "@near-js/transactions";
let selector: WalletSelector | undefined;
export async function connectWallet(contract:string, network:"testnet"|"mainnet") {
  if(!contract) throw new Error("Auction contract is not configured yet. No wallet transaction will be requested.");
  const {setupWalletSelector}=await import("@near-wallet-selector/core");
  const {setupMyNearWallet}=await import("@near-wallet-selector/my-near-wallet");
  const {setupModal}=await import("@near-wallet-selector/modal-ui");
  selector ??= await setupWalletSelector({network,modules:[setupMyNearWallet()]});
  if(!selector.isSignedIn()) setupModal(selector,{contractId:contract}).show();
  return selector;
}
export async function contractAction(contract:string, network:"testnet"|"mainnet",methodName:string,args:Record<string,unknown>,deposit="0") {
  const selected=await connectWallet(contract,network);
  if(!selected.isSignedIn()) throw new Error("Connect your wallet, then submit again.");
  const wallet=await selected.wallet();
  const result=await wallet.signAndSendTransaction({receiverId:contract,actions:[actionCreators.functionCall(methodName,args,200000000000000n,BigInt(deposit))]});
  if(!result || !("status" in result) || typeof result.status!=="object" || "Failure" in result.status) throw new Error("Transaction was not confirmed. Inspect your wallet or explorer before retrying.");
  // A delayed receipt index must never cause the user to repeat a successful bid.
  try {await fetch("/api/v1/receipts",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({transaction_hash:result.transaction.hash,sender:result.transaction.signer_id})});}catch{}
  return result;
}
