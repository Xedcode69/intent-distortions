import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {verifyTraitDocument} from '../lib/nft-traits.ts';
test('trait document hash and displayed attributes must agree',async()=>{
 const document={schema:'echo-nft-traits-v1',name:'Echo',description:'Frozen',attributes:[{trait_type:'Material',value:'glass'}],source:{image_sha256:'01',provenance_sha256:'02',manifest_sha256:'03',seed:'04',merkle_root:'05'}};
 const bytes=new TextEncoder().encode(JSON.stringify(document)).buffer;
 const bundle={...document,sha256:createHash('sha256').update(new Uint8Array(bytes)).digest('hex')};
 assert.equal(await verifyTraitDocument(bundle,bytes),true);
 assert.equal(await verifyTraitDocument({...bundle,attributes:[{trait_type:'Material',value:'ink'}]},bytes),false);
 assert.equal(await verifyTraitDocument(bundle,new TextEncoder().encode('{}').buffer),false);
});
