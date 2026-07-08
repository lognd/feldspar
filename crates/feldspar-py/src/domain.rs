//! PyO3 wrapper for `feldspar_core::Domain` (01-interfaces `Domain`).

use std::collections::{BTreeMap, BTreeSet};

use pyo3::prelude::*;

use crate::errors::domain_violation_to_py;
use crate::interval::PyInterval;

/// Frozen validity region: a box of per-port allowed intervals plus
/// regime tags.
#[pyclass(frozen, name = "Domain")]
#[derive(Clone)]
pub struct PyDomain(pub feldspar_core::Domain);

#[pymethods]
impl PyDomain {
    #[new]
    #[pyo3(signature = (port_box, tags=None))]
    fn py_new(port_box: BTreeMap<String, PyInterval>, tags: Option<BTreeSet<String>>) -> Self {
        let core_box: BTreeMap<String, feldspar_core::Interval> =
            port_box.into_iter().map(|(k, v)| (k, v.0)).collect();
        PyDomain(feldspar_core::Domain::new(
            core_box,
            tags.unwrap_or_default(),
        ))
    }

    #[getter(port_box)]
    fn port_box(&self) -> BTreeMap<String, PyInterval> {
        self.0
            .port_box
            .iter()
            .map(|(k, v)| (k.clone(), PyInterval(*v)))
            .collect()
    }

    #[getter(tags)]
    fn tags(&self) -> BTreeSet<String> {
        self.0.tags.clone()
    }

    /// `Result[None, DomainViolation]` at the Python surface; this raw
    /// method raises so `feldspar/core.py` can wrap it into a typani
    /// `Result` (see `errors.rs` module docs).
    fn _admits_checked(
        &self,
        inputs: BTreeMap<String, PyInterval>,
        tags: BTreeSet<String>,
    ) -> PyResult<()> {
        let core_inputs: BTreeMap<String, feldspar_core::Interval> =
            inputs.into_iter().map(|(k, v)| (k, v.0)).collect();
        self.0
            .admits(&core_inputs, &tags)
            .map_err(domain_violation_to_py)
    }

    fn __repr__(&self) -> String {
        format!(
            "Domain(port_box={{{} ports}}, tags={:?})",
            self.0.port_box.len(),
            self.0.tags
        )
    }
}
