//! PyO3 wrapper for `feldspar_core::BuiltinUnitSystem` (01-interfaces
//! `UnitSystem`).

use pyo3::prelude::*;

use crate::dimension::PyDimension;
use crate::errors::unit_error_to_py;

/// The built-in, dependency-free `UnitSystem` implementation.
// frob:doc docs/modules/feldspar-py.md#py_units
#[pyclass(frozen, name = "UnitSystem")]
pub struct PyUnitSystem(pub feldspar_core::BuiltinUnitSystem);

#[pymethods]
impl PyUnitSystem {
    // frob:doc docs/modules/feldspar-py.md#py_units
    #[staticmethod]
    fn builtin() -> Self {
        PyUnitSystem(feldspar_core::BuiltinUnitSystem::builtin())
    }

    /// `Result[Dimension, UnitError]` at the Python surface; raw/raising
    /// (see `errors.rs`).
    // frob:doc docs/modules/feldspar-py.md#py_units
    fn _dimension_of_checked(&self, unit: &str) -> PyResult<PyDimension> {
        use feldspar_core::UnitSystem;
        self.0
            .dimension_of(unit)
            .map(PyDimension)
            .map_err(unit_error_to_py)
    }

    // frob:doc docs/modules/feldspar-py.md#py_units
    fn _to_si_checked(&self, value: f64, unit: &str) -> PyResult<f64> {
        use feldspar_core::UnitSystem;
        self.0.to_si(value, unit).map_err(unit_error_to_py)
    }

    // frob:doc docs/modules/feldspar-py.md#py_units
    fn _from_si_checked(&self, value: f64, unit: &str) -> PyResult<f64> {
        use feldspar_core::UnitSystem;
        self.0.from_si(value, unit).map_err(unit_error_to_py)
    }

    // frob:doc docs/modules/feldspar-py.md#py_units
    fn compatible(&self, a: &str, b: &str) -> bool {
        use feldspar_core::UnitSystem;
        self.0.compatible(a, b)
    }
}
