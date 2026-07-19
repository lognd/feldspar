from __future__ import annotations

"""`PlanError` -- the planner's total error union (01-interfaces
`feldspar.plan`, WO-05, FINV-5). Same small tagged-value shape as
`feldspar.solve.errors.RegistryError`/`SolveError` (`BudgetUnreachable`
and `UnknownTarget` carry payloads; the rest are flat), so it is built
on the SAME shared `_TaggedError` base rather than duplicating the
kind/fields/eq/hash/repr machinery (house rule: no duplication)."""

from feldspar.solve.errors import _TaggedError

__all__ = ["PlanError"]


# frob:doc docs/modules/plan.md#plan_errors
class PlanError(_TaggedError):
    """`plan()` failures (01-interfaces `PlanError`); every variant is
    reachable via `tests/unit/test_plan.py` (FINV-5)."""

    # frob:doc docs/modules/plan.md#plan_errors
    @classmethod
    def InvalidBudget(cls) -> "PlanError":
        return cls("InvalidBudget")

    # frob:doc docs/modules/plan.md#plan_errors
    @classmethod
    def UnknownTarget(cls, target: str) -> "PlanError":
        return cls("UnknownTarget", target=target)

    # frob:doc docs/modules/plan.md#plan_errors
    @classmethod
    def NoApplicableSolver(cls) -> "PlanError":
        return cls("NoApplicableSolver")

    # frob:doc docs/modules/plan.md#plan_errors
    @classmethod
    def BudgetUnreachable(cls, best_eps: float) -> "PlanError":
        return cls("BudgetUnreachable", best_eps=best_eps)

    # frob:doc docs/modules/plan.md#plan_errors
    @classmethod
    def CyclicPortEquivalence(cls) -> "PlanError":
        return cls("CyclicPortEquivalence")
