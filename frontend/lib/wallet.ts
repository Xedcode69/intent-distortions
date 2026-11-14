import { actionCreators } from "@near-js/transactions";
import { createWalletSession } from "./wallet-session";
import {duringWalletApproval,walletFailure} from "./wallet-activity";
import {assertTransactionConfirmed} from "./transactions";
export const walletSession = createWalletSession(async network => {
  const {createDirectorySession}=await import("./wallet-connector");
  return createDirectorySession(network);
}, async selector => {
  await selector.connect();
});
export async function connectWallet(_contract:string, network:"testnet"|"mainnet") {
  return walletSession.connect(network);
}
export async function contractAction(contract:string, network:"testnet"|"mainnet",methodName:string,args:Record<string,unknown>,deposit="0",expectedSigner?:string) {
  if(!contract) throw new Error("Contract is not configured. No wallet transaction will be requested.");
  const selected=await connectWallet(contract,network);
  if(!selected.isSignedIn()) throw new Error("Connect your wallet, then submit again.");
  const wallet=await selected.wallet();
  const active=selected.store.getState().accounts.find(a=>a.active)||selected.store.getState().accounts[0];
  if(expectedSigner&&active?.accountId!==expectedSigner)throw new Error("Wallet account changed. Review the transaction again.");
  let result;
  try{result=await duringWalletApproval(()=>wallet.signAndSendTransaction({receiverId:contract,actions:[actionCreators.functionCall(methodName,args,200000000000000n,BigInt(deposit))]}));}
  catch(error){throw walletFailure(error);}
  assertTransactionConfirmed(result,network);
  if(!result)throw new Error("Transaction was not confirmed.");
  // A delayed receipt index must never cause the user to repeat a successful bid.
  try {await fetch("/api/v1/receipts",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({transaction_hash:result.transaction.hash,sender:result.transaction.signer_id})});}catch{}
  return result;
}
export async function walletAccount(contract:string,network:"testnet"|"mainnet"){
 const selected=await connectWallet(contract,network);
 const account=selected.store.getState().accounts.find(a=>a.active)||selected.store.getState().accounts[0];
 if(!account)throw new Error("Connect your NEAR wallet, then try again.");
 return account.accountId;
}
