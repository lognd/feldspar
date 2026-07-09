//! PyO3 wrapper for `feldspar_core::Domain` (01-interfaces `Domain`).
//!
//! 01-interfaces names the field `box` (a reserved keyword in Rust);
//! `r#box` is Rust's raw-identifier escape for using a keyword as a
//! plain identifier -- Python sees the identifier text itself, `box`,
//! with no `r#` artifact (examples/solvers/00_raw_protocol.py:
//! `Domain(box={...}, tags=frozenset())`).

use std::collections::{BTreeMap, BTreeSet};

use pyo3::prelude::*;

use crate::errors::domain_violation_to_py;
use crate::interval::PyInterval;

/// Frozen validity region: a box of per-port allowed intervals plus
/// regime tags.
#[pyclass(frozen, from_py_object, name = "Domain")]
#[derive(Clone)]
pub struct PyDomain(pub feldspar_core::Domain);

#[pymethods]
impl PyDomain {
    #[new]
    #[pyo3(signature = (r#box, tags=None))]
    fn py_new(r#box: BTreeMap<String, PyInterval>, tags: Option<BTreeSet<String>>) -> Self {
        let core_box: BTreeMap<String, feldspar_core::Interval> =
            r#box.into_iter().map(|(k, v)| (k, v.0)).collect();
        PyDomain(feldspar_core::Domain::new(
            core_box,
            tags.unwrap_or_default(),
        ))
    }

    #[getter(r#box)]
    fn get_box(&self) -> BTreeMap<String, PyInterval> {
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
            "Domain(box={{{} ports}}, tags={:?})",
            self.0.port_box.len(),
            self.0.tags
        )
    }
}
