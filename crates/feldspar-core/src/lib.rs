//! Core types, unit algebra, error propagation, and planner search (AD-1).
//!
//! Depends on nothing else in the feldspar workspace (00-architecture
//! repository layout). WO-02 populates the frozen, deterministic
//! quantity core (`Interval`, `Accuracy`, `Domain`, `PortDecl`/`Rank`,
//! `Dimension`, `UnitSystem`, the digest home); WO-04 adds propagation/
//! error accumulation (`corner_sweep`, `inflate`, `total_error`).
//!
//! `tracing` is pulled in with the `log-always` feature (AD-8): every
//! span/event emitted here also flows through the `log` crate facade
//! regardless of whether a `tracing::Subscriber` is installed, which is
//! what lets `feldspar-py`'s `pyo3-log` bridge forward it into Python
//! logging without feldspar-core knowing PyO3 exists.

pub mod accuracy;
pub mod digest;
pub mod dimension;
pub mod domain;
pub mod error;
pub mod interval;
pub mod propagation;
pub mod rank;
pub mod search;
pub mod symbolic;
pub mod units;

pub use accuracy::Accuracy;
pub use digest::{canonical_digest, format_f64};
pub use dimension::Dimension;
pub use domain::{Domain, DomainViolation};
pub use error::{CoreError, UnitError};
pub use interval::Interval;
pub use propagation::{
    corner_sweep, enumerate_corners, hull_from_results, inflate, total_error, Propagation,
};
pub use rank::{PortDecl, Rank};
pub use search::{plan, PlanError, Route, RouteStep, Sense, SolverSummary};
pub use units::{BuiltinUnitSystem, UnitSystem};

/// Emits one tracing span and info event; WO-01 smoke test fixture proving
/// a Rust-side span reaches Python logging through the pyo3-log bridge.
// frob:doc docs/modules/feldspar-core.md#core_lib
pub fn emit_smoke_span() {
    let span = tracing::info_span!("feldspar_core.smoke");
    let _enter = span.enter();
    tracing::info!(target: "feldspar_core", "smoke span reached tracing");
}

#[cfg(test)]
mod tests {
    use super::*;

    // frob:tests crates/feldspar-core/src/lib.rs::emit_smoke_span kind="unit"
    #[test]
    fn emit_smoke_span_does_not_panic() {
        emit_smoke_span();
    }
}
