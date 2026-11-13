use near_contract_standards::non_fungible_token::{NonFungibleToken, Token, TokenId};
use near_contract_standards::non_fungible_token::metadata::{NFTContractMetadata, NonFungibleTokenMetadataProvider, TokenMetadata, NFT_METADATA_SPEC};
use near_sdk::{env, near, AccountId, BorshStorageKey, PanicOnDefault, Promise, PromiseOrValue};
use near_sdk::collections::{LazyOption, LookupMap, UnorderedSet};
use near_sdk::json_types::Base64VecU8;
use near_contract_standards::non_fungible_token::core::{NonFungibleTokenCore,NonFungibleTokenResolver};
use near_contract_standards::non_fungible_token::approval::NonFungibleTokenApproval;
use near_contract_standards::non_fungible_token::enumeration::NonFungibleTokenEnumeration;
use near_sdk::json_types::U128;

#[derive(BorshStorageKey)]
#[near(serializers=[borsh])]
enum Key { Tokens, Metadata, TokenMetadata, Enumeration, Approval, Epochs, Hashes, Provenance, Deliveries }

#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct Delivery { pub receiver_id:AccountId, pub confirmed:bool }

#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct Commitment {
    pub epoch: u64,
    pub image_hash: String,
    pub provenance_hash: String,
    pub merkle_root: String,
    pub seed: String,
    pub block_hash: String,
}

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct EchoNFT {
    tokens: NonFungibleToken,
    metadata: LazyOption<NFTContractMetadata>,
    minter: AccountId,
    latest_epoch: u64,
    epochs: LookupMap<u64, TokenId>,
    image_hashes: UnorderedSet<String>,
    commitments: LookupMap<TokenId, Commitment>,
    auction_contract:Option<AccountId>,
    deliveries:LookupMap<TokenId,Delivery>,
}

#[near]
impl EchoNFT {
    #[init]
    pub fn new(owner_id: AccountId, minter: AccountId) -> Self {
        let metadata = NFTContractMetadata { spec:NFT_METADATA_SPEC.into(), name:"NEAR ECHOES".into(), symbol:"ECHO".into(), icon:None, base_uri:None, reference:None, reference_hash:None };
        Self { tokens:NonFungibleToken::new(Key::Tokens,owner_id,Some(Key::TokenMetadata),Some(Key::Enumeration),Some(Key::Approval)),
            metadata:LazyOption::new(Key::Metadata,Some(&metadata)),minter,latest_epoch:0,
            epochs:LookupMap::new(Key::Epochs),image_hashes:UnorderedSet::new(Key::Hashes),commitments:LookupMap::new(Key::Provenance),
            auction_contract:None,deliveries:LookupMap::new(Key::Deliveries) }
    }

    #[init]
    pub fn new_production(owner_id:AccountId,minter:AccountId,auction_contract:AccountId)->Self {
        assert_ne!(auction_contract,env::current_account_id(),"Separate auction contract required");
        let mut contract=Self::new(owner_id,minter);contract.auction_contract=Some(auction_contract);contract
    }

