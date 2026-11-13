//! UTC calendar arithmetic, deliberately independent of relayer clocks.
pub const SECOND: u64 = 1_000_000_000;
pub const DAY: u64 = 86400 * SECOND;
pub const FIRST_EDITION: u64 = 1_794_700_800 * SECOND; // 2026-11-15 00:00 UTC
pub const FIRST_AUCTION: u64 = FIRST_EDITION + 21 * DAY;

pub fn civil(days: u64) -> (u32, u32, u32) {
    let z = days as i64 + 719468;
    let era = z / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let mut y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = mp + if mp < 10 { 3 } else { -9 };
    y += if m <= 2 { 1 } else { 0 };
    (y as u32, m as u32, d as u32)
}
pub fn days(y: u32, m: u32, d: u32) -> u64 {
    let y = y as i64 - if m <= 2 { 1 } else { 0 };
    let era = y / 400;
    let yoe = y - era * 400;
    let mp = m as i64 + if m > 2 { -3 } else { 9 };
    let doy = (153 * mp + 2) / 5 + d as i64 - 1;
    (era * 146097 + yoe * 365 + yoe / 4 - yoe / 100 + doy - 719468) as u64
}
pub fn cycle(ns: u64) -> u32 {
    let (y, m, _) = civil(ns / DAY);
    y * 100 + m
}
pub fn next(c: u32) -> u32 {
    validate(c);
    if c % 100 == 12 {
        (c / 100 + 1) * 100 + 1
    } else {
        c + 1
    }
}
pub fn cutoff(c: u32) -> u64 {
    let n = next(c);
    days(n / 100, n % 100, 1) * DAY
}
pub fn validate(c: u32) {
    assert!(
        (2026..=2500).contains(&(c / 100)) && (1..=12).contains(&(c % 100)),
        "Invalid cycle"
    );
}
pub fn label(ns: u64) -> String {
    let (y, m, d) = civil(ns / DAY);
    let names = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ];
    let number = (d - 1) / 7 + 1 - if y == 2026 && m == 11 { 2 } else { 0 };
    format!("{}{y}-edition-{number}", names[(m - 1) as usize])
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn dates_and_leap_years() {
        assert_eq!(civil(FIRST_EDITION / DAY), (2026, 11, 15));
        assert_eq!(civil(FIRST_AUCTION / DAY), (2026, 12, 6));
        assert_eq!(civil(cutoff(202612) / DAY), (2027, 1, 1));
        assert_eq!(civil(cutoff(202802) / DAY), (2028, 3, 1));
        assert_eq!(label(FIRST_AUCTION), "december2026-edition-1");
    }
}
