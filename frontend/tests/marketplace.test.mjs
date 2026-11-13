import test from 'node:test';
import assert from 'node:assert/strict';
import {royaltyFee,units} from '../lib/marketplace.ts';
test('secondary royalty and seller proceeds conserve every yocto without floating point',()=>{
 for(const value of [1n,19n,20n,100n,123456789012345678901234567n]){
  const fee=royaltyFee(String(value));assert.equal(fee,value/20n);assert.equal((value-fee)+fee,value);
 }
 assert.equal(units('1234567890123456789012345',24),'1.234567890123456789012345');
 assert.equal(units('1000000',6),'1');assert.equal(units('42',0),'42');
 assert.throws(()=>units('1.2',24));
});
