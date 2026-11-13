import test from 'node:test';
import assert from 'node:assert/strict';
import {createHmac} from 'node:crypto';
import {verifyFamilySelection} from '../lib/family-selection.ts';
const seed='01'.repeat(32);
const proof={policy:'seed-rejection-six-v1',family:'flow_field',index:3,counter:0,digest:'8e4824dbd6908f216c056899dcf46616ee5c0424ebafd37b37b1a824db0544d9'};
test('browser-compatible WebCrypto verifies the Python family vector',async()=>{
  assert.equal(await verifyFamilySelection(seed,'flow_field',proof),true);
  assert.equal(await verifyFamilySelection(seed,'crystalline',proof),false);
  assert.equal(await verifyFamilySelection(seed,'flow_field',{...proof,index:2}),false);
  assert.equal(await verifyFamilySelection(seed,'flow_field',{...proof,digest:'00'.repeat(32)}),false);
});
test('a later HMAC counter cannot reroll an already accepted draw',async()=>{
  const counter=Buffer.alloc(8);counter.writeBigUInt64BE(1n);
  const digest=createHmac('sha256',Buffer.from(seed,'hex')).update(Buffer.concat([Buffer.from('NEAR_ECHOES_FAMILY_V1'),counter])).digest('hex');
  assert.equal(await verifyFamilySelection(seed,'flow_field',{...proof,counter:1,digest}),false);
});
