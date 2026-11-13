use near_contract_standards::non_fungible_token::Token;
use near_sdk::collections::{LookupMap, UnorderedMap};
use near_sdk::json_types::{U128, U64};
use near_sdk::{
    assert_one_yocto, env, ext_contract, near, AccountId, BorshStorageKey, Gas, NearToken,
    PanicOnDefault, Promise, PromiseOrValue,
};

const SECOND: u64 = 1_000_000_000;
const WEEK: u64 = 7 * 24 * 3600 * SECOND;
const EXTENSION: u64 = 300 * SECOND;
const STORAGE: u128 = 10_000_000_000_000_000_000_000; // 0.01 NEAR covers a fixed bidder balance entry

#[near(serializers=[borsh,json])]
#[derive(Clone, PartialEq, Debug)]
pub enum Status {
    CheckingCustody,
    Active,
    SettlementPending,
    Settled,
    Unsold,
    RecoveryRequired,
    CustodyFailed,
    FundingPending,
    FundingFailed,
}
#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct Auction {
    pub token_id: String,
    pub status: Status,
    pub highest_bid: U128,
    pub highest_bidder: Option<AccountId>,
    pub min_bid: U128,
    pub increment: U128,
    pub end_ns: U64,
    pub custody_verified: bool,
}

#[near(serializers=[json])]
pub struct Delivery {
    pub receiver_id: AccountId,
    pub confirmed: bool,
}

#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct ThemeRecord {
    pub token_id: String,
    pub theme: String,
}

#[derive(BorshStorageKey)]
#[near(serializers=[borsh])]
enum Key {
    Auctions,
    Refunds,
    Treasury,
    Registered,
    ThemeHistory,
}

#[ext_contract(ext_nft)]
#[allow(dead_code)]
trait NFT {
    fn nft_token(&self, token_id: String) -> Option<Token>;
    fn get_auction_candidate(&self, token_id: String) -> Option<Token>;
    fn nft_transfer(
        &mut self,
        receiver_id: AccountId,
        token_id: String,
        approval_id: Option<u64>,
        memo: Option<String>,
    );
    fn get_auction_delivery(&self, token_id: String) -> Option<Delivery>;
    fn receive_auction_proceeds(&mut self, token_id: String) -> bool;
    fn get_funding_receipt(&self, token_id: String) -> Option<U128>;
}
#[ext_contract(ext_self)]
#[allow(dead_code)]
trait Callbacks {
    fn on_custody(&mut self, token_id: String) -> bool;
    fn on_transfer(&mut self, token_id: String) -> bool;
    fn on_claim(&mut self, account: AccountId, amount: U128, treasury: bool) -> bool;
    fn on_theme_owner(&mut self, token_id: String, caller: AccountId, theme: String) -> bool;
    fn on_delivery_check(&mut self, token_id: String) -> PromiseOrValue<bool>;
    fn on_recovery_owner(&mut self, token_id: String) -> bool;
    fn on_proceeds(&mut self, token_id: String) -> bool;
    fn on_funding_check(&mut self, token_id: String) -> bool;
}

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct EchoAuction {
    owner: AccountId,
    nft_contract: AccountId,
    auctions: UnorderedMap<String, Auction>,
    refunds: UnorderedMap<AccountId, u128>,
    treasury: UnorderedMap<AccountId, u128>,
    treasury_accounts: Vec<AccountId>,
    splits: Vec<u16>,
    earned: u128,
    duration: u64,
    min_bid: u128,
    increment: u128,
    extension: u64,
    latest_settled: Option<String>,
    theme_deadline: u64,
    theme: Option<String>,
    theme_history: LookupMap<u64, ThemeRecord>,
    economy: bool,
    creator: Option<AccountId>,
}

fn event(name: &str, data: near_sdk::serde_json::Value) {
    env::log_str(&format!(
        "EVENT_JSON:{}",
        near_sdk::serde_json::json!({"standard":"near_echoes","version":"1.0.0","event":name,"data":[data]})
    ));
}

#[near]
impl EchoAuction {
    #[init]
    pub fn new(
        owner: AccountId,
        nft_contract: AccountId,
        treasury_accounts: Vec<AccountId>,
        splits: Vec<u16>,
        min_bid: U128,
        increment: U128,
        demo_duration_seconds: Option<u64>,
    ) -> Self {
        assert_eq!(
            treasury_accounts.len(),
            3,
            "Three treasury accounts required"
        );
        assert!(
            treasury_accounts[0] != treasury_accounts[1]
                && treasury_accounts[1] != treasury_accounts[2]
                && treasury_accounts[0] != treasury_accounts[2],
            "Distinct treasuries required"
        );
        assert_eq!(splits.len(), 3);
        assert_eq!(
            splits.iter().map(|s| *s as u32).sum::<u32>(),
            10000,
            "Splits must sum to 10000 bps"
        );
        assert!(
            !treasury_accounts.contains(&owner)
                && !treasury_accounts.contains(&env::current_account_id()),
            "Worker and auction cannot be treasury withdrawal accounts"
        );
        assert!(
            min_bid.0 > 0 && increment.0 > 0,
            "Positive bid rules required"
        );
        let duration = demo_duration_seconds
            .map(|s| {
                assert!(
                    env::current_account_id().as_str().ends_with(".testnet"),
                    "Compressed auctions only on testnet accounts"
                );
                assert!((30..=3600).contains(&s));
                s.checked_mul(SECOND).unwrap()
            })
            .unwrap_or(WEEK);
        let mut result = Self {
            owner,
            nft_contract,
            auctions: UnorderedMap::new(Key::Auctions),
            refunds: UnorderedMap::new(Key::Refunds),
            treasury: UnorderedMap::new(Key::Treasury),
            treasury_accounts,
            splits,
            earned: 0,
            duration,
            min_bid: min_bid.0,
            increment: increment.0,
            extension: if demo_duration_seconds.is_some() {
                10 * SECOND
            } else {
                EXTENSION
            },
            latest_settled: None,
            theme_deadline: 0,
            theme: None,
            theme_history: LookupMap::new(Key::ThemeHistory),
            economy: false,
            creator: None,
        };
        for a in &result.treasury_accounts {
            result.treasury.insert(a, &0);
        }
        result
    }

