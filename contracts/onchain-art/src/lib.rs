//! Separate immutable onchain-art NFT prototype. No economy or upgrade authority.
mod renderer;
use near_contract_standards::non_fungible_token::core::{
    NonFungibleTokenCore, NonFungibleTokenResolver,
};
use near_contract_standards::non_fungible_token::enumeration::NonFungibleTokenEnumeration;
use near_contract_standards::non_fungible_token::metadata::{
    NFTContractMetadata, NonFungibleTokenMetadataProvider, TokenMetadata, NFT_METADATA_SPEC,
};
use near_contract_standards::non_fungible_token::{NonFungibleToken, Token, TokenId};
use near_sdk::base64::{engine::general_purpose::STANDARD, Engine};
use near_sdk::collections::{LookupMap, UnorderedSet};
use near_sdk::json_types::{Base64VecU8, U128};
use near_sdk::{
    env, near, AccountId, BorshStorageKey, NearToken, PanicOnDefault, Promise, PromiseOrValue,
};

const FORMAT: &str = "intent-distortions-onchain-v1";
const CHUNK: usize = 16384;

#[derive(BorshStorageKey)]
#[near(serializers=[borsh])]
enum Key {
    Tokens,
    Metadata,
    Enumeration,
    Editions,
    RecipeHashes,
    Sources,
}

#[near(serializers=[borsh,json])]
#[derive(Clone)]
#[serde(deny_unknown_fields)]
pub struct ArtMetadata {
    pub title: String,
    pub description: String,
    pub family: String,
    pub direction: String,
    pub ai_model: String,
    pub seed: String,
    pub merkle_root: String,
    pub source_provenance: String,
    pub source_manifest: String,
    pub source_image: String,
    pub source_edition: String,
    pub source_start: String,
    pub source_end: String,
    pub record_count: u32,
    pub traits: String,
    pub motion: String,
    pub prototype: bool,
}
#[near(serializers=[borsh])]
pub struct Edition {
    meta: ArtMetadata,
    receiver: AccountId,
    expected_hash: Vec<u8>,
    expected_length: u32,
    data: Vec<u8>,
    sealed: bool,
    static_hash: Option<Vec<u8>>,
    animated_hash: Option<Vec<u8>>,
    storage_bytes: u64,
    prepaid: u128,
    content_hash: Vec<u8>,
}
#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct OnchainArt {
    tokens: NonFungibleToken,
    minter: AccountId,
    editions: LookupMap<TokenId, Edition>,
    recipe_hashes: UnorderedSet<Vec<u8>>,
    sources: UnorderedSet<String>,
}
fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
fn hash_arg(value: &str) -> Vec<u8> {
    assert!(
        value.len() == 64
            && value
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)),
        "Invalid SHA-256"
    );
    (0..64)
        .step_by(2)
        .map(|i| u8::from_str_radix(&value[i..i + 2], 16).unwrap())
        .collect()
}
fn validate_meta(m: &ArtMetadata) {
    assert!(
        !m.title.is_empty() && m.title.len() <= 100 && m.description.len() <= 1500,
        "Title/description budget"
    );
    assert!(
        m.ai_model.len() <= 160 && !m.ai_model.is_empty(),
        "NEAR AI model required"
    );
    assert!(
        m.source_edition.len() <= 64 && m.record_count > 0,
        "Invalid source"
    );
    assert!(
        m.direction.len() <= 2400 && m.traits.len() <= 6000 && m.motion.len() <= 1200,
        "Metadata budget"
    );
    assert!(
        m.source_start.parse::<u64>().unwrap() < m.source_end.parse::<u64>().unwrap(),
        "Invalid source interval"
    );
    for h in [
        &m.seed,
        &m.merkle_root,
        &m.source_provenance,
        &m.source_manifest,
        &m.source_image,
    ] {
        hash_arg(h);
    }
    let direction: near_sdk::serde_json::Value =
        near_sdk::serde_json::from_str(&m.direction).expect("Invalid direction");
    assert_eq!(
        direction["composition"].as_str(),
        Some(m.family.as_str()),
        "Family differs from AI direction"
    );
    assert!(
        [
            "orbital_network",
            "fractal_branches",
            "crystalline",
            "flow_field",
            "spiral_constellation",
            "particle_nebula"
        ]
        .contains(&m.family.as_str()),
        "Unknown family"
    );
    let _: Vec<near_sdk::serde_json::Value> =
        near_sdk::serde_json::from_str(&m.traits).expect("Invalid traits");
    let _: near_sdk::serde_json::Value =
        near_sdk::serde_json::from_str(&m.motion).expect("Invalid motion metadata");
}

