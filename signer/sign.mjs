import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";
import { KeyPair } from "@near-js/crypto";
import { actionCreators, createTransaction, SignedTransaction, Signature } from "@near-js/transactions";
import { base58 } from "@scure/base";

export async function execute(request,env=process.env){
  const credential=JSON.parse(await readFile(request.key_file,"utf8"));
  if(credential.account_id!==request.account_id)throw new Error("Signer account mismatch");
  const key=KeyPair.fromString(credential.private_key);
  if(key.getPublicKey().keyType!==0)throw new Error("Only Ed25519 signing keys are accepted");
  if(request.op==="public_key")return {public_key:key.getPublicKey().toString()};
  if(env.ENABLE_CHAIN_WRITES!=="true")throw new Error("Chain writes are disabled");
  if(env.NEAR_NETWORK==="mainnet"&&env.MAINNET_WRITES_APPROVED!=="true")throw new Error("Mainnet signing not approved");
  const allowed=request.receiver_id===env.NEAR_NFT_CONTRACT?["mint_weekly_artwork"]:
    request.receiver_id===env.NEAR_AUCTION_CONTRACT?["create_auction","finalize_auction","retry_custody","reconcile_settlement"]:[];
  if(!allowed.includes(request.method))throw new Error("Signing request outside contract/method allowlist");
  const deposit=BigInt(request.deposit),gas=BigInt(request.gas);
  if(deposit<0n||deposit>100000000000000000000000n||gas<1n||gas>200000000000000n)throw new Error("Signing limits exceeded");
  const transaction=createTransaction(request.account_id,key.getPublicKey(),request.receiver_id,BigInt(request.nonce),
    [actionCreators.functionCall(request.method,request.args,gas,deposit)],base58.decode(request.block_hash));
  const hash=createHash("sha256").update(transaction.encode()).digest();
  const signed=new SignedTransaction({transaction,signature:new Signature({keyType:key.getPublicKey().keyType,data:key.sign(hash).signature})});
  return {signed_transaction:Buffer.from(signed.encode()).toString("base64"),transaction_hash:base58.encode(hash)};
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  try{
    let input="";for await(const chunk of process.stdin){input+=chunk;if(input.length>131072)throw new Error("Request too large");}
    process.stdout.write(JSON.stringify(await execute(JSON.parse(input))));
  }catch{process.stderr.write("Signing failed; check account, policy and mounted secret file.\n");process.exitCode=1;}
}
