//! IDART1 geometry and immutable SVG renderer live in this keyless collection.
//! Separate verification calls keep both large views outside the final mint gas.
use super::*;
use near_sdk::NearToken;
use near_sdk::base64::{engine::general_purpose::STANDARD, Engine};
use near_sdk::json_types::U64;

pub const FORMAT: &str = "intent-distortions-weekly-onchain-v1";
const CHUNK: usize = 16384;

#[near(serializers=[borsh])]
pub struct FrozenEdition {
    release_ns: U64,
    metadata: Option<TokenMetadata>,
    metadata_hash: Vec<u8>,
    commitment: Commitment,
    recipe_hash: String,
    recipe_bytes: u32,
    data: Vec<u8>,
    static_hash: String,
    animated_hash: String,
    static_verified: bool,
    animated_verified: bool,
    minted: bool,
    prepaid: u128,
    storage_bytes: u64,
}
fn digest(bytes: &[u8]) -> String { crate::beacon::hex(&env::sha256(bytes)) }
fn hash(value: &str) {
    assert!(value.len()==64 && value.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)), "Invalid SHA-256");
}

#[near]
impl EchoNFT {
    pub fn get_onchain_format(&self) -> String { FORMAT.into() }

    #[payable]
    pub fn begin_onchain_art(&mut self, release_ns: U64, metadata: TokenMetadata, commitment: Commitment,
        recipe_sha256: String, recipe_bytes: u32, static_sha256: String, animated_sha256: String) {
        assert_eq!(env::predecessor_account_id(), self.minter, "Minter only");
        assert!(env::current_account_id().as_str().ends_with(".testnet"), "Testnet only");
        assert!(recipe_bytes>76 && recipe_bytes as usize<=renderer::MAX_BYTES, "Recipe budget");
        for value in [&recipe_sha256,&static_sha256,&animated_sha256] { hash(value); }
        assert_eq!(commitment.image_hash,static_sha256,"Static commitment mismatch");
        let token=format!("ECHO-{:06}",commitment.epoch);
        assert!(self.frozen_art.get(&token).is_none() && self.epochs.get(&commitment.epoch).is_none(),"Edition already prepared");
        assert_eq!(metadata.media.as_deref(),Some(format!("near://{}/{token}/static.svg",env::current_account_id()).as_str()),"Onchain media required");
        let reference=metadata.reference.as_ref().expect("Inline provenance required");
        assert!(reference.starts_with("data:application/json;base64,") && reference.len()<=20000,"Inline provenance budget");
        let public=STANDARD.decode(reference.split_once(',').unwrap().1).expect("Invalid provenance");
        assert_eq!(digest(&public),commitment.provenance_hash,"Provenance hash mismatch");
        let document:near_sdk::serde_json::Value=near_sdk::serde_json::from_slice(&public).expect("Invalid provenance JSON");
        assert_eq!(document["seed"].as_str(),Some(commitment.seed.as_str()),"Seed mismatch");
        assert_eq!(document["merkle_root"].as_str(),Some(commitment.merkle_root.as_str()),"Merkle root mismatch");
        assert_eq!(document["recipe_sha256"].as_str(),Some(recipe_sha256.as_str()),"Recipe binding mismatch");
        assert_eq!(document["ai"]["provider"].as_str(),Some("near_ai_cloud"),"NEAR AI direction required");
        assert_eq!(document["ai"]["policy"].as_str(),Some("first-valid-v1"),"Frozen AI direction required");
        let required=(recipe_bytes as u128+32000)*env::storage_byte_cost().as_yoctonear();
        assert!(env::attached_deposit().as_yoctonear()>=required,"Prepay upload storage");
        let initial=env::storage_usage();
        let metadata_hash=env::sha256(&near_sdk::serde_json::to_vec(&near_sdk::serde_json::to_value(&metadata).unwrap()).unwrap());
        self.frozen_art.insert(&token,&FrozenEdition{release_ns,metadata:Some(metadata),metadata_hash,commitment,
            recipe_hash:recipe_sha256,recipe_bytes,data:vec![],static_hash:static_sha256,animated_hash:animated_sha256,
            static_verified:false,animated_verified:false,minted:false,prepaid:env::attached_deposit().as_yoctonear(),storage_bytes:0});
        let mut e=self.frozen_art.get(&token).unwrap();e.storage_bytes=env::storage_usage()-initial;self.frozen_art.insert(&token,&e);
    }

