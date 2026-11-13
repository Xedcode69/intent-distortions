import {NearConnector,type DataStorage,type NearConnector_ConnectOptions} from "@hot-labs/near-connect";
import {createConnectorAdapter} from "./wallet-adapter";
import {directoryManifest,isDirectoryWallet} from "./wallet-policy";
import type {WalletNetwork} from "./wallet-session";

async function manifest(){
  for(const url of ["https://raw.githubusercontent.com/hot-dao/near-selector/refs/heads/main/repository/manifest.json","https://cdn.jsdelivr.net/gh/azbang/near-connect/repository/manifest.json"]){
    try{const response=await fetch(url,{signal:AbortSignal.timeout(8000)});if(response.ok)return directoryManifest(await response.json());}catch{}
  }
  throw new Error("Wallet directory could not be loaded. Check your connection and try again.");
}

export async function createDirectorySession(network:WalletNetwork){
  const prefix=`near-echoes:wallet:${network}:`;
  const storage:DataStorage={
    async get(key){const value=localStorage.getItem(prefix+key);return key==="selected-wallet"&&value&&!isDirectoryWallet(value)?null:value;},
    async set(key,value){if(key==="selected-wallet"&&!isDirectoryWallet(value))throw new Error("Wallet is not in the supported NEAR directory list.");localStorage.setItem(prefix+key,value);},
    async remove(key){localStorage.removeItem(prefix+key);},
  };
  class DirectoryConnector extends NearConnector{
    override get availableWallets(){return super.availableWallets.filter(wallet=>isDirectoryWallet(wallet.manifest.id)&&!wallet.manifest.debug);}
    override async connect(input:NearConnector_ConnectOptions={}){
      if(input.walletId&&!isDirectoryWallet(input.walletId))throw new Error("Wallet is not supported.");
      return super.connect(input);
    }
    override async wallet(id?:string|null){
      if(id&&!isDirectoryWallet(id))throw new Error("Wallet is not supported.");
      return super.wallet(id);
    }
    override async registerDebugWallet():Promise<never>{throw new Error("Custom wallet sources are disabled.");}
  }
  const connector=new DirectoryConnector({network,storage,manifest:await manifest(),autoConnect:false,
    features:{signInWithoutAddKey:true,signAndSendTransaction:true}});
  await connector.whenManifestLoaded;
  return createConnectorAdapter(connector,network,isDirectoryWallet);
}