    #[init]
    pub fn new_economy(
        owner: AccountId,
        nft_contract: AccountId,
        creator: AccountId,
        treasury: AccountId,
        min_bid: U128,
        increment: U128,
    ) -> Self {
        assert!(
            min_bid.0 >= 10 && increment.0 > 0,
            "Positive bid rules required"
        );
        assert_ne!(owner, treasury, "Separate treasury authority required");
        assert_ne!(creator, env::current_account_id());
        Self {
            owner,
            nft_contract,
            auctions: UnorderedMap::new(Key::Auctions),
            refunds: UnorderedMap::new(Key::Refunds),
            treasury: UnorderedMap::new(Key::Treasury),
            treasury_accounts: vec![treasury],
            splits: vec![2000, 8000],
            earned: 0,
            duration: 24 * 3600 * SECOND,
            min_bid: min_bid.0,
            increment: increment.0,
            extension: 0,
            latest_settled: None,
            theme_deadline: 0,
            theme: None,
            theme_history: LookupMap::new(Key::ThemeHistory),
            economy: true,
            creator: Some(creator),
        }
    }

    #[payable]
    pub fn register_bidder(&mut self) {
        let account = env::predecessor_account_id();
        assert!(self.refunds.get(&account).is_none(), "Already registered");
        let before = env::storage_usage();
        self.refunds.insert(&account, &0);
        let required = env::storage_byte_cost()
            .as_yoctonear()
            .checked_mul((env::storage_usage() - before) as u128)
            .unwrap();
        assert!(
            env::attached_deposit().as_yoctonear() >= required.max(STORAGE),
            "0.01 NEAR storage deposit required"
        );
        let surplus = env::attached_deposit().as_yoctonear() - required.max(STORAGE);
        if surplus > 0 {
            self.refunds.insert(&account, &surplus);
        }
    }

    #[payable]
    pub fn create_auction(&mut self, token_id: String) -> Promise {
        assert_eq!(
            env::predecessor_account_id(),
            self.owner,
            "Only operator can list"
        );
        assert!(
            self.auctions.get(&token_id).is_none(),
            "Auction already exists"
        );
        assert!(token_id.len() <= 64, "Invalid token ID");
        // Fixed 0.05 NEAR funds worst-case storage growth including a 64-byte winner.
        assert!(
            env::attached_deposit().as_yoctonear() >= 5 * STORAGE,
            "Auction storage deposit requires 0.05 NEAR"
        );
        self.auctions.insert(
            &token_id,
            &Auction {
                token_id: token_id.clone(),
                status: Status::CheckingCustody,
                highest_bid: U128(0),
                highest_bidder: None,
                min_bid: U128(self.min_bid),
                increment: U128(self.increment),
                end_ns: U64(0),
                custody_verified: false,
            },
        );
        let query = ext_nft::ext(self.nft_contract.clone()).with_static_gas(Gas::from_tgas(15));
        let promise = if self.economy {
            query.get_auction_candidate(token_id.clone())
        } else {
            query.nft_token(token_id.clone())
        };
        promise.then(
            ext_self::ext(env::current_account_id())
                .with_static_gas(Gas::from_tgas(15))
                .on_custody(token_id),
        )
    }

    #[private]
    pub fn on_custody(&mut self, token_id: String) -> bool {
        let mut a = self.auctions.get(&token_id).expect("Missing auction");
        if a.status != Status::CheckingCustody {
            return a.custody_verified;
        }
        let valid = env::promise_result_checked(0, 32_768)
            .ok()
            .and_then(|bytes| {
                near_sdk::serde_json::from_slice::<Option<Token>>(&bytes)
                    .ok()
                    .flatten()
            })
            .map(|t| t.owner_id == env::current_account_id() && t.token_id == token_id)
            .unwrap_or(false);
        a.status = if valid {
            Status::Active
        } else {
            Status::CustodyFailed
        };
        a.custody_verified = valid;
        if valid {
            a.end_ns = U64(env::block_timestamp().checked_add(self.duration).unwrap());
        }
        self.auctions.insert(&token_id, &a);
        event(
            "custody",
            near_sdk::serde_json::json!({"token_id":token_id,"valid":valid}),
        );
        valid
    }

