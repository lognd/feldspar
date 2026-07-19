//! PyO3 wrapper for `feldspar_core::symbolic` (11 "the symbolic core",
//! WO-11). Exposes the canonical `Expr` AST, `Predicate`, and the
//! declaration-time algebra primitives (`invert_for`, `invertible_targets`,
//! `predicate_to_box`) to Python. `Cmp` is deliberately kept as a plain
//! `str` ("lt"/"le"/"gt"/"ge") rather than a wrapped enum type, matching
//! how other small closed enums (e.g. `tier`) cross the boundary as
//! strings elsewhere in this crate.

use std::collections::{BTreeMap, BTreeSet};

use pyo3::prelude::*;

use crate::domain::PyDomain;
use crate::errors::{eval_error_to_py, symbolic_error_to_py};
use crate::interval::PyInterval;

/// Parses a `Cmp` string ("lt"/"le"/"gt"/"ge") into the core enum, raising
/// `PyValueError` on anything else -- the boundary-level validation for
/// the plain-string `Cmp` convention.
fn cmp_from_str(s: &str) -> PyResult<feldspar_core::symbolic::Cmp> {
    use feldspar_core::symbolic::Cmp;
    match s {
        "lt" => Ok(Cmp::Lt),
        "le" => Ok(Cmp::Le),
        "gt" => Ok(Cmp::Gt),
        "ge" => Ok(Cmp::Ge),
        other => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "unrecognized Cmp {other:?}: expected one of \"lt\", \"le\", \"gt\", \"ge\""
        ))),
    }
}

/// Parses a `Branch` string ("principal"/"+"/"-") into the core enum,
/// raising `PyValueError` on anything else.
fn branch_from_str(s: &str) -> PyResult<feldspar_core::symbolic::Branch> {
    use feldspar_core::symbolic::Branch;
    match s {
        "principal" => Ok(Branch::Principal),
        "+" => Ok(Branch::Positive),
        "-" => Ok(Branch::Negative),
        other => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "unrecognized Branch {other:?}: expected one of \"principal\", \"+\", \"-\""
        ))),
    }
}

/// Frozen mirror of `feldspar_core::symbolic::Expr` (11 sec. 1): the
/// canonical algebraic AST a law is authored as. Constructed via the
/// staticmethod builders below (never `#[new]` -- `Expr` has multiple
/// constructor shapes, unlike the single-shape types elsewhere).
// frob:doc docs/modules/feldspar-py.md#py_symbolic
#[pyclass(frozen, from_py_object, name = "Expr")]
#[derive(Clone)]
pub struct PyExpr(pub feldspar_core::symbolic::Expr);

#[pymethods]
impl PyExpr {
    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    #[staticmethod]
    fn var(name: String) -> PyExpr {
        PyExpr(feldspar_core::symbolic::Expr::Var(name))
    }

    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    #[staticmethod]
    fn lit(x: f64) -> PyExpr {
        PyExpr(feldspar_core::symbolic::Expr::Lit(x))
    }

    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    #[staticmethod]
    fn neg(e: PyExpr) -> PyExpr {
        PyExpr(feldspar_core::symbolic::Expr::Neg(Box::new(e.0)))
    }

    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    #[staticmethod]
    fn add(items: Vec<PyExpr>) -> PyExpr {
        PyExpr(feldspar_core::symbolic::Expr::Add(
            items.into_iter().map(|e| e.0).collect(),
        ))
    }

    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    #[staticmethod]
    fn mul(items: Vec<PyExpr>) -> PyExpr {
        PyExpr(feldspar_core::symbolic::Expr::Mul(
            items.into_iter().map(|e| e.0).collect(),
        ))
    }

    /// `a - b`, lowered to `Add([a, Neg(b)])` (subtraction never appears
    /// as its own node in the canonical form).
    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    #[staticmethod]
    fn sub(a: PyExpr, b: PyExpr) -> PyExpr {
        PyExpr(feldspar_core::symbolic::Expr::Add(vec![
            a.0,
            feldspar_core::symbolic::Expr::Neg(Box::new(b.0)),
        ]))
    }

    /// `a / b`, lowered to `Mul([a, Pow(b, -1)])` (division never appears
    /// as its own node in the canonical form).
    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    #[staticmethod]
    fn div(a: PyExpr, b: PyExpr) -> PyExpr {
        PyExpr(feldspar_core::symbolic::Expr::Mul(vec![
            a.0,
            feldspar_core::symbolic::Expr::Pow(
                Box::new(b.0),
                Box::new(feldspar_core::symbolic::Expr::Lit(-1.0)),
            ),
        ]))
    }

    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    #[staticmethod]
    fn pow(base: PyExpr, exp: PyExpr) -> PyExpr {
        PyExpr(feldspar_core::symbolic::Expr::Pow(
            Box::new(base.0),
            Box::new(exp.0),
        ))
    }

    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    #[staticmethod]
    fn sqrt(e: PyExpr) -> PyExpr {
        PyExpr(feldspar_core::symbolic::Expr::Unary(
            feldspar_core::symbolic::UnaryFn::Sqrt,
            Box::new(e.0),
        ))
    }

    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    fn canonicalize(&self) -> PyExpr {
        PyExpr(self.0.canonicalize())
    }

