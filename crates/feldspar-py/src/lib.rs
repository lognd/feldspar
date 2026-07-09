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
// PyO3 0.22's macros emit a `gil-refs` cfg newer rustc doesn't know; the
// warning is upstream boilerplate, not our code (removed when pyo3 bumps).
#![allow(unexpected_cfgs)]
// PyO3's generated wrappers call `.into()` on already-`PyErr` results;
// the useless-conversion is in generated glue, not our bodies.
#![allow(clippy::useless_conversion)]

use pyo3::prelude::*;

mod accuracy;
mod digest;
mod dimension;
mod domain;
mod errors;
mod interval;
mod library;
mod propagation;
mod rank;
mod search;
mod symbolic;
mod units;

use accuracy::{exact_accuracy, PyAccuracy};
use digest::{canonical_digest, format_f64};
use dimension::PyDimension;
use domain::PyDomain;
use interval::PyInterval;
use library::{
    mech_bore_von_mises_py, mech_cantilever_required_youngs_modulus_py,
    mech_cantilever_tip_deflection_py, mech_lame_hoop_stress_bore_py,
    mech_lame_radial_stress_bore_py, mech_rect_second_moment_py, mech_von_mises_principal_py,
};
use propagation::{corner_sweep_py, inflate_py, total_error_py};
use rank::{PyPortDecl, PyRank};
use search::{plan_py, PyRoute, PyRouteStep, PySolverInput};
use symbolic::{invert_for_py, invertible_targets_py, predicate_to_box_py, PyExpr, PyPredicate};
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
    m.add_function(wrap_pyfunction!(corner_sweep_py, m)?)?;
    m.add_function(wrap_pyfunction!(inflate_py, m)?)?;
    m.add_function(wrap_pyfunction!(total_error_py, m)?)?;
    m.add_function(wrap_pyfunction!(plan_py, m)?)?;
    m.add_function(wrap_pyfunction!(mech_rect_second_moment_py, m)?)?;
    m.add_function(wrap_pyfunction!(mech_cantilever_tip_deflection_py, m)?)?;
    m.add_function(wrap_pyfunction!(
        mech_cantilever_required_youngs_modulus_py,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(mech_lame_hoop_stress_bore_py, m)?)?;
    m.add_function(wrap_pyfunction!(mech_lame_radial_stress_bore_py, m)?)?;
    m.add_function(wrap_pyfunction!(mech_von_mises_principal_py, m)?)?;
    m.add_function(wrap_pyfunction!(mech_bore_von_mises_py, m)?)?;
    m.add_function(wrap_pyfunction!(invert_for_py, m)?)?;
    m.add_function(wrap_pyfunction!(invertible_targets_py, m)?)?;
    m.add_function(wrap_pyfunction!(predicate_to_box_py, m)?)?;

    m.add_class::<PyInterval>()?;
    m.add_class::<PyAccuracy>()?;
    m.add_class::<PyDimension>()?;
    m.add_class::<PyRank>()?;
    m.add_class::<PyPortDecl>()?;
    m.add_class::<PyDomain>()?;
    m.add_class::<PyUnitSystem>()?;
    m.add_class::<PySolverInput>()?;
    m.add_class::<PyRoute>()?;
    m.add_class::<PyRouteStep>()?;
    m.add_class::<PyExpr>()?;
    m.add_class::<PyPredicate>()?;

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
    m.add(
        "PropagationErrorRaised",
        _py.get_type_bound::<errors::PropagationErrorRaised>(),
    )?;
    m.add(
        "PlanErrorRaised",
        _py.get_type_bound::<errors::PlanErrorRaised>(),
    )?;
    m.add(
        "EvalErrorRaised",
        _py.get_type_bound::<errors::EvalErrorRaised>(),
    )?;
    m.add(
        "SymbolicErrorRaised",
        _py.get_type_bound::<errors::SymbolicErrorRaised>(),
    )?;

    Ok(())
}