    #[payable]
    pub fn place_bid(&mut self, token_id: String) {
        let who = env::predecessor_account_id();
        assert!(
            self.refunds.get(&who).is_some(),
            "Register bidder storage first"
        );
        let mut a = self.auctions.get(&token_id).expect("Unknown auction");
        assert_eq!(a.status, Status::Active, "Auction not active");
        assert!(a.custody_verified, "Custody unverified");
        assert!(env::block_timestamp() < a.end_ns.0, "Auction ended");
        let amount = env::attached_deposit().as_yoctonear();
        let minimum = if a.highest_bid.0 == 0 {
            a.min_bid.0
        } else {
            a.highest_bid
                .0
                .checked_add(a.increment.0)
                .expect("Bid overflow")
        };
        assert!(amount >= minimum, "Bid below required minimum");
        let previous = a.highest_bidder.clone();
        if let Some(previous) = &previous {
            let refund = self.refunds.get(previous).unwrap();
            self.refunds
                .insert(previous, &refund.checked_add(a.highest_bid.0).unwrap());
        }
        a.highest_bid = U128(amount);
        a.highest_bidder = Some(who.clone());
        if a.end_ns.0 - env::block_timestamp() <= self.extension {
            a.end_ns = U64(env::block_timestamp().checked_add(self.extension).unwrap());
        }
        self.auctions.insert(&token_id, &a);
        event(
            "bid",
            near_sdk::serde_json::json!({"token_id":token_id,"bidder":who,"amount":amount.to_string(),"end_ns":a.end_ns}),
        );
        if self.economy {
            if let Some(previous) = previous {
                self.process_refund(previous).detach();
            }
        }
    }

