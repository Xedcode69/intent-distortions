//! Keyless, single-edition native-NEAR vault. No arbitrary call, key or upgrade method.
use near_sdk::json_types::U128;
use near_sdk::{env, near, AccountId, Gas, NearToken, PanicOnDefault, Promise, PromiseOrValue};

#[near(serializers=[borsh,json])]
#[derive(Clone, Debug, PartialEq)]
pub enum PaymentStatus {
    Pending,
    Retryable,
    Paid,
}

#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct Payment {
    pub recipient: AccountId,
    pub amount: U128,
    pub status: PaymentStatus,
    pub attempt: u64,
    pub cycle: Option<u32>,
}

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct EditionVault {
    controller: AccountId,
    token_id: String,
    original: u128,
    available: u128,
    early: Option<Payment>,
    collection: Option<Payment>,
}

#[near]
impl EditionVault {
    #[init]
    pub fn new(controller: AccountId, token_id: String) -> Self {
        assert_eq!(env::predecessor_account_id(), controller, "Factory only");
        assert!(
            env::current_account_id()
                .as_str()
                .ends_with(&format!(".{controller}")),
            "Must be factory subaccount"
        );
        assert!(token_id.len() <= 64);
        Self {
            controller,
            token_id,
            original: 0,
            available: 0,
            early: None,
            collection: None,
        }
    }

    #[payable]
    pub fn fund(&mut self) {
        self.authorize();
        assert_eq!(self.original, 0, "Already funded");
        let amount = env::attached_deposit().as_yoctonear();
        assert!(amount > 0, "Empty allocation");
        self.original = amount;
        self.available = amount;
    }

    pub fn withdraw_early(&mut self, beneficiary: AccountId) -> PromiseOrValue<bool> {
        self.authorize();
        if let Some(payment) = &self.early {
            assert_eq!(payment.recipient, beneficiary, "Beneficiary fixed");
            return self.retry_payment(false);
        }
        assert!(
            self.original > 0 && self.collection.is_none(),
            "Allocation unavailable"
        );
        let amount = self.original / 5 * 2 + self.original % 5 * 2 / 5;
        assert!(amount > 0, "Allocation too small");
        self.available = self.available.checked_sub(amount).unwrap();
        self.early = Some(Payment {
            recipient: beneficiary,
            amount: U128(amount),
            status: PaymentStatus::Retryable,
            attempt: 0,
            cycle: None,
        });
        self.retry_payment(false)
    }

    pub fn collect(
        &mut self,
        cycle: u32,
        expected: U128,
        early_required: bool,
    ) -> PromiseOrValue<bool> {
        self.authorize();
        assert!(
            !early_required || self.early.is_some(),
            "Register early withdrawal first"
        );
        if let Some(payment) = &self.collection {
            assert_eq!(payment.cycle, Some(cycle), "Collection cycle fixed");
            assert_eq!(payment.amount, expected, "Collection amount fixed");
            return self.retry_payment(true);
        }
        assert!(
            self.original > 0 && self.available > 0,
            "Allocation unavailable"
        );
        let amount = self.available;
        assert_eq!(amount, expected.0, "Collection amount mismatch");
        self.available = 0;
        self.collection = Some(Payment {
            recipient: self.controller.clone(),
            amount: U128(amount),
            status: PaymentStatus::Retryable,
            attempt: 0,
            cycle: Some(cycle),
        });
        self.retry_payment(true)
    }

    /// Anyone may retry a failed payment; its amount and destination never change.
    pub fn retry(&mut self, collection: bool) -> PromiseOrValue<bool> {
        self.retry_payment(collection)
    }

    #[private]
    pub fn on_payment(&mut self, collection: bool, attempt: u64) -> bool {
        let payment = if collection {
            &mut self.collection
        } else {
            &mut self.early
        };
        let p = payment.as_mut().expect("Unknown payment");
        if p.attempt != attempt || p.status != PaymentStatus::Pending {
            return p.status == PaymentStatus::Paid;
        }
        let success = env::promise_result_checked(0, 1024).is_ok();
        p.status = if success {
            PaymentStatus::Paid
        } else {
            PaymentStatus::Retryable
        };
        // Failed payments remain reserved. They are never added to available funds.
        success
    }

    pub fn get_state(&self) -> near_sdk::serde_json::Value {
        near_sdk::serde_json::json!({"version":"echo-vault-1","controller":self.controller,"token_id":self.token_id,
            "original":self.original.to_string(),"available":self.available.to_string(),"early":self.early,"collection":self.collection})
    }
}

