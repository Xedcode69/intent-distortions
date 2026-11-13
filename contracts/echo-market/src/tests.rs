use super::*;
use near_sdk::test_utils::VMContextBuilder;
use near_sdk::{test_vm_config, testing_env, PromiseResult, RuntimeFeesConfig};
fn id(s: &str) -> AccountId {
    s.parse().unwrap()
}
fn ctx(who: &str, deposit: u128, result: Option<PromiseResult>) {
    let mut c = VMContextBuilder::new();
    c.current_account_id(id("market.testnet"))
        .predecessor_account_id(id(who))
        .attached_deposit(NearToken::from_yoctonear(deposit))
        .account_balance(NearToken::from_near(1000))
        .block_timestamp(100);
    testing_env!(
        c.build(),
        test_vm_config(),
        RuntimeFeesConfig::test(),
        std::collections::HashMap::default(),
        result.into_iter().collect()
    );
}
fn setup() -> EchoMarket {
    ctx("owner.testnet", 0, None);
    let mut m = EchoMarket::new(id("nft.testnet"), id("auction.testnet"), id("team.testnet"));
    for a in ["alice.testnet", "bob.testnet"] {
        ctx(a, STORAGE * 4, None);
        m.storage_deposit();
    }
    list(&mut m);
    m
}
fn list(m: &mut EchoMarket) {
    ctx("nft.testnet", 0, None);
    m.nft_on_approve(
        "ECHO-000001".into(),
        id("alice.testnet"),
        7,
        near_sdk::serde_json::json!({"price":"1000","expires_ns":"1000000"}).to_string(),
    );
}
#[test]
fn sale_success_credits_seller_once_and_releases_storage() {
    let mut m = setup();
    let l = m.get_listing("ECHO-000001".into()).unwrap();
    ctx("bob.testnet", 1001, None);
    m.buy(l.token_id.clone(), l.nonce, "01".repeat(32));
    let pending = m.get_listing(l.token_id.clone()).unwrap().sale.unwrap();
    ctx("market.testnet", 0, Some(PromiseResult::Successful(vec![])));
    assert!(m.resolve_sale(l.token_id.clone(), pending.id));
    assert_eq!(m.get_balance(id("alice.testnet")).credit.0, 950);
    assert!(m.get_listing(l.token_id.clone()).is_none());
    assert!(!m.resolve_sale(l.token_id, pending.id));
    assert_eq!(m.get_balance(id("alice.testnet")).credit.0, 950);
}
#[test]
fn failed_transfer_refunds_buyer_and_keeps_listing() {
    let mut m = setup();
    let l = m.get_listing("ECHO-000001".into()).unwrap();
    ctx("bob.testnet", 1001, None);
    m.buy(l.token_id.clone(), l.nonce, "01".repeat(32));
    let sale = m.get_listing(l.token_id.clone()).unwrap().sale.unwrap();
    ctx("market.testnet", 0, Some(PromiseResult::Failed));
    assert!(!m.resolve_sale(l.token_id.clone(), sale.id));
    assert_eq!(m.get_balance(id("bob.testnet")).credit.0, 1000);
    assert!(m.get_listing(l.token_id).unwrap().sale.is_none());
}
#[test]
fn offer_escrow_acceptance_and_cancellation_conserve_credit() {
    let mut m = setup();
    let l = m.get_listing("ECHO-000001".into()).unwrap();
    ctx("bob.testnet", 801, None);
    let o = m.make_offer(
        l.token_id.clone(),
        l.nonce,
        U128(800),
        U64(10000),
        "01".repeat(32),
    );
    ctx("bob.testnet", 1, None);
    m.cancel_offer(o.id);
    assert_eq!(m.get_balance(id("bob.testnet")).credit.0, 800);
    ctx("bob.testnet", 901, None);
    let o = m.make_offer(
        l.token_id.clone(),
        l.nonce,
        U128(900),
        U64(10000),
        "01".repeat(32),
    );
    ctx("alice.testnet", 1, None);
    m.accept_offer(o.id);
    assert!(m.get_offer(o.id).is_none());
    let sale = m.get_listing(l.token_id.clone()).unwrap().sale.unwrap();
    ctx("market.testnet", 0, Some(PromiseResult::Successful(vec![])));
    m.resolve_sale(l.token_id, sale.id);
    assert_eq!(m.get_balance(id("alice.testnet")).credit.0, 855);
}
#[test]
fn failed_withdrawal_restores_credit_and_can_retry() {
    let mut m = setup();
    m.credit(&id("bob.testnet"), 1000);
    m.liability += 1000;
    ctx("bob.testnet", 1, None);
    m.withdraw_credit();
    assert_eq!(m.get_balance(id("bob.testnet")).credit.0, 0);
    ctx("market.testnet", 0, Some(PromiseResult::Failed));
    assert!(!m.resolve_withdraw(id("bob.testnet")));
    assert_eq!(m.get_balance(id("bob.testnet")).credit.0, 1000);
    ctx("bob.testnet", 1, None);
    m.withdraw_credit();
    ctx("market.testnet", 0, Some(PromiseResult::Successful(vec![])));
    assert!(m.resolve_withdraw(id("bob.testnet")));
    assert_eq!(m.get_balance(id("bob.testnet")).credit.0, 0);
}
#[test]
#[should_panic(expected = "Canonical NFT only")]
fn forged_approval_is_rejected() {
    let mut m = setup();
    ctx("bob.testnet", 0, None);
    m.nft_on_approve("fake".into(), id("alice.testnet"), 8, "{}".into());
}
#[test]
#[should_panic(expected = "Listing changed")]
fn old_nonce_cannot_buy_a_relisting() {
    let mut m = setup();
    let l = m.get_listing("ECHO-000001".into()).unwrap();
    list(&mut m);
    ctx("bob.testnet", 1001, None);
    m.buy(l.token_id, l.nonce, "01".repeat(32));
}
#[test]
#[should_panic(expected = "Sale pending")]
fn concurrent_buy_is_rejected() {
    let mut m = setup();
    let l = m.get_listing("ECHO-000001".into()).unwrap();
    ctx("bob.testnet", 1001, None);
    m.buy(l.token_id.clone(), l.nonce, "01".repeat(32));
    m.buy(l.token_id, l.nonce, "01".repeat(32));
}
#[test]
#[should_panic(expected = "Attach price plus one yocto")]
fn underpayment_is_rejected() {
    let mut m = setup();
    let l = m.get_listing("ECHO-000001".into()).unwrap();
    ctx("bob.testnet", 1000, None);
    m.buy(l.token_id, l.nonce, "01".repeat(32));
}
#[test]
#[should_panic(expected = "Seller only")]
fn buyer_cannot_accept_own_offer() {
    let mut m = setup();
    let l = m.get_listing("ECHO-000001".into()).unwrap();
    ctx("bob.testnet", 801, None);
    let o = m.make_offer(l.token_id, l.nonce, U128(800), U64(10000), "01".repeat(32));
    ctx("bob.testnet", 1, None);
    m.accept_offer(o.id);
}
#[test]
fn cancelled_listing_does_not_trap_outstanding_offer() {
    let mut m = setup();
    let l = m.get_listing("ECHO-000001".into()).unwrap();
    ctx("bob.testnet", 801, None);
    let o = m.make_offer(
        l.token_id.clone(),
        l.nonce,
        U128(800),
        U64(10000),
        "01".repeat(32),
    );
    ctx("alice.testnet", 1, None);
    m.cancel_listing(l.token_id, l.nonce);
    ctx("bob.testnet", 1, None);
    m.cancel_offer(o.id);
    assert_eq!(m.get_balance(id("bob.testnet")).credit.0, 800);
}

