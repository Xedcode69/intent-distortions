import test from "node:test";
import assert from "node:assert/strict";
import {readFile,writeFile} from "node:fs/promises";
import {fileURLToPath} from "node:url";
import {Worker} from "near-workspaces";
import {SandboxServer} from "near-workspaces/dist/server/server.js";

// Calendar tests advance weeks/months. A long LOCAL validator epoch avoids
// generating thousands of staking snapshots while preserving real timestamps,
// receipt execution, gas charging and the unmodified production WASM.
const originalStart=SandboxServer.prototype.start;
SandboxServer.prototype.start=async function(){
 const path=`${this.homeDir}/genesis.json`,genesis=JSON.parse(await readFile(path,"utf8"));
 genesis.epoch_length=1_000_000_000;
 await writeFile(path,JSON.stringify(genesis));
 return originalStart.call(this);
};

const N=10n**24n, GAS=200n*10n**12n, FIRST=1794700800n*10n**9n, WEEK=604800n*10n**9n;
const wasm=new URL("../target/wasm32-unknown-unknown/release/",import.meta.url);
const opts=(attachedDeposit=0n)=>({gas:GAS,attachedDeposit});
const nextMonth=c=>c%100===12?(Math.floor(c/100)+1)*100+1:c+1;
const cutoff=c=>BigInt(Date.UTC(Math.floor(nextMonth(c)/100),nextMonth(c)%100-1,1))*10n**6n;
async function clock(w){return BigInt((await w.provider.block({finality:"final"})).header.timestamp_nanosec);}
async function advance(w,target){
 for(let i=0;i<5;i++){
  const before=(await w.provider.block({finality:"final"})).header;
  const now=BigInt(before.timestamp_nanosec);if(now>=target)return;
  const delta=Number((target-now)/10n**9n)+10;
  await w.provider.fastForward(delta);
  // The RPC acknowledges scheduling before final block views catch up. Do not
  // enqueue the same time jump again while still observing the old final head.
  let applied=false;
  for(let poll=0;poll<200;poll++){
   const after=(await w.provider.block({finality:"final"})).header;
   if(after.height>=before.height+delta){applied=true;break;}
   await new Promise(resolve=>setTimeout(resolve,100));
  }
  assert.ok(applied,"Scheduled sandbox time jump did not finalize");
 }
 assert.ok(await clock(w)>=target,"Sandbox clock did not reach target");
}

