import test from 'node:test';
import assert from 'node:assert/strict';
import {directoryManifest,isDirectoryWallet,directoryWalletIds} from '../lib/wallet-policy.ts';
import {createConnectorAdapter} from '../lib/wallet-adapter.ts';

test('wallet directory is an explicit allowlist and excludes MyNearWallet and injected additions',()=>{
 const manifest=id=>({id,type:'sandbox',executor:'https://wallet.example/executor.js',features:{signInWithoutAddKey:true,signAndSendTransaction:true},permissions:{}});
 const result=directoryManifest({version:'1',wallets:[...directoryWalletIds.map(manifest),manifest('my-near-wallet'),manifest('unknown-wallet'),{...manifest('hot-wallet'),type:'injected'}]});
 assert.deepEqual(result.wallets.map(wallet=>wallet.id),[...directoryWalletIds]);
 assert.equal(isDirectoryWallet('my-near-wallet'),false);
 assert.equal(isDirectoryWallet('ethereum-wallets'),false);
 assert.throws(()=>directoryManifest({wallets:[{...manifest('meteor-wallet'),executor:'http://untrusted.example'}]}));
 assert.throws(()=>directoryManifest({wallets:[{...manifest('meteor-wallet'),features:{signAndSendTransaction:true}}]}));
});

test('restored accounts, account changes and disconnect propagate; transactions bind the reviewed signer and network',async()=>{
 const events=new Map();let rows=[{accountId:'one.near'},{accountId:'two.near'}],sent,disconnected=false;
 const wallet={manifest:{id:'meteor-wallet'},signAndSendTransaction:async params=>{sent=params;return {status:{SuccessValue:''}};}};
 const connector={on:(name,callback)=>events.set(name,callback),getConnectedWallet:async()=>({wallet,accounts:rows}),connect:async()=>{},disconnect:async()=>{disconnected=true;events.get('wallet:signOut')({success:true});}};
 const adapter=await createConnectorAdapter(connector,'mainnet',isDirectoryWallet);
 let changes=0;const subscription=adapter.store.observable.subscribe(()=>changes++);
 assert.equal(adapter.store.getState().accounts.find(row=>row.active).accountId,'one.near');
 const reviewed=await adapter.wallet();adapter.setActiveAccount('two.near');
 await assert.rejects(reviewed.signAndSendTransaction({receiverId:'nft.near',actions:[]}),/account changed/i);
 const selected=await adapter.wallet();await selected.signAndSendTransaction({receiverId:'nft.near',actions:[],signerId:'wrong.near',network:'testnet'});
 assert.equal(sent.signerId,'two.near');assert.equal(sent.network,'mainnet');
 rows=[{accountId:'buyer.near'}];await adapter.refresh();
 assert.equal(adapter.store.getState().accounts[0].accountId,'buyer.near');
 await (await adapter.wallet()).signOut();assert.equal(disconnected,true);assert.equal(adapter.isSignedIn(),false);
 assert.ok(changes>=3);subscription.unsubscribe();
});

test('unlisted restored wallets and removed signer accounts cannot submit',async()=>{
 let rows=[{accountId:'one.near'}],id='my-near-wallet';
 const wallet={manifest:{get id(){return id;}},signAndSendTransaction:async()=>{throw new Error('must not sign');}};
 const connector={on:()=>{},getConnectedWallet:async()=>({wallet,accounts:rows})};
 const adapter=await createConnectorAdapter(connector,'testnet',isDirectoryWallet);
 assert.equal(adapter.isSignedIn(),false);
 await assert.rejects(adapter.wallet(),/account changed/i);
 id='meteor-wallet';await adapter.refresh();const reviewed=await adapter.wallet();rows=[];
 await assert.rejects(reviewed.signAndSendTransaction({receiverId:'nft.testnet',actions:[]}),/account changed/i);
 assert.equal(adapter.isSignedIn(),false);
});
