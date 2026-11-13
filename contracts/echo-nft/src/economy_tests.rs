use super::*;
use crate::economy::{MonthStatus, PaymentStatus, WalletStatus};
use near_sdk::json_types::U64;
use near_sdk::{
    test_utils::{testing_env_with_promise_results, VMContextBuilder},
    testing_env, NearToken, PromiseResult,
};

fn id(s: &str) -> AccountId {
    s.parse().unwrap()
}
fn ctx(who: &str, deposit: u128, time: u64) {
    testing_env!(VMContextBuilder::new()
        .current_account_id(id("nft.testnet"))
        .predecessor_account_id(id(who))
        .account_balance(NearToken::from_near(1000))
        .attached_deposit(NearToken::from_yoctonear(deposit))
        .block_timestamp(time)
        .build());
}
fn contract() -> EchoNFT {
    ctx("operator.testnet", 0, calendar::FIRST_EDITION);
    EchoNFT::new_economy(
        id("gov.testnet"),
        id("operator.testnet"),
        id("auction.testnet"),
        id("team.testnet"),
        id("treasury.testnet"),
    )
}

#[test]
fn permanent_royalty_ownership_uses_exact_month_end_and_last_finalized_owner() {
    let mut c = contract();
    let date = calendar::FIRST_EDITION;
    let token = mint(&mut c, date);
    ctx("team.testnet", 1, date + calendar::DAY);
    c.nft_transfer(id("alice.testnet"), token.clone(), None, None);
    ctx("alice.testnet", 1, date + 2 * calendar::DAY);
    c.nft_transfer(id("bob.testnet"), token.clone(), None, None);
    assert_eq!(c.royalty_history.get(&token).unwrap().len(), 1); // Same month overwrites, retaining final owner.
    ctx("bob.testnet", 1, calendar::cutoff(202611));
    c.nft_transfer(id("carol.testnet"), token.clone(), None, None);
    let previous = c.get_royalty_owners(202611, U64(0), 25);
    assert_eq!(previous["owners"][0]["owner_id"], "bob.testnet");
    ctx("carol.testnet", 1, calendar::cutoff(202612));
    c.nft_transfer(id("dave.testnet"), token.clone(), None, None);
    assert_eq!(
        c.get_royalty_owners(202611, U64(0), 25)["owners"][0]["owner_id"],
        "bob.testnet"
    );
    assert_eq!(
        c.get_royalty_owners(202612, U64(0), 25)["owners"][0]["owner_id"],
        "carol.testnet"
    );
}

#[test]
#[should_panic(expected = "Edition financial rights changed")]
fn market_cannot_transfer_with_a_stale_reviewed_financial_snapshot() {
    let mut c = contract();
    let token = mint(&mut c, calendar::FIRST_EDITION);
    ctx("team.testnet", 1, calendar::FIRST_EDITION + 1);
    c.market_transfer(
        token,
        id("buyer.testnet"),
        id("team.testnet"),
        1,
        "00".repeat(32),
    );
}

