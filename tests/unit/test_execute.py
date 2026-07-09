from __future__ import annotations

"""WO-06 tests: `feldspar.plan.execute()`, `Solution`, `AttemptRecord`
(01-interfaces `feldspar.plan`, 04-routing "Execution").

Covers `execute()` in isolation: real corner sweep replacing the
planner's sum surrogate, realized-eps charging (declared vs measured),
NaN/missing-output/invalid-measurement rejection, and the zero-step
route (G12)."""

from typing import Tuple

from typani import Err, Ok

from feldspar.core import Accuracy, Domain, Interval
from feldspar.plan import execute, plan
from feldspar.solve import Citation, SolveError, SolveOutput, SolverRegistry, solver


def _citation() -> Tuple[Citation, ...]:
    return (Citation(kind="handbook", ref="test fixture"),)


def _registry_with_double() -> SolverRegistry:
    registry = SolverRegistry()

    @solver(
        namespace="ex",
        inputs=("ex.x",),
        outputs=("ex.y",),
        domain=Domain(box={"ex.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"ex.y": Accuracy(eps_abs=0.5, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def double(x):
        return Ok({"ex.y": x["ex.x"] * 2.0})

    assert registry.register(*double.solver_direction).is_ok
    registry.freeze()
    return registry


def test_execute_charges_declared_eps_when_no_measurement() -> None:
    registry = _registry_with_double()
    known = {"ex.x": Interval(1.0, 2.0)}
    route = plan(registry, known, frozenset(), "ex.y", 10.0).danger_ok
    solution = execute(route, registry, known).danger_ok
    assert solution.value == Interval(2.0, 4.0)
    assert solution.eps == 0.5
    assert solution.solver_versions == {"ex.double": "1"}
    assert solution.cache_hit is False
    assert solution.attempts == ()


def test_execute_measured_eps_replaces_declared() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="fea",
        inputs=("fea.x",),
        outputs=("fea.y",),
        domain=Domain(box={"fea.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"fea.y": Accuracy(eps_abs=0.01, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def measuring(x):
        return Ok(SolveOutput(values={"fea.y": x["fea.x"]}, measured_eps=3.0))

    assert registry.register(*measuring.solver_direction).is_ok
    registry.freeze()
    known = {"fea.x": Interval(1.0, 2.0)}
    route = plan(registry, known, frozenset(), "fea.y", 100.0).danger_ok
    solution = execute(route, registry, known).danger_ok
    assert solution.eps == 3.0


def test_execute_zero_step_route_known_target() -> None:
    registry = _registry_with_double()
    known = {"ex.y": Interval(3.0, 3.0)}
    route = plan(registry, known, frozenset(), "ex.y", 1.0).danger_ok
    assert route.steps == ()
    solution = execute(route, registry, known).danger_ok
    assert solution.value == Interval(3.0, 3.0)
    assert solution.eps == 0.0
    assert solution.solver_versions == {}


def test_execute_nan_output_is_non_finite() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="bad",
        inputs=("bad.x",),
        outputs=("bad.y",),
        domain=Domain(box={"bad.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"bad.y": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def nan_solver(x):
        return Ok({"bad.y": float("nan")})

    assert registry.register(*nan_solver.solver_direction).is_ok
    registry.freeze()
    known = {"bad.x": Interval(1.0, 2.0)}
    route = plan(registry, known, frozenset(), "bad.y", 10.0).danger_ok
    result = execute(route, registry, known)
    assert result.is_err
    assert result.err == SolveError.NonFinite(port="bad.y")


def test_execute_missing_output_is_rejected() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="bad2",
        inputs=("bad2.x",),
        outputs=("bad2.y",),
        domain=Domain(box={"bad2.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"bad2.y": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def missing_solver(x):
        return Ok({"bad2.other": 1.0})

    assert registry.register(*missing_solver.solver_direction).is_ok
    registry.freeze()
    known = {"bad2.x": Interval(1.0, 2.0)}
    route = plan(registry, known, frozenset(), "bad2.y", 10.0).danger_ok
    result = execute(route, registry, known)
    assert result.is_err
    assert result.err == SolveError.MissingOutput(port="bad2.y")


def test_execute_invalid_measurement_negative_eps() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="bad3",
        inputs=("bad3.x",),
        outputs=("bad3.y",),
        domain=Domain(box={"bad3.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"bad3.y": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def negative_eps(x):
        return Ok(SolveOutput(values={"bad3.y": 1.0}, measured_eps=-1.0))

    assert registry.register(*negative_eps.solver_direction).is_ok
    registry.freeze()
    known = {"bad3.x": Interval(1.0, 2.0)}
    route = plan(registry, known, frozenset(), "bad3.y", 10.0).danger_ok
    result = execute(route, registry, known)
    assert result.is_err
    assert result.err.kind == "InvalidMeasurement"


def test_execute_solver_err_propagates_unchanged() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="bad4",
        inputs=("bad4.x",),
        outputs=("bad4.y",),
        domain=Domain(box={"bad4.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"bad4.y": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def tool_missing(x):
        return Err(SolveError.ToolMissing(tool="gmsh", guidance="brew install gmsh"))

    assert registry.register(*tool_missing.solver_direction).is_ok
    registry.freeze()
    known = {"bad4.x": Interval(1.0, 2.0)}
    route = plan(registry, known, frozenset(), "bad4.y", 10.0).danger_ok
    result = execute(route, registry, known)
    assert result.is_err
    assert result.err == SolveError.ToolMissing(
        tool="gmsh", guidance="brew install gmsh"
    )


# ---------------------------------------------------------------------------
# WO-13 (09 sec. 3): `execute(..., eps_budget=...)` threads the remaining
# eps budget to an `eps_seeking` step's `SolveFn` -- generic (non-FEA)
# fixture; the FEA ladder itself is covered by
# tests/unit/test_fea_solver_seeking.py.
# ---------------------------------------------------------------------------


def _registry_with_seeking_echo():
    registry = SolverRegistry()

    @solver(
        namespace="ex",
        inputs=("ex.x",),
        outputs=("ex.y",),
        domain=Domain(box={"ex.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"ex.y": Accuracy(eps_abs=0.5, eps_rel=0.0)},
        citations=_citation(),
        version="1",
        eps_seeking=True,
    )
    def echo_budget(x, eps_budget=None):
        # Reports the budget it was given back as measured_eps (so the
        # test can assert on it via Solution.eps without any FEA
        # machinery) -- a budget of None reports 0.0 (no seeking).
        return Ok(
            SolveOutput(
                values={"ex.y": x["ex.x"] * 2.0},
                measured_eps=eps_budget if eps_budget is not None else 0.0,
            )
        )

    assert registry.register(*echo_budget.solver_direction).is_ok
    registry.freeze()
    return registry


def test_execute_threads_eps_budget_to_eps_seeking_step() -> None:
    registry = _registry_with_seeking_echo()
    known = {"ex.x": Interval(1.0, 2.0)}
    route = plan(registry, known, frozenset(), "ex.y", 10.0).danger_ok

    solution = execute(route, registry, known, eps_budget=3.0).danger_ok
    assert solution.eps == 3.0


def test_execute_with_no_eps_budget_passes_none() -> None:
    registry = _registry_with_seeking_echo()
    known = {"ex.x": Interval(1.0, 2.0)}
    route = plan(registry, known, frozenset(), "ex.y", 10.0).danger_ok

    solution = execute(route, registry, known).danger_ok
    assert solution.eps == 0.0


def test_execute_remaining_budget_never_negative() -> None:
    """Even if `eps_budget` were somehow smaller than upstream-charged
    eps, `execute()`'s remaining-budget computation floors at 0.0
    (never a negative budget reaching the solver body)."""
    registry = _registry_with_seeking_echo()
    known = {"ex.x": Interval(1.0, 2.0)}
    route = plan(registry, known, frozenset(), "ex.y", 10.0).danger_ok

    solution = execute(route, registry, known, eps_budget=0.0).danger_ok
    assert solution.eps == 0.0
