use super::*;
use near_sdk::json_types::U64;
#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct Checkpoint {
    pub timestamp_ns: U64,
    pub owner_id: AccountId,
}

#[near]
impl EchoNFT {
    /// Ownership is the last finalized transfer strictly before UTC month end.
    /// Monthly checkpoints are retained permanently, so a delayed keeper can
    /// distribute old royalties without trusting an off-chain ownership oracle.
    pub fn get_royalty_owners(
        &self,
        cycle: u32,
        offset: U64,
        limit: u32,
    ) -> near_sdk::serde_json::Value {
        let cutoff = calendar::cutoff(cycle);
        assert!(crate::clock::now() >= cutoff, "Month still open");
        let end = (offset.0 + u64::from(limit.min(25))).min(self.royalty_tokens.len());
        let mut owners = vec![];
        for index in offset.0..end {
            let token = self.royalty_tokens.get(index).unwrap();
            let h = self.royalty_history.get(&token).unwrap();
            let mut low = 0;
            let mut high = h.len();
            while low < high {
                let mid = low + (high - low) / 2;
                if h.get(mid).unwrap().timestamp_ns.0 < cutoff {
                    low = mid + 1
                } else {
                    high = mid
                }
            }
            let owner = if low == 0 {
                None
            } else {
                Some(h.get(low - 1).unwrap().owner_id)
            };
            owners.push(
                near_sdk::serde_json::json!({"index":index,"token_id":token,"owner_id":owner}),
            );
        }
        near_sdk::serde_json::json!({"cycle":cycle,"total":self.royalty_tokens.len(),"offset":offset,"owners":owners})
    }
    #[payable]
    pub fn fund_royalty_storage(&mut self) {} // Operator funding; never a royalty deduction.
}
impl EchoNFT {
    pub(crate) fn record_royalty_owner(&mut self, token: &String, check_reserve: bool) {
        let owner = self.tokens.owner_by_id.get(token).unwrap();
        let now = crate::clock::now();
        let initial = env::storage_usage();
        let mut history = self.royalty_history.get(token).unwrap_or_else(|| {
            let mut prefix = b"royalty_checkpoint:".to_vec();
            prefix.extend(env::sha256(token.as_bytes()));
            near_sdk::collections::Vector::new(prefix)
        });
        let checkpoint = Checkpoint {
            timestamp_ns: U64(now),
            owner_id: owner,
        };
        if history.len() > 0
            && calendar::cycle(history.get(history.len() - 1).unwrap().timestamp_ns.0)
                == calendar::cycle(now)
        {
            history.replace(history.len() - 1, &checkpoint);
        } else {
            history.push(&checkpoint);
        }
        self.royalty_history.insert(token, &history);
        if check_reserve && env::storage_usage() > initial {
            let stake = u128::from(env::storage_usage()) * env::storage_byte_cost().as_yoctonear();
            let liabilities = self.economy.as_ref().map(|e| e.hub_liability).unwrap_or(0);
            assert!(
                env::account_balance()
                    .as_yoctonear()
                    .saturating_sub(stake)
                    .saturating_sub(liabilities)
                    >= 5 * 10u128.pow(22),
                "Fund NFT operating storage reserve"
            );
        }
    }
}