#[test]
fn mint_traits_remain_flat_and_immutable_with_authoritative_calendar_and_wallet() {
    let mut c = contract();
    let date = calendar::FIRST_EDITION;
    ctx("operator.testnet", 10u128.pow(24), date);
    let bytes = vec![77u8; 32];
    let hash = beacon::hex(&bytes);
    let metadata:TokenMetadata=near_sdk::serde_json::from_value(near_sdk::serde_json::json!({"title":"Echo","media":"https://art.example/image","media_hash":Base64VecU8(bytes.clone()),
        "copies":1,"reference":"https://art.example/proof","reference_hash":Base64VecU8(bytes),"extra":near_sdk::serde_json::json!({"trait_schema":"echo-nft-traits-v1","account_id":"fake.near",
            "attributes":[{"trait_type":"Material","value":"glass"},{"trait_type":"Edition month","value":"Fake"}],"traits_reference":{"sha256":"03".repeat(32),"uri":"https://art.example/traits"}}).to_string()})).unwrap();
    let t = c.mint_scheduled_artwork(
        U64(date),
        metadata,
        Commitment {
            epoch: 1,
            image_hash: hash.clone(),
            provenance_hash: hash.clone(),
            merkle_root: hash.clone(),
            seed: hash,
            block_hash: "block".into(),
        },
    );
    let original = t.metadata.unwrap().extra.unwrap();
    let extra: near_sdk::serde_json::Value = near_sdk::serde_json::from_str(&original).unwrap();
    assert_eq!(extra["account_id"], "november2026-edition-1.nft.testnet");
    assert_eq!(extra["attributes"][0]["value"], "glass");
    assert_eq!(extra["attributes"][1]["value"], "November");
    assert_eq!(extra["attributes"][2]["value"], 2026);
    assert_eq!(extra["attributes"][3]["value"], 1);
    assert_eq!(extra["trait_schema"], "echo-nft-traits-v1");
    assert!(extra.get("original_extra").is_none());
    ctx("team.testnet", 1, date + 1);
    c.nft_transfer(id("alice.testnet"), t.token_id.clone(), None, None);
    assert_eq!(
        c.nft_token(t.token_id)
            .unwrap()
            .metadata
            .unwrap()
            .extra
            .unwrap(),
        original
    );
}
fn mint(c: &mut EchoNFT, date: u64) -> String {
    let epoch = (date - calendar::FIRST_EDITION) / (7 * calendar::DAY) + 1;
    ctx("operator.testnet", 10u128.pow(24), date);
    let bytes = vec![epoch as u8; 32];
    let hash = beacon::hex(&bytes);
    let metadata:TokenMetadata=near_sdk::serde_json::from_value(near_sdk::serde_json::json!({"title":"Echo","media":"https://art.example/image","media_hash":Base64VecU8(bytes.clone()),
        "copies":1,"reference":"https://art.example/proof","reference_hash":Base64VecU8(bytes)})).unwrap();
    c.mint_scheduled_artwork(
        U64(date),
        metadata,
        Commitment {
            epoch,
            image_hash: hash.clone(),
            provenance_hash: hash.clone(),
            merkle_root: hash.clone(),
            seed: hash,
            block_hash: "block".into(),
        },
    )
    .token_id
}
fn funded(c: &mut EchoNFT, date: u64) -> String {
    let t = mint(c, date);
    let mut d = c.edition(&t);
    d.wallet_status = WalletStatus::Ready;
    c.economy.as_mut().unwrap().editions.insert(&t, &d);
    ctx("auction.testnet", 1, date);
    c.nft_transfer(id("alice.testnet"), t.clone(), None, None);
    ctx("auction.testnet", 100, date);
    assert!(c.receive_auction_proceeds(t.clone()));
    ctx("keeper.testnet", 0, date);
    let _ = c.fund_edition_wallet(t.clone());
    testing_env_with_promise_results(
        VMContextBuilder::new()
            .current_account_id(id("nft.testnet"))
            .predecessor_account_id(id("nft.testnet"))
            .block_timestamp(date)
            .build(),
        PromiseResult::Successful(vec![]),
    );
    assert!(c.on_wallet_funded(t.clone()));
    t
}
#[test]
fn november_team_mints_and_monthly_account_numbering() {
    let mut c = contract();
    for i in 0..3 {
        let t = mint(&mut c, calendar::FIRST_EDITION + i * 7 * calendar::DAY);
        assert_eq!(c.nft_token(t.clone()).unwrap().owner_id, id("team.testnet"));
        assert_eq!(
            c.edition(&t).account_id.as_str(),
            format!("november2026-edition-{}.nft.testnet", i + 1)
        );
    }
    let t = mint(&mut c, calendar::FIRST_AUCTION);
    assert_eq!(
        c.nft_token(t.clone()).unwrap().owner_id,
        id("auction.testnet")
    );
    assert_eq!(
        c.edition(&t).account_id.as_str(),
        "december2026-edition-1.nft.testnet"
    );
    assert_eq!(c.edition(&t).original.0, 0);
}
#[test]
fn factory_creates_account_without_access_keys() {
    let mut c = contract();
    let t = mint(&mut c, calendar::FIRST_EDITION);
    ctx("keeper.testnet", 0, calendar::FIRST_EDITION);
    let _ = c.create_edition_wallet(t);
    let receipts = format!("{:?}", near_sdk::test_utils::get_created_receipts());
    assert!(receipts.contains("CreateAccount"));
    assert!(receipts.contains("DeployContract"));
    assert!(!receipts.contains("AddKey"));
}

