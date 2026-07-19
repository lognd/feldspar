//! PyO3 wrapper for `feldspar_core::Dimension` (01-interfaces `Dimension`).

use pyo3::basic::CompareOp;
use pyo3::prelude::*;

/// Frozen `[i8; 7]` SI base-dimension exponent vector (m, kg, s, A, K,
/// mol, cd order).
// frob:doc docs/modules/feldspar-py.md#py_dimension
#[pyclass(frozen, from_py_object, name = "Dimension")]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub struct PyDimension(pub feldspar_core::Dimension);

#[pymethods]
impl PyDimension {
    // frob:doc docs/modules/feldspar-py.md#py_dimension
    #[new]
    fn py_new(exponents: [i8; 7]) -> Self {
        PyDimension(feldspar_core::Dimension::new(exponents))
    }

    // frob:doc docs/modules/feldspar-py.md#py_dimension
    #[getter]
    fn exponents(&self) -> [i8; 7] {
        self.0.exponents
    }

    // frob:doc docs/modules/feldspar-py.md#py_dimension
    fn __repr__(&self) -> String {
        format!("Dimension(exponents={:?})", self.0.exponents)
    }

    // frob:doc docs/modules/feldspar-py.md#py_dimension
    fn __richcmp__(&self, other: &PyDimension, op: CompareOp) -> PyResult<bool> {
        match op {
            CompareOp::Eq => Ok(self.0 == other.0),
            CompareOp::Ne => Ok(self.0 != other.0),
            _ => Err(pyo3::exceptions::PyTypeError::new_err(
                "Dimension only supports == and !=",
            )),
        }
    }

    // frob:doc docs/modules/feldspar-py.md#py_dimension
    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        self.0.hash(&mut hasher);
        hasher.finish()
    }
}
