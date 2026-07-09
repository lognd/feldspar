from __future__ import annotations

"""Plan/execute/solve facade over core search (WO-05/06/10)."""

from feldspar.plan.cache import PayloadStepCache, SolveCache
from feldspar.plan.errors import PlanError
from feldspar.plan.execute import AttemptRecord, Solution, execute
from feldspar.plan.parallel import parallel_corner_sweep
from feldspar.plan.policy import RoutePolicy
from feldspar.plan.report import render_explain, render_to_dict
from feldspar.plan.route import Route, RouteStep, plan
from feldspar.plan.solve import solve

__all__ = [
    "AttemptRecord",
    "PayloadStepCache",
    "PlanError",
    "Route",
    "RoutePolicy",
    "RouteStep",
    "SolveCache",
    "Solution",
    "execute",
    "parallel_corner_sweep",
    "plan",
    "render_explain",
    "render_to_dict",
    "solve",
]