    pub fn finalize_auction(&mut self, token_id: String) -> Promise {
        let mut a = self.auctions.get(&token_id).expect("Unknown auction");
        assert!(
            a.status == Status::Active || a.status == Status::RecoveryRequired,
            "Settlement not allowed"
        );
        assert!(env::block_timestamp() >= a.end_ns.0, "Auction still open");
        let recipient = a.highest_bidder.clone().unwrap_or_else(|| {
            self.creator
                .clone()
                .unwrap_or(self.treasury_accounts[0].clone())
        });
        a.status = Status::SettlementPending;
        self.auctions.insert(&token_id, &a);
        ext_nft::ext(self.nft_contract.clone())
            .with_attached_deposit(NearToken::from_yoctonear(1))
            .with_static_gas(Gas::from_tgas(45))
            .nft_transfer(
                recipient,
                token_id.clone(),
                None,
                Some("NEAR ECHOES settlement".into()),
            )
            .then(
                ext_self::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(100))
                    .on_transfer(token_id),
            )
    }

    #[private]
    pub fn on_transfer(&mut self, token_id: String) -> bool {
        let mut a = self.auctions.get(&token_id).expect("Unknown auction");
        if a.status != Status::SettlementPending {
            return a.status == Status::Settled || a.status == Status::Unsold;
        }
        let success = env::promise_result_checked(0, 1024).is_ok();
        if !success {
            a.status = Status::RecoveryRequired;
            self.auctions.insert(&token_id, &a);
            return false;
        }
        self.complete_settlement(token_id, a)
    }

    pub fn retry_custody(&mut self, token_id: String) -> Promise {
        let mut a = self.auctions.get(&token_id).expect("Unknown auction");
        assert!(
            a.status == Status::CheckingCustody || a.status == Status::CustodyFailed,
            "Custody already verified"
        );
        a.status = Status::CheckingCustody;
        self.auctions.insert(&token_id, &a);
        let query = ext_nft::ext(self.nft_contract.clone()).with_static_gas(Gas::from_tgas(15));
        let promise = if self.economy {
            query.get_auction_candidate(token_id.clone())
        } else {
            query.nft_token(token_id.clone())
        };
        promise.then(
            ext_self::ext(env::current_account_id())
                .with_static_gas(Gas::from_tgas(15))
                .on_custody(token_id),
        )
    }

    pub fn reconcile_settlement(&mut self, token_id: String) -> Promise {
        let a = self.auctions.get(&token_id).expect("Unknown auction");
        assert!(
            a.status == Status::SettlementPending || a.status == Status::RecoveryRequired,
            "Reconciliation not needed"
        );
        assert!(env::block_timestamp() >= a.end_ns.0, "Auction still open");
        ext_nft::ext(self.nft_contract.clone())
            .with_static_gas(Gas::from_tgas(15))
            .get_auction_delivery(token_id.clone())
            .then(
                ext_self::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(100))
                    .on_delivery_check(token_id),
            )
    }

    #[private]
    pub fn on_delivery_check(&mut self, token_id: String) -> PromiseOrValue<bool> {
        let a = self.auctions.get(&token_id).expect("Unknown auction");
        if a.status == Status::Settled || a.status == Status::Unsold {
            return PromiseOrValue::Value(true);
        }
        assert!(a.status == Status::SettlementPending || a.status == Status::RecoveryRequired);
        let result = env::promise_result_checked(0, 2048)
            .ok()
            .and_then(|b| near_sdk::serde_json::from_slice::<Option<Delivery>>(&b).ok());
        match result {
            Some(Some(delivery)) => {
                assert!(
                    delivery.confirmed
                        && delivery.receiver_id
                            == a.highest_bidder.clone().unwrap_or_else(|| self
                                .creator
                                .clone()
                                .unwrap_or(self.treasury_accounts[0].clone())),
                    "Delivery beneficiary mismatch"
                );
                PromiseOrValue::Value(self.complete_settlement(token_id, a))
            }
            Some(None) => ext_nft::ext(self.nft_contract.clone())
                .with_static_gas(Gas::from_tgas(15))
                .nft_token(token_id.clone())
                .then(
                    ext_self::ext(env::current_account_id())
                        .with_static_gas(Gas::from_tgas(15))
                        .on_recovery_owner(token_id),
                )
                .into(),
            None => PromiseOrValue::Value(false),
        }
    }

    #[private]
    pub fn on_recovery_owner(&mut self, token_id: String) -> bool {
        let mut a = self.auctions.get(&token_id).expect("Unknown auction");
        if a.status == Status::Settled || a.status == Status::Unsold {
            return true;
        }
        let owned = env::promise_result_checked(0, 32_768)
            .ok()
            .and_then(|b| {
                near_sdk::serde_json::from_slice::<Option<Token>>(&b)
                    .ok()
                    .flatten()
            })
            .map(|t| t.owner_id == env::current_account_id())
            .unwrap_or(false);
        if owned {
            a.status = Status::RecoveryRequired;
            self.auctions.insert(&token_id, &a);
        }
        owned
    }

    pub fn get_config(&self) -> near_sdk::serde_json::Value {
        near_sdk::serde_json::json!({"owner":self.owner,"nft_contract":self.nft_contract,"creator":self.creator,"duration_ns":self.duration.to_string(),"extension_ns":self.extension.to_string(),"min_bid":self.min_bid.to_string(),"increment":self.increment.to_string(),"treasury_accounts":self.treasury_accounts,"splits":self.splits,"version":if self.economy{"echo-auction-3"}else{"echo-auction-2"}})
    }

    pub fn forward_proceeds(&mut self, token_id: String) -> Promise {
        assert!(self.economy, "Economy not configured");
        let mut a = self.auctions.get(&token_id).expect("Unknown auction");
        assert_eq!(a.status, Status::FundingFailed, "Funding not retryable");
        a.status = Status::FundingPending;
        self.auctions.insert(&token_id, &a);
        ext_nft::ext(self.nft_contract.clone())
            .with_attached_deposit(NearToken::from_yoctonear(a.highest_bid.0))
            .with_static_gas(Gas::from_tgas(35))
            .receive_auction_proceeds(token_id.clone())
            .then(
                ext_self::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(20))
                    .on_proceeds(token_id),
            )
    }
    #[private]
    pub fn on_proceeds(&mut self, token_id: String) -> bool {
        let mut a = self.auctions.get(&token_id).unwrap();
        if a.status != Status::FundingPending {
            return a.status == Status::Settled;
        }
        if env::promise_result_checked(0, 1024).is_err() {
            a.status = Status::FundingFailed;
            self.auctions.insert(&token_id, &a);
            return false;
        }
        self.record_economy_settlement(token_id, a);
        true
    }
    pub fn reconcile_funding(&self, token_id: String) -> Promise {
        let a = self.auctions.get(&token_id).expect("Unknown auction");
        assert_eq!(a.status, Status::FundingPending, "Funding not pending");
        ext_nft::ext(self.nft_contract.clone())
            .with_static_gas(Gas::from_tgas(10))
            .get_funding_receipt(token_id.clone())
            .then(
                ext_self::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(20))
                    .on_funding_check(token_id),
            )
    }
    #[private]
    pub fn on_funding_check(&mut self, token_id: String) -> bool {
        let a = self.auctions.get(&token_id).unwrap();
        if a.status != Status::FundingPending {
            return a.status == Status::Settled;
        }
        let receipt = env::promise_result_checked(0, 1024).ok().and_then(|b| {
            near_sdk::serde_json::from_slice::<Option<U128>>(&b)
                .ok()
                .flatten()
        });
        if receipt == Some(a.highest_bid) {
            self.record_economy_settlement(token_id, a);
            return true;
        }
        false
    }

    pub fn process_refund(&mut self, account: AccountId) -> Promise {
        let amount = self.refunds.get(&account).unwrap_or(0);
        assert!(amount > 0, "Nothing to claim");
        self.refunds.insert(&account, &0);
        Promise::new(account.clone())
            .transfer(NearToken::from_yoctonear(amount))
            .then(
                ext_self::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(15))
                    .on_claim(account, U128(amount), false),
            )
    }
    pub fn get_refund_accounts(
        &self,
        from_index: Option<u64>,
        limit: Option<u64>,
    ) -> Vec<near_sdk::serde_json::Value> {
        self.refunds.iter().skip(from_index.unwrap_or(0) as usize).take(limit.unwrap_or(100).min(100) as usize)
            .map(|(account,amount)|near_sdk::serde_json::json!({"account":account,"amount":amount.to_string()})).collect()
    }

    #[payable]
    pub fn claim_refund(&mut self) -> Promise {
        assert_one_yocto();
        self.claim(false)
    }
    #[payable]
    pub fn claim_proceeds(&mut self) -> Promise {
        assert_one_yocto();
        self.claim(true)
    }
}

