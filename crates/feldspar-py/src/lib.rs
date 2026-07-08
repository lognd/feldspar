//! PyO3 module `_feldspar`: marshalling only, no logic (AD-1 layering).
//!
//! Depends on `feldspar-core` and `feldspar-library`. Populated by later
//! WOs; WO-01 wires only the `pyo3-log` bridge (AD-8) and a smoke-test
//! function proving a Rust `tracing` span reaches Python logging.

use pyo3::prelude::*;

/// Runs `feldspar_core::emit_smoke_span` so the pyo3-log bridge can be
/// exercised end-to-end from Python (WO-01 smoke test).
#[pyfunction]
fn smoke_span() -> PyResult<()> {
    feldspar_core::emit_smoke_span();
    Ok(())
}

/// Module init: installs the pyo3-log bridge once, before anything else
/// in the extension emits a `tracing`/`log` record (AD-8).
#[pymodule]
fn _feldspar(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    pyo3_log::init();
    m.add_function(wrap_pyfunction!(smoke_span, m)?)?;
    Ok(())
}
