use super::*;
use near_sdk::{test_utils::VMContextBuilder, testing_env};
fn id(s: &str) -> AccountId {
    s.parse().unwrap()
}
fn ctx(who: &str, deposit: u128, time: u64) {
    testing_env!(VMContextBuilder::new()
        .current_account_id(id("art.testnet"))
        .predecessor_account_id(id(who))
        .signer_account_id(id(who))
        .attached_deposit(NearToken::from_yoctonear(deposit))
        .account_balance(NearToken::from_near(100))
        .prepaid_gas(near_sdk::Gas::from_tgas(300))
        .block_timestamp(time)
        .build());
}
fn recipe() -> Vec<u8> {
    let mut d = b"IDART1".to_vec();
    d.extend(1440u16.to_be_bytes());
    d.extend(1440u16.to_be_bytes());
    d.extend([8, 12, 19, 16, 20, 30]);
    d.extend(1u16.to_be_bytes());
    d.extend(32000u16.to_be_bytes());
    d.extend(150u16.to_be_bytes());
    d.extend([128; 48]);
    d.push(6);
    d.extend(500u16.to_be_bytes());
    d.push(1);
    d.extend(6000u16.to_be_bytes());
    d.extend([0, 100, 200, 180, 200, 4, 0, 0]);
    for n in [1000u32, 720000, 720000] {
        d.extend(&n.to_be_bytes()[1..]);
    }
    d
}
fn meta() -> ArtMetadata {
    ArtMetadata {
        title: "A <frozen> study".into(),
        description: "From saved aggregate activity".into(),
        family: "crystalline".into(),
        direction: r##"{"composition":"crystalline","palette":["#112233","#223344","#334455"]}"##
            .into(),
        ai_model: "recorded-near-ai-model".into(),
        seed: "01".repeat(32),
        merkle_root: "02".repeat(32),
        source_provenance: "03".repeat(32),
        source_manifest: "04".repeat(32),
        source_image: "05".repeat(32),
        source_edition: "ECHO-000001".into(),
        source_start: "1".into(),
        source_end: "2".into(),
        record_count: 12,
        traits: "[]".into(),
        motion: r#"{"profile":2,"variant":0,"strength":500,"direction":1,"route_period_ms":6000}"#
            .into(),
        prototype: true,
    }
}
fn draft() -> OnchainArt {
    ctx("operator.testnet", 0, 1);
    let mut c = OnchainArt::new(id("operator.testnet"));
    let d = recipe();
    ctx("operator.testnet", 10u128.pow(24), 1);
    c.begin_edition(
        "ART-1".into(),
        meta(),
        id("team.testnet"),
        hex(&env::sha256(&d)),
        d.len() as u32,
    );
    ctx("operator.testnet", 0, 1);
    c.append_recipe("ART-1".into(), 0, Base64VecU8(d));
    c
}
fn sealed() -> OnchainArt {
    let mut c = draft();
    c.seal_and_mint("ART-1".into());
    c
}
#[test]
fn canonical_views_are_time_independent_self_contained_and_bound_to_nft() {
    let c = sealed();
    let still = c.get_static_svg("ART-1".into());
    let motion = c.get_animated_svg("ART-1".into());
    assert!(still.contains("A &lt;frozen&gt; study"));
    assert!(!still.contains("<animate"));
    assert!(motion.contains("<animate"));
    assert!(!motion.contains("<script"));
    assert!(!motion.contains("href="));
    ctx("anyone.testnet", 0, 999999999);
    assert_eq!(still, c.get_static_svg("ART-1".into()));
    assert_eq!(motion, c.get_animated_svg("ART-1".into()));
    let token = c.nft_token("ART-1".into()).unwrap();
    assert_eq!(token.owner_id, id("team.testnet"));
    let metadata = token.metadata.unwrap();
    assert_eq!(
        metadata.media_hash.unwrap().0,
        env::sha256(still.as_bytes())
    );
    assert!(metadata
        .media
        .unwrap()
        .starts_with("data:image/svg+xml;base64,"));
    let info = c.get_edition("ART-1".into()).unwrap();
    assert_eq!(info["static_sha256"], hex(&env::sha256(still.as_bytes())));
    assert_eq!(c.get_recipe_chunk("ART-1".into(), 0).0, recipe());
    assert_eq!(c.nft_total_supply().0, 1);
}
#[test]
fn transfer_changes_ownership_without_changing_art() {
    let mut c = sealed();
    let mut before = c.get_edition("ART-1".into()).unwrap();
    ctx("team.testnet", 1, 1);
    c.nft_transfer(id("collector.testnet"), "ART-1".into(), None, None);
    before["owner_id"] = "collector.testnet".into();
    assert_eq!(c.get_edition("ART-1".into()).unwrap(), before);
    assert_eq!(
        c.nft_token("ART-1".into()).unwrap().owner_id,
        id("collector.testnet")
    );
}
#[test]
#[should_panic(expected = "Edition sealed")]
fn cannot_replace_sealed_geometry() {
    let mut c = sealed();
    c.append_recipe("ART-1".into(), 0, Base64VecU8(vec![1]));
}
#[test]
#[should_panic(expected = "Edition sealed")]
fn cannot_mint_sealed_edition_again() {
    let mut c = sealed();
    c.seal_and_mint("ART-1".into());
}
#[test]
#[should_panic(expected = "Edition already prepared")]
fn cannot_reroll_prepared_direction() {
    let mut c = draft();
    ctx("operator.testnet", 10u128.pow(24), 1);
    let mut m = meta();
    m.title = "Another choice".into();
    c.begin_edition("ART-1".into(), m, id("team.testnet"), "06".repeat(32), 100);
}
#[test]
#[should_panic(expected = "Duplicate recipe")]
fn cannot_remint_recipe_under_another_id() {
    let mut c = sealed();
    ctx("operator.testnet", 10u128.pow(24), 1);
    c.begin_edition(
        "ART-2".into(),
        meta(),
        id("team.testnet"),
        hex(&env::sha256(&recipe())),
        recipe().len() as u32,
    );
}
#[test]
#[should_panic(expected = "Source edition already registered")]
fn cannot_reroll_source_under_another_id() {
    let mut c = sealed();
    ctx("operator.testnet", 10u128.pow(24), 1);
    c.begin_edition(
        "ART-2".into(),
        meta(),
        id("team.testnet"),
        "06".repeat(32),
        100,
    );
}
#[test]
#[should_panic(expected = "Unexpected offset")]
fn cannot_overwrite_uploaded_chunk() {
    let mut c = draft();
    c.append_recipe("ART-1".into(), 0, Base64VecU8(vec![1]));
}
#[test]
#[should_panic(expected = "Minter only")]
fn collector_cannot_change_art() {
    let mut c = draft();
    ctx("team.testnet", 0, 1);
    c.seal_and_mint("ART-1".into());
}
#[test]
fn decoder_rejects_truncation_unknown_shapes_and_trailing_bytes() {
    let d = recipe();
    assert!(renderer::decode(&d).is_ok());
    for n in 0..d.len() {
        assert!(renderer::decode(&d[..n]).is_err());
    }
    let mut trailing = d.clone();
    trailing.push(0);
    assert!(renderer::decode(&trailing).is_err());
    let mut bad = d.clone();
    bad[76] = 99;
    assert!(renderer::decode(&bad).is_err());
    assert!(renderer::decode(&vec![0; renderer::MAX_BYTES + 1]).is_err());
}
#[test]
fn data_controls_change_motion_while_static_geometry_stays_identical() {
    let d = recipe();
    let scene = renderer::decode(&d).unwrap();
    let still = renderer::svg(&scene, "Study", false).unwrap();
    let motion = renderer::svg(&scene, "Study", true).unwrap();
    let mut changed = d;
    changed[70] = 8;
    changed[71..73].copy_from_slice(&900u16.to_be_bytes());
    let scene = renderer::decode(&changed).unwrap();
    assert_eq!(still, renderer::svg(&scene, "Study", false).unwrap());
    assert_ne!(motion, renderer::svg(&scene, "Study", true).unwrap());
}
#[test]
fn all_six_motion_profiles_are_fixed_self_contained_programs() {
    let mut scene = renderer::decode(&recipe()).unwrap();
    let original = renderer::svg(&scene, "Study", false).unwrap();
    let mut outputs = std::collections::HashSet::new();
    for family in 0..6 {
        scene.style = family * 3;
        assert_eq!(renderer::svg(&scene, "Study", false).unwrap(), original);
        let svg = renderer::svg(&scene, "Study", true).unwrap();
        assert!(!svg.contains("href="));
        assert!(!svg.contains("<script"));
        if family == 5 {
            assert!(svg.contains("type=\"scale\""));
        }
        outputs.insert(svg);
    }
    assert!(outputs.len() >= 3);
}
