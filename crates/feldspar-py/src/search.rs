//! PyO3 wrapper for `feldspar_core::search` (01-interfaces `feldspar.plan`,
//! WO-05). The frozen registry snapshot crosses ONCE per `plan()` call as
//! a `Vec<PySolverInput>` built by `python/feldspar/plan/route.py` from
//! `SolverRegistry.__iter__()`; nothing here calls back into Python
//! during search itself (04-routing: "search never calls back into
//! Python").

use std::collections::{BTreeMap, BTreeSet};

use pyo3::prelude::*;

use crate::accuracy::PyAccuracy;
use crate::domain::PyDomain;
use crate::errors::plan_error_to_py;
use crate::interval::PyInterval;

/// One solver's planning-relevant metadata, marshalled from a Python
/// `SolverInfo` by the caller (`feldspar/plan/route.py`). Deliberately
/// carries no `tier` field (FINV-8: the search must not be ABLE to read
/// tier, not merely choose not to).
#[pyclass(frozen, from_py_object, name = "_PlanSolverInput")]
#[derive(Clone)]
pub struct PySolverInput {
    pub solver_id: String,
    pub inputs: Vec<String>,
    pub outputs: Vec<String>,
    pub domain: PyDomain,
    pub cost: f64,
    pub accuracy: BTreeMap<String, PyAccuracy>,
    pub conservative_for: String,
}

#[pymethods]
impl PySolverInput {
    #[new]
    #[allow(clippy::too_many_arguments)]
    fn py_new(
        solver_id: String,
        inputs: Vec<String>,
        outputs: Vec<String>,
        domain: PyDomain,
        cost: f64,
        accuracy: BTreeMap<String, PyAccuracy>,
        conservative_for: String,
    ) -> Self {
        PySolverInput {
            solver_id,
            inputs,
            outputs,
            domain,
            cost,
            accuracy,
            conservative_for,
        }
    }
}

fn to_core_summary(s: &PySolverInput) -> feldspar_core::SolverSummary {
    feldspar_core::SolverSummary {
        solver_id: s.solver_id.clone(),
        inputs: s.inputs.clone(),
        outputs: s.outputs.clone(),
        domain: s.domain.0.clone(),
        cost: s.cost,
        accuracy: s.accuracy.iter().map(|(k, v)| (k.clone(), v.0)).collect(),
        conservative_for: feldspar_core::Sense::parse(&s.conservative_for),
    }
}

/// Frozen mirror of `feldspar_core::RouteStep` (01-interfaces `RouteStep`).
#[pyclass(frozen, from_py_object, name = "RouteStep")]
#[derive(Clone)]
pub struct PyRouteStep {
    inner: feldspar_core::RouteStep,
}

#[pymethods]
impl PyRouteStep {
    #[getter]
    fn solver_id(&self) -> String {
        self.inner.solver_id.clone()
    }

    #[getter]
    fn realized_domain(&self) -> PyDomain {
        let box_: BTreeMap<String, feldspar_core::Interval> = self
            .inner
            .realized_domain
            .port_box
            .iter()
            .map(|(k, (lo, hi))| {
                (
                    k.clone(),
                    feldspar_core::Interval::new(*lo, *hi)
                        .expect("route steps carry finite bounds"),
                )
            })
            .collect();
        PyDomain(feldspar_core::Domain::new(
            box_,
            self.inner.realized_domain.tags.clone(),
        ))
    }

    #[getter]
    fn predicted_eps(&self) -> f64 {
        self.inner.predicted_eps
    }

    #[getter]
    fn cost(&self) -> f64 {
        self.inner.cost
    }

    fn __repr__(&self) -> String {
        format!(
            "RouteStep(solver_id={:?}, predicted_eps={}, cost={})",
            self.inner.solver_id,
            feldspar_core::format_f64(self.inner.predicted_eps),
            feldspar_core::format_f64(self.inner.cost)
        )
    }
}

/// Frozen mirror of `feldspar_core::Route` (01-interfaces `Route`, AD-5).
#[pyclass(frozen, from_py_object, name = "Route")]
#[derive(Clone)]
pub struct PyRoute {
    inner: feldspar_core::Route,
}

#[pymethods]
impl PyRoute {
    #[getter]
    fn target(&self) -> String {
        self.inner.target.clone()
    }

    #[getter]
    fn steps(&self) -> Vec<PyRouteStep> {
        self.inner
            .steps
            .iter()
            .cloned()
            .map(|inner| PyRouteStep { inner })
            .collect()
    }

    #[getter]
    fn predicted_eps(&self) -> f64 {
        self.inner.predicted_eps
    }

    #[getter]
    fn total_cost(&self) -> f64 {
        self.inner.total_cost
    }

    #[getter]
    fn digest(&self) -> String {
        self.inner.digest.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "Route(target={:?}, steps={}, predicted_eps={}, total_cost={}, digest={:?})",
            self.inner.target,
            self.inner.steps.len(),
            feldspar_core::format_f64(self.inner.predicted_eps),
            feldspar_core::format_f64(self.inner.total_cost),
            self.inner.digest
        )
    }
}

/// Runs `feldspar_core::search::plan`; raises `PlanErrorRaised` carrying
/// `(variant, ...)` on `Err` so `feldspar/plan/route.py` can reconstruct
/// a typani `Err(PlanError...)` value (see `errors.rs`).
#[pyfunction]
#[pyo3(name = "plan")]
pub fn plan_py(
    solvers: Vec<PySolverInput>,
    known: BTreeMap<String, PyInterval>,
    tags: BTreeSet<String>,
    target: String,
    eps_budget: f64,
    sense: String,
) -> PyResult<PyRoute> {
    let core_solvers: Vec<feldspar_core::SolverSummary> =
        solvers.iter().map(to_core_summary).collect();
    let core_known: BTreeMap<String, feldspar_core::Interval> =
        known.into_iter().map(|(k, v)| (k, v.0)).collect();
    let sense = feldspar_core::Sense::parse(&sense);

    feldspar_core::plan(
        &core_solvers,
        &core_known,
        &tags,
        &target,
        eps_budget,
        sense,
    )
    .map(|inner| PyRoute { inner })
    .map_err(plan_error_to_py)
}
