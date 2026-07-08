//! `Accuracy`: a solver's declared model-error bound (02-quantities "The
//! error split").

use crate::interval::Interval;

/// Model-error bound: `eps(v) = eps_abs + eps_rel * |v|`.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Accuracy {
    pub eps_abs: f64,
    pub eps_rel: f64,
}

impl Accuracy {
    /// `Accuracy(0.0, 0.0)`; the EXACT constant (01-interfaces).
    pub const EXACT: Accuracy = Accuracy {
        eps_abs: 0.0,
        eps_rel: 0.0,
    };

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
