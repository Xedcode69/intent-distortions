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
    const request={key_file:file,account_id:"worker.testnet",op:"sign",receiver_id:"nft.testnet",method:"mint_onchain_art",
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
    await assert.rejects(execute({...request,method:"withdraw_edition"},env),/allowlist/);
    await assert.rejects(execute({...request,method:"fund_edition_wallet",deposit:"1"},env),/zero deposit/);
    const maintenance=await execute({...request,method:"close_month",args:{cycle:202612}},env);
    assert.ok(maintenance.transaction_hash);
    const marketEnv={...env,NEAR_MARKET_CONTRACT:"market.testnet"};
    const payment={...request,receiver_id:"market.testnet",method:"pay_royalty",args:{cycle:202612,index:"0"},deposit:"1"};
    assert.ok((await execute(payment,marketEnv)).transaction_hash);
    await assert.rejects(execute({...payment,deposit:"0"},marketEnv),/one yocto/);
    await assert.rejects(execute({...payment,method:"buy"},marketEnv),/allowlist/);
    await assert.rejects(execute({...payment,method:"withdraw_credit"},marketEnv),/allowlist/);
    await assert.rejects(execute({...request,deposit:"1000000000000000000000001"},env),/limits/);
    assert.ok((await execute({...request,method:"mint_onchain_art",deposit:"1000000000000000000000000"},env)).transaction_hash);
    await assert.rejects(execute({...request,method:"mint_onchain_art",deposit:"1000000000000000000000001"},env),/limits/);
    await assert.rejects(execute({...request,receiver_id:"auction.testnet",method:"create_auction",deposit:"1000000000000000000000000"},env),/limits/);
    await assert.rejects(execute(request,{...env,ENABLE_CHAIN_WRITES:"false"}),/disabled/);
    await assert.rejects(execute(request,{...env,NEAR_NETWORK:"mainnet"}),/Testnet signing only/);
    await assert.rejects(execute({...request,account_id:"other.testnet"},env),/mismatch/);
  } finally {await rm(directory,{recursive:true,force:true});}
});
