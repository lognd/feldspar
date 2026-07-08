//! PyO3 wrapper for `feldspar_core::{corner_sweep, inflate, total_error}`
//! (01-interfaces WO-04 section): the executor (WO-06) and planner
//! estimator (WO-05) call these SAME symbols (FINV-4).

use std::collections::BTreeMap;

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::errors::PropagationErrorRaised;
use crate::interval::PyInterval;

/// Evaluates the Python `SolveFn`-shaped `callback` (a callable
/// returning a typani `Result[Mapping[str, float], SolveError]`) at
/// every deduplicated, sorted corner of `box_` and hulls the per-port
/// results. On the first `Err`, raises `PropagationErrorRaised`
/// carrying the ORIGINAL `SolveError` value untouched; `feldspar/core.py`
/// re-wraps it as a typani `Err` (see `errors.rs`).
#[pyfunction]
#[pyo3(name = "corner_sweep")]
pub fn corner_sweep_py(
    py: Python<'_>,
    box_: BTreeMap<String, PyInterval>,
    callback: PyObject,
) -> PyResult<BTreeMap<String, PyInterval>> {
    let core_box: BTreeMap<String, feldspar_core::Interval> =
        box_.into_iter().map(|(k, v)| (k, v.0)).collect();

    let hull = feldspar_core::corner_sweep(&core_box, |corner: &BTreeMap<String, f64>| {
        let corner_dict = PyDict::new_bound(py);
        for (k, v) in corner {
            corner_dict.set_item(k, v)?;
        }
        let raw = callback.call1(py, (corner_dict,))?;
        let bound = raw.bind(py);
        let is_err: bool = bound.getattr("is_err")?.extract()?;
        if is_err {
            let err_obj = bound.getattr("err")?;
            return Err(PropagationErrorRaised::new_err((err_obj.unbind(),)));
        }
        let ok_obj = bound.getattr("danger_ok")?;
        let values: BTreeMap<String, f64> = ok_obj.extract()?;
        Ok::<_, PyErr>(values)
    })?;

    Ok(hull.into_iter().map(|(k, v)| (k, PyInterval(v))).collect())
}

/// `[lo - eps, hi + eps]`; the accumulation primitive (audit A-1).
#[pyfunction]
#[pyo3(name = "inflate")]
pub fn inflate_py(iv: &PyInterval, eps: f64) -> PyInterval {
    PyInterval(feldspar_core::inflate(iv.0, eps))
}

/// `half_width(out_hull) + model_eps`: the budget-checked quantity at
/// a route's target.
#[pyfunction]
#[pyo3(name = "total_error")]
pub fn total_error_py(out_hull: &PyInterval, model_eps: f64) -> f64 {
    feldspar_core::total_error(out_hull.0, model_eps)
}
