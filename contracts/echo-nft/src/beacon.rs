//! drand default chained BLS verifier. RFC9380 hash-to-G2 plus NEP-488 host pairing.
//! Public key and network parameters are immutable; callers cannot supply a key.
use near_sdk::env;
pub const GENESIS: u64 = 1595431050;
pub const PERIOD: u64 = 30;
pub const CHAIN: &str = "8990e7a9aaed2ffed73dbd7092123d6f289930540d7651336225dc172e51b2ce";
const PK:&str="868f005eb8e6e4ca0a47c8a77ceaa5309a47978a7c71bc5cce96366b5d7a569937c529eeda66c7293784a9402801af31";
const NEG_G1:&str="b7f1d3a73197d7942695638c4fa9ac0fc3688c4f9774b905a14e3a3f171bac586c55e83ff97a1aeffb3af00adb22c6bb";
const MODULUS:&str="1a0111ea397fe69a4b1ba7b6434bacd764774b84f38512bf6730d2a0f6b0f6241eabfffeb153ffffb9feffffffffaaab";
const DST: &[u8] = b"BLS_SIG_BLS12381G2_XMD:SHA-256_SSWU_RO_NUL_";

pub fn round_after(cutoff_ns: u64) -> u64 {
    // Fixed one-minute gap after the cutoff; never selected by a keeper.
    let time = cutoff_ns / 1_000_000_000 + 60;
    (time - GENESIS).div_ceil(PERIOD) + 1
}
pub fn decode(s: &str) -> Vec<u8> {
    assert!(
        s.len() % 2 == 0
            && s.bytes()
                .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()),
        "Invalid lowercase hex"
    );
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
        .collect()
}
pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn reduce(bytes: &[u8]) -> Vec<u8> {
    let p = decode(MODULUS);
    let mut r = vec![0u8; 48];
    for b in bytes {
        for bit in (0..8).rev() {
            let mut carry = (b >> bit) & 1;
            for v in r.iter_mut().rev() {
                let c = *v >> 7;
                *v = (*v << 1) | carry;
                carry = c;
            }
            if r >= p {
                let mut borrow = 0i16;
                for i in (0..48).rev() {
                    let d = r[i] as i16 - p[i] as i16 - borrow;
                    r[i] = d as u8;
                    borrow = if d < 0 { 1 } else { 0 };
                }
            }
        }
    }
    r
}
fn expand(message: &[u8]) -> Vec<u8> {
    // expand_message_xmd(SHA-256), len_in_bytes=256, b_in_bytes=32, r_in_bytes=64.
    let mut dst = DST.to_vec();
    dst.push(DST.len() as u8);
    let mut input = vec![0; 64];
    input.extend_from_slice(message);
    input.extend_from_slice(&[1, 0, 0]);
    input.extend_from_slice(&dst);
    let b0 = env::sha256(&input);
    let mut input = b0.clone();
    input.push(1);
    input.extend_from_slice(&dst);
    let mut last = env::sha256(&input);
    let mut output = last.clone();
    for i in 2..=8 {
        let mut input: Vec<u8> = b0.iter().zip(&last).map(|(a, b)| a ^ b).collect();
        input.push(i);
        input.extend_from_slice(&dst);
        last = env::sha256(&input);
        output.extend_from_slice(&last);
    }
    output
}
pub fn hash_g2(message: &[u8]) -> Option<Vec<u8>> {
    let uniform = expand(message);
    let fields: Vec<Vec<u8>> = uniform.chunks_exact(64).map(reduce).collect();
    // RFC9380 hash_to_field coefficients c0,c1; NEP-488 encodes Fp2 as c1||c0.
    let mut encoded = Vec::with_capacity(192);
    for i in [0, 2] {
        encoded.extend_from_slice(&fields[i + 1]);
        encoded.extend_from_slice(&fields[i]);
    }
    let points = env::bls12381_map_fp2_to_g2(encoded)?;
    if points.len() != 384 {
        return None;
    }
    let mut sum = vec![0];
    sum.extend_from_slice(&points[..192]);
    sum.push(0);
    sum.extend_from_slice(&points[192..]);
    env::bls12381_p2_sum(sum)
}
pub fn verify(round: u64, signature: &str, previous_signature: &str) -> Option<Vec<u8>> {
    if signature.len() != 192 || previous_signature.len() != 192 || round == 0 {
        return None;
    }
    let sig = decode(signature);
    let prev = decode(previous_signature);
    // Reject infinity independently of the pairing identity.
    if sig[0] & 0x40 != 0 {
        return None;
    }
    let mut message = prev;
    message.extend_from_slice(&round.to_be_bytes());
    let digest = env::sha256(&message);
    let hash = hash_g2(&digest)?;
    let pk = env::bls12381_p1_decompress(decode(PK))?;
    let neg = env::bls12381_p1_decompress(decode(NEG_G1))?;
    let signature_point = env::bls12381_p2_decompress(&sig)?;
    let mut pairs = pk;
    pairs.extend_from_slice(&hash);
    pairs.extend_from_slice(&neg);
    pairs.extend_from_slice(&signature_point);
    if env::bls12381_pairing_check(pairs) != Some(true) {
        return None;
    }
    Some(env::sha256(&sig))
}
pub fn winner(randomness: &[u8], cycle: u32, count: usize) -> usize {
    assert!(count > 0 && count <= 64);
    let n = count as u64;
    let threshold = n.wrapping_neg() % n;
    for counter in 0u64.. {
        let mut input = b"NEAR_ECHOES_MONTHLY_DRAW_V1".to_vec();
        input.extend_from_slice(&cycle.to_be_bytes());
        input.extend_from_slice(randomness);
        input.extend_from_slice(&counter.to_be_bytes());
        let bytes = env::sha256(&input);
        let value = u64::from_be_bytes(bytes[..8].try_into().unwrap());
        if value >= threshold {
            return (value % n) as usize;
        }
    }
    unreachable!()
}

#[cfg(test)]
mod tests {
    use super::*;
    use near_sdk::{test_utils::VMContextBuilder, testing_env};
    #[test]
    fn verifies_real_beacon_and_rejects_changed_round() {
        testing_env!(VMContextBuilder::new().build());
        let b: near_sdk::serde_json::Value = near_sdk::serde_json::from_str(include_str!(
            "../../../fixtures/sample-epoch/verified-beacon.json"
        ))
        .unwrap();
        let round = b["round"].as_u64().unwrap();
        let sig = b["signature"].as_str().unwrap();
        let prev = b["previous_signature"].as_str().unwrap();
        let result = verify(round, sig, prev)
            .expect("Captured real drand signature must verify through NEP-488");
        assert_eq!(hex(&result), b["randomness"].as_str().unwrap());
        testing_env!(VMContextBuilder::new().build());
        assert!(verify(round + 1, sig, prev).is_none());
    }
    #[test]
    fn rejects_infinity() {
        testing_env!(VMContextBuilder::new().build());
        assert!(verify(1, &format!("c0{}", "00".repeat(95)), &"00".repeat(96)).is_none());
    }
    #[test]
    fn round_is_strictly_after_cutoff() {
        let c = crate::calendar::cutoff(202612);
        let r = round_after(c);
        assert!(GENESIS + (r - 1) * PERIOD > c / 1_000_000_000);
    }
}
