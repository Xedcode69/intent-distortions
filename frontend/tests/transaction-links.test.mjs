import test from 'node:test';
import assert from 'node:assert/strict';
import {transactionUrl,transactionLabel,assertTransactionConfirmed} from '../lib/transactions.ts';
const hash='FYULV4rD2eWqQBHBT1VsU8rouMaW6VoqPWAAt7Bvatu1';
test('confirmation URLs target the correct network and reject injected references',()=>{
 assert.equal(transactionUrl(hash,'testnet'),`https://testnet.nearblocks.io/txns/${hash}`);
 assert.equal(transactionUrl(hash,'mainnet'),`https://nearblocks.io/txns/${hash}`);
 for(const invalid of ['javascript:alert(1)','../../account','<script>','x'.repeat(100)])assert.throws(()=>transactionUrl(invalid,'testnet'));
 assert.throws(()=>transactionUrl(hash,'unknown'));
 assert.equal(transactionLabel('storage_deposit'),'Storage setup');assert.equal(transactionLabel('place_bid'),'Bid');
});
test('a known failed receipt retains its explorer URL and an ambiguous result is never confirmed',()=>{
 assert.doesNotThrow(()=>assertTransactionConfirmed({status:{SuccessValue:''},transaction:{hash}},'testnet'));
 assert.throws(()=>assertTransactionConfirmed({status:{Failure:{}},transaction:{hash}},'testnet'),new RegExp(`https://testnet.nearblocks.io/txns/${hash}`));
 assert.throws(()=>assertTransactionConfirmed({status:null},'testnet'),/not confirmed/);
 assert.throws(()=>assertTransactionConfirmed({status:{}},'testnet'),/not confirmed/);
});
