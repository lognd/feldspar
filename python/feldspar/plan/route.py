from __future__ import annotations

"""`RouteStep`, `Route`, `plan()` -- the planner search facade over
`feldspar-core::search` (01-interfaces `feldspar.plan`, WO-05, 04-routing).

`plan()` marshals the frozen `SolverRegistry` into the Rust-side search
snapshot ONCE per call (`_PlanSolverInput` per solver -- deliberately
carrying no `tier` field, FINV-8) and re-wraps the Rust `_feldspar.plan`
raising primitive into a typani `Result[Route, PlanError]` (the same
raw/checked marshalling pattern `feldspar/core.py` uses for WO-02/04)."""

from typing import TYPE_CHECKING, Mapping

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from feldspar import _feldspar
from feldspar.core import Domain, Interval
from feldspar.logging_setup import get_logger
from feldspar.plan.errors import PlanError
from feldspar.solve._models import ClaimSenses

if TYPE_CHECKING:
    from feldspar.solve.registry import SolverRegistry

__all__ = ["Route", "RouteStep", "plan"]

_log = get_logger(__name__)


class RouteStep(BaseModel):
    """One committed step in a `Route` (01-interfaces `RouteStep`)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    solver_id: str
    realized_domain: Domain
    predicted_eps: float
    cost: float


class Route(BaseModel):
    """The ordered result of a successful `plan()` (01-interfaces `Route`,
    AD-5 digest convention); carries enough for WO-06 to execute without
    re-searching and WO-10 to explain "why this path"."""

    model_config = ConfigDict(frozen=True)

    target: str
    steps: "tuple[RouteStep, ...]"
    predicted_eps: float
    total_cost: float
    digest: str


def _plan_error_from_exc(exc: Exception) -> PlanError:
    args = exc.args
    variant: str = args[0]
    if variant == "UnknownTarget":
        return PlanError.UnknownTarget(target=args[1])
    if variant == "BudgetUnreachable":
        return PlanError.BudgetUnreachable(best_eps=args[1])
    return getattr(PlanError, variant)()


def _route_from_native(native: "_feldspar.Route") -> Route:
    steps = tuple(
        RouteStep(
            solver_id=s.solver_id,
            realized_domain=s.realized_domain,
            predicted_eps=s.predicted_eps,
            cost=s.cost,
        )
        for s in native.steps
    )
    return Route(
        target=native.target,
        steps=steps,
        predicted_eps=native.predicted_eps,
        total_cost=native.total_cost,
        digest=native.digest,
    )


def plan(
    registry: "SolverRegistry",
    known: Mapping[str, Interval],
    tags: "frozenset[str] | set[str]",
    target: str,
    eps_budget: float,
    sense: "ClaimSenses | str" = ClaimSenses.BOTH,
) -> "Result[Route, PlanError]":
    """Deterministic forward AND-graph search from `known` ports to
    `target` (01-interfaces `plan`, 04-routing). Zero-step `Route` when
    `target` is already in `known` (G12); `sense` filters `conservative_for`
    edges and folds into the request digest via the route it produces
    (A-3); a one-sided edge is admissible only as the FINAL step (A-2).
    """
    resolved_sense = ClaimSenses.coerce(sense)
    solver_inputs = [
        _feldspar._PlanSolverInput(
            info.solver_id,
            list(info.inputs),
            list(info.outputs),
            info.domain,
            info.cost,
            dict(info.accuracy),
            info.conservative_for.value,
        )
        for info, _fn in registry
    ]
    _log.info(
        "plan: target=%s eps_budget=%s sense=%s known_ports=%d solvers=%d",
        target,
        eps_budget,
        resolved_sense.value,
        len(known),
        len(solver_inputs),
    )
    try:
        native = _feldspar.plan(
            solver_inputs,
            dict(known),
            set(tags),
            target,
            eps_budget,
            resolved_sense.value,
        )
    except _feldspar.PlanErrorRaised as exc:
        err = _plan_error_from_exc(exc)
        _log.warning("plan failed for target=%s: %r", target, err)
        return Err(err)
    route = _route_from_native(native)
    _log.info(
        "plan succeeded: target=%s steps=%d cost=%s eps=%s digest=%s",
        target,
        len(route.steps),
        route.total_cost,
        route.predicted_eps,
        route.digest,
    )
    return Ok(route)
