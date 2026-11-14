import test from 'node:test';
import assert from 'node:assert/strict';
import {walletTransactionsEnabled} from '../lib/api.ts';
test('testnet rehearsal enables only testnet wallet actions and leaves saved demos read-only',()=>{
 assert.equal(walletTransactionsEnabled({mode:'testnet_rehearsal',network:'testnet',lab_ready:true}),true);
 assert.equal(walletTransactionsEnabled({mode:'testnet_rehearsal',network:'testnet',lab_ready:false}),false);
 assert.equal(walletTransactionsEnabled({mode:'testnet_rehearsal',network:'testnet'}),false);
 assert.equal(walletTransactionsEnabled({mode:'testnet_rehearsal',network:'mainnet'}),false);
 assert.equal(walletTransactionsEnabled({mode:'historical_replay',network:'testnet'}),false);
 assert.equal(walletTransactionsEnabled({mode:'demo',network:'testnet'}),false);
 assert.equal(walletTransactionsEnabled({mode:'live',network:'testnet'}),true);
 assert.equal(walletTransactionsEnabled(undefined),false);
});
