import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp,writeFile,rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { KeyPair } from "@near-js/crypto";
import { SignedTransaction,encodeTransaction } from "@near-js/transactions";
import { base58 } from "@scure/base";
import { execute } from "./sign.mjs";

test("SDK-encoded transaction verifies against the signing key and enforces scope",async()=>{
  const directory=await mkdtemp(join(tmpdir(),"echoes-signer-test-"));
  try {
    const key=KeyPair.fromRandom("ed25519"),file=join(directory,"credential.json");
    await writeFile(file,JSON.stringify({account_id:"worker.testnet",private_key:key.toString()}));
    const request={key_file:file,account_id:"worker.testnet",op:"sign",receiver_id:"nft.testnet",method:"mint_weekly_artwork",
      args:{epoch:1},gas:"200000000000000",deposit:"0",nonce:"12",block_hash:base58.encode(new Uint8Array(32).fill(1))};
    const env={ENABLE_CHAIN_WRITES:"true",NEAR_NETWORK:"testnet",NEAR_NFT_CONTRACT:"nft.testnet",NEAR_AUCTION_CONTRACT:"auction.testnet"};
    const result=await execute(request,env);
    const signed=SignedTransaction.decode(Buffer.from(result.signed_transaction,"base64"));
    const hash=createHash("sha256").update(encodeTransaction(signed.transaction)).digest();
    assert.equal(base58.encode(hash),result.transaction_hash);
    assert.equal(key.verify(hash,Uint8Array.from(signed.signature.ed25519Signature.data)),true);
    assert.equal(signed.transaction.receiverId,"nft.testnet");
    await assert.rejects(execute({...request,receiver_id:"attacker.testnet"},env),/allowlist/);
    await assert.rejects(execute({...request,method:"delete_account"},env),/allowlist/);
    await assert.rejects(execute({...request,deposit:"100000000000000000000001"},env),/limits/);
    await assert.rejects(execute(request,{...env,ENABLE_CHAIN_WRITES:"false"}),/disabled/);
    await assert.rejects(execute(request,{...env,NEAR_NETWORK:"mainnet"}),/not approved/);
    await assert.rejects(execute({...request,account_id:"other.testnet"},env),/mismatch/);
  } finally {await rm(directory,{recursive:true,force:true});}
});
