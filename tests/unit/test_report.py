from __future__ import annotations

"""WO-10 tests: `Solution.explain()`/`Solution.to_dict()`
(`feldspar.plan.report`, 04-routing "Justification report").

Covers: pure-rendering (no solver/registry calls during explain/
to_dict, mock-asserted per 02-edge-cases "explain on cached Solution"),
a byte-stable golden for a toy two-step registry, the reroute-trail
rendering (02-edge-cases "explain after reroute"), and the eps-vs-
budget decomposition. FINV-1/FINV-4 (this module reuses the ONE
`total_error` home rather than re-deriving eps math, no separate
test needed here -- exercised directly by `test_propagation.py`)."""

from typing import Tuple

from typani import Err, Ok

from feldspar.core import Accuracy, Domain, Interval
from feldspar.plan import execute, plan, solve
from feldspar.solve import Citation, SolveError, SolverRegistry, solver


def _citation() -> Tuple[Citation, ...]:
    return (Citation(kind="handbook", ref="test fixture", note="a note"),)


def _toy_registry() -> SolverRegistry:
    """Two-step chain: ex.x -> ex.y -> ex.z, deterministic golden
    fixture (no gmsh/ccx required, "toy registry" per WO-10 acceptance)."""
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

    @solver(
        namespace="ex",
        inputs=("ex.y",),
        outputs=("ex.z",),
        domain=Domain(box={"ex.y": Interval(0.0, 100.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"ex.z": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def increment(x):
        return Ok({"ex.z": x["ex.y"] + 1.0})

    assert registry.register(*double.solver_direction).is_ok
    assert registry.register(*increment.solver_direction).is_ok
    registry.freeze()
    return registry


def _toy_known():
    return {"ex.x": Interval(1.0, 2.0)}


# ---------------------------------------------------------------------------
# Pure-rendering: explain()/to_dict() never touch a solver function.
# ---------------------------------------------------------------------------


def test_explain_makes_no_solver_calls() -> None:
    calls = []

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
        calls.append(x)
        return Ok({"ex.y": x["ex.x"] * 2.0})

    assert registry.register(*double.solver_direction).is_ok
    registry.freeze()
    known = {"ex.x": Interval(1.0, 2.0)}
    route = plan(registry, known, frozenset(), "ex.y", 10.0).danger_ok
    solution = execute(route, registry, known).danger_ok

    calls_before = len(calls)
    assert calls_before == 2  # corner sweep over [1.0, 2.0]'s two corners

    text = solution.explain()
    as_dict = solution.to_dict()

    assert (
        len(calls) == calls_before
    )  # explain()/to_dict() called the SolveFn zero more times
    assert isinstance(text, str)
    assert isinstance(as_dict, dict)


# frob:tests python/feldspar/plan/report.py::render_to_dict kind="unit"
# frob:tests python/feldspar/plan/report.py::render_explain kind="unit"
def test_to_dict_and_explain_share_step_data() -> None:
    registry = _toy_registry()
    known = _toy_known()
    route = plan(registry, known, frozenset(), "ex.z", 10.0).danger_ok
    solution = execute(route, registry, known).danger_ok

    d = solution.to_dict()
    assert len(d["route"]["steps"]) == 2
    assert d["route"]["steps"][0]["solver_id"] == "ex.double"
    assert d["route"]["steps"][1]["solver_id"] == "ex.increment"
    assert d["route"]["steps"][0]["citations"][0]["ref"] == "test fixture"

    text = solution.explain()
    assert "ex.double" in text
    assert "ex.increment" in text
    assert "test fixture" in text


# ---------------------------------------------------------------------------
# Golden: byte-stable output for a fixed toy registry + request.
# ---------------------------------------------------------------------------


# frob:tests crates/feldspar-py/src/search.rs::PyRouteStep.realized_domain
# frob:tests crates/feldspar-py/src/search.rs::PyRouteStep.predicted_eps
def test_explain_golden_toy_registry() -> None:
    registry = _toy_registry()
    known = _toy_known()
    route = plan(registry, known, frozenset(), "ex.z", 10.0).danger_ok
    solution = execute(route, registry, known).danger_ok

    expected = """Solution for target='ex.z'
  value=[2.5, 5.5]  eps=0.1
  realized_error(worst-case)=1.6
  eps_budget: (no budget context -- execute() called directly)
  cache_hit=False
  settings_digest={settings_digest}
  route_digest={route_digest}
  route_total_cost=2.0
  route: 2 step(s)
  step 1: solver='ex.double'
    citation: handbook: test fixture -- a note
    declared_domain: box=(ex.x=[0.0, 10.0]) tags=((none))
    realized_domain: box=(ex.x=[1.0, 2.0]) tags=((none))
    predicted_eps=0.5  charged_eps=0.5  cost=1.0
    algebraic_form: (not carried -- hand-written direction)
    admission_predicate: (none)
  step 2: solver='ex.increment'
    citation: handbook: test fixture -- a note
    declared_domain: box=(ex.y=[0.0, 100.0]) tags=((none))
    realized_domain: box=(ex.y=[0.5, 2.5]) tags=((none))
    predicted_eps=0.1  charged_eps=0.1  cost=1.0
    algebraic_form: (not carried -- hand-written direction)
    admission_predicate: (none)
  reroute trail: (none -- solved on the first attempt)""".format(
        settings_digest=solution.settings_digest, route_digest=solution.route.digest
    )

    assert solution.explain() == expected


def test_explain_golden_is_stable_across_two_runs() -> None:
    """Determinism (04-routing): the same request produces byte-
    identical `explain()` output on a second, independently-built
    registry/route/solution."""
    r1, r2 = _toy_registry(), _toy_registry()
    known = _toy_known()
    s1 = execute(
        plan(r1, known, frozenset(), "ex.z", 10.0).danger_ok, r1, known
    ).danger_ok
    s2 = execute(
        plan(r2, known, frozenset(), "ex.z", 10.0).danger_ok, r2, known
    ).danger_ok
    assert s1.explain() == s2.explain()
    assert s1.to_dict() == s2.to_dict()


# ---------------------------------------------------------------------------
# Zero-step route (G12).
# ---------------------------------------------------------------------------


def test_explain_zero_step_route() -> None:
    registry = _toy_registry()
    known = {"ex.z": Interval(9.0, 9.0)}
    route = plan(registry, known, frozenset(), "ex.z", 10.0).danger_ok
    solution = execute(route, registry, known).danger_ok
    text = solution.explain()
    assert "zero-step" in text
    assert solution.to_dict()["route"]["steps"] == []


# ---------------------------------------------------------------------------
# eps-vs-budget decomposition (via solve(), which stamps eps_budget).
# ---------------------------------------------------------------------------


def test_explain_renders_budget_decomposition_via_solve() -> None:
    registry = _toy_registry()
    known = _toy_known()
    solution = solve(registry, known, frozenset(), "ex.z", 10.0).danger_ok
    text = solution.explain()
    assert "eps_budget=10.0" in text
    assert "spent=1.6" in text
    assert "remaining=8.4" in text
    d = solution.to_dict()
    assert d["eps_budget"] == 10.0
    assert d["eps_remaining"] == 10.0 - d["realized_error"]


# ---------------------------------------------------------------------------
# Reroute trail + cache provenance rendering (02-edge-cases WO-10 rows).
# ---------------------------------------------------------------------------


def test_explain_renders_reroute_trail() -> None:
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
    def flaky(x):
        return Err(SolveError.ToolMissing(tool="nope", guidance="install nope"))

    @solver(
        namespace="ex",
        inputs=("ex.x",),
        outputs=("ex.y",),
        domain=Domain(box={"ex.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=2.0,
        accuracy={"ex.y": Accuracy(eps_abs=0.5, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def backup(x):
        return Ok({"ex.y": x["ex.x"] * 3.0})

    assert registry.register(*flaky.solver_direction).is_ok
    assert registry.register(*backup.solver_direction).is_ok
    registry.freeze()
    known = {"ex.x": Interval(1.0, 2.0)}
    solution = solve(registry, known, frozenset(), "ex.y", 10.0).danger_ok

    assert len(solution.attempts) == 1
    text = solution.explain()
    assert "reroute trail: 1 attempt(s)" in text
    assert "ex.flaky" in text
    assert solution.to_dict()["attempts"][0]["failed_solver_id"] == "ex.flaky"


def test_explain_renders_cache_hit() -> None:
    registry = _toy_registry()
    known = _toy_known()
    assert solve(registry, known, frozenset(), "ex.z", 10.0).is_ok
    second = solve(registry, known, frozenset(), "ex.z", 10.0).danger_ok
    assert second.cache_hit is True
    assert "cache_hit=True" in second.explain()
    assert second.to_dict()["cache_hit"] is True
