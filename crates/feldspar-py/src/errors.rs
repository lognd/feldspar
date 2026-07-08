//! Rust `Result`/`Err` -> Python exception marshalling (AD-1: feldspar-py
//! is marshalling only). Each raised exception carries `(variant, ...)`
//! so the Python-side `feldspar/core.py` shim can reconstruct a typani
//! `Err(...)` value from it -- Rust-side `Result` becomes a Python
//! exception at this boundary, then Python re-wraps it as the typani
//! `Result` the 01-interfaces surface promises callers.

use pyo3::create_exception;
use pyo3::exceptions::PyException;
use pyo3::PyErr;

create_exception!(_feldspar, CoreErrorRaised, PyException);
create_exception!(_feldspar, UnitErrorRaised, PyException);
create_exception!(_feldspar, DomainViolationRaised, PyException);
// `corner_sweep`'s per-corner callback (a Python `SolveFn`) already
// returns a typani `Result`; when it's `Err`, this exception carries
// the ORIGINAL Python `SolveError` object through untouched (single
// arg, `.args[0]`) so `feldspar/core.py` can re-wrap it as
// `Err(that_same_value)` -- unlike the other exceptions above, Rust
// never interprets this payload's shape (WO-04, FINV-4).
create_exception!(_feldspar, PropagationErrorRaised, PyException);
// `feldspar_core::search::plan`'s total `PlanError` union (WO-05,
// 01-interfaces `PlanError`), marshalled the same `(variant, ...)` way
// as `CoreErrorRaised`/`UnitErrorRaised` above.
create_exception!(_feldspar, PlanErrorRaised, PyException);
// `feldspar_core::symbolic`'s declaration-time algebra errors (WO-11, 11
// sec. 2), marshalled the same `(variant, ...)` way as the errors above.
create_exception!(_feldspar, EvalErrorRaised, PyException);
create_exception!(_feldspar, SymbolicErrorRaised, PyException);

pub fn plan_error_to_py(e: feldspar_core::PlanError) -> PyErr {
    use feldspar_core::PlanError::*;
    match e {
        InvalidBudget => PlanErrorRaised::new_err(("InvalidBudget",)),
        UnknownTarget(target) => PlanErrorRaised::new_err(("UnknownTarget", target)),
        NoApplicableSolver => PlanErrorRaised::new_err(("NoApplicableSolver",)),
        BudgetUnreachable { best_eps } => PlanErrorRaised::new_err(("BudgetUnreachable", best_eps)),
        CyclicPortEquivalence => PlanErrorRaised::new_err(("CyclicPortEquivalence",)),
    }
}

pub fn core_error_to_py(e: feldspar_core::CoreError) -> PyErr {
    let variant = match e {
        feldspar_core::CoreError::NonFiniteBound(_) => "NonFiniteBound",
        feldspar_core::CoreError::InvertedInterval { .. } => "InvertedInterval",
    };
    CoreErrorRaised::new_err((variant, e.to_string()))
}

pub fn unit_error_to_py(e: feldspar_core::UnitError) -> PyErr {
    let variant = match &e {
        feldspar_core::UnitError::UnknownUnit(_) => "UnknownUnit",
        feldspar_core::UnitError::IncompatibleDimensions { .. } => "IncompatibleDimensions",
        feldspar_core::UnitError::OffsetInCompound(_) => "OffsetInCompound",
    };
    UnitErrorRaised::new_err((variant, e.to_string()))
}

#[allow(clippy::type_complexity)]
pub fn domain_violation_to_py(v: feldspar_core::DomainViolation) -> PyErr {
    use feldspar_core::DomainViolation::*;
    let (kind, port, tag, lo, hi, box_lo, box_hi): (
        &str,
        Option<String>,
        Option<String>,
        Option<f64>,
        Option<f64>,
        Option<f64>,
        Option<f64>,
    ) = match v {
        MissingInput { port } => ("MissingInput", Some(port), None, None, None, None, None),
        OutOfBox {
            port,
            lo,
            hi,
            box_lo,
            box_hi,
        } => (
            "OutOfBox",
            Some(port),
            None,
            Some(lo),
            Some(hi),
            Some(box_lo),
            Some(box_hi),
        ),
        MissingTag { tag } => ("MissingTag", None, Some(tag), None, None, None, None),
    };
    DomainViolationRaised::new_err((kind, port, tag, lo, hi, box_lo, box_hi))
}

pub fn eval_error_to_py(e: feldspar_core::symbolic::EvalError) -> PyErr {
    use feldspar_core::symbolic::EvalError::*;
    match e {
        MissingPort { port } => EvalErrorRaised::new_err(("MissingPort", port)),
        DomainFault { detail } => EvalErrorRaised::new_err(("DomainFault", detail)),
    }
}

pub fn symbolic_error_to_py(e: feldspar_core::symbolic::SymbolicError) -> PyErr {
    use feldspar_core::symbolic::SymbolicError::*;
    match e {
        NonInvertible { variable, reason } => {
            SymbolicErrorRaised::new_err(("NonInvertible", variable, reason.to_string()))
        }
        MultiBranch { variable, branches } => SymbolicErrorRaised::new_err((
            "MultiBranch",
            variable,
            branches
                .iter()
                .map(|b| b.label().to_string())
                .collect::<Vec<_>>(),
        )),
        UnboundablePredicate { predicate } => {
            SymbolicErrorRaised::new_err(("UnboundablePredicate", predicate))
        }
        EmptyDomain { port } => SymbolicErrorRaised::new_err(("EmptyDomain", port)),
    }
}
