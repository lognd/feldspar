//! `Interval`: the v1 uncertain-value representation (02-quantities sec.
//! "Values are uncertain"). Frozen, `lo <= hi`, both finite.

use crate::error::CoreError;

/// A closed interval `[lo, hi]`; the worst-case-bounds uncertainty
/// representation that crosses the pack boundary (02).
#[derive(Debug, Clone, Copy, PartialEq, PartialOrd)]
pub struct Interval {
    pub lo: f64,
    pub hi: f64,
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