impl EditionVault {
    fn authorize(&self) {
        assert_eq!(
            env::predecessor_account_id(),
            self.controller,
            "Controller only"
        );
    }
    fn retry_payment(&mut self, collection: bool) -> PromiseOrValue<bool> {
        let p = if collection {
            self.collection.as_mut()
        } else {
            self.early.as_mut()
        }
        .expect("Unknown payment");
        if p.status != PaymentStatus::Retryable {
            return PromiseOrValue::Value(p.status == PaymentStatus::Paid);
        }
        p.attempt = p.attempt.checked_add(1).unwrap();
        p.status = PaymentStatus::Pending;
        let attempt = p.attempt;
        let promise = if collection {
            Promise::new(self.controller.clone()).function_call("receive_vault_funds",
                near_sdk::serde_json::to_vec(&near_sdk::serde_json::json!({"token_id":self.token_id,"cycle":p.cycle.unwrap()})).unwrap(),
                NearToken::from_yoctonear(p.amount.0), Gas::from_tgas(25))
        } else {
            Promise::new(p.recipient.clone()).transfer(NearToken::from_yoctonear(p.amount.0))
        };
        promise
            .then(
                Promise::new(env::current_account_id()).function_call(
                    "on_payment",
                    near_sdk::serde_json::to_vec(
                        &near_sdk::serde_json::json!({"collection":collection,"attempt":attempt}),
                    )
                    .unwrap(),
                    NearToken::from_yoctonear(0),
                    Gas::from_tgas(10),
                ),
            )
            .into()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use near_sdk::{
        test_utils::{testing_env_with_promise_results, VMContextBuilder},
        testing_env, PromiseResult,
    };
    fn ctx(who: &str, deposit: u128) -> near_sdk::VMContext {
        VMContextBuilder::new()
            .current_account_id("edition.nft.testnet".parse().unwrap())
            .predecessor_account_id(who.parse().unwrap())
            .attached_deposit(NearToken::from_yoctonear(deposit))
            .build()
    }
    #[test]
    fn failed_exit_remains_reserved_and_collection_cannot_spend_it() {
        testing_env!(ctx("nft.testnet", 0));
        let mut v = EditionVault::new("nft.testnet".parse().unwrap(), "ECHO-1".into());
        testing_env!(ctx("nft.testnet", 80));
        v.fund();
        testing_env!(ctx("nft.testnet", 0));
        v.withdraw_early("alice.testnet".parse().unwrap());
        assert_eq!(v.available, 48);
        testing_env_with_promise_results(ctx("edition.nft.testnet", 0), PromiseResult::Failed);
        assert!(!v.on_payment(false, 1));
        assert_eq!(v.available, 48);
        testing_env!(ctx("nft.testnet", 0));
        v.collect(202701, U128(48), true);
        assert_eq!(v.collection.as_ref().unwrap().amount.0, 48);
        testing_env!(ctx("anyone.testnet", 0));
        v.retry(false);
        assert_eq!(v.early.as_ref().unwrap().amount.0, 32);
        assert_eq!(v.early.as_ref().unwrap().attempt, 2);
        assert_eq!(v.available, 0);
    }
    #[test]
    #[should_panic(expected = "Controller only")]
    fn owner_cannot_bypass_controller() {
        testing_env!(ctx("nft.testnet", 0));
        let mut v = EditionVault::new("nft.testnet".parse().unwrap(), "ECHO-1".into());
        testing_env!(ctx("thief.testnet", 80));
        v.fund();
    }
    #[test]
    fn duplicate_calls_do_not_schedule_second_payment() {
        testing_env!(ctx("nft.testnet", 0));
        let mut v = EditionVault::new("nft.testnet".parse().unwrap(), "ECHO-1".into());
        testing_env!(ctx("nft.testnet", 80));
        v.fund();
        testing_env!(ctx("nft.testnet", 0));
        v.withdraw_early("alice.testnet".parse().unwrap());
        v.withdraw_early("alice.testnet".parse().unwrap());
        assert_eq!(v.early.unwrap().attempt, 1);
        assert_eq!(v.available, 48);
    }
    #[test]
    #[should_panic(expected = "Register early withdrawal first")]
    fn rollover_cannot_collect_before_exit_is_reserved() {
        testing_env!(ctx("nft.testnet", 0));
        let mut v = EditionVault::new("nft.testnet".parse().unwrap(), "ECHO-1".into());
        testing_env!(ctx("nft.testnet", 80));
        v.fund();
        testing_env!(ctx("nft.testnet", 0));
        let _ = v.collect(202701, U128(48), true);
    }
}
