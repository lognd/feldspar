//! Property tests: WO-02 (interval ordering/finiteness, domain subset
//! logic, digest stability across map insertion orders, unit
//! round-trips) and WO-04 (corner_sweep hull/dedup correctness).

use std::collections::BTreeMap;

use feldspar_core::{
    canonical_digest, corner_sweep, enumerate_corners, BuiltinUnitSystem, Domain, Interval,
    UnitSystem,
};
use proptest::prelude::*;

proptest! {
    /// Any two finite, ordered bounds construct a valid interval whose
    /// width is non-negative and whose bounds are exactly preserved.
    #[test]
    fn interval_ordering_and_finiteness(a in -1e6f64..1e6, b in -1e6f64..1e6) {
        let (lo, hi) = if a <= b { (a, b) } else { (b, a) };
        let iv = Interval::new(lo, hi).unwrap();
        prop_assert!(iv.width() >= 0.0);
        prop_assert_eq!(iv.lo, lo);
        prop_assert_eq!(iv.hi, hi);
        prop_assert!(iv.lo.is_finite() && iv.hi.is_finite());
    }

    /// An interval nested strictly inside another via padding is always
    /// reported as a subset; the outer interval is a subset of itself.
    #[test]
    fn domain_subset_logic(lo in -1e6f64..1e6, pad in 0f64..1e6, extra in 0f64..1e6) {
        let outer = Interval::new(lo - pad - extra, lo + pad + extra).unwrap();
        let inner = Interval::new(lo - pad, lo + pad).unwrap();
        prop_assert!(inner.is_subset(&outer));
        prop_assert!(outer.is_subset(&outer));
    }

    /// A Domain whose box is built from the same (port, interval) pairs
    /// in different insertion orders (BTreeMap is order-independent by
    /// key) admits the same inputs identically.
    #[test]
    fn domain_admits_independent_of_construction_order(
        lo in -1e3f64..1e3, hi_pad in 0f64..1e3
    ) {
        let hi = lo + hi_pad;
        let iv = Interval::new(lo, hi).unwrap();
        let mut box_a = BTreeMap::new();
        box_a.insert("p1".to_string(), iv);
        box_a.insert("p2".to_string(), iv);
        let mut box_b = BTreeMap::new();
        box_b.insert("p2".to_string(), iv);
        box_b.insert("p1".to_string(), iv);
        let domain_a = Domain::new(box_a, Default::default());
        let domain_b = Domain::new(box_b, Default::default());

        let mut inputs = BTreeMap::new();
        inputs.insert("p1".to_string(), iv);
        inputs.insert("p2".to_string(), iv);
        prop_assert_eq!(
            domain_a.admits(&inputs, &Default::default()),
            domain_b.admits(&inputs, &Default::default())
        );
    }

    /// Digest of a reference map is identical regardless of the order
    /// keys were inserted (canonical-JSON's BTreeMap-backed object
    /// ordering, AD-5).
    #[test]
    fn digest_stability_across_map_insertion_orders(
        a_val in any::<i32>(), b_val in any::<i32>(), c_val in any::<i32>()
    ) {
        let mut m1 = BTreeMap::new();
        m1.insert("a", a_val);
        m1.insert("b", b_val);
        m1.insert("c", c_val);
        let mut m2 = BTreeMap::new();
        m2.insert("c", c_val);
        m2.insert("a", a_val);
        m2.insert("b", b_val);
        prop_assert_eq!(canonical_digest(&m1), canonical_digest(&m2));
    }

    /// Round-tripping any coherent-SI Pa value through MPa ingest/print
    /// recovers the original value.
    #[test]
    fn unit_round_trip_mpa_pa(v in -1e6f64..1e6) {
        let sys = BuiltinUnitSystem::builtin();
        let si = sys.to_si(v, "MPa").unwrap();
        let back = sys.from_si(si, "MPa").unwrap();
        prop_assert!((back - v).abs() < 1e-6 * v.abs().max(1.0));
    }

    /// Round-tripping any degC value through to_si/from_si recovers the
    /// original value (affine unit correctness).
    #[test]
    fn unit_round_trip_degc(v in -200f64..2000.0) {
        let sys = BuiltinUnitSystem::builtin();
        let si = sys.to_si(v, "degC").unwrap();
        let back = sys.from_si(si, "degC").unwrap();
        prop_assert!((back - v).abs() < 1e-9);
    }

    /// The swept hull always contains every individual corner's result
    /// (a hull can never be narrower than any point it was built from).
    #[test]
    fn corner_sweep_hull_contains_all_corner_results(
        a_lo in -1e3f64..1e3, a_pad in 0f64..1e3,
        b_lo in -1e3f64..1e3, b_pad in 0f64..1e3,
        gain in -10f64..10.0,
    ) {
        let mut box_ = BTreeMap::new();
        box_.insert("a".to_string(), Interval::new(a_lo, a_lo + a_pad).unwrap());
        box_.insert("b".to_string(), Interval::new(b_lo, b_lo + b_pad).unwrap());
        let corners = enumerate_corners(&box_);

        let hull = corner_sweep(&box_, |corner| {
            let mut out = BTreeMap::new();
            out.insert("y".to_string(), gain * corner["a"] + corner["b"]);
            Ok::<_, ()>(out)
        }).unwrap();

        for corner in &corners {
            let y = gain * corner["a"] + corner["b"];
            prop_assert!(hull["y"].contains(y));
        }
    }

    /// Dedup correctness: the number of enumerated corners is exactly
    /// 2^(number of non-degenerate ports); a fully degenerate box always
    /// enumerates to exactly one corner, matching a single evaluation.
    #[test]
    fn corner_sweep_dedup_matches_degenerate_port_count(
        a_lo in -1e3f64..1e3, a_pad in 0f64..1e3,
        b_lo in -1e3f64..1e3, b_pad in 0f64..1e3,
        c_lo in -1e3f64..1e3,
    ) {
        let mut box_ = BTreeMap::new();
        box_.insert("a".to_string(), Interval::new(a_lo, a_lo + a_pad).unwrap());
        box_.insert("b".to_string(), Interval::new(b_lo, b_lo + b_pad).unwrap());
        box_.insert("c".to_string(), Interval::new(c_lo, c_lo).unwrap()); // always degenerate

        let non_degenerate = [a_pad, b_pad].iter().filter(|&&p| p > 0.0).count();
        let expected = 1usize << non_degenerate;
        prop_assert_eq!(enumerate_corners(&box_).len(), expected);
    }

    /// A box of only degenerate (point) intervals sweeps to exactly the
    /// single evaluation at that point.
    #[test]
    fn corner_sweep_of_degenerate_box_equals_single_evaluation(
        x in -1e6f64..1e6, y in -1e6f64..1e6
    ) {
        let mut box_ = BTreeMap::new();
        box_.insert("x".to_string(), Interval::new(x, x).unwrap());
        box_.insert("y".to_string(), Interval::new(y, y).unwrap());

        let hull = corner_sweep(&box_, |corner| {
            let mut out = BTreeMap::new();
            out.insert("z".to_string(), corner["x"] + corner["y"]);
            Ok::<_, ()>(out)
        }).unwrap();

        let direct = x + y;
        prop_assert_eq!(hull["z"], Interval::point(direct).unwrap());
    }
}

// frob:tests crates/feldspar-core/src kind="integration"
#[test]
fn domain_admits_own_port_box_after_digesting_it() {
    let iv = Interval::new(-1.0, 1.0).unwrap();
    let mut port_box = BTreeMap::new();
    port_box.insert("p1".to_string(), iv);
    port_box.insert("p2".to_string(), iv);

    let domain = Domain::new(port_box.clone(), Default::default());

    let mut tags = BTreeMap::new();
    tags.insert("kind".to_string(), "domain".to_string());
    let digest_a = canonical_digest(&tags);
    let digest_b = canonical_digest(&tags);
    assert_eq!(
        digest_a, digest_b,
        "digest must be stable across repeated calls over the same map"
    );
    assert!(
        domain.admits(&port_box, &Default::default()).is_ok(),
        "a domain must admit its own port box"
    );
}
