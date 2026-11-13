use super::*;
use crate::{beacon, calendar};
use near_sdk::collections::UnorderedMap;
use near_sdk::json_types::U64;
use near_sdk::{Gas, NearToken};

// Built from the source in echo-vault by scripts/build_contracts.py, never downloaded.
const VAULT_WASM: &[u8] = include_bytes!("../../artifacts/echo_vault.wasm");
const ZERO: NearToken = NearToken::from_yoctonear(0);

#[near(serializers=[borsh,json])]
#[derive(Clone, PartialEq, Debug)]
pub enum WalletStatus {
    Uncreated,
    Creating,
    Ready,
    Funding,
    Funded,
}
#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct Edition {
    pub token_id: String,
    pub release_ns: U64,
    pub account_id: AccountId,
    pub wallet_status: WalletStatus,
    pub creation_attempt: u64,
    pub gross: U128,
    pub original: U128,
    pub remaining: U128,
    pub cycle: Option<u32>,
    pub beneficiary: AccountId,
    pub exited: bool,
    pub exit_beneficiary: Option<AccountId>,
    pub collection_cycle: Option<u32>,
    pub collected: bool,
    pub transfer_pending: bool,
}
#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct Ticket {
    pub token_id: String,
    pub beneficiary: AccountId,
}
#[near(serializers=[borsh,json])]
#[derive(Clone, PartialEq, Debug)]
pub enum MonthStatus {
    Open,
    Collecting,
    Drawn,
    Carried,
}
#[near(serializers=[borsh,json])]
#[derive(Clone, PartialEq, Debug)]
pub enum PaymentStatus {
    Retryable,
    Pending,
    Paid,
}
#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct Payout {
    pub beneficiary: AccountId,
    pub amount: U128,
    pub status: PaymentStatus,
    pub attempt: u64,
}
#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct Month {
    pub cycle: u32,
    pub cutoff_ns: U64,
    pub entropy_round: U64,
    pub status: MonthStatus,
    pub tokens: Vec<String>,
    pub entries: Vec<Ticket>,
    pub expected_receipts: u32,
    pub received_receipts: u32,
    pub pending_sources: u32,
    pub pot: U128,
    pub rollover_received: U128,
    pub prize: U128,
    pub randomness: Option<String>,
    pub winner: Option<Ticket>,
    pub payout: Option<Payout>,
}
impl Month {
    fn new(cycle: u32) -> Self {
        let cutoff = calendar::cutoff(cycle);
        Self {
            cycle,
            cutoff_ns: U64(cutoff),
            entropy_round: U64(beacon::round_after(cutoff)),
            status: MonthStatus::Open,
            tokens: vec![],
            entries: vec![],
            expected_receipts: 0,
            received_receipts: 0,
            pending_sources: 0,
            pot: U128(0),
            rollover_received: U128(0),
            prize: U128(0),
            randomness: None,
            winner: None,
            payout: None,
        }
    }
}
#[near(serializers=[borsh])]
pub struct Economy {
    pub creator: AccountId,
    pub treasury: AccountId,
    pub editions: UnorderedMap<String, Edition>,
    pub months: UnorderedMap<u32, Month>,
    pub release_tokens: LookupMap<u64, String>,
    pub next_close: u32,
    pub treasury_credit: u128,
    pub treasury_pending: Option<Payout>,
    pub treasury_earned: u128,
    pub gross_earned: u128,
    pub hub_liability: u128,
}
impl Economy {
    fn new(creator: AccountId, treasury: AccountId) -> Self {
        assert!(
            env::current_account_id().as_str().len() <= 40,
            "NFT account must leave room for edition names (max 40 bytes)"
        );
        assert_ne!(creator, env::current_account_id());
        assert_ne!(treasury, env::current_account_id());
        Self {
            creator,
            treasury,
            editions: UnorderedMap::new(b"econ_ed".to_vec()),
            months: UnorderedMap::new(b"econ_mo".to_vec()),
            release_tokens: LookupMap::new(b"econ_re".to_vec()),
            next_close: 202612,
            treasury_credit: 0,
            treasury_pending: None,
            treasury_earned: 0,
            gross_earned: 0,
            hub_liability: 0,
        }
    }
    fn month(&self, c: u32) -> Month {
        self.months.get(&c).unwrap_or_else(|| Month::new(c))
    }
}
fn call(
    account: AccountId,
    method: &str,
    args: near_sdk::serde_json::Value,
    deposit: u128,
    gas: u64,
) -> Promise {
    Promise::new(account).function_call(
        method,
        near_sdk::serde_json::to_vec(&args).unwrap(),
        NearToken::from_yoctonear(deposit),
        Gas::from_tgas(gas),
    )
}
fn callback(method: &str, args: near_sdk::serde_json::Value, gas: u64) -> Promise {
    call(env::current_account_id(), method, args, 0, gas)
}
fn emit(name: &str, data: near_sdk::serde_json::Value) {
    env::log_str(&format!(
        "EVENT_JSON:{}",
        near_sdk::serde_json::json!({"standard":"near_echoes","version":"2.0.0","event":name,"data":[data]})
    ));
}

