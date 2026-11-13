"use client";
import {useState,useEffect} from "react";
import Link from "next/link";
import {useWallet} from "./wallet-provider";
import {useQuery} from "@tanstack/react-query";
import {api,useAPI,toYocto,yocto,type Health} from "@/lib/api";
import {contractAction,walletAccount} from "@/lib/wallet";
import {units,type MarketConfig,type MarketDetail,type MarketListing,type MarketOffer,type MarketToken,type RoyaltyMonth} from "@/lib/marketplace";
import {RoyaltyExample} from "./royalty-example";
import {Button} from "./ui/button";

type Quote={quote_response:{quote:{depositAddress?:string;depositMemo?:string;amountIn:string;maxAmountIn?:string;deadline:string;amountOut:string};quoteRequest:Record<string,unknown>};funding_yocto:string;notice:string};
type Source={assetId:string;symbol:string;blockchain:string;decimals:number};
function CrossChain({listing,tokenId,account,enabled,offer,network,onMessage}:{listing:MarketListing;tokenId:string;account:string;enabled:boolean;offer:string;network:Health["network"];onMessage:(s:string)=>void}){
 const [source,setSource]=useState(""),[refund,setRefund]=useState(""),[quote,setQuote]=useState<Quote|null>(null),[status,setStatus]=useState(""),[busy,setBusy]=useState(false);
 const {data:sources}=useQuery({queryKey:["swap-sources"],queryFn:()=>api<Source[]>("/marketplace/crosschain/tokens"),enabled});
 useEffect(()=>{setQuote(null);setStatus("");},[source,refund,account,listing.nonce,offer,tokenId]);
 async function request(dry:boolean){setBusy(true);setQuote(null);try{
  const q=await api<Quote>("/marketplace/crosschain/quote",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({token_id:tokenId,listing_nonce:listing.nonce,buyer:account,origin_asset:source,refund_to:refund,dry,offer_amount:offer?toYocto(offer):null})});setQuote(q);
 }catch(e){onMessage((e as Error).message);}finally{setBusy(false);}}
 async function poll(){if(!quote?.quote_response.quote.depositAddress)return;setBusy(true);try{
  const q=quote.quote_response.quote,params=new URLSearchParams({deposit_address:q.depositAddress!});if(q.depositMemo!=null)params.set("deposit_memo",q.depositMemo);
  const value=await api<{status:string}>(`/marketplace/crosschain/status?${params}`);setStatus(value.status);
 }catch(e){onMessage((e as Error).message);}finally{setBusy(false);}}
 const selected=sources?.find(t=>t.assetId===source),q=quote?.quote_response.quote;
 return <details className="market-crosschain"><summary>Pay from another chain with NEAR Intents</summary>
 {!enabled?<p>Cross-chain checkout becomes available with an enabled, reviewed mainnet marketplace. Testnet and this replay do not accept deposits.</p>:<>
 <p>Swap into your connected NEAR account, then approve Buy or Make offer. This does not reserve the artwork. If it sells meanwhile, your funds stay in your wallet. Funding includes an extra 0.1 NEAR for registration, offer storage and gas; unused funds are yours.</p>
 <label>Source asset<select value={source} onChange={e=>setSource(e.target.value)}><option value="">Choose network and token</option>{sources?.map(t=><option key={t.assetId} value={t.assetId}>{t.blockchain} · {t.symbol}</option>)}</select></label>
 <label>Refund address on the source chain<input value={refund} onChange={e=>setRefund(e.target.value)} placeholder="Your source wallet address"/></label>
 <p>Receiving NEAR account: <code>{account||"Connect a NEAR wallet first"}</code>. {offer?`Funding an offer of ${offer} NEAR.`:"Funding the fixed listing price."}</p>
 <Button disabled={!account||!source||!refund||busy} onClick={()=>request(true)}>Preview funding quote</Button>
 {q&&<div className="market-quote"><p>Quoted input: {selected?units(q.maxAmountIn||q.amountIn,selected.decimals):q.amountIn} {selected?.symbol} (maximum, including input-side slippage). Output: {units(q.amountOut,24)} NEAR. Provider fees are included in the quote; marketplace royalty is deducted from the sale price.</p><p>Deadline: {q.deadline}</p>
 {q.depositAddress?<><p>Send the quoted source asset on <b>{selected?.blockchain}</b> to:</p><code>{q.depositAddress}</code>{q.depositMemo!=null&&<p className="notice">Required deposit memo: <code>{q.depositMemo}</code></p>}<p>Use your source wallet to send. Include the exact memo when provided; never send after the deadline.</p><Button disabled={busy} onClick={poll}>Check swap status</Button>{status&&<p role="status">Swap: {status}. NFT ownership is checked separately.</p>}</>:<Button disabled={busy} onClick={()=>request(false)}>Create deposit instructions</Button>}
 </div>}
 </>}
 </details>;
}