    /// Entire mint, including custom commitments, is covered by the attached storage deposit.
    #[payable]
    pub fn mint_weekly_artwork(&mut self, receiver_id: AccountId, metadata:TokenMetadata, commitment:Commitment) -> Token {
        assert_eq!(env::predecessor_account_id(),self.minter,"Unauthorized minter");
        assert!(commitment.epoch>0,"Invalid epoch");
        assert!(self.epochs.get(&commitment.epoch).is_none(),"Epoch already minted");
        assert!(!self.image_hashes.contains(&commitment.image_hash),"Duplicate image hash");
        for hash in [&commitment.image_hash,&commitment.provenance_hash,&commitment.merkle_root,&commitment.seed] {
            assert!(hash.len()==64 && hash.bytes().all(|b|b.is_ascii_hexdigit() && !b.is_ascii_uppercase()),"Expected lowercase SHA-256");
        }
        assert!(metadata.media.is_some() && metadata.reference.is_some(),"Content and provenance URIs required");
        assert_eq!(metadata.copies,Some(1),"One of one only");
        let decode = |hash:&str| -> Vec<u8> { (0..hash.len()).step_by(2).map(|i|u8::from_str_radix(&hash[i..i+2],16).unwrap()).collect() };
        assert_eq!(metadata.media_hash,Some(Base64VecU8(decode(&commitment.image_hash))),"Media hash mismatch");
        assert_eq!(metadata.reference_hash,Some(Base64VecU8(decode(&commitment.provenance_hash))),"Provenance hash mismatch");
        let initial=env::storage_usage();
        let token_id=format!("ECHO-{:06}",commitment.epoch);
        if let Some(auction)=&self.auction_contract {
            assert_eq!(&receiver_id,auction,"Canonical NFTs must mint into configured auction custody");
            // Prepay a maximum-sized immutable delivery record at mint. Settlement
            // can update it with one yocto without increasing required storage.
            self.deliveries.insert(&token_id,&Delivery{receiver_id:"a".repeat(64).parse().unwrap(),confirmed:false});
        }
        self.epochs.insert(&commitment.epoch,&token_id);
        self.image_hashes.insert(&commitment.image_hash);
        self.commitments.insert(&token_id,&commitment);
        self.latest_epoch=self.latest_epoch.max(commitment.epoch);
        let custom_cost=env::storage_byte_cost().as_yoctonear().checked_mul((env::storage_usage()-initial) as u128).unwrap();
        assert!(env::attached_deposit().as_yoctonear()>=custom_cost,"Insufficient commitment storage deposit");
        // Standard mint helper refunds only storage surplus. We subtract custom storage
        // by requiring an additional exact reserve through the measured total below.
        let token=self.tokens.internal_mint_with_refund(token_id.clone(),receiver_id,Some(metadata),None);
        let total=env::storage_byte_cost().as_yoctonear().checked_mul((env::storage_usage()-initial) as u128).unwrap();
        let paid=env::attached_deposit().as_yoctonear();
        assert!(paid>=total,"Insufficient NFT storage deposit");
        if paid>total { near_sdk::Promise::new(env::predecessor_account_id()).transfer(near_sdk::NearToken::from_yoctonear(paid-total)).detach(); }
        near_contract_standards::non_fungible_token::events::NftMint { owner_id:&token.owner_id, token_ids:&[&token_id], memo:Some("weekly genesis") }.emit();
        token
    }

    pub fn get_epoch_token(&self, epoch:u64) -> Option<TokenId> { self.epochs.get(&epoch) }
    pub fn get_provenance(&self, token_id:TokenId) -> Option<Commitment> { self.commitments.get(&token_id) }
    pub fn get_latest_edition(&self) -> u64 { self.latest_epoch }
    pub fn is_artwork_hash_used(&self, image_hash:String) -> bool { self.image_hashes.contains(&image_hash) }
    pub fn get_auction_delivery(&self,token_id:TokenId)->Option<Delivery>{self.deliveries.get(&token_id).filter(|d|d.confirmed)}
    pub fn get_config(&self)->near_sdk::serde_json::Value{near_sdk::serde_json::json!({"minter":self.minter,"auction_contract":self.auction_contract,"version":"echo-nft-2"})}
}