#[test]
fn auction_activation_requires_scheduled_ready_undelivered_edition() {
    let mut c = contract();
    let team = mint(&mut c, calendar::FIRST_EDITION);
    let mut d = c.edition(&team);
    d.wallet_status = WalletStatus::Ready;
    c.economy.as_mut().unwrap().editions.insert(&team, &d);
    assert!(c.get_auction_candidate(team).is_none());
    let token = mint(&mut c, calendar::FIRST_AUCTION);
    assert!(c.get_auction_candidate(token.clone()).is_none());
    let mut d = c.edition(&token);
    d.wallet_status = WalletStatus::Ready;
    c.economy.as_mut().unwrap().editions.insert(&token, &d);
    assert!(c.get_auction_candidate(token.clone()).is_some());
    ctx("auction.testnet", 1, calendar::FIRST_AUCTION);
    c.nft_transfer(id("alice.testnet"), token.clone(), None, None);
    assert!(c.get_auction_candidate(token).is_none());
}
#[test]
fn five_sales_two_exits_conserve_money_and_use_actual_beacon() {
    let mut c = contract();
    let jan3 = calendar::days(2027, 1, 3) * calendar::DAY;
    let tokens: Vec<_> = (0..5)
        .map(|i| funded(&mut c, jan3 + i * 7 * calendar::DAY))
        .collect();
    for t in &tokens[..2] {
        ctx("alice.testnet", 1, jan3 + 29 * calendar::DAY - 1);
        let _ = c.withdraw_edition(t.clone());
        assert_eq!(c.edition(t).remaining.0, 48);
    }
    let cutoff = calendar::cutoff(202701);
    ctx("keeper.testnet", 0, cutoff);
    c.close_month(202612);
    c.draw_month(202612, "".into(), "".into());
    c.close_month(202701);
    for t in &tokens {
        let d = c.edition(t);
        ctx(d.account_id.as_str(), d.remaining.0, cutoff);
        c.receive_vault_funds(t.clone(), d.collection_cycle.unwrap());
    }
    let e = c.economy.as_ref().unwrap();
    assert_eq!(e.treasury_earned, 100);
    let m = e.months.get(&202701).unwrap();
    assert_eq!(m.entries.len(), 3);
    assert_eq!(m.pot.0, 240);
    assert_eq!(e.months.get(&202702).unwrap().pot.0, 96);
    assert_eq!(100 + 2 * 32 + 240 + 96, 500);
    assert_eq!(m.pending_sources, 0);
    assert_eq!(e.hub_liability, 436);
    // Historical proof is deliberately substituted ONLY in native test state;
    // production has no setter and always computes its fixed future round.
    let b: near_sdk::serde_json::Value = near_sdk::serde_json::from_str(include_str!(
        "../../../fixtures/sample-epoch/verified-beacon.json"
    ))
    .unwrap();
    let mut m = m;
    m.entropy_round = U64(b["round"].as_u64().unwrap());
    c.economy.as_mut().unwrap().months.insert(&202701, &m);
    ctx("keeper.testnet", 0, cutoff);
    assert!(c.draw_month(
        202701,
        b["signature"].as_str().unwrap().into(),
        b["previous_signature"].as_str().unwrap().into()
    ));
    let m = c.get_month(202701).unwrap();
    assert_eq!(m.status, MonthStatus::Drawn);
    assert_eq!(m.prize.0, 240);
    assert!(tokens[2..].contains(&m.winner.unwrap().token_id));
    assert_eq!(m.payout.unwrap().status, PaymentStatus::Pending);
    assert_eq!(c.economy.as_ref().unwrap().hub_liability, 196);
}
#[test]
fn ownership_at_cutoff_is_not_changed_by_late_close_or_resale() {
    let mut c = contract();
    let t = funded(&mut c, calendar::FIRST_AUCTION);
    let cutoff = calendar::cutoff(202612);
    ctx("alice.testnet", 1, cutoff - 1);
    c.nft_transfer(id("bob.testnet"), t.clone(), None, None);
    ctx("bob.testnet", 1, cutoff);
    c.nft_transfer(id("carol.testnet"), t.clone(), None, None);
    ctx("keeper.testnet", 0, cutoff + 5 * calendar::DAY);
    c.close_month(202612);
    assert_eq!(
        c.get_month(202612).unwrap().entries[0].beneficiary,
        id("bob.testnet")
    );
    assert_eq!(c.nft_token(t).unwrap().owner_id, id("carol.testnet"));
}
#[test]
fn secondary_buyer_inherits_one_time_exit() {
    let mut c = contract();
    let t = funded(&mut c, calendar::FIRST_AUCTION);
    ctx("alice.testnet", 1, calendar::FIRST_AUCTION + 1);
    c.nft_transfer(id("bob.testnet"), t.clone(), None, None);
    ctx("bob.testnet", 1, calendar::FIRST_AUCTION + 2);
    let _ = c.withdraw_edition(t.clone());
    ctx("bob.testnet", 1, calendar::FIRST_AUCTION + 3);
    c.nft_transfer(id("carol.testnet"), t.clone(), None, None);
    let d = c.edition(&t);
    assert!(d.exited);
    assert_eq!(d.exit_beneficiary, Some(id("bob.testnet")));
    assert_eq!(d.remaining.0, 48);
}
#[test]
#[should_panic(expected = "Withdrawal unavailable")]
fn resale_does_not_reset_exit() {
    let mut c = contract();
    let t = funded(&mut c, calendar::FIRST_AUCTION);
    ctx("alice.testnet", 1, calendar::FIRST_AUCTION + 1);
    let _ = c.withdraw_edition(t.clone());
    ctx("alice.testnet", 1, calendar::FIRST_AUCTION + 2);
    c.nft_transfer(id("bob.testnet"), t.clone(), None, None);
    ctx("bob.testnet", 1, calendar::FIRST_AUCTION + 3);
    let _ = c.withdraw_edition(t);
}
#[test]
#[should_panic(expected = "cutoff passed")]
fn exit_at_boundary_rejected() {
    let mut c = contract();
    let t = funded(&mut c, calendar::FIRST_AUCTION);
    ctx("alice.testnet", 1, calendar::cutoff(202612));
    let _ = c.withdraw_edition(t);
}
#[test]
#[should_panic(expected = "Current NFT owner")]
fn former_owner_cannot_exit() {
    let mut c = contract();
    let t = funded(&mut c, calendar::FIRST_AUCTION);
    ctx("alice.testnet", 1, calendar::FIRST_AUCTION + 1);
    c.nft_transfer(id("bob.testnet"), t.clone(), None, None);
    ctx("alice.testnet", 1, calendar::FIRST_AUCTION + 2);
    let _ = c.withdraw_edition(t);
}
#[test]
#[should_panic(expected = "already recorded")]
fn allocation_cannot_be_replayed() {
    let mut c = contract();
    let t = funded(&mut c, calendar::FIRST_AUCTION);
    ctx("auction.testnet", 100, calendar::FIRST_AUCTION + 1);
    c.receive_auction_proceeds(t);
}
#[test]
#[should_panic(expected = "No allocation")]
fn free_team_nft_has_no_prize_allocation() {
    let mut c = contract();
    let t = mint(&mut c, calendar::FIRST_EDITION);
    ctx("keeper.testnet", 0, calendar::FIRST_EDITION);
    let _ = c.fund_edition_wallet(t);
}
#[test]
fn all_exits_roll_then_empty_month_carries_without_new_tickets() {
    let mut c = contract();
    let t = funded(&mut c, calendar::FIRST_AUCTION);
    ctx("alice.testnet", 1, calendar::FIRST_AUCTION + 1);
    let _ = c.withdraw_edition(t.clone());
    ctx("keeper.testnet", 0, calendar::cutoff(202612));
    c.close_month(202612);
    let d = c.edition(&t);
    ctx(d.account_id.as_str(), 48, calendar::cutoff(202612));
    c.receive_vault_funds(t, 202701);
    ctx("keeper.testnet", 0, calendar::cutoff(202612));
    c.draw_month(202612, "".into(), "".into());
    ctx("keeper.testnet", 0, calendar::cutoff(202701));
    c.close_month(202701);
    c.draw_month(202701, "".into(), "".into());
    assert_eq!(c.get_month(202701).unwrap().status, MonthStatus::Carried);
    let next = c.get_month(202702).unwrap();
    assert_eq!(next.pot.0, 48);
    assert!(next.entries.is_empty());
}
#[test]
fn pending_transfer_cannot_exit_and_failed_transfer_restores_original_rights() {
    let mut c = contract();
    let t = funded(&mut c, calendar::FIRST_AUCTION);
    ctx("alice.testnet", 1, calendar::FIRST_AUCTION + 1);
    let _ = c.nft_transfer_call(id("market.testnet"), t.clone(), None, None, "".into());
    assert!(c.edition(&t).transfer_pending);
    testing_env_with_promise_results(
        VMContextBuilder::new()
            .current_account_id(id("nft.testnet"))
            .predecessor_account_id(id("nft.testnet"))
            .block_timestamp(calendar::FIRST_AUCTION + 2)
            .build(),
        PromiseResult::Successful(b"true".to_vec()),
    );
    c.nft_resolve_transfer(id("alice.testnet"), id("market.testnet"), t.clone(), None);
    assert!(!c.edition(&t).transfer_pending);
    assert_eq!(c.edition(&t).beneficiary, id("alice.testnet"));
}
#[test]
fn failed_funding_returns_liability_and_can_retry_without_double_credit() {
    let mut c = contract();
    let t = funded(&mut c, calendar::FIRST_AUCTION);
    let mut d = c.edition(&t);
    d.wallet_status = WalletStatus::Funding;
    c.economy.as_mut().unwrap().editions.insert(&t, &d);
    testing_env_with_promise_results(
        VMContextBuilder::new()
            .current_account_id(id("nft.testnet"))
            .predecessor_account_id(id("nft.testnet"))
            .build(),
        PromiseResult::Failed,
    );
    assert!(!c.on_wallet_funded(t.clone()));
    assert_eq!(c.economy.as_ref().unwrap().hub_liability, 100);
    assert!(!c.on_wallet_funded(t));
    assert_eq!(c.economy.as_ref().unwrap().hub_liability, 100);
}
