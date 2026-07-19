//! PyO3 wrapper for `feldspar_core::Interval` (01-interfaces `Interval`).

use std::hash::{Hash, Hasher};

use pyo3::basic::CompareOp;
use pyo3::prelude::*;

use crate::errors::core_error_to_py;

/// Frozen, ordered, hashable closed interval `[lo, hi]`.
// frob:doc docs/modules/feldspar-py.md#py_interval
#[pyclass(frozen, from_py_object, name = "Interval")]
#[derive(Clone, Copy)]
pub struct PyInterval(pub feldspar_core::Interval);

#[pymethods]
impl PyInterval {
    /// Direct construction raises on invalid bounds (a programmer bug in
    /// literal code); see `_new_checked`/`_point_checked` for the
    /// checked `Result` path wired up by `feldspar/core.py`.
    // frob:doc docs/modules/feldspar-py.md#py_interval
    #[new]
    fn py_new(lo: f64, hi: f64) -> PyResult<Self> {
        feldspar_core::Interval::new(lo, hi)
            .map(PyInterval)
            .map_err(core_error_to_py)
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    #[staticmethod]
    fn _new_checked(lo: f64, hi: f64) -> PyResult<Self> {
        Self::py_new(lo, hi)
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    #[staticmethod]
    fn _point_checked(x: f64) -> PyResult<Self> {
        feldspar_core::Interval::point(x)
            .map(PyInterval)
            .map_err(core_error_to_py)
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    #[getter]
    fn lo(&self) -> f64 {
        self.0.lo
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    #[getter]
    fn hi(&self) -> f64 {
        self.0.hi
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    fn width(&self) -> f64 {
        self.0.width()
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    fn half_width(&self) -> f64 {
        self.0.half_width()
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    fn midpoint(&self) -> f64 {
        self.0.midpoint()
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    fn contains(&self, x: f64) -> bool {
        self.0.contains(x)
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    fn is_subset(&self, outer: &PyInterval) -> bool {
        self.0.is_subset(&outer.0)
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    fn hull(&self, other: &PyInterval) -> PyInterval {
        PyInterval(self.0.hull(&other.0))
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    fn __repr__(&self) -> String {
        format!(
            "Interval(lo={}, hi={})",
            feldspar_core::format_f64(self.0.lo),
            feldspar_core::format_f64(self.0.hi)
        )
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    fn __richcmp__(&self, other: &PyInterval, op: CompareOp) -> PyResult<bool> {
        match op {
            CompareOp::Eq => Ok(self.0 == other.0),
            CompareOp::Ne => Ok(self.0 != other.0),
            _ => Err(pyo3::exceptions::PyTypeError::new_err(
                "Interval only supports == and !=",
            )),
        }
    }

    // frob:doc docs/modules/feldspar-py.md#py_interval
    fn __hash__(&self) -> u64 {
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        self.0.hash(&mut hasher);
        hasher.finish()
    }
}