fn snapshot_result(cycle: u32, owners: Vec<Option<&str>>) -> Vec<u8> {
    near_sdk::serde_json::to_vec(&near_sdk::serde_json::json!({"cycle":cycle,"total":owners.len(),"offset":"0",
        "owners":owners.into_iter().enumerate().map(|(i,o)|near_sdk::serde_json::json!({"index":i,"token_id":format!("ECHO-{i:06}"),"owner_id":o})).collect::<Vec<_>>()})).unwrap()
}
#[test]
fn royalties_exclude_team_and_custody_count_each_nft_and_preserve_dust() {
    let mut m = setup();
    m.next_royalty_close = 202611;
    let mut month = m.royalty_month(202611);
    month.pot = U128(1013);
    month.earned = U128(1013);
    m.royalty_months.insert(&202611, &month);
    m.liability += 1013;
    let result = snapshot_result(
        202611,
        vec![
            Some("team.testnet"),
            Some("auction.testnet"),
            Some("alice.testnet"),
            Some("alice.testnet"),
            Some("bob.testnet"),
            None,
        ],
    );
    ctx("market.testnet", 0, Some(PromiseResult::Successful(result)));
    assert!(m.resolve_royalty_snapshot(202611, U64(0)));
    let month = m.royalty_month(202611);
    assert_eq!(month.eligible, 3);
    assert_eq!(month.share.0, 337);
    assert_eq!(month.pot.0, 1011);
    assert_eq!(m.royalty_month(202612).pot.0, 2);
    assert_eq!(
        m.royalty_shares.get(&(202611, 0)).unwrap().owner_id,
        id("alice.testnet")
    );
    assert_eq!(
        m.royalty_shares.get(&(202611, 1)).unwrap().owner_id,
        id("alice.testnet")
    );
    assert!(!m.resolve_royalty_snapshot(202611, U64(0))); // No duplicate entitlements.
    ctx("bob.testnet", 1, None);
    m.pay_royalty(202611, U64(0));
    ctx("market.testnet", 0, Some(PromiseResult::Failed));
    assert!(!m.resolve_royalty_payment(202611, U64(0)));
    assert_eq!(m.royalty_month(202611).pot.0, 1011);
    assert_eq!(
        m.royalty_shares.get(&(202611, 0)).unwrap().status,
        "Retryable"
    );
    ctx("bob.testnet", 1, None);
    m.pay_royalty(202611, U64(0));
    ctx("market.testnet", 0, Some(PromiseResult::Successful(vec![])));
    assert!(m.resolve_royalty_payment(202611, U64(0)));
    assert!(!m.resolve_royalty_payment(202611, U64(0)));
    assert_eq!(m.royalty_month(202611).pot.0, 674);
    assert_eq!(m.royalty_month(202611).paid, 1);
}
#[test]
fn no_eligible_holder_rolls_entire_pool_forward() {
    let mut m = setup();
    m.next_royalty_close = 202611;
    let mut month = m.royalty_month(202611);
    month.pot = U128(100);
    m.royalty_months.insert(&202611, &month);
    m.liability += 100;
    ctx(
        "market.testnet",
        0,
        Some(PromiseResult::Successful(snapshot_result(
            202611,
            vec![Some("team.testnet")],
        ))),
    );
    assert!(m.resolve_royalty_snapshot(202611, U64(0)));
    assert_eq!(m.royalty_month(202611).eligible, 0);
    assert_eq!(m.royalty_month(202611).pot.0, 0);
    assert_eq!(m.royalty_month(202612).pot.0, 100);
}
