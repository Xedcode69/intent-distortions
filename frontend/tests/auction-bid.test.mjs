import test from 'node:test';
import assert from 'node:assert/strict';
import {submitAuctionBid} from '../lib/auction-bid.ts';

const N=10n**24n;
function fixture(options={}){
 const input={account:'bidder.testnet',contract:'auction.testnet',tokenId:'ECHO-000004',amount:String(N)};
 let registered=!!options.registered,account=input.account,reads=0;
 const calls=[];
 const io={
  currentAccount:async()=>account,
  readBidder:async()=>({account_id:input.account,contract:input.contract,registered,refund_yocto:'0'}),
  readAuction:async()=>({status:'Active',custody_verified:true,end_ns:String(2000n*1000000n),highest_bid:options.outbid&&reads++>0?String(N):'0',min_bid:String(N),increment:String(N/10n)}),
  now:()=>options.expired?3000:1000,
  submit:async(method,args,deposit)=>{
   calls.push({method,args,deposit});
   if(method==='register_bidder'){
    if(options.cancel)throw new Error('User cancelled registration');
    registered=!options.unconfirmed;
    if(options.switchAccount)account='other.testnet';
   }
   return {method};
  },
 };
 return {input,io,calls};
}

test('first Place bid registers once, confirms state, then requests the exact bid',async()=>{
 const f=fixture();const result=await submitAuctionBid(f.input,f.io);
 assert.equal(result.method,'place_bid');
 assert.deepEqual(f.calls,[{method:'register_bidder',args:{},deposit:String(N/100n)},{method:'place_bid',args:{token_id:'ECHO-000004'},deposit:String(N)}]);
 await submitAuctionBid(f.input,f.io);
 assert.deepEqual(f.calls.map(c=>c.method),['register_bidder','place_bid','place_bid']);
});

test('already registered bidder receives one approval',async()=>{
 const f=fixture({registered:true});await submitAuctionBid(f.input,f.io);
 assert.deepEqual(f.calls.map(c=>c.method),['place_bid']);
});

for(const [option,message] of [['cancel',/cancelled/],['unconfirmed',/not confirmed/],['switchAccount',/account changed/],['outbid',/current minimum/]]){
 test(`${option} stops before requesting the bid`,async()=>{
  const f=fixture({[option]:true});
  await assert.rejects(submitAuctionBid(f.input,f.io),message);
  assert.deepEqual(f.calls.map(c=>c.method),['register_bidder']);
 });
}

test('invalid or expired bids request neither registration nor a bid',async()=>{
 const f=fixture({expired:true});await assert.rejects(submitAuctionBid(f.input,f.io),/ended/);assert.deepEqual(f.calls,[]);
 const low=fixture();low.input.amount='1';await assert.rejects(submitAuctionBid(low.input,low.io),/minimum/);assert.deepEqual(low.calls,[]);
});