    pub fn append_onchain_recipe(&mut self, token_id: String, offset:u32, data:Base64VecU8) {
        assert_eq!(env::predecessor_account_id(),self.minter,"Minter only");
        let mut e=self.frozen_art.get(&token_id).expect("Unknown edition");
        assert!(!e.minted && !e.static_verified && !e.animated_verified,"Artwork frozen");
        assert_eq!(offset as usize,e.data.len(),"Unexpected offset");
        assert!(!data.0.is_empty() && data.0.len()<=CHUNK && e.data.len()+data.0.len()<=e.recipe_bytes as usize,"Chunk budget");
        let initial=env::storage_usage();e.data.extend(data.0);self.frozen_art.insert(&token_id,&e);
        e.storage_bytes+=env::storage_usage()-initial;self.frozen_art.insert(&token_id,&e);
    }

    pub fn verify_onchain_view(&mut self,token_id:String,animated:bool) {
        assert_eq!(env::predecessor_account_id(),self.minter,"Minter only");
        let mut e=self.frozen_art.get(&token_id).expect("Unknown edition");
        assert!(!e.minted,"Artwork frozen");
        assert_eq!(e.data.len(),e.recipe_bytes as usize,"Incomplete upload");
        assert_eq!(digest(&e.data),e.recipe_hash,"Recipe hash mismatch");
        let metadata=e.metadata.as_ref().unwrap();
        let scene=renderer::decode(&e.data).expect("Invalid recipe");
        let reference=metadata.reference.as_ref().unwrap();
        let public:near_sdk::serde_json::Value=near_sdk::serde_json::from_slice(&STANDARD.decode(reference.split_once(',').unwrap().1).unwrap()).unwrap();
        let family=["orbital_network","fractal_branches","crystalline","flow_field","spiral_constellation","particle_nebula"][scene.style as usize/3];
        assert_eq!(public["direction"]["composition"].as_str(),Some(family),"Recipe family mismatch");
        let svg=renderer::svg(&scene,metadata.title.as_deref().unwrap_or(""),animated).expect("SVG budget");
        assert_eq!(digest(svg.as_bytes()),if animated {e.animated_hash.clone()} else {e.static_hash.clone()},"SVG hash mismatch");
        if animated {e.animated_verified=true} else {e.static_verified=true}
        self.frozen_art.insert(&token_id,&e);
    }

    /// No rendering here: the verified recipe becomes immutable and enters auction custody.
    #[payable]
    pub fn mint_onchain_art(&mut self,token_id:String) -> Token {
        assert_eq!(env::predecessor_account_id(),self.minter,"Minter only");
        let mut e=self.frozen_art.get(&token_id).expect("Unknown edition");
        assert!(!e.minted && e.static_verified && e.animated_verified,"Both views must be frozen before mint");
        let metadata=e.metadata.take().unwrap();
        let token=self.mint_scheduled_impl(e.release_ns,metadata,e.commitment.clone());
        assert_eq!(token.token_id,token_id,"Token mismatch");
        e.minted=true;self.frozen_art.insert(&token_id,&e);
        let charge=e.storage_bytes as u128*env::storage_byte_cost().as_yoctonear();
        assert!(e.prepaid>=charge,"Upload storage underfunded");
        let refund=e.prepaid-charge;
        if refund>0 { Promise::new(self.minter.clone()).transfer(NearToken::from_yoctonear(refund)).detach(); }
        token
    }

