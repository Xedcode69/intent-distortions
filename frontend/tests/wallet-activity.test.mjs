import test from 'node:test';
import assert from 'node:assert/strict';
import {duringWalletApproval,subscribeWalletActivity,walletApprovalPending,walletFailure} from '../lib/wallet-activity.ts';

test('wallet approval pauses polling until the last overlapping prompt completes',async()=>{
 const states=[],stop=subscribeWalletActivity(()=>states.push(walletApprovalPending()));let release1,release2;
 const first=duringWalletApproval(()=>new Promise(resolve=>{release1=resolve;}));
 const second=duringWalletApproval(()=>new Promise(resolve=>{release2=resolve;}));
 assert.equal(walletApprovalPending(),true);release1('one');await first;assert.equal(walletApprovalPending(),true);
 release2('two');await second;assert.equal(walletApprovalPending(),false);stop();
 assert.deepEqual(states,[true,true,true,false]);
});
test('failed approval restores polling without automatically repeating a payment',async()=>{
 let submits=0;
 await assert.rejects(duringWalletApproval(async()=>{submits++;throw new Error('RPC -429');}),/-429/);
 assert.equal(submits,1);assert.equal(walletApprovalPending(),false);
});
test('rate-limit error is readable and does not leak provider URLs or tokens',()=>{
 for(const error of [new Error('{"code":-429,"message":"Rate limits exceeded https://private-rpc.example?apiKey=secret"}'),{code:-429,message:'limit'},'429 Too Many Requests']){
  const message=walletFailure(error).message;assert.match(message,/rate limited/);assert.match(message,/No automatic payment retry/);assert.doesNotMatch(message,/private-rpc|apiKey|secret/);
 }
 const cancellation=new Error('User rejected');assert.equal(walletFailure(cancellation),cancellation);
});
