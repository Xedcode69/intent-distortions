"use client";
import {useEffect,useRef,useState} from "react";
import Link from "next/link";
import {useQuery,useQueryClient} from "@tanstack/react-query";
import {X,ArrowUpRight} from "lucide-react";
import {api,financialNow,toYocto,useAPI,walletTransactionsEnabled,type Health} from "@/lib/api";
import {contractAction,walletAccount} from "@/lib/wallet";
import {duringWalletApproval} from "@/lib/wallet-activity";
import {auctionArtworkId,activeListing,tokenTraits,units,type MarketConfig,type MarketDetail,type MarketOffer,type MarketBalance} from "@/lib/marketplace";
import {submitPreparedMarketAction} from "@/lib/market-action";
import {withdrawalState,monthLabel,type EditionWallet} from "@/lib/economy";
import {useWallet} from "./wallet-provider";
import {CrossChain} from "./market-extras";
import {Button} from "./ui/button";
import {TransactionLinks,TransactionMessage} from "./transaction-links";
import {transactionLabel,type TransactionReceipt} from "@/lib/transactions";

export function ArtworkDetail({tokenId,onClose}:{tokenId:string;onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null),cache=useQueryClient(),wallet=useWallet();
 const {account}=wallet;
 const [receipts,setReceipts]=useState<TransactionReceipt[]>([]);
 const {data:health}=useAPI<Health>("/health"),{data:config}=useAPI<MarketConfig>("/marketplace");
 const [price,setPrice]=useState(""),[offer,setOffer]=useState(""),[recipient,setRecipient]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false),[confirmExit,setConfirmExit]=useState(false),[offerOffset,setOfferOffset]=useState(0);
 const readDetail=()=>api<MarketDetail>(`/marketplace/tokens/${encodeURIComponent(tokenId)}`);
 const {data:d,error}=useQuery({queryKey:["artwork-detail",health?.network,tokenId],queryFn:readDetail,enabled:config?.status==="onchain",refetchInterval:30000});
 const {data:offers}=useQuery({queryKey:["item-offers",health?.network,tokenId,offerOffset],queryFn:()=>api<MarketOffer[]>(`/marketplace/offers?token_id=${encodeURIComponent(tokenId)}&offset=${offerOffset}&limit=20`),enabled:config?.status==="onchain",refetchInterval:30000});
 const {data:vault}=useQuery({queryKey:["item-vault",health?.network,tokenId],queryFn:()=>api<EditionWallet&{current_owner:string;vault_state:{early:{status:string}|null}|null}>(`/economy/wallets/${encodeURIComponent(tokenId)}`),enabled:!!d,refetchInterval:30000});
 useEffect(()=>{const node=dialog.current;node?.showModal();const previous=document.body.style.overflow;document.body.style.overflow="hidden";return()=>{node?.close();document.body.style.overflow=previous;};},[]);
 useEffect(()=>{setConfirmExit(false);},[account,tokenId,d?.snapshot.rights_hash]);
 const enabled=walletTransactionsEnabled(health)&&config?.status==="onchain"&&wallet.network===health?.network;
 const owner=!!account&&account===d?.nft.owner_id;
 const primary=!!d?.auction&&d.nft.owner_id===health?.contracts.auction;
 const auctionId=d?auctionArtworkId(d.nft,health?.mode||"live"):null;
 const active=!!d&&!!config&&activeListing(d,config.contract,financialNow(health));
 const exit=d?withdrawalState(d.wallet,d.nft.owner_id,account,financialNow(health)):null;
 async function refresh(){await cache.invalidateQueries();}
 async function submit(method:string,args:Record<string,unknown>,deposit="1",contract=config?.contract){
  if(!enabled||!health||!contract||!account)throw new Error("Connect your wallet on this site's network first.");
  const result=await contractAction(contract,health.network,method,args,deposit,account);
  setReceipts(previous=>[...previous,{hash:result.transaction.hash,network:health.network,label:transactionLabel(method)}]);return result;
 }
 async function run(task:()=>Promise<unknown>){if(busy)return;setBusy(true);setMessage("");setReceipts([]);try{await duringWalletApproval(task);setMessage("Transaction confirmed. Refreshing ownership and payment status…");await refresh();}catch(e){setMessage((e as Error).message);if(!/rate limit/i.test((e as Error).message))await refresh();}finally{setBusy(false);}}
 async function validate(kind:"buy"|"offer"|"list"){
  const fresh=await readDetail();const h=await api<Health>("/health");
  if(!health||!walletTransactionsEnabled(h)||h.network!==health.network||h.contracts.nft!==health.contracts.nft||h.contracts.auction!==health.contracts.auction)throw new Error("The site network or contracts changed. Reload before trading.");
  if(!d||!config||fresh.nft.owner_id!==d.nft.owner_id||fresh.snapshot.rights_hash!==d.snapshot.rights_hash)throw new Error("Ownership or edition funds changed. Review the updated artwork.");
  if(kind==="list"){
   if(fresh.nft.owner_id!==account||fresh.listing?.sale)throw new Error("Only the current owner can list an available artwork.");
  }else if(!activeListing(fresh,config.contract,financialNow(h))||fresh.listing?.nonce!==d.listing?.nonce||fresh.listing?.price!==d.listing?.price||fresh.nft.owner_id===account)throw new Error("The listing changed. Review its current price and availability.");
  return h;
 }
 async function trade(kind:"buy"|"offer"|"list"){
  if(!d||!config||!health)return;
  // Validate monetary input before asking for any storage approval.
  const amount=kind==="offer"?toYocto(offer):kind==="list"&&price?toYocto(price):null;
  if(amount!==null&&BigInt(amount)<=0n)throw new Error("Enter a positive NEAR amount.");
  let reviewedHealth=health;
  await submitPreparedMarketAction({account,kind,replacesOwnListing:kind==="list"&&d.listing?.seller===account},{
   currentAccount:()=>walletAccount(config.contract,health.network),validate:async()=>{reviewedHealth=await validate(kind);},
   readBalance:()=>api<MarketBalance>(`/marketplace/balances/${encodeURIComponent(account)}`),
   register:deposit=>submit("storage_deposit",{},deposit),
   progress:phase=>setMessage(phase==="storage"?"Approve storage setup, then the artwork action in your wallet.":"Review the artwork action in your wallet."),
   submit:async()=>{
    const h=reviewedHealth;
    if(kind==="list"){
     const expires_ns=String(BigInt(financialNow(h)+7*86400000)*1000000n);
     await submit("nft_approve",{token_id:tokenId,account_id:config.contract,msg:JSON.stringify({price:amount,expires_ns})},toYocto("0.01"),health.contracts.nft);
     const fresh=await readDetail();if(!activeListing(fresh,config.contract,financialNow(h))||fresh.listing?.price!==amount)throw new Error("Listing not confirmed. Check the NFT approval and refresh before trying again.");
    }else if(kind==="buy")await submit("buy",{token_id:tokenId,nonce:d.listing!.nonce,rights_hash:d.snapshot.rights_hash},String(BigInt(d.listing!.price!)+1n));
    else{
     const expires_ns=String(BigInt(Math.min(financialNow(h)+86400000,Number(BigInt(d.listing!.expires_ns)/1000000n)))*1000000n);
     await submit("make_offer",{token_id:tokenId,nonce:d.listing!.nonce,amount,expires_ns,rights_hash:d.snapshot.rights_hash},String(BigInt(amount!)+1n));
    }
   }
  });
 }
 async function withdraw(){
  if(!health||!d)return;const [fresh,h]=await Promise.all([readDetail(),api<Health>("/health")]);
  const state=withdrawalState(fresh.wallet,fresh.nft.owner_id,account,financialNow(h));
  if(!walletTransactionsEnabled(h)||h.network!==health.network||h.contracts.nft!==health.contracts.nft||!state.eligible||fresh.snapshot.rights_hash!==d.snapshot.rights_hash)throw new Error("Withdrawal eligibility changed. Review the artwork again.");
  await submit("withdraw_edition",{token_id:tokenId},"1",health.contracts.nft);setConfirmExit(false);
 }
 async function cancelListing(){
  if(!d?.listing||!health||!config)return;await validate("list");
  // Cancellation and revocation share one button. Stop on a failed first step.
  await submit("cancel_listing",{token_id:tokenId,nonce:d.listing.nonce});
  const fresh=await readDetail();if(fresh.listing)throw new Error("Cancellation not confirmed. Refresh before revoking approval.");
  if(fresh.nft.owner_id===account&&fresh.nft.approved_account_ids[config.contract]!==undefined)await submit("nft_revoke",{token_id:tokenId,account_id:config.contract},"1",health.contracts.nft);
 }
 async function accept(o:MarketOffer){
  const fresh=await readDetail(),h=await api<Health>("/health");
  if(!config||!activeListing(fresh,config.contract,financialNow(h))||fresh.nft.owner_id!==account||fresh.listing?.nonce!==o.listing_nonce||fresh.snapshot.rights_hash!==o.rights_hash)throw new Error("This offer no longer matches the artwork's current rights or listing.");
  await submit("accept_offer",{id:o.id});
 }
 return <dialog ref={dialog} className="id-art-dialog" onCancel={onClose} onClick={e=>{if(e.target===dialog.current)onClose();}} aria-labelledby="artwork-title">
 <div className="id-detail-shell"><button className="id-dialog-close" onClick={onClose} aria-label="Close artwork details"><X size={22}/></button>
 {!d?<div className="id-detail-loading" role={error?"alert":"status"}>{error?"Current artwork details could not be verified.":"Loading artwork…"}</div>:<>
 <div className="id-detail-image">{d.nft.metadata?.media&&<img src={d.nft.metadata.media} alt={d.nft.metadata.title||tokenId}/>}</div>
 <div className="id-detail-content"><span className="eyebrow">INTENT DISTORTIONS · {tokenId}</span><h2 id="artwork-title">{d.nft.metadata?.title||tokenId}</h2><p className="id-owner">{owner?"Owned by you":<>Owned by <span>{d.nft.owner_id}</span></>}</p>
 <div className="id-price-block"><small>{active?d.listing?.price?"Current price":"Open to offers":"Not listed"}</small><strong>{active&&d.listing?.price?`${units(d.listing.price,24)} NEAR`:"One of one"}</strong><span>5% of marketplace sales goes to eligible collection holders.</span></div>
 {!account&&<Button disabled={wallet.busy} onClick={()=>void wallet.connect()}>Connect wallet</Button>}
 {primary&&auctionId&&<div className="id-primary-auction"><p>{d.auction?.status==="Active"?"This artwork is in its primary auction.":`Primary auction: ${d.auction?.status}`}</p><Link className="button primary" href={`/auction/${auctionId}`}>View auction & bid <ArrowUpRight size={16}/></Link></div>}
 {d.auction?.status==="Settled"&&<p>Primary auction sold for {units(d.auction.highest_bid,24)} NEAR.</p>}
 {d.auction?.status==="Unsold"&&<p>No bids were placed. The primary auction returned this edition to the team.</p>}
 {!owner&&!primary&&<><div className="market-actions"><Button className="primary" disabled={!enabled||busy||!account||!active||!d.listing?.price} onClick={()=>void run(()=>trade("buy"))}>Buy artwork <ArrowUpRight size={16}/></Button></div>
 <div className="id-offer-form"><label>Offer in NEAR<input inputMode="decimal" value={offer} onChange={e=>setOffer(e.target.value)} placeholder="Your offer"/></label><Button disabled={!enabled||busy||!account||!active||!offer} onClick={()=>void run(()=>trade("offer"))}>Place offer</Button></div><small>Offers are escrowed for up to 24 hours. The owner must list or open the artwork to offers first.</small></>}
 {owner&&<section className="id-owner-actions"><h3>Manage your artwork</h3><label>Listing price · NEAR<input inputMode="decimal" value={price} onChange={e=>setPrice(e.target.value)} placeholder="Leave blank to accept offers only"/></label><div className="market-actions"><Button className="primary" disabled={!enabled||busy||!!d.listing?.sale} onClick={()=>void run(()=>trade("list"))}>{active?"Update listing":price?"List artwork":"Open to offers"}</Button>{d.listing?.seller===account&&<Button disabled={!enabled||busy||!!d.listing.sale} onClick={()=>void run(cancelListing)}>Cancel listing</Button>}{!d.listing&&config&&d.nft.approved_account_ids[config.contract]!==undefined&&<Button disabled={!enabled||busy} onClick={()=>void run(()=>submit("nft_revoke",{token_id:tokenId,account_id:config.contract},"1",health!.contracts.nft))}>Revoke approval</Button>}</div></section>}
 <p className="id-microcopy">One button handles the required steps. Your wallet may request separate approvals. First use may add up to 0.02 NEAR for market storage; listing approval attaches 0.01 NEAR. Gas is separate.</p>
 {message&&<TransactionMessage message={message} className="id-action-message"/>}
 <TransactionLinks receipts={receipts}/>
 <section className="id-vault-panel"><div><h3>Edition wallet</h3><span>{d.wallet.exited?"Withdrawal used":d.wallet.collected?"Pooled":d.wallet.cycle?monthLabel(d.wallet.cycle):"Unfunded edition"}</span></div><strong>{units(d.wallet.remaining,24)} <small>NEAR remaining</small></strong><code>{d.wallet.account_id}</code>
 <p>These funds are separate from the artwork's sale price. {d.wallet.exited?"This artwork has left its funded month's draw. Its remainder rolls forward without a ticket.":d.wallet.collected?"This allocation has entered the monthly pot.":d.wallet.cycle?"Unused rights follow ownership until the UTC month-end cutoff.":"This edition has no funded auction allocation yet."}</p>
 {owner&&exit?.eligible&&<>{!confirmExit?<Button disabled={!enabled||busy} onClick={()=>setConfirmExit(true)}>Early withdrawal · {units(exit.amount,24)} NEAR</Button>:<div className="id-exit-confirm"><h4>Leave this month's draw?</h4><p>You receive {units(exit.amount,24)} NEAR (40% of the original allocation). The remaining {units(exit.rollover,24)} NEAR rolls into next month's pot. This NFT loses its draw ticket. This choice cannot be undone.</p><div className="market-actions"><Button disabled={!enabled||busy} onClick={()=>void run(withdraw)}>Confirm withdrawal</Button><Button disabled={busy} onClick={()=>setConfirmExit(false)}>Keep my ticket</Button></div></div>}</>}
 {d.wallet.exited&&<p>Payment: {vault?.vault_state?.early?.status||"Checking vault delivery"} · {d.wallet.exit_beneficiary}{owner&&<Button disabled={!enabled||busy} onClick={()=>void run(()=>submit("dispatch_exit",{token_id:tokenId},"0",health!.contracts.nft))}>Check / retry delivery</Button>}</p>}
 </section>
 <details className="id-item-section"><summary>Offers {offers?.length?`· ${offers.length} on this page`:""}</summary>{offers?.map(o=><div className="id-offer-row" key={o.id}><div><b>{units(o.amount,24)} NEAR</b><span>{o.buyer===account?"Your offer":o.buyer}</span><small>Until {new Date(Number(BigInt(o.expires_ns)/1000000n)).toUTCString()}</small></div><div>{owner&&<Button disabled={!enabled||busy||financialNow(health)>=Number(BigInt(o.expires_ns)/1000000n)} onClick={()=>void run(()=>accept(o))}>Accept offer</Button>}{(o.buyer===account||financialNow(health)>=Number(BigInt(o.expires_ns)/1000000n))&&<Button disabled={!enabled||busy} onClick={()=>void run(()=>submit("cancel_offer",{id:o.id}))}>{o.buyer===account?"Cancel offer":"Release expired offer"}</Button>}</div></div>)}{!offers?.length&&<p>No offers on this page.</p>}<div className="market-actions"><Button disabled={offerOffset===0} onClick={()=>setOfferOffset(Math.max(0,offerOffset-20))}>Previous</Button><Button disabled={!offers||offers.length<20} onClick={()=>setOfferOffset(offerOffset+20)}>Next</Button></div><p>Cancelled offers return to your marketplace credit. Withdraw credit from Wallet & balances.</p></details>
 <details className="id-item-section"><summary>Artwork traits</summary><dl className="id-traits">{tokenTraits(d.nft).map((a,i)=><div key={`${a.trait_type}:${i}`}><dt>{a.trait_type}</dt><dd>{a.value}</dd></div>)}</dl></details>
 {owner&&<details className="id-item-section"><summary>Transfer artwork</summary><p>Unused rights follow the NFT before cutoff. Fixed monthly entitlements stay with the recorded beneficiary.</p><label>Recipient NEAR account<input value={recipient} onChange={e=>setRecipient(e.target.value)} placeholder={health?.network==="mainnet"?"collector.near":"collector.testnet"}/></label><Button disabled={!enabled||busy||!recipient.trim()||d.wallet.transfer_pending} onClick={()=>void run(async()=>{const fresh=await readDetail();if(fresh.nft.owner_id!==account)throw new Error("Ownership changed.");await submit("nft_transfer",{receiver_id:recipient.trim(),token_id:tokenId,approval_id:null,memo:null},"1",health!.contracts.nft);})}>Authorize transfer</Button></details>}
 {!owner&&d.listing&&<CrossChain listing={d.listing} tokenId={tokenId} account={account} enabled={!!enabled&&!!config?.crosschain&&active} offer={offer} network={health?.network||"testnet"} onMessage={setMessage}/>}
 </div></>}
 </div></dialog>;
}