test("real WASM receipts: keyless accounts, refunds, vault exit, rollover and verified prize",{timeout:900000},async()=>{
 console.log("Starting isolated NEAR sandbox");
 const worker=await Worker.init();
 console.log("Sandbox RPC ready");
 try{
  const root=worker.rootAccount;
  const nft=await root.createSubAccount("nft",{initialBalance:1000n*N});
  const auction=await root.createSubAccount("auction",{initialBalance:100n*N});
  const market=await root.createSubAccount("market",{initialBalance:100n*N});
  const operator=await root.createSubAccount("operator",{initialBalance:100n*N});
  const team=await root.createSubAccount("team",{initialBalance:10n*N});
  const treasury=await root.createSubAccount("treasury",{initialBalance:10n*N});
  const alice=await root.createSubAccount("alice",{initialBalance:1000n*N});
  const bob=await root.createSubAccount("bob",{initialBalance:1000n*N});
  console.log("Created test accounts");
  await nft.deploy(fileURLToPath(new URL("echo_nft.wasm",wasm)));
  await auction.deploy(fileURLToPath(new URL("echo_auction.wasm",wasm)));
  await market.deploy(fileURLToPath(new URL("echo_market.wasm",wasm)));
  await nft.call(nft,"new_economy",{owner_id:root.accountId,minter:operator.accountId,auction_contract:auction.accountId,creator:team.accountId,treasury:treasury.accountId},opts());
  await auction.call(auction,"new_economy",{owner:operator.accountId,nft_contract:nft.accountId,creator:team.accountId,treasury:treasury.accountId,min_bid:String(N),increment:String(N/10n)},opts());
  await market.call(market,"new",{nft_contract:nft.accountId,primary_auction:auction.accountId,creator:team.accountId},opts());
  console.log("Initialized production WASM contracts");
  await advance(worker,FIRST+6n*WEEK);
  console.log("Advanced sandbox clock to edition schedule");
  const all=[];
  for(let i=0;i<7;i++){
   const release=FIRST+BigInt(i)*WEEK,epoch=i+1,bytes=Buffer.alloc(32,epoch),hash=bytes.toString("hex");
   const metadata={title:`Echo ${epoch}`,media:"https://example.com/image",media_hash:bytes.toString("base64"),copies:1,reference:"https://example.com/proof",reference_hash:bytes.toString("base64"),
    extra:JSON.stringify({trait_schema:"echo-nft-traits-v1",attributes:[{trait_type:"Material",value:"glass"},...Array.from({length:32},(_,n)=>({trait_type:`Test scene control ${n}`,value:n/32}))],traits_reference:{uri:"https://example.com/traits",sha256:"03".repeat(32)}})};
   await operator.call(nft,"mint_scheduled_artwork",{release_ns:String(release),metadata,commitment:{epoch,image_hash:hash,provenance_hash:hash,merkle_root:hash,seed:hash,block_hash:"sandbox-block"}},opts(N/10n));
   const token=await nft.view("get_epoch_token",{epoch});all.push(token);
   const extra=JSON.parse((await nft.view("nft_token",{token_id:token})).metadata.extra);
   assert.equal(extra.attributes.find(a=>a.trait_type==="Material").value,"glass");
   assert.equal(extra.attributes.find(a=>a.trait_type==="Monthly edition").value,i<3?i+1:i-2);
   assert.equal(extra.attributes.find(a=>a.trait_type==="Edition month").value,i<3?"November":"December");
   assert.equal(extra.traits_reference.sha256,"03".repeat(32));
   await root.call(nft,"create_edition_wallet",{token_id:token},opts());
   const d=await nft.view("get_edition_wallet",{token_id:token});assert.equal(d.wallet_status,"Ready");
   assert.equal(d.account_id,`${i<3?`november2026-edition-${i+1}`:`december2026-edition-${i-2}`}.${nft.accountId}`);
   assert.equal((await worker.provider.query({request_type:"view_access_key_list",account_id:d.account_id,finality:"final"})).keys.length,0);
   if(i<3)assert.equal((await nft.view("nft_token",{token_id:token})).owner_id,team.accountId);
  }
  const sold=all.slice(3,6),unsold=all[6];
  console.log("Verified seven dedicated accounts and creator mints");
  for(const who of [alice,bob])await who.call(auction,"register_bidder",{},opts(N/100n));
  let end=0n;
  for(const token of sold){
   await operator.call(auction,"create_auction",{token_id:token},opts(N/20n));
   const a=await auction.view("get_auction",{token_id:token});assert.equal(a.status,"Active");end=BigInt(a.end_ns)>end?BigInt(a.end_ns):end;
   await alice.call(auction,"place_bid",{token_id:token},opts(100n*N));
   await bob.call(auction,"place_bid",{token_id:token},opts(110n*N));
   assert.equal(await auction.view("get_refund",{account:alice.accountId}),"0","Losing bid should refund automatically");
   assert.equal((await auction.view("get_auction",{token_id:token})).end_ns,a.end_ns,"No rolling extension");
  }
  await operator.call(auction,"create_auction",{token_id:unsold},opts(N/20n));
  const noBid=await auction.view("get_auction",{token_id:unsold});end=BigInt(noBid.end_ns)>end?BigInt(noBid.end_ns):end;
  await advance(worker,end+1n);
  console.log("Verified bids/refunds; auction deadlines passed");
  for(const token of sold){
   await root.call(auction,"finalize_auction",{token_id:token},opts());
   assert.equal((await auction.view("get_auction",{token_id:token})).status,"Settled");
   await root.call(nft,"fund_edition_wallet",{token_id:token},opts());
   const d=await nft.view("get_edition_wallet",{token_id:token});assert.equal(d.wallet_status,"Funded");assert.equal(d.original,String(88n*N));
  }
  await root.call(auction,"finalize_auction",{token_id:unsold},opts());
  assert.equal((await auction.view("get_auction",{token_id:unsold})).status,"Unsold");
  assert.equal((await nft.view("nft_token",{token_id:unsold})).owner_id,team.accountId);
  assert.equal((await nft.view("get_edition_wallet",{token_id:unsold})).cycle,null);
  // A receiver without nft_on_transfer rejects the call. The real resolver
  // must restore ownership and clear economic pending state within its gas.
  await bob.call(nft,"nft_transfer_call",{receiver_id:team.accountId,token_id:sold[0],approval_id:null,memo:null,msg:""},opts(1n));
  assert.equal((await nft.view("nft_token",{token_id:sold[0]})).owner_id,bob.accountId);
  assert.equal((await nft.view("get_edition_wallet",{token_id:sold[0]})).transfer_pending,false);
  // Secondary buyer inherits the unused right, and cannot use it twice.
  for(const who of [alice,bob,team])await who.call(market,"storage_deposit",{},opts(N/10n));
  const marketExpiry=()=>String(clockValue+7n*86400n*10n**9n);
  let clockValue=await clock(worker);
  await bob.call(nft,"nft_approve",{token_id:sold[0],account_id:market.accountId,msg:JSON.stringify({price:String(10n*N),expires_ns:marketExpiry()})},opts(N/100n));
  let listing=await market.view("get_listing",{token_id:sold[0]});
  let snapshot=await nft.view("get_market_snapshot",{token_id:sold[0]});
  await alice.call(market,"buy",{token_id:sold[0],nonce:listing.nonce,rights_hash:snapshot.rights_hash},opts(10n*N+1n));
  assert.equal((await nft.view("nft_token",{token_id:sold[0]})).owner_id,alice.accountId);
  assert.equal((await market.view("get_balance",{account:bob.accountId})).credit,String(95n*N/10n));
  assert.equal((await nft.view("get_edition_wallet",{token_id:sold[0]})).beneficiary,alice.accountId);
  await bob.call(market,"withdraw_credit",{},opts(1n));assert.equal((await market.view("get_balance",{account:bob.accountId})).credit,"0");
  // Offer-only sale, including a creator-owned, unfunded edition.
  await team.call(nft,"nft_approve",{token_id:unsold,account_id:market.accountId,msg:JSON.stringify({price:null,expires_ns:marketExpiry()})},opts(N/100n));
  listing=await market.view("get_listing",{token_id:unsold});snapshot=await nft.view("get_market_snapshot",{token_id:unsold});
  await alice.call(market,"make_offer",{token_id:unsold,nonce:listing.nonce,amount:String(4n*N),expires_ns:marketExpiry(),rights_hash:snapshot.rights_hash},opts(4n*N+1n));
  const offers=await market.view("get_offers",{});assert.equal(offers.length,1);
  await team.call(market,"accept_offer",{id:offers[0].id},opts(1n));assert.equal((await nft.view("nft_token",{token_id:unsold})).owner_id,alice.accountId);
  assert.equal((await market.view("get_balance",{account:team.accountId})).credit,String(38n*N/10n));
  // An old listing with a revoked approval must refund the entire payment.
  await team.call(nft,"nft_approve",{token_id:all[0],account_id:market.accountId,msg:JSON.stringify({price:String(9n*N),expires_ns:marketExpiry()})},opts(N/100n));
  listing=await market.view("get_listing",{token_id:all[0]});snapshot=await nft.view("get_market_snapshot",{token_id:all[0]});
  await team.call(nft,"nft_revoke",{token_id:all[0],account_id:market.accountId},opts(1n));
  await alice.call(market,"buy",{token_id:all[0],nonce:listing.nonce,rights_hash:snapshot.rights_hash},opts(9n*N+1n));
  assert.equal((await market.view("get_balance",{account:alice.accountId})).credit,String(9n*N));
  await alice.call(market,"withdraw_credit",{},opts(1n));assert.equal((await market.view("get_balance",{account:alice.accountId})).credit,"0");
  const royaltyDate=new Date(Number((await clock(worker))/1_000_000n));const royaltyCycle=royaltyDate.getUTCFullYear()*100+royaltyDate.getUTCMonth()+1;
  assert.equal((await market.view("get_royalty_month",{cycle:royaltyCycle})).pot,String(7n*N/10n));
  console.log("Verified noncustodial fixed-price sale, offer acceptance, 95/5 split and revoked-approval refund");
  await alice.call(nft,"withdraw_edition",{token_id:sold[0]},opts(1n));
  await assert.rejects(alice.call(nft,"withdraw_edition",{token_id:sold[0]},opts(1n)));
  const exited=await nft.view("get_edition_wallet",{token_id:sold[0]});
  assert.equal(exited.remaining,String(528n*N/10n));
  const cycle=exited.cycle;await advance(worker,cutoff(cycle)+120n*10n**9n);
  if(await clock(worker)<cutoff(royaltyCycle))await advance(worker,cutoff(royaltyCycle)+120n*10n**9n);
  // Transferring after cutoff cannot redirect already-earned royalties.
  await alice.call(nft,"nft_transfer",{receiver_id:team.accountId,token_id:unsold,approval_id:null,memo:null},opts(1n));
  for(let count=0;count<24;count++){
   const config=await market.view("get_config",{});if(config.next_royalty_close>royaltyCycle)break;
   await root.call(market,"prepare_royalties",{cycle:config.next_royalty_close},opts());
  }
  const royalty=await market.view("get_royalty_month",{cycle:royaltyCycle});assert.ok(royalty.ready);assert.equal(royalty.eligible,4);assert.equal(royalty.share,String(175n*N/1000n));
  const shares=await market.view("get_royalty_shares",{cycle:royaltyCycle,offset:"0",limit:25});
  assert.equal(shares.filter(s=>s.owner_id===alice.accountId).length,2);assert.equal(shares.filter(s=>s.owner_id===team.accountId).length,0);
  for(const share of shares)await root.call(market,"pay_royalty",{cycle:royaltyCycle,index:String(share.index)},opts(1n));
  const royaltyPaid=await market.view("get_royalty_month",{cycle:royaltyCycle});assert.equal(royaltyPaid.pot,"0");assert.equal(royaltyPaid.paid,4);
  console.log("Verified full-collection month-end royalties, creator exclusion and immutable prior-owner payments");
  for(let c=202612;c<cycle;c=nextMonth(c)){
   await root.call(nft,"close_month",{cycle:c},opts());await root.call(nft,"draw_month",{cycle:c,signature:"",previous_signature:""},opts());
  }
  await root.call(nft,"close_month",{cycle},opts());
  for(const token of sold)await root.call(nft,"collect_edition",{token_id:token},opts());
  let m=await nft.view("get_month",{cycle});assert.equal(m.entries.length,2);assert.equal(m.pot,String(176n*N));assert.equal(m.pending_sources,0);
  const following=await nft.view("get_month",{cycle:nextMonth(cycle)});assert.equal(following.pot,String(528n*N/10n));
  await assert.rejects(root.call(nft,"draw_month",{cycle,signature:"00".repeat(96),previous_signature:"00".repeat(96)},opts()));
  // Sandbox-only state intervention lets a captured historical proof exercise
  // the actual BLS host calls and payout receipts. No such setter exists in WASM.
  const beacon=JSON.parse(await readFile(new URL("../../fixtures/sample-epoch/verified-beacon.json",import.meta.url),"utf8"));
  const state=await nft.viewStateRaw("");
  const entry=state.find(x=>{
   const key=Buffer.from(x.key,"base64"),value=Buffer.from(x.value,"base64");
   return key.subarray(0,8).toString()==="econ_mov"&&value.length>=20&&value.readUInt32LE(0)===cycle;
  });assert.ok(entry,"Locate the sandbox month's Borsh value");
  const value=Buffer.from(entry.value,"base64");value.writeBigUInt64LE(BigInt(beacon.round),12);
  await nft.updateData(Buffer.from(entry.key,"base64"),value);
  // Both eligible tickets belong to Bob. Delete only this sandbox account to
  // exercise a real failed native transfer and its fixed-beneficiary retry.
  await bob.delete(root.accountId);
  await root.call(nft,"draw_month",{cycle,signature:beacon.signature,previous_signature:beacon.previous_signature},opts());
  m=await nft.view("get_month",{cycle});assert.equal(m.status,"Drawn");assert.equal(m.payout.status,"Retryable");assert.equal(m.prize,String(176n*N));
  assert.equal(m.payout.beneficiary,bob.accountId);
  await root.createSubAccount("bob",{initialBalance:10n*N});
  await root.call(nft,"pay_month",{cycle},opts());
  m=await nft.view("get_month",{cycle});assert.equal(m.payout.status,"Paid");
  assert.equal(m.randomness,beacon.randomness);assert.ok(sold.slice(1).includes(m.winner.token_id));
  await assert.rejects(root.call(nft,"draw_month",{cycle,signature:beacon.signature,previous_signature:beacon.previous_signature},opts()));
  await root.call(nft,"process_treasury",{},opts());const economy=await nft.view("get_economy",{});
  assert.equal(economy.treasury_earned,String(66n*N));assert.equal(economy.treasury_credit,"0");assert.equal(economy.hub_liability,String(528n*N/10n));
  console.log(JSON.stringify({schema:"echo-economy-sandbox-v1",currency:"sandbox NEAR",gross:"330",treasury:"66",early_withdrawal:"35.2",prize:"176",rollover:"52.8",eligible_tickets:2,secondary_gross:"14",royalties:"0.7",royalty_shares:4,secondary_refund_verified:true,drand_host_proof_verified:true,failed_prize_retry_verified:true,no_bid_creator_delivery_verified:true,real_network_deployment:false}));
 }finally{await worker.tearDown();}
});