function RoyaltyCycle({m,enabled,act}:{m:RoyaltyMonth;enabled:boolean;act:(method:string,args:Record<string,unknown>,deposit?:string)=>Promise<void>}){
 const [offset,setOffset]=useState(0);
 const {data:shares,refetch}=useQuery({queryKey:["royalty-shares",m.cycle,offset,m.paid,m.processed],queryFn:()=>api<{index:number;token_id:string;owner_id:string;status:string;amount:string}[]>(`/marketplace/royalties/${m.cycle}/shares?offset=${offset}&limit=25`),enabled:m.ready,refetchInterval:15000});
 return <article className="market-royalty"><h3>{m.cycle.toString().slice(0,4)} / {m.cycle%100}</h3><p>Royalties earned: {yocto(m.earned)} NEAR · Held unpaid: {yocto(m.pot)} NEAR</p><p>{m.ready?`${m.eligible} eligible artworks · ${yocto(m.share)} NEAR per artwork · ${m.paid} payments delivered`:`Ownership snapshot: ${m.processed} / ${m.snapshot_total??"pending"}; ${m.pending_sales} sales awaiting resolution.`}</p>
 {shares?.map(s=><div className="market-share" key={s.index}><span>{s.token_id} → {s.owner_id} · {s.status}</span><Button className="subtle" disabled={!enabled||BigInt(s.amount)===0n||!["Claimable","Retryable"].includes(s.status)} onClick={async()=>{await act("pay_royalty",{cycle:m.cycle,index:String(s.index)},"1");await refetch();}}>Deliver payment</Button></div>)}
 {m.ready&&<div className="market-actions"><Button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-25))}>Previous shares</Button><Button disabled={!shares||shares.length<25} onClick={()=>setOffset(offset+25)}>Next shares</Button></div>}
 </article>;
}