#[near]
impl OnchainArt {
    #[init]
    pub fn new(minter: AccountId) -> Self {
        Self {
            tokens: NonFungibleToken::new(
                Key::Tokens,
                minter.clone(),
                Some(Key::Metadata),
                Some(Key::Enumeration),
                None::<Key>,
            ),
            minter,
            editions: LookupMap::new(Key::Editions),
            recipe_hashes: UnorderedSet::new(Key::RecipeHashes),
            sources: UnorderedSet::new(Key::Sources),
        }
    }
    /// A draft's hash, artistic direction and beneficiary bind on the first call.
    #[payable]
    pub fn begin_edition(
        &mut self,
        token_id: TokenId,
        metadata: ArtMetadata,
        receiver_id: AccountId,
        recipe_sha256: String,
        recipe_bytes: u32,
    ) {
        assert_eq!(env::predecessor_account_id(), self.minter, "Minter only");
        assert!(
            !token_id.is_empty()
                && token_id.len() <= 64
                && token_id
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b == b'-'),
            "Invalid token ID"
        );
        assert!(
            self.editions.get(&token_id).is_none(),
            "Edition already prepared"
        );
        assert!(
            recipe_bytes > 76 && recipe_bytes as usize <= renderer::MAX_BYTES,
            "Recipe budget"
        );
        validate_meta(&metadata);
        let hash = hash_arg(&recipe_sha256);
        assert!(!self.recipe_hashes.contains(&hash), "Duplicate recipe");
        assert!(
            !self.sources.contains(&metadata.source_provenance),
            "Source edition already registered"
        );
        let required = NearToken::from_yoctonear(
            (recipe_bytes as u128 + 24000) * env::storage_byte_cost().as_yoctonear(),
        );
        assert!(
            env::attached_deposit() >= required,
            "Prepay bounded upload storage"
        );
        let storage_start = env::storage_usage();
        let commitment = env::sha256(
            &near_sdk::serde_json::to_vec(&(
                FORMAT,
                &token_id,
                &metadata,
                &receiver_id,
                &recipe_sha256,
            ))
            .unwrap(),
        );
        self.recipe_hashes.insert(&hash);
        self.sources.insert(&metadata.source_provenance);
        self.editions.insert(
            &token_id,
            &Edition {
                meta: metadata,
                receiver: receiver_id,
                expected_hash: hash,
                expected_length: recipe_bytes,
                data: Vec::new(),
                sealed: false,
                static_hash: None,
                animated_hash: None,
                storage_bytes: 0,
                prepaid: env::attached_deposit().as_yoctonear(),
                content_hash: commitment,
            },
        );
        let mut e = self.editions.get(&token_id).unwrap();
        e.storage_bytes = env::storage_usage() - storage_start;
        self.editions.insert(&token_id, &e);
    }
    /// Append-only uploads. Duplicate/out-of-order chunks are rejected, not replaced.
    pub fn append_recipe(&mut self, token_id: TokenId, offset: u32, data: Base64VecU8) {
        assert_eq!(env::predecessor_account_id(), self.minter, "Minter only");
        let mut e = self.editions.get(&token_id).expect("Unknown edition");
        assert!(!e.sealed, "Edition sealed");
        assert_eq!(offset as usize, e.data.len(), "Unexpected offset");
        assert!(!data.0.is_empty() && data.0.len() <= CHUNK, "Chunk budget");
        assert!(
            e.data.len() + data.0.len() <= e.expected_length as usize,
            "Upload exceeds commitment"
        );
        let storage_start = env::storage_usage();
        e.data.extend(data.0);
        self.editions.insert(&token_id, &e);
        e.storage_bytes += env::storage_usage() - storage_start;
        self.editions.insert(&token_id, &e);
    }
    /// Atomically validates both views, seals the artwork and mints its sole NFT.
    pub fn seal_and_mint(&mut self, token_id: TokenId) -> Token {
        assert_eq!(env::predecessor_account_id(), self.minter, "Minter only");
        let mut e = self.editions.get(&token_id).expect("Unknown edition");
        assert!(!e.sealed, "Edition sealed");
        assert_eq!(
            e.data.len(),
            e.expected_length as usize,
            "Incomplete upload"
        );
        assert_eq!(
            env::sha256(&e.data),
            e.expected_hash,
            "Recipe hash mismatch"
        );
        let scene = renderer::decode(&e.data).expect("Invalid recipe");
        let motion: near_sdk::serde_json::Value =
            near_sdk::serde_json::from_str(&e.meta.motion).unwrap();
        for (name, value) in [
            ("profile", scene.style / 3),
            ("variant", scene.style % 3),
            ("strength", scene.strength),
            ("direction", scene.direction),
            ("route_period_ms", scene.route_period),
        ] {
            assert_eq!(
                motion[name].as_u64(),
                Some(value as u64),
                "Motion metadata differs from recipe"
            );
        }
        assert_eq!(
            [
                "orbital_network",
                "fractal_branches",
                "crystalline",
                "flow_field",
                "spiral_constellation",
                "particle_nebula"
            ][scene.style as usize / 3],
            e.meta.family,
            "Motion family differs"
        );
        let static_svg =
            renderer::svg(&scene, &e.meta.title, false).expect("Static SVG exceeds budget");
        let animated_svg =
            renderer::svg(&scene, &e.meta.title, true).expect("Animated SVG exceeds budget");
        e.static_hash = Some(env::sha256(static_svg.as_bytes()));
        e.animated_hash = Some(env::sha256(animated_svg.as_bytes()));
        e.sealed = true;
        let metadata=TokenMetadata{title:Some(e.meta.title.clone()),description:Some(e.meta.description.clone()),copies:Some(1),
            extra:Some(near_sdk::serde_json::json!({"format":FORMAT,"prototype":e.meta.prototype,"artwork_commitment":hex(&e.content_hash),
                "recipe_sha256":hex(&e.expected_hash),"static_sha256":hex(e.static_hash.as_ref().unwrap()),
                "animated_sha256":hex(e.animated_hash.as_ref().unwrap()),"animation_method":"get_animated_svg"}).to_string()),
            ..Default::default()};
        let storage_start = env::storage_usage();
        let token = self.tokens.internal_mint_with_refund(
            token_id.clone(),
            e.receiver.clone(),
            Some(metadata),
            None,
        );
        near_contract_standards::non_fungible_token::events::NftMint {
            owner_id: &e.receiver,
            token_ids: &[&token_id],
            memo: Some("Sealed onchain artwork"),
        }
        .emit();
        self.editions.insert(&token_id, &e);
        let used = e.storage_bytes + env::storage_usage().checked_sub(storage_start).unwrap();
        e.storage_bytes = used;
        self.editions.insert(&token_id, &e);
        let charge = used as u128 * env::storage_byte_cost().as_yoctonear();
        assert!(e.prepaid >= charge, "Storage prepayment insufficient");
        let refund = e.prepaid - charge;
        if refund > 0 {
            Promise::new(self.minter.clone())
                .transfer(NearToken::from_yoctonear(refund))
                .detach();
        }
        env::log_str(&format!(
            "EVENT_JSON:{}",
            near_sdk::serde_json::json!({"standard":"intent_distortions_art","version":"1.0.0","event":"art_sealed",
            "data":[{"token_id":token_id,"artwork_commitment":hex(&e.content_hash),"recipe_sha256":hex(&e.expected_hash),
                "static_sha256":hex(e.static_hash.as_ref().unwrap()),"animated_sha256":hex(e.animated_hash.as_ref().unwrap()),"storage_bytes":used}]})
        ));
        token
    }
    pub fn get_config(&self) -> near_sdk::serde_json::Value {
        near_sdk::serde_json::json!({"format":FORMAT,"minter":self.minter,"max_recipe_bytes":renderer::MAX_BYTES,
            "chunk_bytes":CHUNK,"renderer":"idart1-svg-1","upgrade_method":false,"external_dependencies":false})
    }
    pub fn get_edition(&self, token_id: TokenId) -> Option<near_sdk::serde_json::Value> {
        let e = self.editions.get(&token_id)?;
        Some(
            near_sdk::serde_json::json!({"format":FORMAT,"token_id":token_id,"metadata":e.meta,"sealed":e.sealed,
            "recipe_bytes":e.expected_length,"uploaded_bytes":e.data.len(),"recipe_sha256":hex(&e.expected_hash),
            "owner_id":self.tokens.owner_by_id.get(&token_id),"artwork_commitment":hex(&e.content_hash),"static_sha256":e.static_hash.map(|h|hex(&h)),
            "animated_sha256":e.animated_hash.map(|h|hex(&h))}),
        )
    }
    pub fn get_recipe_chunk(&self, token_id: TokenId, offset: u32) -> Base64VecU8 {
        let e = self.editions.get(&token_id).expect("Unknown edition");
        assert!(e.sealed, "Edition not sealed");
        let start = offset as usize;
        assert!(start <= e.data.len(), "Offset outside recipe");
        Base64VecU8(e.data[start..(start + CHUNK).min(e.data.len())].to_vec())
    }
    pub fn get_static_svg(&self, token_id: TokenId) -> String {
        self.render(&token_id, false)
    }
    pub fn get_animated_svg(&self, token_id: TokenId) -> String {
        self.render(&token_id, true)
    }
}
impl OnchainArt {
    fn render(&self, token: &str, animated: bool) -> String {
        let e = self
            .editions
            .get(&token.to_string())
            .expect("Unknown edition");
        assert!(e.sealed, "Edition not sealed");
        renderer::svg(&renderer::decode(&e.data).unwrap(), &e.meta.title, animated).unwrap()
    }
    fn with_media(&self, mut token: Token) -> Token {
        if let Some(metadata) = token.metadata.as_mut() {
            let svg = self.render(&token.token_id, false);
            metadata.media_hash = Some(Base64VecU8(env::sha256(svg.as_bytes())));
            metadata.media = Some(format!(
                "data:image/svg+xml;base64,{}",
                STANDARD.encode(svg)
            ));
            let e = self.editions.get(&token.token_id).unwrap();
            let mut extra: near_sdk::serde_json::Value =
                near_sdk::serde_json::from_str(metadata.extra.as_ref().unwrap()).unwrap();
            extra["attributes"] = near_sdk::serde_json::from_str(&e.meta.traits).unwrap();
            extra["artistic_director"] = near_sdk::serde_json::json!({"provider":"near_ai_cloud","model":e.meta.ai_model,"policy":"persisted-first-valid"});
            extra["motion"] = near_sdk::serde_json::from_str(&e.meta.motion).unwrap();
            metadata.extra = Some(extra.to_string());
        }
        token
    }
}
#[near]
impl NonFungibleTokenCore for OnchainArt {
    #[payable]
    fn nft_transfer(
        &mut self,
        receiver_id: AccountId,
        token_id: TokenId,
        approval_id: Option<u64>,
        memo: Option<String>,
    ) {
        self.tokens
            .nft_transfer(receiver_id, token_id, approval_id, memo);
    }
    #[payable]
    fn nft_transfer_call(
        &mut self,
        receiver_id: AccountId,
        token_id: TokenId,
        approval_id: Option<u64>,
        memo: Option<String>,
        msg: String,
    ) -> PromiseOrValue<bool> {
        self.tokens
            .nft_transfer_call(receiver_id, token_id, approval_id, memo, msg)
    }
    fn nft_token(&self, token_id: TokenId) -> Option<Token> {
        self.tokens.nft_token(token_id).map(|t| self.with_media(t))
    }
}
#[near]
impl NonFungibleTokenResolver for OnchainArt {
    #[private]
    fn nft_resolve_transfer(
        &mut self,
        previous_owner_id: AccountId,
        receiver_id: AccountId,
        token_id: TokenId,
        approved_account_ids: Option<std::collections::HashMap<AccountId, u64>>,
    ) -> bool {
        self.tokens.nft_resolve_transfer(
            previous_owner_id,
            receiver_id,
            token_id,
            approved_account_ids,
        )
    }
}
#[near]
impl NonFungibleTokenEnumeration for OnchainArt {
    fn nft_total_supply(&self) -> U128 {
        self.tokens.nft_total_supply()
    }
    fn nft_tokens(&self, from_index: Option<U128>, limit: Option<u64>) -> Vec<Token> {
        self.tokens
            .nft_tokens(from_index, Some(limit.unwrap_or(1).min(2)))
            .into_iter()
            .map(|t| self.with_media(t))
            .collect()
    }
    fn nft_supply_for_owner(&self, account_id: AccountId) -> U128 {
        self.tokens.nft_supply_for_owner(account_id)
    }
    fn nft_tokens_for_owner(
        &self,
        account_id: AccountId,
        from_index: Option<U128>,
        limit: Option<u64>,
    ) -> Vec<Token> {
        self.tokens
            .nft_tokens_for_owner(account_id, from_index, Some(limit.unwrap_or(1).min(2)))
            .into_iter()
            .map(|t| self.with_media(t))
            .collect()
    }
}
#[near]
impl NonFungibleTokenMetadataProvider for OnchainArt {
    fn nft_metadata(&self) -> NFTContractMetadata {
        NFTContractMetadata {
            spec: NFT_METADATA_SPEC.into(),
            name: "Intent Distortions — Onchain Studies".into(),
            symbol: "IDART".into(),
            icon: None,
            base_uri: None,
            reference: None,
            reference_hash: None,
        }
    }
}

#[cfg(test)]
mod tests;