    pub fn get_onchain_art(&self,token_id:String) -> Option<near_sdk::serde_json::Value> {
        let e=self.frozen_art.get(&token_id)?;
        Some(near_sdk::serde_json::json!({"format":FORMAT,"token_id":token_id,"recipe_sha256":e.recipe_hash,
            "recipe_bytes":e.recipe_bytes,"uploaded_bytes":e.data.len(),"static_sha256":e.static_hash,
            "animated_sha256":e.animated_hash,"static_verified":e.static_verified,"animated_verified":e.animated_verified,
            "sealed":e.minted,"metadata_sha256":crate::beacon::hex(&e.metadata_hash),"commitment":e.commitment,"release_ns":e.release_ns}))
    }
    pub fn get_recipe_chunk(&self,token_id:String,offset:u32) -> Base64VecU8 {
        let e=self.frozen_art.get(&token_id).expect("Unknown edition");
        // Minter recovery can inspect its committed draft; no overwrite API exists.
        let start=offset as usize;assert!(start<=e.data.len(),"Offset outside recipe");
        Base64VecU8(e.data[start..(start+CHUNK).min(e.data.len())].to_vec())
    }
    pub fn get_static_svg(&self,token_id:String) -> String { self.frozen_svg(&token_id,false) }
    pub fn get_animated_svg(&self,token_id:String) -> String { self.frozen_svg(&token_id,true) }
    /// For low-gas ownership callbacks; metadata contains compact NEAR URIs.
    pub fn nft_token_compact(&self,token_id:String) -> Option<Token> { self.tokens.nft_token(token_id) }
}