export function Marketplace({initialToken=""}:{initialToken?:string}){
 const {data:config,error,refetch:refreshConfig}=useAPI<MarketConfig>("/marketplace");const {data:health}=useAPI<Health>("/health");
 const wallet=useWallet(),{account}=wallet;
 const [selected,setSelected]=useState(initialToken),[price,setPrice]=useState(""),[offer,setOffer]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
 useEffect(()=>setSelected(initialToken),[initialToken]);
 const [offset,setOffset]=useState(0),[listingOffset,setListingOffset]=useState(0),[offerOffset,setOfferOffset]=useState(0),[royaltyOffset,setRoyaltyOffset]=useState(0);
 const {data:listings,refetch:refreshListings}=useAPI<MarketListing[]>(`/marketplace/listings?offset=${listingOffset}&limit=20`);
 const {data:tokens,refetch:refreshTokens}=useAPI<MarketToken[]>(`/marketplace/tokens?offset=${offset}&limit=20`);
 const {data:offers,refetch:refreshOffers}=useAPI<MarketOffer[]>(`/marketplace/offers?offset=${offerOffset}&limit=20`);
 const {data:months,refetch:refreshMonths}=useAPI<RoyaltyMonth[]>(`/marketplace/royalties?offset=${royaltyOffset}&limit=24`);
 const {data:detail,refetch:refreshDetail,error:detailError}=useQuery({queryKey:["market-token",selected],queryFn:()=>api<MarketDetail>(`/marketplace/tokens/${encodeURIComponent(selected)}`),enabled:!!selected&&config?.status==="onchain",refetchInterval:15000});
 const {data:balance,refetch:refreshBalance}=useQuery({queryKey:["market-balance",account],queryFn:()=>api<{storage_available:string;credit:string;withdrawing:string}>(`/marketplace/balances/${account}`),enabled:!!account&&config?.status==="onchain",refetchInterval:15000});
 const enabled=config?.status==="onchain"&&health?.mode==="live";
 async function refresh(){await Promise.all([refreshConfig(),refreshListings(),refreshTokens(),refreshOffers(),refreshMonths(),...(selected?[refreshDetail()]:[]),...(account?[refreshBalance()]:[])]);}
 async function connect(){await wallet.connect();}
 async function action(method:string,args:Record<string,unknown>,deposit="0",contract=config?.contract){
  if(!enabled||!health||!contract)return;setBusy(true);setMessage("");try{
   const current=await walletAccount(config!.contract,health.network);if(current!==account)throw new Error("Active wallet changed. Review the artwork before submitting again.");
   const result=await contractAction(contract,health.network,method,args,deposit);setMessage(`Transaction finalized: ${result.transaction.hash}. Check the on-chain result below; a failed sale returns credit instead of transferring the NFT.`);await refresh();
  }catch(e){setMessage((e as Error).message);}finally{setBusy(false);}
 }
 const l=detail?.listing,active=l&&!l.sale&&BigInt(l.expires_ns)>BigInt(Date.now())*1000000n&&l.seller===detail?.nft.owner_id&&detail?.nft.approved_account_ids?.[config?.contract||""]===l.approval_id;
 const owner=account===detail?.nft.owner_id;
 async function list(){if(!detail||!health||!config)return;const expires=String(BigInt(Date.now()+7*86400000)*1000000n);
  await action("nft_approve",{token_id:detail.nft.token_id,account_id:config.contract,msg:JSON.stringify({price:price?toYocto(price):null,expires_ns:expires})},toYocto("0.01"),health.contracts.nft);
 }
 async function funding(){if(!account||!health)return;setBusy(true);try{
  const f=await api<{amount:string;wrapped_near:string}>(`/marketplace/funding/${account}`);
  setMessage(`Wallet balance: ${units(f.amount,24)} native NEAR (includes storage reserve); ${units(f.wrapped_near,24)} wrapped NEAR. Review your wallet’s spendable balance and keep gas for the purchase.`);
  if(BigInt(f.wrapped_near)>0n)await action("near_withdraw",{amount:f.wrapped_near},"1",health.network==="mainnet"?"wrap.near":"wrap.testnet");
 }catch(e){setMessage((e as Error).message);}finally{setBusy(false);}}
 if(error)return <div className="page-container"><h1>Marketplace unavailable</h1><p role="alert">{error.message}</p></div>;
 return <div className="page-container market-page"><div className="page-title"><span className="eyebrow">THE MARKETPLACE</span><h1>Find your<br/><em>next echo.</em></h1><p>Originals worth keeping. Or passing on.</p></div>
 <div className="notice">{enabled?`Live contract state on ${health.network}.` :"Preview · Trading is not live. Explore the collection while the market gets ready."}</div>
 {enabled&&<div className="market-toolbar"><Button disabled={busy} onClick={connect}>{account||"Connect wallet"}</Button><details className="wallet-tools"><summary>Wallet & balances</summary><div className="market-actions"><Button className="subtle" disabled={busy||!account} onClick={()=>action("storage_deposit",{},toYocto("0.05"))}>Set up / top up · 0.05 NEAR</Button><Button className="subtle" disabled={busy||!account} onClick={()=>action("withdraw_credit",{},"1")}>Withdraw credit</Button><Button className="subtle" disabled={busy||!account} onClick={()=>action("withdraw_storage",{},"1")}>Withdraw unused storage</Button></div>{balance&&<p className="account-balance">Credit {yocto(balance.credit)} NEAR · Available storage {yocto(balance.storage_available)} NEAR · Withdrawing {yocto(balance.withdrawing)} NEAR</p>}<p>Registration retains 0.01 NEAR. Each active listing or offer reserves another 0.01 NEAR, released when removed.</p></details></div>}
 {message&&<p className="notice" role="status">{message}</p>}
 <section className="economy-section"><h2>Available originals.</h2><p>Priced in NEAR. A 5% fee supports the collection’s eligible holders.</p><div className="market-grid">{listings?.map(l=><button className="market-card" key={l.token_id} onClick={()=>{setSelected(l.token_id);setOffer("");setPrice("");}}><strong>{l.token_id}</strong><span>{l.price?`${units(l.price,24)} NEAR`:"Offers only"}</span><small>{l.sale?"Sale pending":BigInt(l.expires_ns)<=BigInt(Date.now())*1000000n?"Expired":"Check availability"} · {l.seller}</small></button>)}</div>{!listings?.length&&<div className="marketplace-blank"><span className="market-empty-label">ONE OF ONE. SOON TO BE YOURS.</span><strong>{enabled?"Nothing listed right now.":"The first listings are on their way."}</strong><p>Explore the artworks while you wait.</p><Link href="/gallery" className="text-link">View the collection ↗</Link></div>}<div className="market-actions"><Button disabled={listingOffset===0} onClick={()=>setListingOffset(Math.max(0,listingOffset-20))}>Previous listings</Button><Button disabled={!listings||listings.length<20} onClick={()=>setListingOffset(listingOffset+20)}>Next listings</Button></div></section>
 <section className="economy-section"><h2>The collection.</h2>
 <div className="market-grid">{tokens?.map(t=><button className={`market-card ${selected===t.token_id?"selected":""}`} key={t.token_id} onClick={()=>{setSelected(t.token_id);setOffer("");setPrice("");}}>{t.metadata?.media&&<img src={t.metadata.media} alt={t.metadata.title||t.token_id}/>}<strong>{t.metadata?.title||t.token_id}</strong><span>{t.token_id}</span><small>{t.owner_id}</small></button>)}</div>
 {!tokens?.length&&<p>No deployed collection is available here yet.</p>}<div className="market-actions"><Button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>Previous artworks</Button><Button disabled={!tokens||tokens.length<20} onClick={()=>setOffset(offset+20)}>Next artworks</Button></div>
 </section>
 {detailError&&<p role="alert">The artwork’s current ownership and financial state could not be loaded.</p>}
 {detail&&selected===detail.nft.token_id&&<section className="economy-section market-trade"><h2>{detail.nft.metadata?.title||selected}</h2><p>Owner: <code>{detail.nft.owner_id}</code></p><p>Edition funds remaining: {yocto(detail.wallet.remaining)} NEAR · Withdrawal {detail.wallet.exited?"already used":"unused"} · Allocation {detail.wallet.collected?"already pooled":"not collected"} · Funded cycle {detail.wallet.cycle||"none"}. These funds are separate from the sale price.</p>
 {l?<p>{active?l.price?`Listed for ${units(l.price,24)} NEAR` :"Open to offers":"Listing unavailable: expired, changed, pending or revoked"} · Seller receives 95%; 5% funds holder royalties.</p>:<p>This NFT is not listed. Its owner can list a price or enable offers below.</p>}
 <div className="market-actions"><Button disabled={!enabled||busy||!account||owner||!active||!l?.price} onClick={()=>l&&action("buy",{token_id:selected,nonce:l.nonce,rights_hash:detail.snapshot.rights_hash},String(BigInt(l.price!)+1n))}>Buy in NEAR</Button><Button className="subtle" disabled={!enabled||busy||!account} onClick={funding}>Check wallet / unwrap wNEAR</Button></div>
 <label>Offer in NEAR<input inputMode="decimal" value={offer} onChange={e=>setOffer(e.target.value)} placeholder="Offer amount"/></label>
 <Button disabled={!enabled||busy||!account||owner||!active||!offer} onClick={()=>{try{const amount=toYocto(offer);if(BigInt(amount)<=0n)throw new Error("Positive amount required");const expiry=String(BigInt(Math.min(Date.now()+86400000,Number(BigInt(l!.expires_ns)/1000000n)))*1000000n);void action("make_offer",{token_id:selected,nonce:l!.nonce,amount,expires_ns:expiry,rights_hash:detail.snapshot.rights_hash},String(BigInt(amount)+1n));}catch(e){setMessage((e as Error).message);}}}>Escrow offer · expires within 24 hours</Button>
 {l&&<CrossChain key={`${account}:${selected}:${l.nonce}`} listing={l} tokenId={selected} account={account} enabled={!!enabled&&!!config?.crosschain&&!!active} offer={offer} network={health?.network||"testnet"} onMessage={setMessage}/>}
 {owner&&<details><summary>Sell this artwork</summary><p>Registration and record storage must be funded first. Leave price blank for offers only. Approval lasts seven days. Cancelling the listing leaves other offers refundable; revoke the NFT approval separately if desired.</p><label>Listing price in NEAR<input inputMode="decimal" value={price} onChange={e=>setPrice(e.target.value)} placeholder="Blank = offers only"/></label><div className="market-actions"><Button disabled={!enabled||busy} onClick={()=>{try{if(price&&BigInt(toYocto(price))<=0n)throw new Error("Positive price required");void list();}catch(e){setMessage((e as Error).message);}}}>Approve / update listing</Button>{l&&<Button disabled={!enabled||busy||!!l.sale} onClick={()=>action("cancel_listing",{token_id:selected,nonce:l.nonce},"1")}>Cancel listing</Button>}<Button disabled={!enabled||busy} onClick={()=>action("nft_revoke",{token_id:selected,account_id:config!.contract},"1",health!.contracts.nft)}>Revoke marketplace approval</Button></div></details>}
 </section>}
 <details className="economy-section"><summary>Collection offers · {offers?.length||0} on this page</summary><p>Offers hold NEAR in escrow until accepted, cancelled or released. A changed listing or financial state cannot consume an outdated offer.</p>
 {offers?.map(o=><article className="market-offer" key={o.id}><p><button className="text-link" onClick={()=>setSelected(o.token_id)}>{o.token_id}</button> · {units(o.amount,24)} NEAR from {o.buyer}</p><p>Expires {new Date(Number(BigInt(o.expires_ns)/1000000n)).toISOString()}</p><div className="market-actions"><Button disabled={!enabled||busy||account!==o.seller||Date.now()>=Number(BigInt(o.expires_ns)/1000000n)} onClick={()=>action("accept_offer",{id:o.id},"1")}>Accept offer</Button><Button className="subtle" disabled={!enabled||busy||(account!==o.buyer&&Date.now()<Number(BigInt(o.expires_ns)/1000000n))} onClick={()=>action("cancel_offer",{id:o.id},"1")}>Cancel / release expired offer</Button></div></article>)}
 {!offers?.length&&<p>No offers on this page.</p>}<div className="market-actions"><Button disabled={offerOffset===0} onClick={()=>setOfferOffset(Math.max(0,offerOffset-20))}>Previous offers</Button><Button disabled={!offers||offers.length<20} onClick={()=>setOfferOffset(offerOffset+20)}>Next offers</Button></div></details>
 <details className="economy-section"><summary>Holder royalties · 5% of secondary sales</summary><p>One equal share per eligible artwork, including creator-minted or previously withdrawn editions once held by a collector. The team/creator wallet and protocol custody accounts are excluded at the UTC month-end cutoff. Owning multiple eligible artworks earns multiple shares. This pool is separate from the primary-auction raffle.</p><p>The keeper snapshots ownership in batches and delivers each payment automatically. Anyone may finish or retry delivery. Rounding dust, or a month with no eligible holders, rolls into the following month. Royalties are enforced on sales through this marketplace; external transfers cannot be forced to pay them.</p>
 {config?.next_royalty_close&&<Button disabled={!enabled||busy} onClick={()=>action("prepare_royalties",{cycle:config.next_royalty_close})}>Advance due monthly snapshot</Button>}
 {months?.map(m=><RoyaltyCycle key={m.cycle} m={m} enabled={!!enabled&&!busy} act={action}/>)}{!months?.length&&<p>No royalty pools have been recorded.</p>}<div className="market-actions"><Button disabled={royaltyOffset===0} onClick={()=>setRoyaltyOffset(Math.max(0,royaltyOffset-24))}>Previous pools</Button><Button disabled={!months||months.length<24} onClick={()=>setRoyaltyOffset(royaltyOffset+24)}>Next pools</Button></div>
 </details><details><summary>Try the royalty simulator</summary><RoyaltyExample/></details></div>;
}