#[near]
impl EchoNFT {
    #[init]
    pub fn new_economy(
        owner_id: AccountId,
        minter: AccountId,
        auction_contract: AccountId,
        creator: AccountId,
        treasury: AccountId,
    ) -> Self {
        assert_ne!(
            auction_contract, creator,
            "Creator must differ from auction"
        );
        assert_ne!(minter, treasury, "Treasury must differ from operator");
        let mut c = Self::new_production(owner_id, minter, auction_contract);
        c.economy = Some(Economy::new(creator, treasury));
        c
    }

    #[payable]
    pub fn mint_scheduled_artwork(
        &mut self,
        release_ns: U64,
        metadata: TokenMetadata,
        commitment: Commitment,
    ) -> Token {
        let e = self.economy.as_ref().expect("Economy not configured");
        assert!(
            release_ns.0 >= calendar::FIRST_EDITION
                && (release_ns.0 - calendar::FIRST_EDITION) % (7 * calendar::DAY) == 0,
            "Invalid weekly edition date"
        );
        assert!(release_ns.0 <= env::block_timestamp(), "Edition not due");
        assert_eq!(
            commitment.epoch,
            (release_ns.0 - calendar::FIRST_EDITION) / (7 * calendar::DAY) + 1,
            "Epoch/date mismatch"
        );
        assert!(
            e.release_tokens.get(&release_ns.0).is_none(),
            "Release already minted"
        );
        let receiver = if release_ns.0 < calendar::FIRST_AUCTION {
            e.creator.clone()
        } else {
            self.auction_contract.clone().unwrap()
        };
        let token_id = format!("ECHO-{:06}", commitment.epoch);
        let account_id: AccountId = format!(
            "{}.{}",
            calendar::label(release_ns.0),
            env::current_account_id()
        )
        .parse()
        .expect("Invalid edition account");
        let mut metadata = metadata;
        let original = metadata.extra.take();
        assert!(
            original.as_ref().map(|s| s.len() <= 16384).unwrap_or(true),
            "Extra metadata too large"
        );
        let mut extra = original
            .as_ref()
            .and_then(|s| near_sdk::serde_json::from_str::<near_sdk::serde_json::Value>(s).ok())
            .and_then(|v| v.as_object().cloned())
            .unwrap_or_default();
        if extra.is_empty() {
            if let Some(original) = original {
                extra.insert("original_extra".into(), original.into());
            }
        }
        let mut attrs = extra
            .remove("attributes")
            .map(|v| v.as_array().expect("Attributes must be an array").clone())
            .unwrap_or_default();
        assert!(attrs.len() <= 61, "Too many NFT attributes");
        for attr in &attrs {
            assert!(
                attr.get("trait_type")
                    .and_then(|v| v.as_str())
                    .map(|s| !s.is_empty() && s.len() <= 64)
                    .unwrap_or(false),
                "Invalid trait name"
            );
            assert!(
                attr.get("value")
                    .map(|v| v.is_number() || v.as_str().map(|s| s.len() <= 160).unwrap_or(false))
                    .unwrap_or(false),
                "Invalid trait value"
            );
        }
        attrs.retain(|a| {
            !matches!(
                a["trait_type"].as_str(),
                Some("Edition month" | "Edition year" | "Monthly edition")
            )
        });
        let (year, month, _) = calendar::civil(release_ns.0 / calendar::DAY);
        let months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ];
        let monthly: u64 = calendar::label(release_ns.0)
            .rsplit('-')
            .next()
            .unwrap()
            .parse()
            .unwrap();
        attrs.extend([near_sdk::serde_json::json!({"trait_type":"Edition month","value":months[(month-1) as usize]}),
            near_sdk::serde_json::json!({"trait_type":"Edition year","value":year}),near_sdk::serde_json::json!({"trait_type":"Monthly edition","value":monthly})]);
        extra.insert("attributes".into(), attrs.into());
        for (key,value) in near_sdk::serde_json::json!({"schema":"near-echoes-edition-wallet-v1","account_id":account_id,
            "controller":env::current_account_id(),"release_ns":release_ns,"policy":"dedicated-accounts-calendar-month-v1"}).as_object().unwrap(){extra.insert(key.clone(),value.clone());}
        metadata.extra = Some(near_sdk::serde_json::Value::Object(extra).to_string());
        let edition = Edition {
            token_id: token_id.clone(),
            release_ns,
            account_id,
            wallet_status: WalletStatus::Uncreated,
            creation_attempt: 0,
            gross: U128(0),
            original: U128(0),
            remaining: U128(0),
            cycle: None,
            beneficiary: receiver.clone(),
            exited: false,
            exit_beneficiary: None,
            collection_cycle: None,
            collected: false,
            transfer_pending: false,
        };
        self.mint_impl(receiver, metadata, commitment, Some(edition))
    }

    /// Startup/storage reserves come from operator funding, never prize liabilities.
    pub fn create_edition_wallet(&mut self, token_id: String) -> Promise {
        let mut d = self.edition(&token_id);
        assert_eq!(
            d.wallet_status,
            WalletStatus::Uncreated,
            "Wallet exists or creation pending"
        );
        let reserve = (VAULT_WASM.len() as u128 + 6000) * env::storage_byte_cost().as_yoctonear()
            + 10u128.pow(22);
        let stake = env::storage_usage() as u128 * env::storage_byte_cost().as_yoctonear();
        let liability = self.economy.as_ref().unwrap().hub_liability;
        assert!(
            env::account_balance()
                .as_yoctonear()
                .saturating_sub(stake)
                .saturating_sub(liability)
                >= reserve + 5 * 10u128.pow(22),
            "Fund operator storage reserve first"
        );
        d.wallet_status = WalletStatus::Creating;
        d.creation_attempt += 1;
        self.economy
            .as_mut()
            .unwrap()
            .editions
            .insert(&token_id, &d);
        Promise::new(d.account_id.clone()).create_account().transfer(NearToken::from_yoctonear(reserve)).deploy_contract(VAULT_WASM.to_vec())
            .function_call("new",near_sdk::serde_json::to_vec(&near_sdk::serde_json::json!({"controller":env::current_account_id(),"token_id":token_id})).unwrap(),ZERO,Gas::from_tgas(12))
            .then(callback("on_wallet_created",near_sdk::serde_json::json!({"token_id":token_id,"attempt":d.creation_attempt}),12))
    }
    #[private]
    pub fn on_wallet_created(&mut self, token_id: String, attempt: u64) -> bool {
        let mut d = self.edition(&token_id);
        if d.creation_attempt != attempt || d.wallet_status != WalletStatus::Creating {
            return d.wallet_status == WalletStatus::Ready;
        }
        let ok = env::promise_result_checked(0, 1024).is_ok();
        d.wallet_status = if ok {
            WalletStatus::Ready
        } else {
            WalletStatus::Uncreated
        };
        self.economy
            .as_mut()
            .unwrap()
            .editions
            .insert(&token_id, &d);
        emit(
            "wallet_created",
            near_sdk::serde_json::json!({"token_id":token_id,"account_id":d.account_id,"success":ok}),
        );
        ok
    }
    pub fn reconcile_wallet(&self, token_id: String) -> Promise {
        let d = self.edition(&token_id);
        call(
            d.account_id,
            "get_state",
            near_sdk::serde_json::json!({}),
            0,
            10,
        )
        .then(callback(
            "on_wallet_state",
            near_sdk::serde_json::json!({"token_id":token_id,"attempt":d.creation_attempt}),
            15,
        ))
    }
    #[private]
    pub fn on_wallet_state(&mut self, token_id: String, attempt: u64) -> bool {
        let mut d = self.edition(&token_id);
        if attempt != d.creation_attempt {
            return false;
        }
        let state = env::promise_result_checked(0, 8192)
            .ok()
            .and_then(|b| near_sdk::serde_json::from_slice::<near_sdk::serde_json::Value>(&b).ok());
        if let Some(s) = state {
            assert_eq!(
                s["controller"].as_str(),
                Some(env::current_account_id().as_str()),
                "Vault controller mismatch"
            );
            assert_eq!(
                s["token_id"].as_str(),
                Some(token_id.as_str()),
                "Vault token mismatch"
            );
            if d.wallet_status == WalletStatus::Creating {
                d.wallet_status = WalletStatus::Ready;
            }
            if d.wallet_status == WalletStatus::Funding
                && s["original"].as_str() == Some(d.original.0.to_string().as_str())
            {
                d.wallet_status = WalletStatus::Funded;
            }
            self.economy
                .as_mut()
                .unwrap()
                .editions
                .insert(&token_id, &d);
            return true;
        }
        // Unknown state stays pending. Never resend a value transfer based on a missing response.
        false
    }

    #[payable]
    pub fn receive_auction_proceeds(&mut self, token_id: String) -> bool {
        assert_eq!(
            Some(env::predecessor_account_id()),
            self.auction_contract,
            "Auction only"
        );
        let mut d = self.edition(&token_id);
        assert!(d.cycle.is_none(), "Allocation already recorded");
        assert!(
            d.release_ns.0 >= calendar::FIRST_AUCTION,
            "Creator edition cannot enter raffle"
        );
        assert_eq!(
            d.wallet_status,
            WalletStatus::Ready,
            "Edition wallet not ready"
        );
        assert!(
            self.deliveries
                .get(&token_id)
                .map(|x| x.confirmed)
                .unwrap_or(false),
            "NFT delivery required"
        );
        let amount = env::attached_deposit().as_yoctonear();
        assert!(amount >= 10, "Allocation too small");
        let treasury = amount / 5;
        let allocation = amount - treasury;
        let cycle = calendar::cycle(env::block_timestamp());
        let e = self.economy.as_mut().unwrap();
        let mut m = e.month(cycle);
        assert_eq!(m.status, MonthStatus::Open, "Cycle closed");
        assert!(m.tokens.len() < 64, "Monthly edition bound exceeded");
        d.gross = U128(amount);
        d.original = U128(allocation);
        d.remaining = U128(allocation);
        d.cycle = Some(cycle);
        // Transfers can happen between auction delivery and allocation receipts.
        if !d.transfer_pending {
            d.beneficiary = self.tokens.owner_by_id.get(&token_id).unwrap();
        }
        m.tokens.push(token_id.clone());
        e.months.insert(&cycle, &m);
        e.treasury_credit = e.treasury_credit.checked_add(treasury).unwrap();
        e.treasury_earned = e.treasury_earned.checked_add(treasury).unwrap();
        e.gross_earned = e.gross_earned.checked_add(amount).unwrap();
        e.hub_liability = e.hub_liability.checked_add(amount).unwrap();
        e.editions.insert(&token_id, &d);
        emit(
            "allocation_recorded",
            near_sdk::serde_json::json!({"token_id":token_id,"cycle":cycle,"treasury":treasury.to_string(),"allocation":allocation.to_string()}),
        );
        true
    }
    pub fn get_funding_receipt(&self, token_id: String) -> Option<U128> {
        let d = self.edition(&token_id);
        d.cycle.map(|_| d.gross)
    }
    pub fn fund_edition_wallet(&mut self, token_id: String) -> Promise {
        let mut d = self.edition(&token_id);
        assert!(d.cycle.is_some(), "No allocation");
        assert_eq!(
            d.wallet_status,
            WalletStatus::Ready,
            "Funding already pending or complete"
        );
        d.wallet_status = WalletStatus::Funding;
        let e = self.economy.as_mut().unwrap();
        e.hub_liability = e.hub_liability.checked_sub(d.original.0).unwrap();
        e.editions.insert(&token_id, &d);
        call(
            d.account_id,
            "fund",
            near_sdk::serde_json::json!({}),
            d.original.0,
            15,
        )
        .then(callback(
            "on_wallet_funded",
            near_sdk::serde_json::json!({"token_id":token_id}),
            12,
        ))
    }
    #[private]
    pub fn on_wallet_funded(&mut self, token_id: String) -> bool {
        let mut d = self.edition(&token_id);
        if d.wallet_status != WalletStatus::Funding {
            return d.wallet_status == WalletStatus::Funded;
        }
        let ok = env::promise_result_checked(0, 1024).is_ok();
        let e = self.economy.as_mut().unwrap();
        if ok {
            d.wallet_status = WalletStatus::Funded;
        } else {
            d.wallet_status = WalletStatus::Ready;
            e.hub_liability = e.hub_liability.checked_add(d.original.0).unwrap();
        }
        e.editions.insert(&token_id, &d);
        ok
    }
    #[payable]
    pub fn withdraw_edition(&mut self, token_id: String) -> Promise {
        near_sdk::assert_one_yocto();
        let mut d = self.edition(&token_id);
        let cycle = d.cycle.expect("Edition has no funded rights");
        assert!(
            env::block_timestamp() < calendar::cutoff(cycle),
            "Monthly cutoff passed"
        );
        assert!(!d.exited && !d.transfer_pending, "Withdrawal unavailable");
        assert_eq!(d.wallet_status, WalletStatus::Funded, "Wallet not funded");
        let owner = self.tokens.owner_by_id.get(&token_id).unwrap();
        assert_eq!(
            env::predecessor_account_id(),
            owner,
            "Current NFT owner only"
        );
        d.exited = true;
        d.exit_beneficiary = Some(owner.clone());
        d.remaining = U128(d.original.0 - (d.original.0 / 5 * 2 + d.original.0 % 5 * 2 / 5));
        self.economy
            .as_mut()
            .unwrap()
            .editions
            .insert(&token_id, &d);
        emit(
            "early_exit",
            near_sdk::serde_json::json!({"token_id":token_id,"beneficiary":owner,"amount":(d.original.0-d.remaining.0).to_string(),"rollover":d.remaining,"target_cycle":calendar::next(cycle)}),
        );
        self.dispatch_exit(token_id)
    }
    pub fn dispatch_exit(&self, token_id: String) -> Promise {
        let d = self.edition(&token_id);
        let beneficiary = d.exit_beneficiary.expect("No withdrawal requested");
        call(
            d.account_id,
            "withdraw_early",
            near_sdk::serde_json::json!({"beneficiary":beneficiary}),
            0,
            45,
        )
    }

    pub fn close_month(&mut self, cycle: u32) {
        let e = self.economy.as_mut().expect("Economy not configured");
        assert_eq!(cycle, e.next_close, "Close cycles in order");
        assert!(
            env::block_timestamp() >= calendar::cutoff(cycle),
            "Month still open"
        );
        if cycle > 202612 {
            let prev = if cycle % 100 == 1 {
                (cycle / 100 - 1) * 100 + 12
            } else {
                cycle - 1
            };
            let p = e.month(prev);
            assert!(
                matches!(p.status, MonthStatus::Drawn | MonthStatus::Carried)
                    && p.pending_sources == 0,
                "Previous cycle unfinished"
            );
        }
        let mut m = e.month(cycle);
        assert_eq!(m.status, MonthStatus::Open, "Already closed");
        let mut next = e.month(calendar::next(cycle));
        for token in &m.tokens {
            let mut d = e.editions.get(token).unwrap();
            assert!(!d.transfer_pending, "Pending NFT transfer must resolve");
            assert_eq!(
                d.wallet_status,
                WalletStatus::Funded,
                "All allocations must reach wallets first"
            );
            m.pending_sources += 1;
            if d.exited {
                d.collection_cycle = Some(next.cycle);
                next.expected_receipts += 1;
            } else {
                d.collection_cycle = Some(cycle);
                m.expected_receipts += 1;
                m.entries.push(Ticket {
                    token_id: token.clone(),
                    beneficiary: d.beneficiary.clone(),
                });
            }
            e.editions.insert(token, &d);
        }
        // Stable ordering is public before any entropy is available.
        m.entries.sort_by(|a, b| a.token_id.cmp(&b.token_id));
        m.status = MonthStatus::Collecting;
        e.months.insert(&cycle, &m);
        e.months.insert(&next.cycle, &next);
        e.next_close = calendar::next(cycle);
        emit(
            "month_closed",
            near_sdk::serde_json::json!({"cycle":cycle,"entries":m.entries,"entropy_round":m.entropy_round,"cutoff_ns":m.cutoff_ns}),
        );
    }
    pub fn collect_edition(&self, token_id: String) -> Promise {
        let d = self.edition(&token_id);
        let cycle = d.collection_cycle.expect("Month not closed");
        assert!(!d.collected, "Already collected");
        // Ensure the reserved exit is registered before collecting its remainder, even if its original dispatch failed.
        let args = near_sdk::serde_json::json!({"cycle":cycle,"expected":d.remaining,"early_required":d.exited});
        if d.exited {
            call(
                d.account_id.clone(),
                "withdraw_early",
                near_sdk::serde_json::json!({"beneficiary":d.exit_beneficiary.unwrap()}),
                0,
                45,
            )
            .then(call(d.account_id, "collect", args, 0, 50))
        } else {
            call(d.account_id, "collect", args, 0, 50)
        }
    }
    #[payable]
    pub fn receive_vault_funds(&mut self, token_id: String, cycle: u32) {
        let mut d = self.edition(&token_id);
        assert_eq!(
            env::predecessor_account_id(),
            d.account_id,
            "Edition vault only"
        );
        assert_eq!(d.collection_cycle, Some(cycle), "Wrong collection cycle");
        assert!(!d.collected, "Already collected");
        let amount = env::attached_deposit().as_yoctonear();
        assert_eq!(amount, d.remaining.0, "Incorrect collection amount");
        let source = d.cycle.unwrap();
        let e = self.economy.as_mut().unwrap();
        let mut src = e.month(source);
        src.pending_sources = src.pending_sources.checked_sub(1).unwrap();
        e.months.insert(&source, &src);
        let mut target = e.month(cycle);
        assert!(
            matches!(target.status, MonthStatus::Open | MonthStatus::Collecting),
            "Pot already distributed"
        );
        target.received_receipts += 1;
        target.pot.0 = target.pot.0.checked_add(amount).unwrap();
        if source != cycle {
            target.rollover_received.0 = target.rollover_received.0.checked_add(amount).unwrap();
        }
        e.months.insert(&cycle, &target);
        e.hub_liability = e.hub_liability.checked_add(amount).unwrap();
        d.collected = true;
        d.remaining = U128(0);
        e.editions.insert(&token_id, &d);
        emit(
            "vault_collected",
            near_sdk::serde_json::json!({"token_id":token_id,"cycle":cycle,"source_cycle":source,"amount":amount.to_string()}),
        );
    }
    /// Permissionless proof submission. Empty proof is accepted only with zero or one eligible ticket.
    pub fn draw_month(
        &mut self,
        cycle: u32,
        signature: String,
        previous_signature: String,
    ) -> bool {
        let e = self.economy.as_mut().unwrap();
        let mut m = e.month(cycle);
        assert_eq!(m.status, MonthStatus::Collecting, "Month not awaiting draw");
        assert_eq!(m.pending_sources, 0, "Wallet collections incomplete");
        assert_eq!(
            m.received_receipts, m.expected_receipts,
            "Incoming rollover incomplete"
        );
        if m.entries.is_empty() {
            let mut next = e.month(calendar::next(cycle));
            assert_eq!(next.status, MonthStatus::Open, "Next month already closed");
            next.pot.0 = next.pot.0.checked_add(m.pot.0).unwrap();
            next.rollover_received.0 = next.rollover_received.0.checked_add(m.pot.0).unwrap();
            m.status = MonthStatus::Carried;
            m.pot = U128(0);
            e.months.insert(&next.cycle, &next);
            e.months.insert(&cycle, &m);
            return true;
        }
        let index = if m.entries.len() == 1 {
            0
        } else {
            assert!(
                env::block_timestamp() / calendar::SECOND
                    >= beacon::GENESIS + (m.entropy_round.0 - 1) * beacon::PERIOD,
                "Entropy not released"
            );
            let random = beacon::verify(m.entropy_round.0, &signature, &previous_signature)
                .expect("Invalid drand proof");
            m.randomness = Some(beacon::hex(&random));
            beacon::winner(&random, cycle, m.entries.len())
        };
        let winner = m.entries[index].clone();
        m.prize = m.pot;
        m.pot = U128(0);
        m.status = MonthStatus::Drawn;
        m.winner = Some(winner.clone());
        m.payout = Some(Payout {
            beneficiary: winner.beneficiary.clone(),
            amount: m.prize,
            status: PaymentStatus::Retryable,
            attempt: 0,
        });
        e.months.insert(&cycle, &m);
        emit(
            "month_drawn",
            near_sdk::serde_json::json!({"cycle":cycle,"winner":winner,"prize":m.prize,"randomness":m.randomness,"round":m.entropy_round}),
        );
        self.pay_month(cycle).detach();
        true
    }
    pub fn pay_month(&mut self, cycle: u32) -> Promise {
        let e = self.economy.as_mut().unwrap();
        let mut m = e.month(cycle);
        let p = m.payout.as_mut().expect("No prize");
        assert_eq!(p.status, PaymentStatus::Retryable, "Prize paid or pending");
        p.status = PaymentStatus::Pending;
        p.attempt += 1;
        let amount = p.amount.0;
        let who = p.beneficiary.clone();
        let attempt = p.attempt;
        e.hub_liability = e.hub_liability.checked_sub(amount).unwrap();
        e.months.insert(&cycle, &m);
        Promise::new(who)
            .transfer(NearToken::from_yoctonear(amount))
            .then(callback(
                "on_month_payment",
                near_sdk::serde_json::json!({"cycle":cycle,"attempt":attempt}),
                12,
            ))
    }
    #[private]
    pub fn on_month_payment(&mut self, cycle: u32, attempt: u64) -> bool {
        let e = self.economy.as_mut().unwrap();
        let mut m = e.month(cycle);
        let p = m.payout.as_mut().unwrap();
        if p.attempt != attempt || p.status != PaymentStatus::Pending {
            return p.status == PaymentStatus::Paid;
        }
        let ok = env::promise_result_checked(0, 1024).is_ok();
        p.status = if ok {
            PaymentStatus::Paid
        } else {
            PaymentStatus::Retryable
        };
        if !ok {
            e.hub_liability = e.hub_liability.checked_add(p.amount.0).unwrap();
        }
        e.months.insert(&cycle, &m);
        ok
    }
    pub fn process_treasury(&mut self) -> Promise {
        let e = self.economy.as_mut().unwrap();
        assert!(e.treasury_pending.is_none(), "Treasury payment pending");
        let amount = e.treasury_credit;
        assert!(amount > 0, "No treasury credit");
        e.treasury_credit = 0;
        e.hub_liability = e.hub_liability.checked_sub(amount).unwrap();
        e.treasury_pending = Some(Payout {
            beneficiary: e.treasury.clone(),
            amount: U128(amount),
            status: PaymentStatus::Pending,
            attempt: 0,
        });
        Promise::new(e.treasury.clone())
            .transfer(NearToken::from_yoctonear(amount))
            .then(callback(
                "on_treasury_payment",
                near_sdk::serde_json::json!({}),
                12,
            ))
    }
    #[private]
    pub fn on_treasury_payment(&mut self) -> bool {
        let e = self.economy.as_mut().unwrap();
        let Some(p) = e.treasury_pending.take() else {
            return true;
        };
        let ok = env::promise_result_checked(0, 1024).is_ok();
        if !ok {
            e.treasury_credit = e.treasury_credit.checked_add(p.amount.0).unwrap();
            e.hub_liability = e.hub_liability.checked_add(p.amount.0).unwrap();
        }
        ok
    }
    pub fn get_edition_wallet(&self, token_id: String) -> Option<Edition> {
        self.economy
            .as_ref()
            .and_then(|e| e.editions.get(&token_id))
    }
    /// Auction activation must check economic eligibility as well as custody.
    pub fn get_auction_candidate(&self, token_id: String) -> Option<Token> {
        let d = self.economy.as_ref()?.editions.get(&token_id)?;
        if d.release_ns.0 < calendar::FIRST_AUCTION
            || d.wallet_status != WalletStatus::Ready
            || d.cycle.is_some()
            || self.deliveries.get(&token_id)?.confirmed
        {
            return None;
        }
        self.tokens.nft_token(token_id)
    }
    pub fn get_edition_wallets(&self, from_index: Option<u64>, limit: Option<u64>) -> Vec<Edition> {
        self.economy
            .as_ref()
            .map(|e| {
                e.editions
                    .values()
                    .skip(from_index.unwrap_or(0) as usize)
                    .take(limit.unwrap_or(50).min(100) as usize)
                    .collect()
            })
            .unwrap_or_default()
    }
    pub fn get_month(&self, cycle: u32) -> Option<Month> {
        calendar::validate(cycle);
        self.economy.as_ref().and_then(|e| e.months.get(&cycle))
    }
    pub fn get_months(&self, from_index: Option<u64>, limit: Option<u64>) -> Vec<Month> {
        self.economy
            .as_ref()
            .map(|e| {
                e.months
                    .values()
                    .skip(from_index.unwrap_or(0) as usize)
                    .take(limit.unwrap_or(24).min(100) as usize)
                    .collect()
            })
            .unwrap_or_default()
    }
    pub fn get_economy(&self) -> near_sdk::serde_json::Value {
        match &self.economy {
            None => near_sdk::serde_json::json!({"status":"not_configured"}),
            Some(e) => near_sdk::serde_json::json!({
            "status":"onchain","currency":"NEAR","creator":e.creator,"treasury":e.treasury,"treasury_bps":2000,"vault_bps":8000,"early_exit_bps_of_vault":4000,
            "treasury_credit":e.treasury_credit.to_string(),"treasury_pending":e.treasury_pending,"treasury_earned":e.treasury_earned.to_string(),"gross_earned":e.gross_earned.to_string(),
            "hub_liability":e.hub_liability.to_string(),"next_close":e.next_close,"first_edition_ns":calendar::FIRST_EDITION.to_string(),"first_auction_ns":calendar::FIRST_AUCTION.to_string(),
            "vault_code_hash":beacon::hex(&env::sha256(VAULT_WASM)),"drand_chain":beacon::CHAIN,"owner_snapshot":"last_finalized_transfer_before_utc_cutoff","exited_ticket_reentry":false}),
        }
    }
}

