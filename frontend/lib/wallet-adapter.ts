import type {NearConnector,Account,SignAndSendTransactionParams} from "@hot-labs/near-connect";
import type {WalletNetwork} from "./wallet-session";

export async function createConnectorAdapter(connector:NearConnector,network:WalletNetwork,isDirectoryWallet:(id:string)=>boolean){
  const listeners=new Set<()=>void>();
  let accounts:Account[]=[],active="";
  function update(rows:Account[]){
    accounts=rows.filter(row=>/^(?=.{2,64}$)[a-z0-9]+(?:[._-][a-z0-9]+)*$/.test(row.accountId));
    if(!accounts.some(row=>row.accountId===active))active=accounts[0]?.accountId||"";
    listeners.forEach(listener=>listener());
  }
  connector.on("wallet:signIn",event=>{if(isDirectoryWallet(event.wallet.manifest.id))update(event.accounts);});
  connector.on("wallet:signOut",()=>update([]));
  try{const session=await connector.getConnectedWallet();if(isDirectoryWallet(session.wallet.manifest.id))update(session.accounts);}catch{}
  const adapter={
    isSignedIn:()=>accounts.length>0,
    store:{getState:()=>({accounts:accounts.map(row=>({...row,active:row.accountId===active}))}),
      observable:{subscribe(listener:()=>void){listeners.add(listener);return {unsubscribe:()=>{listeners.delete(listener);}};}}},
    setActiveAccount(accountId:string){if(!accounts.some(row=>row.accountId===accountId))throw new Error("Account is not connected.");active=accountId;listeners.forEach(listener=>listener());},
    async connect(){await connector.connect();},
    async refresh(){try{const current=await connector.getConnectedWallet();if(!isDirectoryWallet(current.wallet.manifest.id))throw new Error("Unsupported wallet");update(current.accounts);}catch{update([]);}},
    async wallet(){
      const {wallet,accounts:current}=await connector.getConnectedWallet();
      if(!isDirectoryWallet(wallet.manifest.id)||!current.some(row=>row.accountId===active)){
        update([]);throw new Error("Wallet account changed. Reconnect before submitting.");
      }
      const signerId=active;
      return {
        async signOut(){await connector.disconnect(wallet);update([]);},
        async signAndSendTransaction(params:SignAndSendTransactionParams){
          if(active!==signerId)throw new Error("Active account changed. Review the transaction again.");
          const latest=await connector.getConnectedWallet();
          if(latest.wallet!==wallet||!latest.accounts.some(row=>row.accountId===signerId)){
            update([]);throw new Error("Wallet account changed. Reconnect before submitting.");
          }
          return wallet.signAndSendTransaction({...params,signerId,network});
        },
      };
    },
  };
  return adapter;
}
