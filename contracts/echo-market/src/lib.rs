#[path = "../../lab_clock.rs"]
mod clock;
use near_sdk::collections::{LookupMap, UnorderedMap};
use near_sdk::json_types::{U128, U64};
use near_sdk::{env, near, AccountId, Gas, NearToken, PanicOnDefault, Promise};
#[path = "../../echo-nft/src/calendar.rs"]
mod calendar;
mod royalties;
use royalties::{RoyaltyMonth, RoyaltyShare};

const STORAGE: u128 = 10u128.pow(22); // 0.01 NEAR per bounded record.
#[near(serializers=[borsh,json])]
#[derive(Clone, Default)]
pub struct Balance {
    pub storage_available: U128,
    pub credit: U128,
    pub withdrawing: U128,
}
#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct Sale {
    pub id: U64,
    pub buyer: AccountId,
    pub amount: U128,
    pub royalty_cycle: u32,
}
#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct Listing {
    pub token_id: String,
    pub seller: AccountId,
    pub approval_id: u64,
    pub nonce: U64,
    pub price: Option<U128>,
    pub expires_ns: U64,
    pub sale: Option<Sale>,
}
#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct Offer {
    pub id: U64,
    pub token_id: String,
    pub seller: AccountId,
    pub listing_nonce: U64,
    pub buyer: AccountId,
    pub amount: U128,
    pub expires_ns: U64,
    pub rights_hash: String,
}
#[near(serializers=[json])]
struct ListingArgs {
    price: Option<U128>,
    expires_ns: U64,
}
#[near_sdk::ext_contract(ext_nft)]
#[allow(dead_code)]
trait NFT {
    fn market_transfer(
        &mut self,
        token_id: String,
        receiver_id: AccountId,
        seller: AccountId,
        approval_id: u64,
        rights_hash: String,
    );
}
#[near_sdk::ext_contract(ext_self)]
#[allow(dead_code)]
trait Callbacks {
    fn resolve_sale(&mut self, token_id: String, sale_id: U64) -> bool;
    fn resolve_withdraw(&mut self, account: AccountId) -> bool;
}

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct EchoMarket {
    nft_contract: AccountId,
    primary_auction: AccountId,
    listings: UnorderedMap<String, Listing>,
    offers: UnorderedMap<u64, Offer>,
    balances: LookupMap<AccountId, Balance>,
    sequence: u64,
    creator: AccountId,
    royalty_months: UnorderedMap<u32, RoyaltyMonth>,
    royalty_shares: LookupMap<(u32, u64), RoyaltyShare>,
    next_royalty_close: u32,
    liability: u128,
}