#[cfg(test)]
mod tests {
    use super::*;
    use near_sdk::{testing_env,test_utils::VMContextBuilder};
    fn context(who:&str,deposit:u128){
        testing_env!(VMContextBuilder::new().current_account_id("nft.testnet".parse().unwrap())
            .predecessor_account_id(who.parse().unwrap()).account_balance(NearToken::from_near(100))
            .attached_deposit(NearToken::from_yoctonear(deposit)).prepaid_gas(near_sdk::Gas::from_tgas(300))
            .block_timestamp(calendar::FIRST_EDITION).build());
    }
    fn recipe()->Vec<u8>{
        let mut d=b"IDART1".to_vec();d.extend(1440u16.to_be_bytes());d.extend(1440u16.to_be_bytes());
        d.extend([8,12,19,16,20,30]);d.extend(1u16.to_be_bytes());d.extend(32000u16.to_be_bytes());d.extend(150u16.to_be_bytes());
        d.extend([128;48]);d.push(6);d.extend(500u16.to_be_bytes());d.push(1);d.extend(6000u16.to_be_bytes());
        d.extend([0,100,200,180,200,4,0,0]);for n in [1000u32,720000,720000]{d.extend(&n.to_be_bytes()[1..]);}d
    }
    fn prepared()->EchoNFT{
        context("operator.testnet",0);
        let mut c=EchoNFT::new_economy("gov.testnet".parse().unwrap(),"operator.testnet".parse().unwrap(),
            "auction.testnet".parse().unwrap(),"team.testnet".parse().unwrap(),"treasury.testnet".parse().unwrap());
        let data=recipe();let scene=renderer::decode(&data).unwrap();
        let still=digest(renderer::svg(&scene,"Frozen",false).unwrap().as_bytes());
        let animated=digest(renderer::svg(&scene,"Frozen",true).unwrap().as_bytes());
        let proof=near_sdk::serde_json::to_vec(&near_sdk::serde_json::json!({"seed":"01".repeat(32),"merkle_root":"02".repeat(32),
            "recipe_sha256":digest(&data),"direction":{"composition":"crystalline"},"ai":{"provider":"near_ai_cloud","policy":"first-valid-v1"}})).unwrap();
        let metadata=TokenMetadata{title:Some("Frozen".into()),copies:Some(1),media:Some("near://nft.testnet/ECHO-000001/static.svg".into()),
            media_hash:Some(Base64VecU8(env::sha256(renderer::svg(&scene,"Frozen",false).unwrap().as_bytes()))),
            reference:Some(format!("data:application/json;base64,{}",STANDARD.encode(&proof))),reference_hash:Some(Base64VecU8(env::sha256(&proof))),..Default::default()};
        context("operator.testnet",10u128.pow(24));
        c.begin_onchain_art(U64(calendar::FIRST_EDITION),metadata,Commitment{epoch:1,image_hash:still.clone(),provenance_hash:digest(&proof),
            merkle_root:"02".repeat(32),seed:"01".repeat(32),block_hash:"verified-source-block".into()},digest(&data),data.len() as u32,still,animated);
        context("operator.testnet",0);c.append_onchain_recipe("ECHO-000001".into(),0,Base64VecU8(data));c
    }
    fn minted()->EchoNFT{
        let mut c=prepared();c.verify_onchain_view("ECHO-000001".into(),false);c.verify_onchain_view("ECHO-000001".into(),true);
        context("operator.testnet",10u128.pow(24));c.mint_onchain_art("ECHO-000001".into());c
    }
    #[test]
    fn frozen_november_edition_enters_auction_and_transfer_preserves_both_views(){
        let mut c=minted();let token="ECHO-000001".to_string();
        let still=c.get_static_svg(token.clone());let motion=c.get_animated_svg(token.clone());let before=c.get_onchain_art(token.clone());
        assert_eq!(c.get_economy()["next_close"],202611);
        assert_eq!(c.nft_token_compact(token.clone()).unwrap().owner_id.as_str(),"auction.testnet");
        assert!(c.nft_token(token.clone()).unwrap().metadata.unwrap().media.unwrap().starts_with("data:image/svg+xml;base64,"));
        assert_eq!(c.get_recipe_chunk(token.clone(),0).0,recipe());
        context("auction.testnet",1);c.nft_transfer("collector.testnet".parse().unwrap(),token.clone(),None,None);
        assert_eq!(c.get_onchain_art(token.clone()),before);assert_eq!(c.get_static_svg(token.clone()),still);assert_eq!(c.get_animated_svg(token),motion);
    }
    #[test]
    #[should_panic(expected="Both views must be frozen")]
    fn cannot_mint_before_both_views_verified(){let mut c=prepared();c.verify_onchain_view("ECHO-000001".into(),false);c.mint_onchain_art("ECHO-000001".into());}
    #[test]
    #[should_panic(expected="Artwork frozen")]
    fn cannot_change_sealed_geometry(){let mut c=minted();context("operator.testnet",0);c.append_onchain_recipe("ECHO-000001".into(),0,Base64VecU8(vec![1]));}
    #[test]
    #[should_panic(expected="Both views must be frozen")]
    fn cannot_mint_twice(){let mut c=minted();c.mint_onchain_art("ECHO-000001".into());}
    #[test]
    #[should_panic(expected="Use staged frozen")]
    fn hosted_mint_cannot_bypass_frozen_art(){let mut c=prepared();let e=c.frozen_art.get(&"ECHO-000001".into()).unwrap();c.mint_scheduled_artwork(e.release_ns,e.metadata.unwrap(),e.commitment);}
}
impl EchoNFT {
    fn frozen_svg(&self,token:&str,animated:bool) -> String {
        let e=self.frozen_art.get(&token.to_string()).expect("Unknown edition");
        assert!(e.minted,"Edition not minted");
        let title=self.tokens.token_metadata_by_id.as_ref().unwrap().get(&token.to_string()).unwrap().title.unwrap_or_default();
        renderer::svg(&renderer::decode(&e.data).unwrap(),&title,animated).unwrap()
    }
    pub(crate) fn frozen_token(&self,mut token:Token) -> Token {
        if self.frozen_art.get(&token.token_id).map(|e| e.minted).unwrap_or(false) {
            if let Some(metadata)=token.metadata.as_mut() {
                metadata.media=Some(format!("data:image/svg+xml;base64,{}",STANDARD.encode(self.frozen_svg(&token.token_id,false))));
            }
        }
        token
    }
}
