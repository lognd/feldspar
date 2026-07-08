//! `Interval`: the v1 uncertain-value representation (02-quantities sec.
//! "Values are uncertain"). Frozen, `lo <= hi`, both finite.

use crate::error::CoreError;

/// A closed interval `[lo, hi]`; the worst-case-bounds uncertainty
/// representation that crosses the pack boundary (02).
#[derive(Debug, Clone, Copy, PartialOrd)]
pub struct Interval {
    pub lo: f64,
    pub hi: f64,
}

// Bit-pattern equality, not `==` on the fields: keeps `Eq`/`Hash` (below)
// consistent at the `-0.0`/`0.0` edge, where `-0.0 == 0.0` under IEEE-754
// but the bit patterns (and thus hashes) would otherwise differ.
impl PartialEq for Interval {
    fn eq(&self, other: &Self) -> bool {
        self.bits() == other.bits()
    }
}

impl Interval {
    /// Checked constructor: `Err` on a non-finite bound or `lo > hi`
    /// (02-edge-cases WO-02 rows).
    pub fn new(lo: f64, hi: f64) -> Result<Self, CoreError> {
        if !lo.is_finite() {
            return Err(CoreError::NonFiniteBound(lo));
        }
        if !hi.is_finite() {
            return Err(CoreError::NonFiniteBound(hi));
        }
        if lo > hi {
            return Err(CoreError::InvertedInterval { lo, hi });
        }
        Ok(Self { lo, hi })
    }

    /// The degenerate interval `[x, x]`.
    pub fn point(x: f64) -> Result<Self, CoreError> {
        Self::new(x, x)
    }

    /// `hi - lo`; zero for a degenerate (point) interval.
    pub fn width(&self) -> f64 {
        self.hi - self.lo
    }

    /// `width() / 2`.
    pub fn half_width(&self) -> f64 {
        self.width() / 2.0
    }

    /// `(lo + hi) / 2`.
    pub fn midpoint(&self) -> f64 {
        (self.lo + self.hi) / 2.0
    }

    /// Whether `x` lies in the closed interval.
    pub fn contains(&self, x: f64) -> bool {
        self.lo <= x && x <= self.hi
    }

    /// Whether `self` sits entirely inside `outer` (Domain box-subset rule).
    pub fn is_subset(&self, outer: &Interval) -> bool {
        outer.lo <= self.lo && self.hi <= outer.hi
    }

    /// The smallest interval containing both `self` and `other`.
    pub fn hull(&self, other: &Interval) -> Interval {
        Interval {
            lo: self.lo.min(other.lo),
            hi: self.hi.max(other.hi),
        }
    }

    /// Bit-pattern equality (NaN-free by construction) usable for hashing.
    pub(crate) fn bits(&self) -> (u64, u64) {
        (self.lo.to_bits(), self.hi.to_bits())
    }
}

// `f64` has no `Eq`/`Hash` (NaN breaks reflexivity); `Interval` is
// NaN-free by construction (`new` rejects non-finite bounds), so bit-
// pattern equality is a sound, total `Eq`/`Hash` pair (01-interfaces:
// "frozen, ordered, hashable").
impl Eq for Interval {}

impl std::hash::Hash for Interval {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.bits().hash(state);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_inverted_is_err() {
        assert_eq!(
            Interval::new(2.0, 1.0),
            Err(CoreError::InvertedInterval { lo: 2.0, hi: 1.0 })
        );
    }

    #[test]
    fn new_non_finite_bound_is_err() {
        assert!(matches!(
            Interval::new(0.0, f64::INFINITY),
            Err(CoreError::NonFiniteBound(_))
        ));
        assert!(matches!(
            Interval::new(f64::NAN, 1.0),
            Err(CoreError::NonFiniteBound(_))
        ));
    }

    #[test]
    fn degenerate_point_has_zero_width() {
        let p = Interval::point(3.0).unwrap();
        assert_eq!(p.width(), 0.0);
        assert_eq!(p.lo, 3.0);
        assert_eq!(p.hi, 3.0);
    }

    #[test]
    fn is_subset_checks_full_containment() {
        let inner = Interval::new(1.0, 2.0).unwrap();
        let outer = Interval::new(0.0, 3.0).unwrap();
        assert!(inner.is_subset(&outer));
        assert!(!outer.is_subset(&inner));
    }

    #[test]
    fn hull_is_the_smallest_covering_interval() {
        let a = Interval::new(0.0, 2.0).unwrap();
        let b = Interval::new(1.0, 5.0).unwrap();
        assert_eq!(a.hull(&b), Interval::new(0.0, 5.0).unwrap());
    }
}
