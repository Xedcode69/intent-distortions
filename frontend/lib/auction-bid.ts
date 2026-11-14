export type BidderStatus={account_id:string;contract:string;registered:boolean;refund_yocto:string};
export type AuctionBidState={status:string;custody_verified:boolean;end_ns:string;highest_bid:string;min_bid:string;increment:string};

function assertBidConditions(bidder:BidderStatus,account:string,contract:string,auction:AuctionBidState,amount:string,now:number,requireRegistration:boolean){
 if(bidder.account_id!==account||bidder.contract!==contract)throw new Error("Wallet or auction changed. Review the bid again.");
 if(typeof bidder.registered!=="boolean")throw new Error("Bidder registration could not be verified.");
 if(requireRegistration&&!bidder.registered)throw new Error("Bidder registration was not confirmed. Check your wallet before retrying.");
 if(auction.status!=="Active"||!auction.custody_verified)throw new Error("This auction is not open for bids.");
 if(BigInt(auction.end_ns)<=BigInt(Math.floor(now))*1000000n)throw new Error("This auction has ended.");
 const highest=BigInt(auction.highest_bid),minimum=highest>0n?highest+BigInt(auction.increment):BigInt(auction.min_bid);
 if(!/^\d+$/.test(amount)||BigInt(amount)<minimum)throw new Error("Your bid is below the current minimum. Review the updated bid.");
}

export function assertBidReady(bidder:BidderStatus,account:string,contract:string,auction:AuctionBidState,amount:string,now:number){
 assertBidConditions(bidder,account,contract,auction,amount,now,true);
}

export async function submitAuctionBid<T>(input:{account:string;contract:string;tokenId:string;amount:string},io:{
 currentAccount:()=>Promise<string>;readBidder:()=>Promise<BidderStatus>;readAuction:()=>Promise<AuctionBidState>;now:()=>number;
 submit:(method:"register_bidder"|"place_bid",args:Record<string,unknown>,deposit:string)=>Promise<T>;
 progress?:(phase:"registration"|"bid")=>void;
}){
 const checkAccount=async()=>{if(await io.currentAccount()!==input.account)throw new Error("Wallet account changed. Review the bid again.");};
 await checkAccount();
 let bidder=await io.readBidder(),auction=await io.readAuction();
 assertBidConditions(bidder,input.account,input.contract,auction,input.amount,io.now(),false);
 if(!bidder.registered){
  await checkAccount();io.progress?.("registration");
  await io.submit("register_bidder",{},"10000000000000000000000");
  await checkAccount();
  bidder=await io.readBidder();auction=await io.readAuction();
 }
 // Recheck the exact amount and current auction after registration. Never
 // increase the user's bid or request a bid after a failed/cancelled first step.
 assertBidReady(bidder,input.account,input.contract,auction,input.amount,io.now());
 await checkAccount();io.progress?.("bid");
 return io.submit("place_bid",{token_id:input.tokenId},input.amount);
}
