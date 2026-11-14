use super::*;
#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct RoyaltyMonth {
    pub cycle: u32,
    pub pot: U128,
    pub earned: U128,
    pub pending_sales: u32,
    pub snapshot_total: Option<u64>,
    pub processed: u64,
    pub eligible: u64,
    pub share: U128,
    pub paid: u64,
    pub ready: bool,
}
#[near(serializers=[borsh,json])]
#[derive(Clone)]
pub struct RoyaltyShare {
    pub token_id: String,
    pub owner_id: AccountId,
    pub status: String,
}
#[near(serializers=[json])]
pub struct OwnerRow {
    pub index: u64,
    pub token_id: String,
    pub owner_id: Option<AccountId>,
}
#[near(serializers=[json])]
pub struct Owners {
    pub cycle: u32,
    pub total: u64,
    pub offset: U64,
    pub owners: Vec<OwnerRow>,
}
#[near_sdk::ext_contract(ext_owners)]
#[allow(dead_code)]
trait OwnersNFT {
    fn get_royalty_owners(&self, cycle: u32, offset: U64, limit: u32) -> Owners;
}
#[near_sdk::ext_contract(ext_royalty)]
#[allow(dead_code)]
trait RoyaltiesCallbacks {
    fn resolve_royalty_snapshot(&mut self, cycle: u32, offset: U64) -> bool;
    fn resolve_royalty_payment(&mut self, cycle: u32, index: U64) -> bool;
}

