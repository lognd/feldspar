//! Core types, unit algebra, error propagation, and planner search (AD-1).
//!
//! Depends on nothing else in the feldspar workspace (00-architecture
//! repository layout). Populated by WO-02 (quantity core) and WO-04
//! (propagation/error accumulation).
//!
//! `tracing` is pulled in with the `log-always` feature (AD-8): every
//! span/event emitted here also flows through the `log` crate facade
//! regardless of whether a `tracing::Subscriber` is installed, which is
//! what lets `feldspar-py`'s `pyo3-log` bridge forward it into Python
//! logging without feldspar-core knowing PyO3 exists.

/// Emits one tracing span and info event; WO-01 smoke test fixture proving
/// a Rust-side span reaches Python logging through the pyo3-log bridge.
pub fn emit_smoke_span() {
    let span = tracing::info_span!("feldspar_core.smoke");
    let _enter = span.enter();
    tracing::info!(target: "feldspar_core", "smoke span reached tracing");
}