    /// Symbolic differentiation w.r.t. `var` (11 sec. 4 R4, WO-22):
    /// kernel differentiation over the canonical AST, canonicalized.
    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    fn differentiate(&self, var: &str) -> PyExpr {
        PyExpr(feldspar_core::symbolic::differentiate(&self.0, var))
    }

    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    fn canonical_string(&self) -> String {
        self.0.canonical_string()
    }

    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    fn eval(&self, inputs: BTreeMap<String, f64>) -> PyResult<f64> {
        self.0.eval(&inputs).map_err(eval_error_to_py)
    }

    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    fn __repr__(&self) -> String {
        format!("Expr({})", self.0.canonical_string())
    }
}

/// Frozen mirror of `feldspar_core::symbolic::Predicate` (11 sec. 2): an
/// inequality over ports, e.g. `Re < 2300`.
// frob:doc docs/modules/feldspar-py.md#py_symbolic
#[pyclass(frozen, from_py_object, name = "Predicate")]
#[derive(Clone)]
pub struct PyPredicate(pub feldspar_core::symbolic::Predicate);

#[pymethods]
impl PyPredicate {
    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    #[new]
    fn py_new(lhs: PyExpr, cmp: String, rhs: PyExpr) -> PyResult<Self> {
        let cmp = cmp_from_str(&cmp)?;
        Ok(PyPredicate(feldspar_core::symbolic::Predicate {
            lhs: lhs.0,
            cmp,
            rhs: rhs.0,
        }))
    }

    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    fn canonical_string(&self) -> String {
        self.0.canonical_string()
    }

    // frob:doc docs/modules/feldspar-py.md#py_symbolic
    fn __repr__(&self) -> String {
        format!("Predicate({})", self.0.canonical_string())
    }
}

/// Runs `feldspar_core::symbolic::invert_for`; raises `SymbolicErrorRaised`
/// carrying `(variant, ...)` on `Err` so Python can reconstruct a typani
/// `Err(SymbolicError...)` value (see `errors.rs`). Returns
/// `(rhs_expr, branch_label, admission_predicates, form_string)` on `Ok`.
// frob:doc docs/modules/feldspar-py.md#py_symbolic
#[pyfunction]
#[pyo3(name = "invert_for", signature = (lhs, rhs, target, branch=None))]
pub fn invert_for_py(
    lhs: PyExpr,
    rhs: PyExpr,
    target: String,
    branch: Option<String>,
) -> PyResult<(PyExpr, String, Vec<PyPredicate>, String)> {
    let branch = match branch {
        Some(s) => Some(branch_from_str(&s)?),
        None => None,
    };

    feldspar_core::symbolic::invert_for(&lhs.0, &rhs.0, &target, branch)
        .map(|inv| {
            let rhs_expr = PyExpr(inv.rhs);
            let branch_label = inv.branch.label().to_string();
            let admission = inv.admission.into_iter().map(PyPredicate).collect();
            (rhs_expr, branch_label, admission, inv.form)
        })
        .map_err(symbolic_error_to_py)
}

/// Runs `feldspar_core::symbolic::invertible_targets`; the returned
/// `Vec<String>` is already sorted (`BTreeSet` iteration order).
// frob:doc docs/modules/feldspar-py.md#py_symbolic
#[pyfunction]
#[pyo3(name = "invertible_targets")]
pub fn invertible_targets_py(lhs: PyExpr, rhs: PyExpr) -> Vec<String> {
    feldspar_core::symbolic::invertible_targets(&lhs.0, &rhs.0)
        .into_iter()
        .collect()
}

/// Runs `feldspar_core::symbolic::predicate_to_box`; raises
/// `SymbolicErrorRaised` carrying `(variant, ...)` on `Err` (see
/// `errors.rs`).
// frob:doc docs/modules/feldspar-py.md#py_symbolic
#[pyfunction]
#[pyo3(name = "predicate_to_box")]
pub fn predicate_to_box_py(
    predicates: Vec<PyPredicate>,
    declared_box: BTreeMap<String, PyInterval>,
    tags: BTreeSet<String>,
) -> PyResult<PyDomain> {
    let core_predicates: Vec<feldspar_core::symbolic::Predicate> =
        predicates.into_iter().map(|p| p.0).collect();
    let core_declared_box: BTreeMap<String, feldspar_core::Interval> =
        declared_box.into_iter().map(|(k, v)| (k, v.0)).collect();

    feldspar_core::symbolic::predicate_to_box(&core_predicates, &core_declared_box, &tags)
        .map(PyDomain)
        .map_err(symbolic_error_to_py)
}
