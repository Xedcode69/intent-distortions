import test from 'node:test';
import assert from 'node:assert/strict';
import {submitPreparedMarketAction} from '../lib/market-action.ts';
import {withdrawalState} from '../lib/economy.ts';

function flow(kind='offer',overrides={}){
 const calls=[];let available='0';
 return {calls,run:(input={})=>submitPreparedMarketAction({account:'alice.testnet',kind,...input},{
  currentAccount:async()=> 'alice.testnet',readBalance:async()=>({storage_available:available}),
  validate:async()=>{calls.push('validate');},register:async amount=>{calls.push(['storage',amount]);available='10000000000000000000000';},
  submit:async()=>{calls.push('action');return 'receipt';},...overrides})};
}
test('one action sets up storage, rechecks rights and submits the exact action',async()=>{
 const f=flow();assert.equal(await f.run(),'receipt');assert.deepEqual(f.calls,['validate',['storage','20000000000000000000000'],'validate','action']);
 const buy=flow('buy');await buy.run();assert.deepEqual(buy.calls[1],['storage','10000000000000000000000']);
 const update=flow('list');await update.run({replacesOwnListing:true});assert.deepEqual(update.calls,['validate','validate','action']);
});
test('a cancelled storage approval cannot trigger the action',async()=>{
 const f=flow('list',{register:async()=>{throw new Error('Cancelled');}});
 await assert.rejects(f.run(),/Cancelled/);assert.ok(!f.calls.includes('action'));
});
test('changed wallet or financial rights after preparation stop the action',async()=>{
 let checks=0;const f=flow('buy',{currentAccount:async()=>++checks<3?'alice.testnet':'other.testnet'});
 await assert.rejects(f.run(),/account changed/);assert.ok(!f.calls.includes('action'));
 let reads=0;const stale=flow('offer',{validate:async()=>{if(++reads===2)throw new Error('Rights changed');}});
 await assert.rejects(stale.run(),/Rights changed/);assert.ok(!stale.calls.includes('action'));
});
test('existing storage avoids extra approvals and failed setup is not silently continued',async()=>{
 const f=flow('offer',{readBalance:async()=>({storage_available:'10000000000000000000000'})});await f.run();assert.deepEqual(f.calls,['validate','validate','action']);
 const bad=flow('offer',{readBalance:async()=>({storage_available:'0'})});await assert.rejects(bad.run(),/not confirmed/);assert.ok(!bad.calls.includes('action'));
});
const wallet={wallet_status:'Funded',cycle:202612,original:'1200000000000000000000000',remaining:'1200000000000000000000000',exited:false,collected:false,transfer_pending:false};
test('only the current NFT owner can exit before UTC month cutoff; exact 40/60 split',()=>{
 const state=withdrawalState(wallet,'alice.testnet','alice.testnet',Date.UTC(2026,11,31,23,59,59));
 assert.equal(state.eligible,true);assert.equal(state.amount,'480000000000000000000000');assert.equal(state.rollover,'720000000000000000000000');
 assert.equal(withdrawalState(wallet,'alice.testnet','bob.testnet',0).eligible,false);
 assert.equal(withdrawalState(wallet,'alice.testnet','alice.testnet',Date.UTC(2027,0,1)).eligible,false);
 for(const override of [{exited:true},{collected:true},{transfer_pending:true},{cycle:null},{wallet_status:'Funding'}])assert.equal(withdrawalState({...wallet,...override},'alice.testnet','alice.testnet',0).eligible,false);
});
