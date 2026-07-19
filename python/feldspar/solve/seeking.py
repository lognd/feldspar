from __future__ import annotations

"""`CostPoint`/`CostCurve` -- the WO-13 cost-curve schema (09 sec. 3):
a budget-seeking solver's `SolverInfo.cost_curve` generalizes the scalar
`cost` field to sampled `(eps, cost)` points, with a CONSERVATIVE
lookup by remaining eps budget.

`SolverInfo.cost` itself is UNCHANGED and still the only thing the
Rust planner (04-routing, WO-05) reads for dominance pruning and total-
cost minimization -- this is an ADDITIVE schema, never a planner
redesign (WO-13's explicit constraint). `cost_curve` is metadata a
budget-seeking solver's own ladder climb (`feldspar.fea.ladder`) and
any future planner/pack estimator can query for "what would this
budget cost", without the Rust search itself branching on it.

Conservative-lookup argument (the WO-13 "dominance pruning still
sound" obligation): a real ladder climbs from the coarsest rung and
STOPS at the first (loosest) rung whose eps fits the requested budget
(sec. 3, `feldspar.fea.ladder.climb_richardson_ladder`). `cost_for_
budget` reproduces exactly that stopping rule -- the cheapest declared
point whose eps still fits -- so it can never UNDER-report the true
cost a climb would pay for a given budget (if it fits, the ladder
would have stopped there too; if nothing fits, we conservatively
report the most expensive -- finest -- declared point's cost, since
that is the closest the ladder can get). Cost is therefore a
non-increasing step function of the budget, which is exactly the
invariant dominance pruning over `cost` needs to stay sound."""

from typing import Tuple

from pydantic import BaseModel, ConfigDict, field_validator

__all__ = ["CostPoint", "CostCurve"]


# frob:doc docs/modules/solve.md#solve_seeking
class CostPoint(BaseModel):
    """One sampled `(eps, cost)` point on a budget-seeker's cost curve."""

    model_config = ConfigDict(frozen=True)

    eps: float  # the eps this point/rung achieves; >= 0
    cost: float  # > 0

    @field_validator("eps")
    @classmethod
    def _eps_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError(f"CostPoint.eps must be >= 0, got {value!r}")
        return value

    @field_validator("cost")
    @classmethod
    def _cost_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError(f"CostPoint.cost must be > 0, got {value!r}")
        return value


# frob:doc docs/modules/solve.md#solve_seeking
class CostCurve(BaseModel):
    """Sampled `(eps, cost)` points, ascending by `eps` (09 sec. 3).
    `scalar()` builds the one-point degenerate curve for a non-eps-
    seeking solver (additive schema: nothing about a plain solver's
    registration changes)."""

    model_config = ConfigDict(frozen=True)

    points: Tuple[CostPoint, ...]

    @field_validator("points")
    @classmethod
    def _validate_points(cls, points: Tuple[CostPoint, ...]) -> Tuple[CostPoint, ...]:
        if not points:
            raise ValueError("CostCurve requires at least one point")
        epses = [p.eps for p in points]
        if epses != sorted(epses):
            raise ValueError(
                f"CostCurve points must be sorted ascending by eps, got {epses!r}"
            )
        return points

    # frob:doc docs/modules/solve.md#solve_seeking
    @classmethod
    def scalar(cls, cost: float) -> "CostCurve":
        """The one-point curve (09 sec. 3: "scalar cost = one-point
        curve") at `eps=0.0` -- fits ANY non-negative budget, so
        `cost_for_budget` always returns `cost` unconditionally. This is
        the degenerate case every non-eps-seeking solver is equivalent
        to, even though v1 leaves `SolverInfo.cost_curve` unset (`None`)
        for those (the scalar `cost` field alone already serves them;
        `scalar()` exists so tests and future callers can treat "no
        curve" and "flat one-point curve" as the same thing when they
        need a `CostCurve` value uniformly)."""
        return cls(points=(CostPoint(eps=0.0, cost=cost),))

    # frob:doc docs/modules/solve.md#solve_seeking
    def cost_for_budget(self, eps_budget: float) -> float:
        """Conservative cost estimate for a remaining `eps_budget` (see
        module docstring for the non-increasing-step-function
        argument). Cheapest point whose declared eps still fits the
        budget; if the budget is tighter than every declared point, the
        finest (most expensive) point's cost is reported -- the
        closest conservative promise, execution decides feasibility."""
        fitting = [p for p in self.points if p.eps <= eps_budget]
        if fitting:
            return max(fitting, key=lambda p: p.eps).cost
        return min(self.points, key=lambda p: p.eps).cost