#[near]
impl EchoMarket {
    pub fn get_royalty_month(&self, cycle: u32) -> RoyaltyMonth {
        calendar::validate(cycle);
        self.royalty_month(cycle)
    }
    pub fn get_royalty_months(&self, offset: Option<u64>, limit: Option<u64>) -> Vec<RoyaltyMonth> {
        self.royalty_months
            .values_as_vector()
            .iter()
            .skip(offset.unwrap_or(0) as usize)
            .take(limit.unwrap_or(24).min(100) as usize)
            .collect()
    }
    pub fn get_royalty_shares(
        &self,
        cycle: u32,
        offset: U64,
        limit: u32,
    ) -> Vec<near_sdk::serde_json::Value> {
        let m = self.royalty_month(cycle);
        (offset.0..(offset.0+u64::from(limit.min(100))).min(m.eligible)).filter_map(|i|self.royalty_shares.get(&(cycle,i)).map(|s|near_sdk::serde_json::json!({"index":i,"token_id":s.token_id,"owner_id":s.owner_id,"status":s.status,"amount":m.share}))).collect()
    }
    /// Bounded, permissionless batches. Permanent NFT checkpoints let this run
    /// late without changing who owned the collection at the exact cutoff.
    pub fn prepare_royalties(&mut self, cycle: u32) -> Promise {
        assert_eq!(
            cycle, self.next_royalty_close,
            "Close royalty months in order"
        );
        assert!(
            crate::clock::now() >= calendar::cutoff(cycle),
            "Month still open"
        );
        let m = self.royalty_month(cycle);
        assert!(
            !m.ready && m.pending_sales == 0,
            "Month not ready to snapshot"
        );
        ext_owners::ext(self.nft_contract.clone())
            .with_static_gas(Gas::from_tgas(40))
            .with_unused_gas_weight(0)
            .get_royalty_owners(cycle, U64(m.processed), 25)
            .then(
                ext_royalty::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(80))
                    .with_unused_gas_weight(0)
                    .resolve_royalty_snapshot(cycle, U64(m.processed)),
            )
    }
    #[private]
    pub fn resolve_royalty_snapshot(&mut self, cycle: u32, offset: U64) -> bool {
        let mut m = self.royalty_month(cycle);
        if m.ready || m.processed != offset.0 || cycle != self.next_royalty_close {
            return false;
        }
        let Some(answer) = env::promise_result_checked(0, 16384)
            .ok()
            .and_then(|v| near_sdk::serde_json::from_slice::<Owners>(&v).ok())
        else {
            return false;
        };
        if answer.cycle != cycle || answer.offset != offset || answer.owners.len() > 25 {
            return false;
        }
        let total = m.snapshot_total.unwrap_or(answer.total);
        if total > answer.total {
            return false;
        }
        let required = (total.saturating_sub(offset.0)).min(25) as usize;
        if answer.owners.len() < required {
            return false;
        }
        m.snapshot_total = Some(total);
        for (n, row) in answer.owners.into_iter().take(required).enumerate() {
            assert_eq!(row.index, offset.0 + n as u64, "Unexpected ownership index");
            assert!(row.token_id.len() <= 64);
            if let Some(owner) = row.owner_id {
                if owner != self.creator
                    && owner != self.primary_auction
                    && owner != self.nft_contract
                    && owner != env::current_account_id()
                {
                    self.royalty_shares.insert(
                        &(cycle, m.eligible),
                        &RoyaltyShare {
                            token_id: row.token_id,
                            owner_id: owner,
                            status: "Claimable".into(),
                        },
                    );
                    m.eligible += 1;
                }
            }
            m.processed += 1;
        }
        if m.processed == total {
            m.ready = true;
            m.share = U128(if m.eligible == 0 {
                0
            } else {
                m.pot.0 / u128::from(m.eligible)
            });
            let remainder = m.pot.0 - m.share.0 * u128::from(m.eligible);
            m.pot.0 -= remainder;
            self.next_royalty_close = calendar::next(cycle);
            let mut next = self.royalty_month(self.next_royalty_close);
            next.pot.0 = next.pot.0.checked_add(remainder).unwrap();
            self.royalty_months.insert(&self.next_royalty_close, &next);
        }
        self.royalty_months.insert(&cycle, &m);
        self.solvent();
        true
    }
    /// Anyone may deliver the fixed beneficiary's payment. Failed transfers are
    /// retryable; selling the NFT after cutoff does not redirect this entitlement.
    #[payable]
    pub fn pay_royalty(&mut self, cycle: u32, index: U64) -> Promise {
        near_sdk::assert_one_yocto();
        let mut m = self.royalty_month(cycle);
        assert!(m.ready && m.share.0 > 0, "No payable share");
        let mut s = self
            .royalty_shares
            .get(&(cycle, index.0))
            .expect("Unknown share");
        assert!(
            s.status == "Claimable" || s.status == "Retryable",
            "Payment already pending or paid"
        );
        s.status = "Pending".into();
        self.royalty_shares.insert(&(cycle, index.0), &s);
        m.pot.0 = m.pot.0.checked_sub(m.share.0).unwrap();
        self.liability = self.liability.checked_sub(m.share.0).unwrap();
        self.royalty_months.insert(&cycle, &m);
        Promise::new(s.owner_id)
            .transfer(NearToken::from_yoctonear(m.share.0))
            .then(
                ext_royalty::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(20))
                    .with_unused_gas_weight(0)
                    .resolve_royalty_payment(cycle, index),
            )
    }
    #[private]
    pub fn resolve_royalty_payment(&mut self, cycle: u32, index: U64) -> bool {
        let mut s = self
            .royalty_shares
            .get(&(cycle, index.0))
            .expect("Unknown share");
        if s.status != "Pending" {
            return false;
        }
        let mut m = self.royalty_month(cycle);
        let ok = env::promise_result_checked(0, 1024).is_ok();
        if ok {
            s.status = "Paid".into();
            m.paid += 1;
        } else {
            s.status = "Retryable".into();
            m.pot.0 = m.pot.0.checked_add(m.share.0).unwrap();
            self.liability = self.liability.checked_add(m.share.0).unwrap();
        }
        self.royalty_shares.insert(&(cycle, index.0), &s);
        self.royalty_months.insert(&cycle, &m);
        ok
    }
}
impl EchoMarket {
    pub(crate) fn royalty_month(&self, cycle: u32) -> RoyaltyMonth {
        self.royalty_months.get(&cycle).unwrap_or(RoyaltyMonth {
            cycle,
            pot: U128(0),
            earned: U128(0),
            pending_sales: 0,
            snapshot_total: None,
            processed: 0,
            eligible: 0,
            share: U128(0),
            paid: 0,
            ready: false,
        })
    }
}
