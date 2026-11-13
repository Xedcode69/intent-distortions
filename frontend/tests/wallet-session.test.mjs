import test from 'node:test';
import assert from 'node:assert/strict';
import {createWalletSession} from '../lib/wallet-session.ts';

test('concurrent wallet callers share initialization and restore without opening sign-in',async()=>{
 let loads=0,shows=0,finish;
 const selector={isSignedIn:()=>true};
 const session=createWalletSession(async network=>{loads++;assert.equal(network,'mainnet');return new Promise(resolve=>{finish=resolve;});},async()=>{shows++;});
 const first=session.get('mainnet'),second=session.connect('mainnet');
 assert.equal(loads,1);finish(selector);
 assert.equal(await first,selector);assert.equal(await second,selector);assert.equal(shows,0);
 await assert.rejects(session.get('testnet'),/network changed/i);
 assert.equal(loads,1);
});

test('failed initialization can retry and disconnect uses the selected wallet',async()=>{
 let loads=0,shows=0,signedIn=false,signOuts=0;
 const selector={isSignedIn:()=>signedIn,wallet:async()=>({signOut:async()=>{signOuts++;signedIn=false;}})};
 const session=createWalletSession(async()=>{if(++loads===1)throw new Error('temporary');return selector;},async value=>{assert.equal(value,selector);shows++;});
 await assert.rejects(session.get('testnet'),/temporary/);
 await session.connect('testnet');assert.equal(shows,1);assert.equal(loads,2);
 signedIn=true;await session.connect('testnet');assert.equal(shows,1);
 await session.disconnect('testnet');assert.equal(signOuts,1);assert.equal(signedIn,false);
 await session.disconnect('testnet');assert.equal(signOuts,1);
});
