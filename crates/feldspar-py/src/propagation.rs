//! PyO3 wrapper for `feldspar_core::{corner_sweep, inflate, total_error}`
//! (01-interfaces WO-04 section): the executor (WO-06) and planner
//! estimator (WO-05) call these SAME symbols (FINV-4).
//!
//! `enumerate_corners`/`hull_from_results` (WO-15, 09 sec. 6) split
//! `corner_sweep` into its enumerate and fold halves so
//! `feldspar.plan.parallel` can dispatch the (GIL-bound, so only
//! Python-side, not Rust-thread) per-corner `SolveFn` callback
//! concurrently and still fold through the ONE core hull routine.

use std::collections::BTreeMap;

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::errors::{eval_error_to_py, PropagationErrorRaised};
use crate::interval::PyInterval;
use crate::symbolic::PyExpr;

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
    callback: Py<PyAny>,
) -> PyResult<BTreeMap<String, PyInterval>> {
    let core_box: BTreeMap<String, feldspar_core::Interval> =
        box_.into_iter().map(|(k, v)| (k, v.0)).collect();

    let hull = feldspar_core::corner_sweep(&core_box, |corner: &BTreeMap<String, f64>| {
        let corner_dict = PyDict::new(py);
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

/// The enumerate half of `corner_sweep`, exposed standalone (WO-15) so
/// a Python caller can evaluate corners itself (e.g. concurrently) and
/// fold with `hull_from_results` below, instead of going through the
/// GIL-serialized single-threaded `corner_sweep` callback path.
#[pyfunction]
#[pyo3(name = "enumerate_corners")]
pub fn enumerate_corners_py(box_: BTreeMap<String, PyInterval>) -> Vec<BTreeMap<String, f64>> {
    let core_box: BTreeMap<String, feldspar_core::Interval> =
        box_.into_iter().map(|(k, v)| (k, v.0)).collect();
    feldspar_core::enumerate_corners(&core_box)
}

/// The fold half of `corner_sweep` (WO-15): hulls a list of per-corner
/// output maps that MUST be in the same order `enumerate_corners`
/// produced (the caller's contract -- see `feldspar_core::propagation::
/// hull_from_results`). Determinism (FINV-9) holds regardless of what
/// order the caller computed `results` in (any thread count), because
/// the fold is the ONE core routine.
#[pyfunction]
#[pyo3(name = "hull_from_results")]
pub fn hull_from_results_py(results: Vec<BTreeMap<String, f64>>) -> BTreeMap<String, PyInterval> {
    feldspar_core::hull_from_results(&results)
        .into_iter()
        .map(|(k, v)| (k, PyInterval(v)))
        .collect()
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

/// Frozen mirror of `feldspar_core::propagation::Normal` (02 "Normal
/// ... first-order (delta-method) propagation"; WO-22, R4).
#[pyclass(frozen, from_py_object, name = "Normal")]
#[derive(Clone, Copy)]
pub struct PyNormal(pub feldspar_core::propagation::Normal);

#[pymethods]
impl PyNormal {
    #[new]
    fn py_new(mean: f64, stddev: f64) -> Self {
        PyNormal(feldspar_core::propagation::Normal { mean, stddev })
    }

    #[getter]
    fn mean(&self) -> f64 {
        self.0.mean
    }

    #[getter]
    fn stddev(&self) -> f64 {
        self.0.stddev
    }

    /// The conservative `NORMAL_TO_INTERVAL_SIGMA`-widened collapse (02:
    /// every representation MUST offer one).
    // Name is the `Propagation::to_interval` normative signature (02),
    // not a `From`-style conversion -- same rationale as `UnitSystem`'s
    // `from_si` (feldspar-core/src/units.rs).
    #[allow(clippy::wrong_self_convention)]
    fn to_interval(&self) -> PyInterval {
        use feldspar_core::propagation::Propagation;
        PyInterval(self.0.to_interval())
    }

    fn __repr__(&self) -> String {
        format!("Normal(mean={}, stddev={})", self.0.mean, self.0.stddev)
    }
}

/// One `DeltaInput`'s wire shape from Python: `(port, mean, stddev)`.
type PyDeltaPoint = (String, f64, f64);

/// Delta-method `Normal` propagation (11 sec. 4 R4) with SYMBOLIC
/// derivatives: every input's partial is `differentiate(rhs, port)`
/// evaluated at the input means -- the mode a step takes when its law
/// is a declared symbolic `Relation`. `inputs` is `[(port, mean,
/// stddev), ...]`.
#[pyfunction]
#[pyo3(name = "delta_propagate_symbolic")]
pub fn delta_propagate_symbolic_py(rhs: &PyExpr, inputs: Vec<PyDeltaPoint>) -> PyResult<PyNormal> {
    use feldspar_core::propagation::{delta_propagate, DeltaInput, DerivativeMode};

    let delta_inputs: Vec<DeltaInput> = inputs
        .into_iter()
        .map(|(port, mean, stddev)| DeltaInput {
            port,
            value: feldspar_core::propagation::Normal { mean, stddev },
            mode: DerivativeMode::Symbolic { expr: &rhs.0 },
        })
        .collect();

    delta_propagate(&delta_inputs, |pt| rhs.0.eval(pt))
        .map(PyNormal)
        .map_err(eval_error_to_py)
}

/// Delta-method `Normal` propagation (11 sec. 4 R4) with NUMERIC
/// (central finite difference) derivatives: the mode a step takes when
/// its law is NOT a declared symbolic `Relation` -- `callback` is a
/// plain `Mapping[str, float] -> float` Python function (the step's
/// point evaluation), differenced with step size `h` per input.
/// `inputs` is `[(port, mean, stddev), ...]`.
#[pyfunction]
#[pyo3(name = "delta_propagate_numeric")]
pub fn delta_propagate_numeric_py(
    py: Python<'_>,
    callback: Py<PyAny>,
    inputs: Vec<PyDeltaPoint>,
    h: f64,
) -> PyResult<PyNormal> {
    use feldspar_core::propagation::{delta_propagate, DeltaInput, DerivativeMode};
    use feldspar_core::symbolic::EvalError;
    use std::cell::RefCell;

    // `delta_propagate`'s callback signature is `Result<f64, EvalError>`
    // (the core, PyO3-agnostic contract shared with the symbolic path);
    // a Python-callback failure (raise, or a non-float return) does not
    // fit that error type, so it is stashed here and re-raised as the
    // REAL `PyErr` after `delta_propagate` returns, rather than being
    // silently downgraded to a generic `EvalError::DomainFault` string
    // (never guessing at a Python exception's meaning, mirroring
    // `corner_sweep_py`'s `PropagationErrorRaised` carry-through).
    let py_error: RefCell<Option<PyErr>> = RefCell::new(None);

    let eval = |pt: &BTreeMap<String, f64>| -> Result<f64, EvalError> {
        let dict = PyDict::new(py);
        for (k, v) in pt {
            if let Err(e) = dict.set_item(k, v) {
                *py_error.borrow_mut() = Some(e);
                return Err(EvalError::DomainFault {
                    detail: "delta_propagate_numeric: building the callback argument failed"
                        .to_string(),
                });
            }
        }
        match callback.call1(py, (dict,)) {
            Ok(result) => result.extract::<f64>(py).map_err(|e| {
                *py_error.borrow_mut() = Some(e);
                EvalError::DomainFault {
                    detail: "delta_propagate_numeric callback did not return a float".to_string(),
                }
            }),
            Err(e) => {
                *py_error.borrow_mut() = Some(e);
                Err(EvalError::DomainFault {
                    detail: "delta_propagate_numeric callback raised".to_string(),
                })
            }
        }
    };

    let delta_inputs: Vec<DeltaInput> = inputs
        .iter()
        .map(|(port, mean, stddev)| DeltaInput {
            port: port.clone(),
            value: feldspar_core::propagation::Normal {
                mean: *mean,
                stddev: *stddev,
            },
            mode: DerivativeMode::Numeric { eval: &eval, h },
        })
        .collect();

    let outcome = delta_propagate(&delta_inputs, eval);
    if let Some(e) = py_error.into_inner() {
        return Err(e);
    }
    outcome.map(PyNormal).map_err(eval_error_to_py)
}
