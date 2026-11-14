//! Compiled into rehearsal WASM only. Production builds expose no clock controls.
use near_sdk::{env, AccountId};

#[cfg(feature = "testnet-lab")]
const KEY: &[u8] = b"intent-distortions:lab-clock:v1";

pub fn now() -> u64 {
    #[cfg(feature = "testnet-lab")]
    if let Some(bytes) = env::storage_read(KEY) {
        let (_, time): (AccountId, u64) = near_sdk::serde_json::from_slice(&bytes).unwrap();
        return time;
    }
    env::block_timestamp()
}

#[cfg(feature = "testnet-lab")]
pub fn initialize(authority: AccountId, timestamp: u64) {
    assert!(env::current_account_id().as_str().ends_with(".testnet"), "Lab accounts must end in .testnet");
    assert!(env::storage_read(KEY).is_none(), "Clock already initialized");
    assert!(env::predecessor_account_id() == authority || env::predecessor_account_id() == env::current_account_id(), "Factory/deployer only");
    assert!((1794700800000000000..=2114380800000000000).contains(&timestamp), "Lab date outside supported range");
    env::storage_write(KEY, &near_sdk::serde_json::to_vec(&(authority, timestamp)).unwrap());
}

#[cfg(feature = "testnet-lab")]
pub fn advance(timestamp: u64) {
    let bytes = env::storage_read(KEY).expect("Lab clock not initialized");
    let (authority, previous): (AccountId, u64) = near_sdk::serde_json::from_slice(&bytes).unwrap();
    assert_eq!(env::predecessor_account_id(), authority, "Clock authority only");
    assert!(timestamp >= previous && timestamp <= 2114380800000000000, "Clock must advance monotonically within supported range");
    env::storage_write(KEY, &near_sdk::serde_json::to_vec(&(authority, timestamp)).unwrap());
}

pub fn describe(mut config: near_sdk::serde_json::Value) -> near_sdk::serde_json::Value {
    #[cfg(feature = "testnet-lab")]
    {
        config["testnet_lab"] = true.into();
        config["clock_ns"] = now().to_string().into();
        config["historical_entropy_round"] = 6624326u64.into();
        config["clock_initialized"] = env::storage_read(KEY).is_some().into();
        if let Some(bytes) = env::storage_read(KEY) {
            let (authority, _): (AccountId, u64) = near_sdk::serde_json::from_slice(&bytes).unwrap();
            config["clock_authority"] = authority.to_string().into();
        }
    }
    // Keep the production configuration byte-for-byte compatible.
    #[cfg(not(feature = "testnet-lab"))]
    let _ = &mut config;
    config
}

#[cfg(all(test, feature = "testnet-lab"))]
mod tests {
    use super::*;
    use near_sdk::{test_utils::VMContextBuilder, testing_env};
    fn context(caller: &str) {
        testing_env!(VMContextBuilder::new().current_account_id("clock.testnet".parse().unwrap())
            .predecessor_account_id(caller.parse().unwrap()).build());
    }
    #[test]
    fn clock_advances() {
        context("operator.testnet");
        initialize("operator.testnet".parse().unwrap(), 1794700800000000000);
        advance(1796515200000000000);
        assert_eq!(now(), 1796515200000000000);
    }
    #[test]
    #[should_panic(expected = "Clock authority only")]
    fn rejects_other_signers() {
        context("operator.testnet");
        initialize("operator.testnet".parse().unwrap(), 1794700800000000000);
        context("buyer.testnet");
        advance(1796515200000000000);
    }
    #[test]
    #[should_panic(expected = "monotonically")]
    fn rejects_rewind() {
        context("operator.testnet");
        initialize("operator.testnet".parse().unwrap(), 1796515200000000000);
        advance(1794700800000000000);
    }
}
