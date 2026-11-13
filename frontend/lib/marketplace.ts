export type MarketListing={token_id:string;seller:string;approval_id:number;nonce:string;price:string|null;expires_ns:string;sale:{id:string;buyer:string;amount:string}|null};
export type MarketOffer={id:string;token_id:string;seller:string;buyer:string;listing_nonce:string;amount:string;expires_ns:string;rights_hash:string};
export type MarketConfig={status:string;contract:string;fee_bps:number;crosschain:boolean;next_royalty_close?:number};
export type MarketToken={token_id:string;owner_id:string;approved_account_ids:Record<string,number>;metadata:{title?:string;media?:string;extra?:string}};
export type MarketDetail={nft:MarketToken;wallet:{remaining:string;exited:boolean;collected:boolean;cycle:number|null;beneficiary:string};snapshot:{owner_id:string;rights_hash:string};listing:MarketListing|null};
export type RoyaltyMonth={cycle:number;pot:string;earned:string;pending_sales:number;snapshot_total:number|null;processed:number;eligible:number;share:string;paid:number;ready:boolean};
export const royaltyFee=(amount:string)=>BigInt(amount)/20n;
export function units(amount:string,decimals:number){
 if(!/^\d+$/.test(amount)||!Number.isInteger(decimals)||decimals<0||decimals>36)throw new Error("Invalid token amount");
 const n=BigInt(amount),scale=10n**BigInt(decimals),fraction=(n%scale).toString().padStart(decimals,"0").replace(/0+$/,"");
 return `${n/scale}${fraction?`.${fraction}`:""}`;
}
