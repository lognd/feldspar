from __future__ import annotations

"""Regression for the coordinator-verified bug: the native planner
(`feldspar_core::search`) rejected any solver direction whose
`Domain.box` contains one of its OWN OUTPUT ports, with
`PlanError.NoApplicableSolver`, even though every INPUT port was known
and in-domain. This made every `Relation`-built direction permanently
unroutable, since `Relation`'s documented API declares ONE domain box
over ALL its ports (see `python/feldspar/library/mech.py`'s
`cantilever`). Fixed by making plan-time admission check ONLY a
solver's declared INPUT ports against the box (04-routing point 2);
an output-port box entry is a validity constraint on the realized
result, checked at execution time instead (`execute.py`'s
`_check_step_output_domain`)."""

from typani import Ok

from feldspar.core import Accuracy, Domain, Interval
from feldspar.plan import plan, solve
from feldspar.solve import Citation, SolverRegistry, solver


def _citation():
    return (Citation(kind="handbook", ref="test fixture"),)


def _registry_with_output_box_entry() -> SolverRegistry:
    """The minimal repro: `q.a` -> `q.b`, box covers BOTH ports (the
    `Relation` shape), `q.a` known and in-domain."""
    registry = SolverRegistry()

    @solver(
        namespace="q",
        inputs=("q.a",),
        outputs=("q.b",),
        domain=Domain(
            box={"q.a": Interval(0.0, 10.0), "q.b": Interval(0.0, 10.0)},
            tags=frozenset(),
        ),
        cost=1.0,
        accuracy={"q.b": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def q_step(x):
        return Ok({"q.b": x["q.a"]})

    assert registry.register(*q_step.solver_direction).is_ok
    registry.freeze()
    return registry


def test_plan_succeeds_when_box_covers_input_only():
    """Control case: box covers only the input port -- already worked
    before the fix, must keep working."""
    registry = SolverRegistry()

    @solver(
        namespace="q",
        inputs=("q.a",),
        outputs=("q.b",),
        domain=Domain(box={"q.a": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"q.b": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def q_step(x):
        return Ok({"q.b": x["q.a"]})

    assert registry.register(*q_step.solver_direction).is_ok
    registry.freeze()

    known = {"q.a": Interval(1.0, 2.0)}
    route = plan(registry, known, frozenset(), "q.b", 1.0).danger_ok
    assert route.steps[0].solver_id == "q.q_step"


def test_plan_succeeds_when_box_also_covers_output():
    """The bug: identical solver, box ALSO covers the output port --
    must plan fine now, previously PlanError.NoApplicableSolver."""
    registry = _registry_with_output_box_entry()
    known = {"q.a": Interval(1.0, 2.0)}
    result = plan(registry, known, frozenset(), "q.b", 1.0)
    assert result.is_ok, result.err
    assert result.danger_ok.steps[0].solver_id == "q.q_step"


def test_solve_succeeds_when_box_also_covers_output():
    """End-to-end `solve()` (plan + execute) over the same repro."""
    registry = _registry_with_output_box_entry()
    known = {"q.a": Interval(1.0, 2.0)}
    result = solve(registry, known, frozenset(), "q.b", 1.0)
    assert result.is_ok, result.err
    solution = result.danger_ok
    assert solution.value == Interval(1.0, 2.0)