#[near]
impl NonFungibleTokenCore for EchoNFT {
    #[payable]
    fn nft_transfer(&mut self,receiver_id:AccountId,token_id:TokenId,approval_id:Option<u64>,memo:Option<String>){
        let custody=self.auction_contract.as_ref()==Some(&env::predecessor_account_id());
        if custody {assert!(self.deliveries.get(&token_id).map(|d|!d.confirmed).unwrap_or(false),"Delivery already recorded");}
        self.tokens.nft_transfer(receiver_id.clone(),token_id.clone(),approval_id,memo);
        if custody {self.deliveries.insert(&token_id,&Delivery{receiver_id,confirmed:true});}
    }
    #[payable]
    fn nft_transfer_call(&mut self,receiver_id:AccountId,token_id:TokenId,approval_id:Option<u64>,memo:Option<String>,msg:String)->PromiseOrValue<bool>{
        assert!(self.auction_contract.as_ref()!=Some(&env::predecessor_account_id()),"Escrow delivery must use nft_transfer");
        self.tokens.nft_transfer_call(receiver_id,token_id,approval_id,memo,msg)
    }
    fn nft_token(&self,token_id:TokenId)->Option<Token>{self.tokens.nft_token(token_id)}
}
#[near]
impl NonFungibleTokenResolver for EchoNFT {
    #[private]
    fn nft_resolve_transfer(&mut self,previous_owner_id:AccountId,receiver_id:AccountId,token_id:TokenId,approved_account_ids:Option<std::collections::HashMap<AccountId,u64>>)->bool{
        self.tokens.nft_resolve_transfer(previous_owner_id,receiver_id,token_id,approved_account_ids)
    }
}
#[near]
impl NonFungibleTokenApproval for EchoNFT {
    #[payable]
    fn nft_approve(&mut self,token_id:TokenId,account_id:AccountId,msg:Option<String>)->Option<Promise>{
        assert!(self.auction_contract.as_ref()!=Some(&env::predecessor_account_id()),"Escrow cannot delegate NFT transfers");
        self.tokens.nft_approve(token_id,account_id,msg)
    }
    #[payable]
    fn nft_revoke(&mut self,token_id:TokenId,account_id:AccountId){self.tokens.nft_revoke(token_id,account_id)}
    #[payable]
    fn nft_revoke_all(&mut self,token_id:TokenId){self.tokens.nft_revoke_all(token_id)}
    fn nft_is_approved(&self,token_id:TokenId,approved_account_id:AccountId,approval_id:Option<u64>)->bool{self.tokens.nft_is_approved(token_id,approved_account_id,approval_id)}
}
#[near]
impl NonFungibleTokenEnumeration for EchoNFT {
    fn nft_total_supply(&self)->U128{self.tokens.nft_total_supply()}
    fn nft_tokens(&self,from_index:Option<U128>,limit:Option<u64>)->Vec<Token>{self.tokens.nft_tokens(from_index,Some(limit.unwrap_or(50).min(100)))}
    fn nft_supply_for_owner(&self,account_id:AccountId)->U128{self.tokens.nft_supply_for_owner(account_id)}
    fn nft_tokens_for_owner(&self,account_id:AccountId,from_index:Option<U128>,limit:Option<u64>)->Vec<Token>{self.tokens.nft_tokens_for_owner(account_id,from_index,Some(limit.unwrap_or(50).min(100)))}
}

#[near]
impl NonFungibleTokenMetadataProvider for EchoNFT {
    fn nft_metadata(&self) -> NFTContractMetadata { self.metadata.get().unwrap() }
}

