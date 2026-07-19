//! PyO3 wrapper for the digest home (AD-5): `canonical_digest`,
//! `format_f64`.

use pyo3::prelude::*;

/// Canonical-JSON -> blake3 digest of any JSON-serializable Python
/// object (`feldspar.solve.digest.canonical_digest`, AD-5). Marshals
/// via `pythonize` into `serde_json::Value`, whose object type is a
/// `BTreeMap` by default (no `preserve_order` feature anywhere in this
/// workspace) -- so a Python `dict`'s insertion order never affects the
/// digest (02-edge-cases WO-02 row).
// frob:doc docs/modules/feldspar-py.md#py_digest
#[pyfunction]
pub fn canonical_digest(py: Python<'_>, obj: Py<PyAny>) -> PyResult<String> {
    let bound = obj.bind(py);
    let value: serde_json::Value = pythonize::depythonize(bound)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(feldspar_core::canonical_digest(&value))
}

/// Shortest round-trip `f64` formatting (the 05 deck's one home).
// frob:doc docs/modules/feldspar-py.md#py_digest
#[pyfunction]
pub fn format_f64(x: f64) -> String {
    feldspar_core::format_f64(x)
}
