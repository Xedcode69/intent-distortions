import type {WalletManifest} from "@hot-labs/near-connect";

// Explicitly selected from wallet.near.org. Manifest updates cannot add wallets
// to the site's menu without a source change and review.
export const directoryWalletIds = ["meteor-wallet","hot-wallet","intear-wallet","nightly-wallet","near-mobile"] as const;
export const isDirectoryWallet = (id:string)=>directoryWalletIds.some(allowed=>allowed===id);

export function directoryManifest(value:unknown):{version:string;wallets:WalletManifest[]}{
  if(!value||typeof value!=="object"||!("wallets" in value)||!Array.isArray(value.wallets))throw new Error("Wallet directory is unavailable.");
  const wallets=value.wallets.filter((row:WalletManifest)=>row&&isDirectoryWallet(row.id)&&row.type==="sandbox"&&
    typeof row.executor==="string"&&row.executor.startsWith("https://")&&
    row.features?.signInWithoutAddKey===true&&row.features?.signAndSendTransaction===true&&!!row.permissions);
  const unique=new Map(wallets.map((wallet:WalletManifest)=>[wallet.id,wallet]));
  if(!unique.size)throw new Error("No supported directory wallets are available.");
  return {version:"version" in value&&typeof value.version==="string"?value.version:"1",wallets:[...unique.values()]};
}
