// Used by the query provider to leave RPC capacity for wallet approvals.
let pending=0;
const listeners=new Set<()=>void>();
export const walletApprovalPending=()=>pending>0;
export function subscribeWalletActivity(listener:()=>void){listeners.add(listener);return()=>{listeners.delete(listener);};}
export async function duringWalletApproval<T>(action:()=>Promise<T>):Promise<T>{
 pending++;listeners.forEach(fn=>fn());
 try{return await action();}finally{pending--;listeners.forEach(fn=>fn());}
}
export function walletFailure(error:unknown):Error{
 const raw=typeof error==="string"?error:error instanceof Error?error.message:JSON.stringify(error);
 if(/rate.?limit|too many requests|["\s:]?-429\b|\b429\b/i.test(raw||""))return new Error("The wallet's RPC provider is rate limited. No automatic payment retry was sent. Close this wallet request, wait a minute, then refresh the artwork and check ownership and marketplace credit before trying again. If it persists, use another supported wallet.");
 return error instanceof Error?error:new Error(typeof error==="string"?error:"The wallet request was not confirmed. Check its transaction history before retrying.");
}
