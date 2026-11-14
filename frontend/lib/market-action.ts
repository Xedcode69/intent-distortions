// One user action, ordered wallet approvals. Never continue after cancellation,
// account changes, or stale financial rights. Storage is recoverable separately.
export async function submitPreparedMarketAction<T>(input:{account:string;kind:"buy"|"offer"|"list";replacesOwnListing?:boolean},io:{
 currentAccount:()=>Promise<string>;readBalance:()=>Promise<{storage_available:string}>;
 validate:()=>Promise<void>;register:(deposit:string)=>Promise<unknown>;submit:()=>Promise<T>;
 progress?:(phase:"storage"|"action")=>void;
}){
 const check=async()=>{if(await io.currentAccount()!==input.account)throw new Error("Wallet account changed. Review this artwork again.");};
 await check();await io.validate();const balance=await io.readBalance();
 const available=BigInt(balance.storage_available),record=10n**22n;
 const needsStorage=input.kind==="buy"?available===0n:available<record&&!input.replacesOwnListing;
 if(needsStorage){
  await check();io.progress?.("storage");
  await io.register(String(input.kind==="buy"?record:record*2n));
  await check();const after=await io.readBalance();
  if(input.kind!=="buy"&&BigInt(after.storage_available)<record)throw new Error("Storage setup was not confirmed. Check your wallet before retrying.");
 }
 await check();await io.validate();io.progress?.("action");return io.submit();
}
