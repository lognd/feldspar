//! PyO3 module `_feldspar`: marshalling only, no logic (AD-1 layering).
//!
//! Depends on `feldspar-core` and `feldspar-library`. WO-01 wired the
//! `pyo3-log` bridge (AD-8) and the tracing-span smoke test; WO-02 adds
//! the quantity core's frozen classes (`Interval`, `Accuracy`, `Domain`,
//! `PortDecl`/`Rank`, `Dimension`, `UnitSystem`) and the digest home
//! (`canonical_digest`, `format_f64`). Result-returning methods in
//! 01-interfaces are exposed here as raising "raw/checked" primitives
//! (see `errors.rs`); `python/feldspar/core.py` wraps them into the
//! typani `Result` values the public Python surface promises.

use pyo3::prelude::*;

mod accuracy;
mod digest;
mod dimension;
mod domain;
mod errors;
mod interval;
mod rank;
mod units;

use accuracy::{exact_accuracy, PyAccuracy};
use digest::{canonical_digest, format_f64};
use dimension::PyDimension;
use domain::PyDomain;
use interval::PyInterval;
use rank::{PyPortDecl, PyRank};
use units::PyUnitSystem;

/// Runs `feldspar_core::emit_smoke_span` so the pyo3-log bridge can be
/// exercised end-to-end from Python (WO-01 smoke test).
#[pyfunction]
fn smoke_span() -> PyResult<()> {
    feldspar_core::emit_smoke_span();
    Ok(())
}

/// Module init: installs the pyo3-log bridge once, before anything else
/// in the extension emits a `tracing`/`log` record (AD-8), then
/// registers the quantity-core classes and free functions.
#[pymodule]
fn _feldspar(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    pyo3_log::init();

    m.add_function(wrap_pyfunction!(smoke_span, m)?)?;
    m.add_function(wrap_pyfunction!(canonical_digest, m)?)?;
    m.add_function(wrap_pyfunction!(format_f64, m)?)?;
    m.add_function(wrap_pyfunction!(exact_accuracy, m)?)?;

    m.add_class::<PyInterval>()?;
    m.add_class::<PyAccuracy>()?;
    m.add_class::<PyDimension>()?;
    m.add_class::<PyRank>()?;
    m.add_class::<PyPortDecl>()?;
    m.add_class::<PyDomain>()?;
    m.add_class::<PyUnitSystem>()?;

    m.add(
        "CoreErrorRaised",
        _py.get_type_bound::<errors::CoreErrorRaised>(),
    )?;
    m.add(
        "UnitErrorRaised",
        _py.get_type_bound::<errors::UnitErrorRaised>(),
    )?;
    m.add(
        "DomainViolationRaised",
        _py.get_type_bound::<errors::DomainViolationRaised>(),
    )?;

    Ok(())
}
