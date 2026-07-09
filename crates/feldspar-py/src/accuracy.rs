//! PyO3 wrapper for `feldspar_core::Accuracy` (01-interfaces `Accuracy`).

use std::hash::{Hash, Hasher};

use pyo3::basic::CompareOp;
use pyo3::prelude::*;

use crate::interval::PyInterval;

/// Frozen model-error bound: `eps(v) = eps_abs + eps_rel * |v|`.
#[pyclass(frozen, from_py_object, name = "Accuracy")]
#[derive(Clone, Copy)]
pub struct PyAccuracy(pub feldspar_core::Accuracy);

#[pymethods]
impl PyAccuracy {
    /// Panics (a programmer-bug guard, not a `Result`) if either bound
    /// is negative or non-finite (01-interfaces: "both >= 0, finite
    /// (ctor checks)").
    #[new]
    fn py_new(eps_abs: f64, eps_rel: f64) -> Self {
        PyAccuracy(feldspar_core::Accuracy::new(eps_abs, eps_rel))
    }

    #[getter]
    fn eps_abs(&self) -> f64 {
        self.0.eps_abs
    }

    #[getter]
    fn eps_rel(&self) -> f64 {
        self.0.eps_rel
    }

    fn eps(&self, v: f64) -> f64 {
        self.0.eps(v)
    }

    fn worst_over(&self, iv: &PyInterval) -> f64 {
        self.0.worst_over(&iv.0)
    }

    fn __repr__(&self) -> String {
        format!(
            "Accuracy(eps_abs={}, eps_rel={})",
            feldspar_core::format_f64(self.0.eps_abs),
            feldspar_core::format_f64(self.0.eps_rel)
        )
    }

    fn __richcmp__(&self, other: &PyAccuracy, op: CompareOp) -> PyResult<bool> {
        match op {
            CompareOp::Eq => Ok(self.0 == other.0),
            CompareOp::Ne => Ok(self.0 != other.0),
            _ => Err(pyo3::exceptions::PyTypeError::new_err(
                "Accuracy only supports == and !=",
            )),
        }
    }

    fn __hash__(&self) -> u64 {
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        self.0.hash(&mut hasher);
        hasher.finish()
    }
}

/// `Accuracy(0.0, 0.0)`; the EXACT constant module attribute.
#[pyfunction]
pub fn exact_accuracy() -> PyAccuracy {
    PyAccuracy(feldspar_core::Accuracy::EXACT)
}