impl EchoAuction {
    fn complete_settlement(&mut self, token_id: String, mut a: Auction) -> bool {
        if a.status == Status::Settled || a.status == Status::Unsold {
            return true;
        }
        if self.economy && a.highest_bidder.is_some() {
            if a.status == Status::FundingPending {
                return true;
            }
            a.status = Status::FundingFailed;
            self.auctions.insert(&token_id, &a);
            self.forward_proceeds(token_id).detach();
            return true;
        }
        if a.highest_bidder.is_none() {
            a.status = Status::Unsold;
        } else {
            a.status = Status::Settled;
            let first = a.highest_bid.0.checked_mul(self.splits[0] as u128).unwrap() / 10000;
            let second = a.highest_bid.0.checked_mul(self.splits[1] as u128).unwrap() / 10000;
            let amounts = [
                first,
                second,
                a.highest_bid
                    .0
                    .checked_sub(first)
                    .unwrap()
                    .checked_sub(second)
                    .unwrap(),
            ];
            for (i, amount) in amounts.into_iter().enumerate() {
                let account = &self.treasury_accounts[i];
                let old = self.treasury.get(account).unwrap();
                self.treasury
                    .insert(account, &old.checked_add(amount).unwrap());
            }
            self.earned = self.earned.checked_add(a.highest_bid.0).unwrap();
            // A settled owner can choose next style before the next Sunday 17:00 UTC.
            self.latest_settled = Some(token_id.clone());
            self.theme = None;
            let seconds = env::block_timestamp() / SECOND;
            let day = seconds / 86400;
            let days_until_sunday = (10 - day % 7) % 7;
            let mut deadline = (day + days_until_sunday) * 86400 + 17 * 3600;
            if deadline <= seconds {
                deadline += 7 * 86400;
            }
            self.theme_deadline = deadline.checked_mul(SECOND).unwrap();
            self.theme_history.insert(
                &self.theme_deadline,
                &ThemeRecord {
                    token_id: token_id.clone(),
                    theme: "celestial".into(),
                },
            );
        }
        self.auctions.insert(&token_id, &a);
        event(
            "settled",
            near_sdk::serde_json::json!({"token_id":token_id,"status":a.status,"amount":a.highest_bid}),
        );
        true
    }

    fn record_economy_settlement(&mut self, token_id: String, mut a: Auction) {
        if a.status == Status::Settled {
            return;
        }
        a.status = Status::Settled;
        self.earned = self.earned.checked_add(a.highest_bid.0).unwrap();
        self.latest_settled = Some(token_id.clone());
        self.theme = None;
        let seconds = env::block_timestamp() / SECOND;
        let day = seconds / 86400;
        let days_until_sunday = (10 - day % 7) % 7;
        let mut deadline = (day + days_until_sunday) * 86400 + 17 * 3600;
        if deadline <= seconds {
            deadline += 7 * 86400;
        }
        self.theme_deadline = deadline * SECOND;
        self.theme_history.insert(
            &self.theme_deadline,
            &ThemeRecord {
                token_id: token_id.clone(),
                theme: "celestial".into(),
            },
        );
        self.auctions.insert(&token_id, &a);
        event(
            "settled",
            near_sdk::serde_json::json!({"token_id":token_id,"status":a.status,"amount":a.highest_bid,"allocation_contract":self.nft_contract}),
        );
    }
}

#[near]
impl EchoAuction {
    #[private]
    pub fn on_claim(&mut self, account: AccountId, amount: U128, treasury: bool) -> bool {
        let success = env::promise_result_checked(0, 1024).is_ok();
        if !success {
            let balances = if treasury {
                &mut self.treasury
            } else {
                &mut self.refunds
            };
            let old = balances.get(&account).unwrap_or(0);
            balances.insert(&account, &old.checked_add(amount.0).unwrap());
        }
        event(
            "claim",
            near_sdk::serde_json::json!({"account":account,"amount":amount,"treasury":treasury,"success":success}),
        );
        success
    }

    pub fn get_auction(&self, token_id: String) -> Option<Auction> {
        self.auctions.get(&token_id)
    }
    pub fn get_auctions(&self, from_index: Option<u64>, limit: Option<u64>) -> Vec<Auction> {
        self.auctions
            .values()
            .skip(from_index.unwrap_or(0) as usize)
            .take(limit.unwrap_or(50).min(100) as usize)
            .collect()
    }
    pub fn get_refund(&self, account: AccountId) -> U128 {
        U128(self.refunds.get(&account).unwrap_or(0))
    }
    pub fn is_bidder_registered(&self, account: AccountId) -> bool {
        self.refunds.get(&account).is_some()
    }
    pub fn get_treasury(&self) -> near_sdk::serde_json::Value {
        near_sdk::serde_json::json!({"status":"onchain","earned_yocto":self.earned.to_string(),"policy_bps":self.splits,"allocations":self.treasury_accounts.iter().map(|a|near_sdk::serde_json::json!({"account":a,"balance":self.treasury.get(a).unwrap_or(0).to_string()})).collect::<Vec<_>>(),"events":[]})
    }