impl EchoNFT {
    pub(crate) fn edition(&self, token: &String) -> Edition {
        self.economy
            .as_ref()
            .expect("Economy not configured")
            .editions
            .get(token)
            .expect("Unknown edition")
    }
    pub(crate) fn before_economic_transfer(&mut self, token: &String) {
        if let Some(e) = &self.economy {
            if let Some(d) = e.editions.get(token) {
                assert!(!d.transfer_pending, "NFT transfer resolution pending");
            }
        }
    }
    pub(crate) fn economic_owner_changed(&mut self, token: &String) {
        if let Some(e) = &mut self.economy {
            if let Some(mut d) = e.editions.get(token) {
                if d.cycle
                    .map(|c| env::block_timestamp() < calendar::cutoff(c))
                    .unwrap_or(true)
                {
                    d.beneficiary = self.tokens.owner_by_id.get(token).unwrap();
                }
                e.editions.insert(token, &d);
            }
        }
        self.record_royalty_owner(token, true);
    }
    pub(crate) fn economic_transfer_pending(&mut self, token: &String, pending: bool) {
        if let Some(e) = &mut self.economy {
            if let Some(mut d) = e.editions.get(token) {
                d.transfer_pending = pending;
                e.editions.insert(token, &d);
            }
        }
    }
}
