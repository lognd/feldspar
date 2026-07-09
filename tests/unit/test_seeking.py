from __future__ import annotations

"""WO-13 tests: `CostPoint`/`CostCurve` (09 sec. 3) -- the sampled
(eps, cost) schema and its conservative budget lookup."""

import pytest

from feldspar.solve.seeking import CostCurve, CostPoint


def test_cost_point_rejects_negative_eps() -> None:
    with pytest.raises(ValueError):
        CostPoint(eps=-1.0, cost=1.0)


def test_cost_point_rejects_non_positive_cost() -> None:
    with pytest.raises(ValueError):
        CostPoint(eps=0.0, cost=0.0)


def test_cost_curve_requires_at_least_one_point() -> None:
    with pytest.raises(ValueError):
        CostCurve(points=())


def test_cost_curve_requires_ascending_eps() -> None:
    with pytest.raises(ValueError):
        CostCurve(
            points=(
                CostPoint(eps=1e-3, cost=5.0),
                CostPoint(eps=1e-4, cost=1.0),
            )
        )


def test_scalar_curve_fits_any_budget() -> None:
    curve = CostCurve.scalar(5.0)
    assert curve.cost_for_budget(1e30) == 5.0
    assert curve.cost_for_budget(1e-30) == 5.0
    assert curve.cost_for_budget(0.0) == 5.0


def test_cost_for_budget_picks_cheapest_fitting_point() -> None:
    curve = CostCurve(
        points=(
            CostPoint(eps=1e-5, cost=20.0),
            CostPoint(eps=1e-4, cost=10.0),
            CostPoint(eps=1e-3, cost=5.0),
        )
    )
    # A loose budget only needs the coarsest (cheapest) fitting rung.
    assert curve.cost_for_budget(1e-2) == 5.0
    assert curve.cost_for_budget(1e-3) == 5.0
    # A tighter budget must climb to a costlier rung.
    assert curve.cost_for_budget(5e-4) == 10.0
    assert curve.cost_for_budget(1e-4) == 10.0
    assert curve.cost_for_budget(5e-5) == 20.0


def test_cost_for_budget_below_finest_point_reports_finest_cost() -> None:
    curve = CostCurve(
        points=(
            CostPoint(eps=1e-5, cost=20.0),
            CostPoint(eps=1e-4, cost=10.0),
        )
    )
    assert curve.cost_for_budget(1e-9) == 20.0


def test_cost_for_budget_is_non_increasing_in_budget() -> None:
    """The dominance-pruning-soundness argument (module docstring):
    cost must never INCREASE as the budget loosens."""
    curve = CostCurve(
        points=(
            CostPoint(eps=1e-5, cost=20.0),
            CostPoint(eps=1e-4, cost=10.0),
            CostPoint(eps=1e-3, cost=5.0),
        )
    )
    budgets = [1e-6, 1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 1e-2, 1.0]
    costs = [curve.cost_for_budget(b) for b in budgets]
    assert costs == sorted(costs, reverse=True)