#[cfg(test)]
mod tests {
    use super::*;
    use near_sdk::test_utils::VMContextBuilder;
    use near_sdk::{testing_env, NearToken};
    fn account(s:&str)->AccountId{s.parse().unwrap()}
    fn context(who:&str){let mut c=VMContextBuilder::new();c.current_account_id(account("nft.testnet")).predecessor_account_id(account(who)).attached_deposit(NearToken::from_near(1));testing_env!(c.build());}
    fn args(epoch:u64)->(TokenMetadata,Commitment){let hash="01".repeat(32);(TokenMetadata{title:Some("Echo".into()),description:None,media:Some("ipfs://image".into()),media_hash:Some(Base64VecU8(vec![1;32])),copies:Some(1),issued_at:None,expires_at:None,starts_at:None,updated_at:None,extra:None,reference:Some("ipfs://provenance".into()),reference_hash:Some(Base64VecU8(vec![1;32]))},Commitment{epoch,image_hash:hash.clone(),provenance_hash:hash.clone(),merkle_root:hash.clone(),seed:hash,block_hash:"block".into()})}
    #[test]fn mint_and_transfer(){context("minter.testnet");let mut c=EchoNFT::new(account("owner.testnet"),account("minter.testnet"));let(m,p)=args(1);let token=c.mint_weekly_artwork(account("alice.testnet"),m,p);assert_eq!(token.token_id,"ECHO-000001");assert_eq!(c.get_epoch_token(1),Some(token.token_id.clone()));context("alice.testnet");let mut ctx=VMContextBuilder::new();ctx.current_account_id(account("nft.testnet")).predecessor_account_id(account("alice.testnet")).attached_deposit(NearToken::from_yoctonear(1));testing_env!(ctx.build());use near_contract_standards::non_fungible_token::core::NonFungibleTokenCore;c.nft_transfer(account("bob.testnet"),token.token_id.clone(),None,None);assert_eq!(c.nft_token(token.token_id).unwrap().owner_id,account("bob.testnet"));}
    #[test]fn durable_auction_delivery_survives_winner_resale(){
        context("minter.testnet");let mut c=EchoNFT::new_production(account("owner.testnet"),account("minter.testnet"),account("auction.testnet"));
        let(m,p)=args(1);let token=c.mint_weekly_artwork(account("auction.testnet"),m,p);
        assert!(c.get_auction_delivery(token.token_id.clone()).is_none());
        let mut ctx=VMContextBuilder::new();ctx.current_account_id(account("nft.testnet")).predecessor_account_id(account("auction.testnet")).attached_deposit(NearToken::from_yoctonear(1));testing_env!(ctx.build());
        c.nft_transfer(account("alice.testnet"),token.token_id.clone(),None,None);
        assert_eq!(c.get_auction_delivery(token.token_id.clone()).unwrap().receiver_id,account("alice.testnet"));
        ctx.predecessor_account_id(account("alice.testnet"));testing_env!(ctx.build());
        c.nft_transfer(account("bob.testnet"),token.token_id.clone(),None,None);
        assert_eq!(c.nft_token(token.token_id.clone()).unwrap().owner_id,account("bob.testnet"));
        assert_eq!(c.get_auction_delivery(token.token_id).unwrap().receiver_id,account("alice.testnet"));
    }
    #[test]#[should_panic(expected="auction custody")]fn production_mint_rejects_wrong_custodian(){
        context("minter.testnet");let mut c=EchoNFT::new_production(account("owner.testnet"),account("minter.testnet"),account("auction.testnet"));let(m,p)=args(1);c.mint_weekly_artwork(account("alice.testnet"),m,p);
    }
    #[test]#[should_panic(expected="Unauthorized")]fn unauthorized(){context("bad.testnet");let mut c=EchoNFT::new(account("owner.testnet"),account("minter.testnet"));let(m,p)=args(1);c.mint_weekly_artwork(account("alice.testnet"),m,p);}
    #[test]#[should_panic(expected="Epoch already")]fn duplicate_epoch(){context("minter.testnet");let mut c=EchoNFT::new(account("owner.testnet"),account("minter.testnet"));let(m,p)=args(1);c.mint_weekly_artwork(account("alice.testnet"),m.clone(),p.clone());c.mint_weekly_artwork(account("alice.testnet"),m,p);}
    #[test]#[should_panic(expected="Duplicate image")]fn duplicate_image(){context("minter.testnet");let mut c=EchoNFT::new(account("owner.testnet"),account("minter.testnet"));let(m,p)=args(1);c.mint_weekly_artwork(account("alice.testnet"),m,p);let(m,p)=args(2);c.mint_weekly_artwork(account("alice.testnet"),m,p);}
}
