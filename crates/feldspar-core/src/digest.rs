//! The one digest home (AD-5): canonical-JSON -> blake3. Every settings/
//! route/cache digest goes through `canonical_digest`.

use serde::Serialize;

/// Canonical-JSON -> blake3 digest, hex-encoded. `serde_json::Value`
/// (and anything serializing through it) stores object keys in a
/// `BTreeMap` by default (no `preserve_order` feature enabled anywhere
/// in the workspace), so two maps built in different insertion orders
/// serialize identically -- this is what makes the digest map-order
/// stable (02-edge-cases WO-02 row) without any extra sorting step here.
// frob:doc docs/modules/feldspar-core.md#core_digest
pub fn canonical_digest<T: Serialize>(value: &T) -> String {
    let bytes = serde_json::to_vec(value).expect("T's Serialize impl cannot fail for our types");
    blake3::hash(&bytes).to_hex().to_string()
}

/// Shortest round-trip `f64` formatting (the 05 deck's one home).
/// `ryu` is pure Rust and platform-independent (AD-13's determinism
/// argument extends to formatting, not just arithmetic).
// frob:doc docs/modules/feldspar-core.md#core_digest
pub fn format_f64(x: f64) -> String {
    let mut buf = ryu::Buffer::new();
    buf.format(x).to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    #[test]
    fn digest_stable_across_map_insertion_orders() {
        let mut a = BTreeMap::new();
        a.insert("b", 2);
        a.insert("a", 1);
        let mut b = BTreeMap::new();
        b.insert("a", 1);
        b.insert("b", 2);
        assert_eq!(canonical_digest(&a), canonical_digest(&b));
    }

    #[test]
    fn digest_differs_for_different_content() {
        let mut a = BTreeMap::new();
        a.insert("a", 1);
        let mut b = BTreeMap::new();
        b.insert("a", 2);
        assert_ne!(canonical_digest(&a), canonical_digest(&b));
    }

    #[test]
    fn format_f64_round_trips() {
        let x = 0.1 + 0.2;
        let s = format_f64(x);
        let parsed: f64 = s.parse().unwrap();
        assert_eq!(parsed, x);
    }
}
