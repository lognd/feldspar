//! `Accuracy`: a solver's declared model-error bound (02-quantities "The
//! error split").

use crate::interval::Interval;

/// Model-error bound: `eps(v) = eps_abs + eps_rel * |v|`.
#[derive(Debug, Clone, Copy)]
pub struct Accuracy {
    pub eps_abs: f64,
    pub eps_rel: f64,
}

// Bit-pattern equality; see `Interval`'s impl for the `-0.0`/`0.0` +
// Hash-consistency rationale.
impl PartialEq for Accuracy {
    fn eq(&self, other: &Self) -> bool {
        self.bits() == other.bits()
    }
}

impl Eq for Accuracy {}

impl std::hash::Hash for Accuracy {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.bits().hash(state);
    }
}

impl Accuracy {
    /// `Accuracy(0.0, 0.0)`; the EXACT constant (01-interfaces).
    pub const EXACT: Accuracy = Accuracy {
        eps_abs: 0.0,
        eps_rel: 0.0,
    };

    /// Constructs an `Accuracy`, asserting `eps_abs >= 0`, `eps_rel >= 0`,
    /// both finite (01-interfaces: "both >= 0, finite (ctor checks)"). A
    /// solver author passing a negative/non-finite literal is a
    /// programmer bug, not a recoverable error (house rule: exceptions
    /// only for programmer bugs) -- mirrors `Interval`'s direct-
    /// construction-raises precedent, so this is a panic, not a `Result`.
    pub fn new(eps_abs: f64, eps_rel: f64) -> Self {
        assert!(
            eps_abs.is_finite() && eps_abs >= 0.0,
            "eps_abs must be finite and >= 0, got {eps_abs}"
        );
        assert!(
            eps_rel.is_finite() && eps_rel >= 0.0,
            "eps_rel must be finite and >= 0, got {eps_rel}"
        );
        Self { eps_abs, eps_rel }
    }

    /// The declared model error at value `v`.
    pub fn eps(&self, v: f64) -> f64 {
        self.eps_abs + self.eps_rel * v.abs()
    }

    /// The worst-case `eps` over an interval: `eps_rel` scales with
    /// `|v|`, so the extremum is at whichever endpoint has the larger
    /// absolute value (02-edge-cases: "interval spanning 0 with eps_rel").
    pub fn worst_over(&self, iv: &Interval) -> f64 {
        let worst_v = if iv.lo.abs() >= iv.hi.abs() {
            iv.lo
        } else {
            iv.hi
        };
        self.eps(worst_v)
    }

    pub(crate) fn bits(&self) -> (u64, u64) {
        (self.eps_abs.to_bits(), self.eps_rel.to_bits())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn worst_over_takes_larger_abs_endpoint() {
        let acc = Accuracy {
            eps_abs: 0.0,
            eps_rel: 0.1,
        };
        // spans zero, |lo| < |hi|
        let iv = Interval::new(-1.0, 5.0).unwrap();
        assert_eq!(acc.worst_over(&iv), acc.eps(5.0));

        // |lo| > |hi|
        let iv2 = Interval::new(-10.0, 3.0).unwrap();
        assert_eq!(acc.worst_over(&iv2), acc.eps(-10.0));
    }

    #[test]
    fn exact_has_zero_eps_everywhere() {
        assert_eq!(Accuracy::EXACT.eps(1e9), 0.0);
    }
}
