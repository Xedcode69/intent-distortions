export type MarketListing={token_id:string;seller:string;approval_id:number;nonce:string;price:string|null;expires_ns:string;sale:{id:string;buyer:string;amount:string}|null};
export type MarketOffer={id:string;token_id:string;seller:string;buyer:string;listing_nonce:string;amount:string;expires_ns:string;rights_hash:string};
export type MarketConfig={status:string;contract:string;fee_bps:number;crosschain:boolean;next_royalty_close?:number};
export type MarketToken={token_id:string;owner_id:string;approved_account_ids:Record<string,number>;metadata:{title?:string;media?:string;extra?:string}};
export type MarketDetail={nft:MarketToken;wallet:import("./economy").EditionWallet;snapshot:{owner_id:string;rights_hash:string};listing:MarketListing|null};
export type CollectionItem={nft:MarketToken;listing:MarketListing|null;family:string};
export type CollectionMarket={items:CollectionItem[];total:number;stats:{items:number;listed:number;owners:number;floor:string|null};families:string[];block_height:number|null};
export type MarketBalance={storage_available:string;credit:string;withdrawing:string};
export function activeListing(detail:MarketDetail,contract:string,now:number){
 const l=detail.listing;
 return !!l&&!l.sale&&BigInt(l.expires_ns)>BigInt(Math.floor(now))*1000000n&&l.seller===detail.nft.owner_id&&detail.nft.approved_account_ids?.[contract]===l.approval_id;
}
export function tokenTraits(token:MarketToken):{trait_type:string;value:string|number}[]{
 try{const a=JSON.parse(token.metadata?.extra||"{}").attributes;return Array.isArray(a)?a.filter(t=>typeof t?.trait_type==="string"&&["string","number"].includes(typeof t.value)):[];}catch{return [];}
}
export type RoyaltyMonth={cycle:number;pot:string;earned:string;pending_sales:number;snapshot_total:number|null;processed:number;eligible:number;share:string;paid:number;ready:boolean};
export const royaltyFee=(amount:string)=>BigInt(amount)/20n;
export function units(amount:string,decimals:number){
 if(!/^\d+$/.test(amount)||!Number.isInteger(decimals)||decimals<0||decimals>36)throw new Error("Invalid token amount");
 const n=BigInt(amount),scale=10n**BigInt(decimals),fraction=(n%scale).toString().padStart(decimals,"0").replace(/0+$/,"");
 return `${n/scale}${fraction?`.${fraction}`:""}`;
}