#[near]
impl EchoMarket {
    #[init]
    pub fn new(nft_contract: AccountId, primary_auction: AccountId, creator: AccountId) -> Self {
        assert_ne!(nft_contract, env::current_account_id());
        assert_ne!(primary_auction, env::current_account_id());
        Self {
            nft_contract,
            primary_auction,
            listings: UnorderedMap::new(b"l"),
            offers: UnorderedMap::new(b"o"),
            balances: LookupMap::new(b"b"),
            sequence: 0,
            creator,
            royalty_months: UnorderedMap::new(b"rm".to_vec()),
            royalty_shares: LookupMap::new(b"rs".to_vec()),
            next_royalty_close: calendar::cycle(crate::clock::now()),
            liability: 0,
        }
    }
    pub fn get_config(&self) -> near_sdk::serde_json::Value {
        clock::describe(near_sdk::serde_json::json!({"version":"echo-market-1","nft_contract":self.nft_contract,
        "primary_auction":self.primary_auction,"creator":self.creator,"currency":"NEAR","fee_bps":500,"record_storage_yocto":STORAGE.to_string(),"transfer_schema":"echo-market-transfer-v1",
        "royalty_policy":"equal-per-nft-utc-cutoff-v1","next_royalty_close":self.next_royalty_close,"liability":self.liability.to_string()}))
    }
    #[payable]
    pub fn storage_deposit(&mut self) -> Balance {
        let account = env::predecessor_account_id();
        let mut paid = env::attached_deposit().as_yoctonear();
        let mut b = if let Some(b) = self.balances.get(&account) {
            b
        } else {
            assert!(paid >= STORAGE, "Registration requires 0.01 NEAR");
            paid -= STORAGE;
            Balance::default()
        };
        b.storage_available.0 = b.storage_available.0.checked_add(paid).unwrap();
        self.liability = self.liability.checked_add(paid).unwrap();
        self.balances.insert(&account, &b);
        self.solvent();
        b
    }
    pub fn get_balance(&self, account: AccountId) -> Balance {
        self.balances.get(&account).unwrap_or_default()
    }
    pub fn get_listing(&self, token_id: String) -> Option<Listing> {
        self.listings.get(&token_id)
    }
    pub fn get_listings(&self, offset: Option<u64>, limit: Option<u64>) -> Vec<Listing> {
        let v = self.listings.values_as_vector();
        let start = offset.unwrap_or(0);
        (start
            ..start
                .saturating_add(limit.unwrap_or(50).min(100))
                .min(v.len()))
            .filter_map(|i| v.get(i))
            .collect()
    }
    pub fn get_offers(&self, offset: Option<u64>, limit: Option<u64>) -> Vec<Offer> {
        let v = self.offers.values_as_vector();
        let start = offset.unwrap_or(0);
        (start
            ..start
                .saturating_add(limit.unwrap_or(50).min(100))
                .min(v.len()))
            .filter_map(|i| v.get(i))
            .collect()
    }
    pub fn get_offer(&self, id: U64) -> Option<Offer> {
        self.offers.get(&id.0)
    }
    /// Only NEP-178's callback from the fixed canonical NFT contract can list.
    pub fn nft_on_approve(
        &mut self,
        token_id: String,
        owner_id: AccountId,
        approval_id: u64,
        msg: String,
    ) {
        assert_eq!(
            env::predecessor_account_id(),
            self.nft_contract,
            "Canonical NFT only"
        );
        assert_ne!(
            owner_id, self.primary_auction,
            "Primary custody cannot list"
        );
        assert!(
            token_id.len() <= 64 && msg.len() <= 1024,
            "Bounded listing required"
        );
        let args: ListingArgs =
            near_sdk::serde_json::from_str(&msg).expect("Invalid listing parameters");
        self.expiry(args.expires_ns.0);
        if let Some(p) = args.price {
            assert!(p.0 > 0, "Positive price required");
        }
        if let Some(old) = self.listings.get(&token_id) {
            assert!(old.sale.is_none(), "Sale pending");
            self.release_storage(&old.seller);
        }
        self.charge_storage(&owner_id);
        let nonce = self.next();
        self.listings.insert(
            &token_id,
            &Listing {
                token_id: token_id.clone(),
                seller: owner_id,
                approval_id,
                nonce: U64(nonce),
                price: args.price,
                expires_ns: args.expires_ns,
                sale: None,
            },
        );
        self.event(
            "listed",
            near_sdk::serde_json::json!({"token_id":token_id,"nonce":nonce}),
        );
    }
    #[payable]
    pub fn cancel_listing(&mut self, token_id: String, nonce: U64) {
        near_sdk::assert_one_yocto();
        let l = self.listing(&token_id, nonce);
        assert!(l.sale.is_none(), "Sale pending");
        assert!(
            env::predecessor_account_id() == l.seller || crate::clock::now() >= l.expires_ns.0,
            "Seller only before expiry"
        );
        self.listings.remove(&token_id);
        self.release_storage(&l.seller);
    }
    #[payable]
    pub fn buy(&mut self, token_id: String, nonce: U64, rights_hash: String) -> Promise {
        let l = self.active(&token_id, nonce);
        let amount = l.price.expect("Offers only").0;
        assert_eq!(
            env::attached_deposit().as_yoctonear(),
            amount.checked_add(1).unwrap(),
            "Attach price plus one yocto"
        );
        let buyer = env::predecessor_account_id();
        self.registered(&buyer);
        self.liability = self.liability.checked_add(amount).unwrap();
        self.begin(l, buyer, amount, rights_hash)
    }
    #[payable]
    pub fn make_offer(
        &mut self,
        token_id: String,
        nonce: U64,
        amount: U128,
        expires_ns: U64,
        rights_hash: String,
    ) -> Offer {
        let l = self.active(&token_id, nonce);
        self.expiry(expires_ns.0);
        assert!(
            expires_ns.0 <= l.expires_ns.0,
            "Offer exceeds listing expiry"
        );
        self.hash(&rights_hash);
        assert!(amount.0 > 0, "Positive offer required");
        assert_eq!(
            env::attached_deposit().as_yoctonear(),
            amount.0.checked_add(1).unwrap(),
            "Attach offer plus one yocto"
        );
        let buyer = env::predecessor_account_id();
        assert_ne!(buyer, l.seller, "Self offer");
        self.charge_storage(&buyer);
        let id = self.next();
        let o = Offer {
            id: U64(id),
            token_id,
            seller: l.seller,
            listing_nonce: nonce,
            buyer,
            amount,
            expires_ns,
            rights_hash,
        };
        self.offers.insert(&id, &o);
        self.liability = self.liability.checked_add(amount.0).unwrap();
        self.solvent();
        o
    }
    #[payable]
    pub fn cancel_offer(&mut self, id: U64) {
        near_sdk::assert_one_yocto();
        let o = self.offers.get(&id.0).expect("Unknown offer");
        assert!(
            env::predecessor_account_id() == o.buyer || crate::clock::now() >= o.expires_ns.0,
            "Buyer only before expiry"
        );
        self.offers.remove(&id.0);
        self.release_storage(&o.buyer);
        self.credit(&o.buyer, o.amount.0);
    }
    #[payable]
    pub fn accept_offer(&mut self, id: U64) -> Promise {
        near_sdk::assert_one_yocto();
        let o = self.offers.get(&id.0).expect("Unknown offer");
        assert!(crate::clock::now() < o.expires_ns.0, "Offer expired");
        let l = self.active(&o.token_id, o.listing_nonce);
        assert_eq!(env::predecessor_account_id(), l.seller, "Seller only");
        assert_eq!(l.seller, o.seller);
        self.offers.remove(&id.0);
        self.release_storage(&o.buyer);
        self.begin(l, o.buyer, o.amount.0, o.rights_hash)
    }
    #[private]
    pub fn resolve_sale(&mut self, token_id: String, sale_id: U64) -> bool {
        let Some(mut l) = self.listings.get(&token_id) else {
            return false;
        };
        let Some(s) = l.sale.clone() else {
            return false;
        };
        if s.id != sale_id {
            return false;
        }
        let ok = env::promise_result_checked(0, 1024).is_ok();
        let mut month = self.royalty_month(s.royalty_cycle);
        month.pending_sales -= 1;
        if ok {
            let fee = s.amount.0 / 20;
            month.pot.0 = month.pot.0.checked_add(fee).unwrap();
            month.earned.0 = month.earned.0.checked_add(fee).unwrap();
            self.credit(&l.seller, s.amount.0 - fee);
            self.listings.remove(&token_id);
            self.release_storage(&l.seller);
        } else {
            self.credit(&s.buyer, s.amount.0);
            l.sale = None;
            self.listings.insert(&token_id, &l);
        }
        self.royalty_months.insert(&s.royalty_cycle, &month);
        self.event(if ok{"sold"}else{"sale_failed"},near_sdk::serde_json::json!({"token_id":token_id,"sale_id":sale_id,"buyer":s.buyer,"seller":l.seller,"amount":s.amount}));
        ok
    }
    #[payable]
    pub fn withdraw_credit(&mut self) -> Promise {
        near_sdk::assert_one_yocto();
        self.withdraw(env::predecessor_account_id(), false)
    }
    #[payable]
    pub fn withdraw_storage(&mut self) -> Promise {
        near_sdk::assert_one_yocto();
        self.withdraw(env::predecessor_account_id(), true)
    }
    #[private]
    pub fn resolve_withdraw(&mut self, account: AccountId) -> bool {
        let mut b = self.registered(&account);
        let amount = b.withdrawing.0;
        if amount == 0 {
            return false;
        }
        let ok = env::promise_result_checked(0, 1024).is_ok();
        b.withdrawing = U128(0);
        if !ok {
            b.credit.0 = b.credit.0.checked_add(amount).unwrap();
            self.liability = self.liability.checked_add(amount).unwrap();
        }
        self.balances.insert(&account, &b);
        ok
    }
}
impl EchoMarket {
    fn next(&mut self) -> u64 {
        self.sequence = self.sequence.checked_add(1).unwrap();
        self.sequence
    }
    fn registered(&self, a: &AccountId) -> Balance {
        self.balances.get(a).expect("Register storage first")
    }
    fn charge_storage(&mut self, a: &AccountId) {
        let mut b = self.registered(a);
        assert!(b.storage_available.0 >= STORAGE, "Top up record storage");
        b.storage_available.0 -= STORAGE;
        self.liability = self.liability.checked_sub(STORAGE).unwrap();
        self.balances.insert(a, &b);
    }
    fn release_storage(&mut self, a: &AccountId) {
        let mut b = self.registered(a);
        b.storage_available.0 = b.storage_available.0.checked_add(STORAGE).unwrap();
        self.liability = self.liability.checked_add(STORAGE).unwrap();
        self.balances.insert(a, &b);
    }
    fn credit(&mut self, a: &AccountId, n: u128) {
        let mut b = self.registered(a);
        b.credit.0 = b.credit.0.checked_add(n).unwrap();
        self.balances.insert(a, &b);
    }
    fn listing(&self, t: &String, n: U64) -> Listing {
        let l = self.listings.get(t).expect("No listing");
        assert_eq!(l.nonce, n, "Listing changed");
        l
    }
    fn active(&self, t: &String, n: U64) -> Listing {
        let l = self.listing(t, n);
        assert!(l.sale.is_none(), "Sale pending");
        assert!(crate::clock::now() < l.expires_ns.0, "Listing expired");
        l
    }
    fn expiry(&self, t: u64) {
        let now = crate::clock::now();
        assert!(
            t > now && t <= now + 30 * 86400 * 1_000_000_000,
            "Expiry must be within 30 days"
        );
    }
    fn hash(&self, s: &str) {
        assert!(
            s.len() == 64
                && s.bytes()
                    .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()),
            "Invalid rights hash"
        );
    }
    fn begin(
        &mut self,
        mut l: Listing,
        buyer: AccountId,
        amount: u128,
        rights_hash: String,
    ) -> Promise {
        assert_ne!(buyer, l.seller, "Self purchase");
        self.hash(&rights_hash);
        let id = self.next();
        l.sale = Some(Sale {
            id: U64(id),
            buyer: buyer.clone(),
            amount: U128(amount),
            royalty_cycle: calendar::cycle(crate::clock::now()),
        });
        let cycle = l.sale.as_ref().unwrap().royalty_cycle;
        let mut month = self.royalty_month(cycle);
        assert!(!month.ready, "Royalty month closed");
        month.pending_sales += 1;
        self.royalty_months.insert(&cycle, &month);
        self.listings.insert(&l.token_id, &l);
        self.solvent();
        ext_nft::ext(self.nft_contract.clone())
            .with_static_gas(Gas::from_tgas(45))
            .with_unused_gas_weight(0)
            .with_attached_deposit(NearToken::from_yoctonear(1))
            .market_transfer(
                l.token_id.clone(),
                buyer,
                l.seller,
                l.approval_id,
                rights_hash,
            )
            .then(
                ext_self::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(35))
                    .with_unused_gas_weight(0)
                    .resolve_sale(l.token_id, U64(id)),
            )
    }
    fn withdraw(&mut self, account: AccountId, storage: bool) -> Promise {
        let mut b = self.registered(&account);
        assert_eq!(b.withdrawing.0, 0, "Withdrawal pending");
        if storage {
            b.credit.0 = b.credit.0.checked_add(b.storage_available.0).unwrap();
            b.storage_available = U128(0);
        }
        let amount = b.credit.0;
        assert!(amount > 0, "No credit");
        b.credit = U128(0);
        b.withdrawing = U128(amount);
        self.balances.insert(&account, &b);
        self.liability = self.liability.checked_sub(amount).unwrap();
        Promise::new(account.clone())
            .transfer(NearToken::from_yoctonear(amount))
            .then(
                ext_self::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(15))
                    .with_unused_gas_weight(0)
                    .resolve_withdraw(account),
            )
    }
    fn event(&self, event: &str, data: near_sdk::serde_json::Value) {
        env::log_str(&format!(
            "EVENT_JSON:{}",
            near_sdk::serde_json::json!({"standard":"near_echoes_market","version":"1.0.0","event":event,"data":[data]})
        ));
    }
    fn solvent(&self) {
        let stake = u128::from(env::storage_usage()) * env::storage_byte_cost().as_yoctonear();
        assert!(
            env::account_balance().as_yoctonear().saturating_sub(stake)
                >= self.liability.checked_add(STORAGE).unwrap(),
            "Fund marketplace operating storage reserve"
        );
    }
}

#[cfg(test)]
mod tests;

#[cfg(feature = "testnet-lab")]
#[near]
impl EchoMarket {
    #[init]
    pub fn new_testnet_lab(nft_contract: AccountId, primary_auction: AccountId, creator: AccountId, clock_authority: AccountId, timestamp_ns: near_sdk::json_types::U64) -> Self {
        clock::initialize(clock_authority.clone(), timestamp_ns.0);
        Self::new(nft_contract, primary_auction, creator)
    }
    pub fn lab_set_time(&mut self, timestamp_ns: near_sdk::json_types::U64) {
        clock::advance(timestamp_ns.0);
    }
}
