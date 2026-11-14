import test from 'node:test';
import assert from 'node:assert/strict';
import {auctionArtworkId,royaltyFee,units} from '../lib/marketplace.ts';
test('secondary royalty and seller proceeds conserve every yocto without floating point',()=>{
 for(const value of [1n,19n,20n,100n,123456789012345678901234567n]){
  const fee=royaltyFee(String(value));assert.equal(fee,value/20n);assert.equal((value-fee)+fee,value);
 }
 assert.equal(units('1234567890123456789012345',24),'1.234567890123456789012345');
 assert.equal(units('1000000',6),'1');assert.equal(units('42',0),'42');
 assert.throws(()=>units('1.2',24));
});
test('primary auction links use the recorded test fixture or production epoch',()=>{
 const t={token_id:'ECHO-000007',metadata:{extra:JSON.stringify({testnet_rehearsal:{source_artwork:'demo-000007'}})}};
 assert.equal(auctionArtworkId(t,'testnet_rehearsal'),'demo-000007');
 assert.equal(auctionArtworkId(t,'live'),'live-000007');
 assert.equal(auctionArtworkId({...t,metadata:{extra:'{"testnet_rehearsal":{"source_artwork":"../../invalid"}}'}},'testnet_rehearsal'),'demo-000007');
 assert.equal(auctionArtworkId({...t,token_id:'other'},'live'),null);
});
