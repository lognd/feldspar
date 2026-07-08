from __future__ import annotations

"""WO-05 tests: `feldspar.plan.plan()` (01-interfaces `feldspar.plan`,
04-routing).

Covers the WO-05 rows of docs/implementation/02-edge-cases.md and the
WO-05 acceptance criteria: a 5-solver toy registry with two routes to
target (budget selects between them), lexicographic tie-break, every
`PlanError` variant reachable, twice-run determinism, and the FINV-8
tier-blindness permutation test."""

from typing import Tuple

from typani import Ok

from feldspar.core import Accuracy, Domain, Interval
from feldspar.plan import PlanError, plan
from feldspar.solve import Citation, ClaimSenses, SolverRegistry, solver


def _citation() -> Tuple[Citation, ...]:
    return (Citation(kind="handbook", ref="test fixture"),)


def _toy_registry(*, tier_a: str = "closed_form", tier_b: str = "table") -> SolverRegistry:
    """5-solver toy registry (WO-05 acceptance): `x` is known; two
    independent routes reach `target` -- `cheap_sloppy` (low cost, wide
    eps) and `via_mid` -> `tight_final` (higher cost, tight eps) -- plus
    two decoys (`unrelated`, `out_of_domain`) that never fire."""

    @solver(
        namespace="toy",
        inputs=("toy.x",),
        outputs=("toy.target",),
        domain=Domain(box={"toy.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"toy.target": Accuracy(eps_abs=5.0, eps_rel=0.0)},
        citations=_citation(),
        version="1",
        tier=tier_a,  # type: ignore[arg-type]
    )
    def cheap_sloppy(x):
        return Ok({"toy.target": x["toy.x"]})

    @solver(
        namespace="toy",
        inputs=("toy.x",),
        outputs=("toy.mid",),
        domain=Domain(box={"toy.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=2.0,
        accuracy={"toy.mid": Accuracy(eps_abs=0.5, eps_rel=0.0)},
        citations=_citation(),
        version="1",
        tier=tier_b,  # type: ignore[arg-type]
    )
    def via_mid(x):
        return Ok({"toy.mid": x["toy.x"]})

    @solver(
        namespace="toy",
        inputs=("toy.mid",),
        outputs=("toy.target",),
        domain=Domain(box={"toy.mid": Interval(-50.0, 50.0)}, tags=frozenset()),
        cost=3.0,
        accuracy={"toy.target": Accuracy(eps_abs=0.01, eps_rel=0.0)},
        citations=_citation(),
        version="1",
        solver_id_suffix="tight",
        tier=tier_a,  # type: ignore[arg-type]
    )
    def tight_final(x):
        return Ok({"toy.target": x["toy.mid"]})

    @solver(
        namespace="toy",
        inputs=("toy.x",),
        outputs=("toy.unrelated",),
        domain=Domain(box={"toy.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=0.5,
        accuracy={"toy.unrelated": Accuracy(eps_abs=0.0, eps_rel=0.0)},
        citations=_citation(),
        version="1",
        tier=tier_b,  # type: ignore[arg-type]
    )
    def unrelated(x):
        return Ok({"toy.unrelated": x["toy.x"]})

    @solver(
        namespace="toy",
        inputs=("toy.x",),
        outputs=("toy.out_of_domain",),
        domain=Domain(box={"toy.x": Interval(1000.0, 2000.0)}, tags=frozenset()),
        cost=0.1,
        accuracy={"toy.out_of_domain": Accuracy(eps_abs=0.0, eps_rel=0.0)},
        citations=_citation(),
        version="1",
        tier=tier_a,  # type: ignore[arg-type]
    )
    def out_of_domain(x):
        return Ok({"toy.out_of_domain": x["toy.x"]})

    registry = SolverRegistry()
    for fn in (cheap_sloppy, via_mid, tight_final, unrelated, out_of_domain):
        assert registry.register(*fn.solver_direction).is_ok
    registry.freeze()
    return registry


def _known() -> dict:
    return {"toy.x": Interval(1.0, 1.0)}


def test_acceptance_loose_budget_selects_cheap_route() -> None:
    registry = _toy_registry()
    route = plan(registry, _known(), frozenset(), "toy.target", 10.0).danger_ok
    assert route.steps[-1].solver_id == "toy.cheap_sloppy"
    assert route.total_cost == 1.0


def test_acceptance_tight_budget_selects_costly_route() -> None:
    registry = _toy_registry()
    route = plan(registry, _known(), frozenset(), "toy.target", 1.0).danger_ok
    solver_ids = [s.solver_id for s in route.steps]
    assert solver_ids == ["toy.via_mid", "toy.tight_final.tight"]
    assert route.total_cost == 5.0


def test_target_already_known_is_zero_step_route() -> None:
    registry = _toy_registry()
    route = plan(registry, {"toy.target": Interval(3.0, 3.0)}, frozenset(), "toy.target", 1.0).danger_ok
    assert route.steps == ()
    assert route.predicted_eps == 0.0
    assert route.total_cost == 0.0


def test_invalid_budget_before_search() -> None:
    registry = _toy_registry()
    err = plan(registry, _known(), frozenset(), "toy.target", 0.0).err
    assert err == PlanError.InvalidBudget()
    err_nan = plan(registry, _known(), frozenset(), "toy.target", float("nan")).err
    assert err_nan == PlanError.InvalidBudget()


def test_unknown_target() -> None:
    registry = _toy_registry()
    result = plan(registry, _known(), frozenset(), "toy.ghost", 1.0)
    assert result.is_err
    assert result.err == PlanError.UnknownTarget(target="toy.ghost")


def test_budget_unreachable_carries_best_eps() -> None:
    registry = _toy_registry()
    result = plan(registry, _known(), frozenset(), "toy.target", 1e-6)
    assert result.is_err
    err = result.err
    assert err.kind == "BudgetUnreachable"
    assert err.best_eps > 0.0


def test_no_applicable_solver_when_domain_excludes_hull() -> None:
    registry = _toy_registry()
    result = plan(registry, {"toy.x": Interval(1500.0, 1500.0)}, frozenset(), "toy.out_of_domain2", 1.0)
    assert result.is_err
    assert result.err == PlanError.UnknownTarget(target="toy.out_of_domain2")


def test_no_applicable_solver_reachable() -> None:
    registry = _toy_registry()
    # out_of_domain's box requires x in [1000, 2000]; our known x=1.0 is
    # outside it, so the only solver producing this target is inadmissible.
    result = plan(registry, _known(), frozenset(), "toy.out_of_domain", 1.0)
    assert result.is_err
    assert result.err == PlanError.NoApplicableSolver()


def test_equal_cost_routes_tie_break_lexicographically_and_are_stable() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="tie",
        inputs=("tie.x",),
        outputs=("tie.y",),
        domain=Domain(box={"tie.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"tie.y": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def b_route(x):
        return Ok({"tie.y": x["tie.x"]})

    @solver(
        namespace="tie",
        inputs=("tie.x",),
        outputs=("tie.y",),
        domain=Domain(box={"tie.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"tie.y": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
        solver_id_suffix="a",
    )
    def a_route(x):
        return Ok({"tie.y": x["tie.x"]})

    assert registry.register(*b_route.solver_direction).is_ok
    assert registry.register(*a_route.solver_direction).is_ok
    registry.freeze()

    known = {"tie.x": Interval(1.0, 1.0)}
    route1 = plan(registry, known, frozenset(), "tie.y", 10.0).danger_ok
    route2 = plan(registry, known, frozenset(), "tie.y", 10.0).danger_ok
    assert route1.steps[0].solver_id == "tie.a_route.a"
    assert route1.digest == route2.digest


def test_cyclic_port_equivalence() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="cyc",
        inputs=("cyc.p1",),
        outputs=("cyc.p2",),
        domain=Domain(box={"cyc.p1": Interval(-1e6, 1e6)}, tags=frozenset()),
        cost=1.0,
        accuracy={"cyc.p2": Accuracy(eps_abs=0.0, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def a_to_b(x):
        return Ok({"cyc.p2": x["cyc.p1"]})

    @solver(
        namespace="cyc",
        inputs=("cyc.p2",),
        outputs=("cyc.p1",),
        domain=Domain(box={"cyc.p2": Interval(-1e6, 1e6)}, tags=frozenset()),
        cost=1.0,
        accuracy={"cyc.p1": Accuracy(eps_abs=0.0, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def b_to_a(x):
        return Ok({"cyc.p1": x["cyc.p2"]})

    assert registry.register(*a_to_b.solver_direction).is_ok
    assert registry.register(*b_to_a.solver_direction).is_ok
    registry.freeze()

    result = plan(registry, {"cyc.p1": Interval(1.0, 1.0)}, frozenset(), "cyc.p2", 1.0)
    assert result.is_err
    assert result.err == PlanError.CyclicPortEquivalence()


def test_plan_twice_yields_identical_route_digest() -> None:
    """FINV-1: same registry contents + same request => byte-identical
    Route digest."""
    registry = _toy_registry()
    route1 = plan(registry, _known(), frozenset(), "toy.target", 1.0).danger_ok
    route2 = plan(registry, _known(), frozenset(), "toy.target", 1.0).danger_ok
    assert route1.digest == route2.digest


def test_finv8_tier_blindness_permuted_tiers_yield_identical_route() -> None:
    """FINV-8: the search reads cost/accuracy/domain only, never tier
    labels. Permuting the tier declared on every solver in the toy
    registry must not change the chosen route or its digest."""
    registry_a = _toy_registry(tier_a="closed_form", tier_b="table")
    registry_b = _toy_registry(tier_a="discretized", tier_b="coupled")

    route_a = plan(registry_a, _known(), frozenset(), "toy.target", 1.0).danger_ok
    route_b = plan(registry_b, _known(), frozenset(), "toy.target", 1.0).danger_ok

    assert route_a.digest == route_b.digest
    assert [s.solver_id for s in route_a.steps] == [s.solver_id for s in route_b.steps]


def test_sense_filters_one_sided_edges_and_folds_into_request() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="sense",
        inputs=("sense.x",),
        outputs=("sense.y",),
        domain=Domain(box={"sense.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"sense.y": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
        conservative_for=ClaimSenses.UPPER,
    )
    def upper_only(x):
        return Ok({"sense.y": x["sense.x"]})

    assert registry.register(*upper_only.solver_direction).is_ok
    registry.freeze()

    known = {"sense.x": Interval(1.0, 1.0)}
    upper_result = plan(registry, known, frozenset(), "sense.y", 1.0, sense=ClaimSenses.UPPER)
    assert upper_result.is_ok

    lower_result = plan(registry, known, frozenset(), "sense.y", 1.0, sense=ClaimSenses.LOWER)
    assert lower_result.is_err
    assert lower_result.err == PlanError.NoApplicableSolver()
