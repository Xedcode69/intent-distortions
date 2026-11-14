export function simulateEconomy(sales:number,exits:number,price:bigint){
  if(!Number.isInteger(sales)||sales<0||sales>5||!Number.isInteger(exits)||exits<0||exits>sales||price<0n)throw new Error("Invalid example");
  const treasuryPerSale=price/5n,allocation=price-treasuryPerSale,withdrawal=allocation*2n/5n;
  return {gross:price*BigInt(sales),treasury:treasuryPerSale*BigInt(sales),withdrawals:withdrawal*BigInt(exits),
    pot:allocation*BigInt(sales-exits),rollover:(allocation-withdrawal)*BigInt(exits),tickets:sales-exits};
}
export type EditionWallet={token_id:string;release_ns:string;account_id:string;wallet_status:string;gross:string;original:string;remaining:string;cycle:number|null;
  beneficiary:string;exited:boolean;exit_beneficiary:string|null;collection_cycle:number|null;collected:boolean;transfer_pending:boolean};
export function withdrawalState(d:EditionWallet,owner:string,account:string,now:number){
 const cutoff=d.cycle?Date.UTC(Math.floor(d.cycle/100),d.cycle%100,1):0;
 const amount=BigInt(d.original)*2n/5n;
 return {amount:String(amount),rollover:String(BigInt(d.remaining)-amount),cutoff,
  eligible:!!account&&account===owner&&d.wallet_status==="Funded"&&!!d.cycle&&!d.exited&&!d.collected&&!d.transfer_pending&&now<cutoff&&amount>0n};
}
export type Month={cycle:number;status:string;cutoff_ns:string;entropy_round:string;entries:{token_id:string;beneficiary:string}[];
  expected_receipts:number;received_receipts:number;pending_sources:number;pot:string;rollover_received:string;prize:string;randomness:string|null;
  winner:{token_id:string;beneficiary:string}|null;payout:{status:string;amount:string;beneficiary:string}|null};
export type Economy={status:string;currency:string;creator:string|null;treasury:string|null;treasury_credit:string;treasury_earned:string;gross_earned?:string;
  next_close:number;vault_code_hash?:string;drand_chain?:string};
export function monthLabel(cycle:number){return new Date(Date.UTC(Math.floor(cycle/100),cycle%100-1,1)).toLocaleDateString("en-GB",{month:"long",year:"numeric",timeZone:"UTC"});}