    pub fn choose_theme(&mut self, theme: String) -> Promise {
        assert!(
            matches!(theme.as_str(), "celestial" | "organic" | "crystalline"),
            "Unsupported theme"
        );
        assert!(
            env::block_timestamp() < self.theme_deadline,
            "Theme deadline passed"
        );
        let token = self.latest_settled.clone().expect("No settled edition");
        ext_nft::ext(self.nft_contract.clone())
            .with_static_gas(Gas::from_tgas(15))
            .nft_token(token.clone())
            .then(
                ext_self::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(15))
                    .on_theme_owner(token, env::predecessor_account_id(), theme),
            )
    }
    #[private]
    pub fn on_theme_owner(&mut self, token_id: String, caller: AccountId, theme: String) -> bool {
        assert!(env::block_timestamp() < self.theme_deadline, "Theme locked");
        assert_eq!(self.latest_settled, Some(token_id));
        let owned = env::promise_result_checked(0, 32_768)
            .ok()
            .and_then(|bytes| {
                near_sdk::serde_json::from_slice::<Option<Token>>(&bytes)
                    .ok()
                    .flatten()
            })
            .map(|t| t.owner_id == caller)
            .unwrap_or(false);
        if owned {
            self.theme_history.insert(
                &self.theme_deadline,
                &ThemeRecord {
                    token_id: self.latest_settled.clone().unwrap(),
                    theme: theme.clone(),
                },
            );
            self.theme = Some(theme);
        }
        owned
    }
    pub fn get_theme(&self) -> near_sdk::serde_json::Value {
        near_sdk::serde_json::json!({"token_id":self.latest_settled,"theme":self.theme.clone().unwrap_or("celestial".into()),"deadline_ns":self.theme_deadline.to_string(),"locked":env::block_timestamp()>=self.theme_deadline})
    }
    pub fn get_theme_for(&self, deadline_ns: U64) -> near_sdk::serde_json::Value {
        let record = self.theme_history.get(&deadline_ns.0);
        near_sdk::serde_json::json!({"token_id":record.as_ref().map(|r|r.token_id.clone()),"theme":record.map(|r|r.theme).unwrap_or("celestial".into()),"deadline_ns":deadline_ns.0.to_string(),"locked":env::block_timestamp()>=deadline_ns.0})
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use near_sdk::{
        test_utils::{testing_env_with_promise_results, VMContextBuilder},
        testing_env, PromiseResult,
    };
    fn id(s: &str) -> AccountId {
        s.parse().unwrap()
    }
    fn context(who: &str, deposit: u128, time: u64) {
        let mut c = VMContextBuilder::new();
        c.current_account_id(id("auction.testnet"))
            .predecessor_account_id(id(who))
            .signer_account_id(id(who))
            .attached_deposit(NearToken::from_yoctonear(deposit))
            .block_timestamp(time);
        testing_env!(c.build());
    }
    fn contract() -> EchoAuction {
        context("owner.testnet", 0, 0);
        EchoAuction::new(
            id("owner.testnet"),
            id("nft.testnet"),
            vec![
                id("creative.testnet"),
                id("dev.testnet"),
                id("community.testnet"),
            ],
            vec![6000, 2500, 1500],
            U128(100),
            U128(10),
            None,
        )
    }
    fn active(c: &mut EchoAuction) {
        c.auctions.insert(
            &"ECHO-000001".into(),
            &Auction {
                token_id: "ECHO-000001".into(),
                status: Status::Active,
                highest_bid: U128(0),
                highest_bidder: None,
                min_bid: U128(100),
                increment: U128(10),
                end_ns: U64(WEEK),
                custody_verified: true,
            },
        );
    }
    fn bidder(c: &mut EchoAuction, who: &str) {
        context(who, STORAGE, 0);
        c.register_bidder();
    }
    fn callback(result: PromiseResult) {
        let mut ctx = VMContextBuilder::new();
        ctx.current_account_id(id("auction.testnet"))
            .predecessor_account_id(id("auction.testnet"))
            .block_timestamp(WEEK + 1);
        testing_env_with_promise_results(ctx.build(), result);
    }
    #[test]
    fn bids_and_multiple_refunds() {
        let mut c = contract();
        active(&mut c);
        bidder(&mut c, "alice.testnet");
        bidder(&mut c, "bob.testnet");
        context("alice.testnet", 100, 1);
        c.place_bid("ECHO-000001".into());
        context("bob.testnet", 110, 2);
        c.place_bid("ECHO-000001".into());
        context("alice.testnet", 120, 3);
        c.place_bid("ECHO-000001".into());
        assert_eq!(c.get_refund(id("alice.testnet")).0, 100);
        assert_eq!(c.get_refund(id("bob.testnet")).0, 110);
        assert_eq!(
            c.get_auction("ECHO-000001".into()).unwrap().highest_bidder,
            Some(id("alice.testnet"))
        );
    }
    #[test]
    #[should_panic(expected = "minimum")]
    fn rejects_low_bid() {
        let mut c = contract();
        active(&mut c);
        bidder(&mut c, "alice.testnet");
        context("alice.testnet", 99, 1);
        c.place_bid("ECHO-000001".into());
    }
    #[test]
    #[should_panic(expected = "ended")]
    fn rejects_late_bid() {
        let mut c = contract();
        active(&mut c);
        bidder(&mut c, "alice.testnet");
        context("alice.testnet", 100, WEEK);
        c.place_bid("ECHO-000001".into());
    }
    #[test]
    fn anti_sniping_rolling_extension() {
        let mut c = contract();
        active(&mut c);
        bidder(&mut c, "alice.testnet");
        context("alice.testnet", 100, WEEK - SECOND);
        c.place_bid("ECHO-000001".into());
        assert_eq!(
            c.get_auction("ECHO-000001".into()).unwrap().end_ns.0,
            WEEK - SECOND + EXTENSION
        );
    }
    #[test]
    fn settlement_waits_for_transfer_and_allocates_remainder() {
        let mut c = contract();
        active(&mut c);
        bidder(&mut c, "alice.testnet");
        context("alice.testnet", 101, 1);
        c.place_bid("ECHO-000001".into());
        context("anyone.testnet", 0, WEEK + 1);
        c.finalize_auction("ECHO-000001".into());
        assert_eq!(c.earned, 0);
        assert_eq!(
            c.get_auction("ECHO-000001".into()).unwrap().status,
            Status::SettlementPending
        );
        callback(PromiseResult::Successful(vec![]));
        assert!(c.on_transfer("ECHO-000001".into()));
        assert_eq!(c.earned, 101);
        assert_eq!(c.treasury.get(&id("creative.testnet")), Some(60));
        assert_eq!(c.treasury.get(&id("dev.testnet")), Some(25));
        assert_eq!(c.treasury.get(&id("community.testnet")), Some(16));
    }
    #[test]
    fn transfer_failure_keeps_escrow_and_can_retry() {
        let mut c = contract();
        active(&mut c);
        context("anyone.testnet", 0, WEEK + 1);
        c.finalize_auction("ECHO-000001".into());
        callback(PromiseResult::Failed);
        assert!(!c.on_transfer("ECHO-000001".into()));
        assert_eq!(c.earned, 0);
        assert_eq!(
            c.get_auction("ECHO-000001".into()).unwrap().status,
            Status::RecoveryRequired
        );
        context("anyone.testnet", 0, WEEK + 1);
        c.finalize_auction("ECHO-000001".into());
        callback(PromiseResult::Successful(vec![]));
        assert!(c.on_transfer("ECHO-000001".into()));
        assert_eq!(
            c.get_auction("ECHO-000001".into()).unwrap().status,
            Status::Unsold
        );
    }
    #[test]
    fn failed_refund_is_restored() {
        let mut c = contract();
        bidder(&mut c, "alice.testnet");
        c.refunds.insert(&id("alice.testnet"), &100);
        context("alice.testnet", 1, 1);
        c.claim_refund();
        assert_eq!(c.get_refund(id("alice.testnet")).0, 0);
        callback(PromiseResult::Failed);
        assert!(!c.on_claim(id("alice.testnet"), U128(100), false));
        assert_eq!(c.get_refund(id("alice.testnet")).0, 100);
    }
    #[test]
    #[should_panic(expected = "Nothing to claim")]
    fn cannot_double_claim() {
        let mut c = contract();
        bidder(&mut c, "alice.testnet");
        c.refunds.insert(&id("alice.testnet"), &100);
        context("alice.testnet", 1, 1);
        c.claim_refund();
        context("alice.testnet", 1, 1);
        c.claim_refund();
    }
    #[test]
    #[should_panic(expected = "Settlement not allowed")]
    fn cannot_double_settle() {
        let mut c = contract();
        active(&mut c);
        context("anyone.testnet", 0, WEEK + 1);
        c.finalize_auction("ECHO-000001".into());
        context("anyone.testnet", 0, WEEK + 1);
        c.finalize_auction("ECHO-000001".into());
    }
    #[test]
    fn lost_settlement_callback_recovers_from_durable_delivery_once() {
        let mut c = contract();
        active(&mut c);
        bidder(&mut c, "alice.testnet");
        context("alice.testnet", 101, 1);
        c.place_bid("ECHO-000001".into());
        context("anyone.testnet", 0, WEEK + 1);
        c.finalize_auction("ECHO-000001".into());
        callback(PromiseResult::Successful(
            near_sdk::serde_json::to_vec(
                &near_sdk::serde_json::json!({"receiver_id":"alice.testnet","confirmed":true}),
            )
            .unwrap(),
        ));
        assert!(matches!(
            c.on_delivery_check("ECHO-000001".into()),
            PromiseOrValue::Value(true)
        ));
        assert_eq!(c.earned, 101);
        callback(PromiseResult::Successful(vec![]));
        assert!(c.on_transfer("ECHO-000001".into()));
        callback(PromiseResult::Successful(
            near_sdk::serde_json::to_vec(
                &near_sdk::serde_json::json!({"receiver_id":"alice.testnet","confirmed":true}),
            )
            .unwrap(),
        ));
        assert!(matches!(
            c.on_delivery_check("ECHO-000001".into()),
            PromiseOrValue::Value(true)
        ));
        assert_eq!(c.earned, 101);
        assert_eq!(c.treasury.get(&id("community.testnet")), Some(16));
    }
    #[test]
    #[should_panic(expected = "beneficiary mismatch")]
    fn recovery_rejects_wrong_delivery_beneficiary() {
        let mut c = contract();
        active(&mut c);
        context("anyone.testnet", 0, WEEK + 1);
        c.finalize_auction("ECHO-000001".into());
        callback(PromiseResult::Successful(
            near_sdk::serde_json::to_vec(
                &near_sdk::serde_json::json!({"receiver_id":"attacker.testnet","confirmed":true}),
            )
            .unwrap(),
        ));
        c.on_delivery_check("ECHO-000001".into());
    }
    #[test]
    fn stale_custody_callback_does_not_restart_auction() {
        let mut c = contract();
        active(&mut c);
        let before = c.get_auction("ECHO-000001".into()).unwrap().end_ns;
        callback(PromiseResult::Failed);
        assert!(c.on_custody("ECHO-000001".into()));
        assert_eq!(c.get_auction("ECHO-000001".into()).unwrap().end_ns, before);
    }
    #[test]
    fn failed_custody_can_be_retried_and_activates_only_once() {
        let mut c = contract();
        context("owner.testnet", 5 * STORAGE, 0);
        c.create_auction("ECHO-000001".into());
        callback(PromiseResult::Failed);
        assert!(!c.on_custody("ECHO-000001".into()));
        context("anyone.testnet", 0, WEEK + 1);
        c.retry_custody("ECHO-000001".into());
        callback(PromiseResult::Successful(near_sdk::serde_json::to_vec(&near_sdk::serde_json::json!({"token_id":"ECHO-000001","owner_id":"auction.testnet","metadata":null,"approved_account_ids":{}})).unwrap()));
        assert!(c.on_custody("ECHO-000001".into()));
        let end = c.get_auction("ECHO-000001".into()).unwrap().end_ns.0;
        assert_eq!(end, 2 * WEEK + 1);
        callback(PromiseResult::Failed);
        assert!(c.on_custody("ECHO-000001".into()));
        assert_eq!(c.get_auction("ECHO-000001".into()).unwrap().end_ns.0, end);
    }
    #[test]
    fn locked_curatorial_choice_survives_a_later_settlement() {
        let mut c = contract();
        active(&mut c);
        let mut a = c.get_auction("ECHO-000001".into()).unwrap();
        a.highest_bidder = Some(id("alice.testnet"));
        a.highest_bid = U128(100);
        a.status = Status::SettlementPending;
        context("auction.testnet", 0, WEEK + 1);
        assert!(c.complete_settlement("ECHO-000001".into(), a.clone()));
        let deadline = c.theme_deadline;
        callback(PromiseResult::Successful(near_sdk::serde_json::to_vec(&near_sdk::serde_json::json!({"token_id":"ECHO-000001","owner_id":"alice.testnet","metadata":null,"approved_account_ids":{}})).unwrap()));
        assert!(c.on_theme_owner("ECHO-000001".into(), id("alice.testnet"), "organic".into()));
        context("auction.testnet", 0, deadline + 1);
        a.token_id = "ECHO-000002".into();
        assert!(c.complete_settlement("ECHO-000002".into(), a));
        assert_eq!(c.get_theme()["theme"], "celestial");
        assert_eq!(c.get_theme_for(U64(deadline))["theme"], "organic");
        assert_eq!(c.get_theme_for(U64(deadline))["locked"], true);
    }
    #[test]
    fn production_rules_and_bounded_enumeration() {
        let c = contract();
        assert_eq!(c.duration, WEEK);
        assert_eq!(c.extension, EXTENSION);
        assert_eq!(
            c.get_config()["splits"],
            near_sdk::serde_json::json!([6000, 2500, 1500])
        );
        assert!(c.get_auctions(Some(999), Some(1000)).is_empty());
    }
    #[test]
    #[should_panic(expected = "Only operator")]
    fn unauthorized_listing() {
        let mut c = contract();
        context("bad.testnet", 5 * STORAGE, 0);
        c.create_auction("ECHO-000001".into());
    }
    #[test]
    fn economy_is_exactly_24h_with_automatic_refund_and_no_extension() {
        context("owner.testnet", 0, 0);
        let mut c = EchoAuction::new_economy(
            id("owner.testnet"),
            id("nft.testnet"),
            id("team.testnet"),
            id("treasury.testnet"),
            U128(100),
            U128(10),
        );
        assert_eq!(c.duration, 86400 * SECOND);
        assert_eq!(c.extension, 0);
        active(&mut c);
        bidder(&mut c, "alice.testnet");
        bidder(&mut c, "bob.testnet");
        context("alice.testnet", 100, 1);
        c.place_bid("ECHO-000001".into());
        context("bob.testnet", 110, WEEK - 1);
        c.place_bid("ECHO-000001".into());
        assert_eq!(c.get_refund(id("alice.testnet")).0, 0);
        assert_eq!(c.get_auction("ECHO-000001".into()).unwrap().end_ns.0, WEEK);
        callback(PromiseResult::Failed);
        c.on_claim(id("alice.testnet"), U128(100), false);
        assert_eq!(c.get_refund(id("alice.testnet")).0, 100);
    }
    #[test]
    fn economy_settlement_waits_for_durable_allocation_receipt() {
        context("owner.testnet", 0, 0);
        let mut c = EchoAuction::new_economy(
            id("owner.testnet"),
            id("nft.testnet"),
            id("team.testnet"),
            id("treasury.testnet"),
            U128(100),
            U128(10),
        );
        active(&mut c);
        bidder(&mut c, "alice.testnet");
        context("alice.testnet", 104, 1);
        c.place_bid("ECHO-000001".into());
        context("anyone.testnet", 0, WEEK + 1);
        let _ = c.finalize_auction("ECHO-000001".into());
        callback(PromiseResult::Successful(vec![]));
        c.on_transfer("ECHO-000001".into());
        assert_eq!(
            c.get_auction("ECHO-000001".into()).unwrap().status,
            Status::FundingPending
        );
        assert_eq!(c.earned, 0);
        callback(PromiseResult::Successful(b"\"104\"".to_vec()));
        assert!(c.on_funding_check("ECHO-000001".into()));
        assert_eq!(c.earned, 104);
        assert!(c.on_proceeds("ECHO-000001".into()));
        assert_eq!(c.earned, 104);
    }
}

impl EchoAuction {
    fn claim(&mut self, treasury: bool) -> Promise {
        let who = env::predecessor_account_id();
        let balances = if treasury {
            &mut self.treasury
        } else {
            &mut self.refunds
        };
        let amount = balances.get(&who).unwrap_or(0);
        assert!(amount > 0, "Nothing to claim");
        balances.insert(&who, &0); // debit before asynchronous transfer; failure restores exactly once
        Promise::new(who.clone())
            .transfer(NearToken::from_yoctonear(amount))
            .then(
                ext_self::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(15))
                    .on_claim(who, U128(amount), treasury),
            )
    }
}
