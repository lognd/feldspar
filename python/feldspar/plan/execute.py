from __future__ import annotations

"""`AttemptRecord`, `Solution`, `execute()`, `route_settings_digest()` --
the WO-06 execution facade (01-interfaces `feldspar.plan`, 04-routing
"Execution"). Walks a planned `Route` in order, running the REAL
`SolveFn` corner sweep per step (the planner's estimate used a sum
surrogate, WO-05 notes; this is where the exact sweep replaces it,
FINV-4: same core `corner_sweep`/`inflate`/`total_error` routines) --
never re-searches (`Route` already carries everything needed)."""

import math
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from feldspar.core import Interval, corner_sweep, inflate
from feldspar.logging import get_logger
from feldspar.plan.route import Route
from feldspar.solve.digest import canonical_digest
from feldspar.solve.errors import SolveError

if TYPE_CHECKING:
    from feldspar.solve.registry import SolverRegistry

__all__ = [
    "AttemptRecord",
    "Solution",
    "error_to_record_fields",
    "execute",
    "execute_with_attribution",
    "route_settings_digest",
]

_log = get_logger(__name__)


class AttemptRecord(BaseModel):
    """One reroute-loop attempt (04-routing "Fallback rerouting"): the
    exclusion set going INTO this attempt, which step (if any) failed --
    `None` means `plan()` itself failed, not an executed step -- and the
    failure as a JSON-safe kind/detail pair (never the live `PlanError`/
    `SolveError` object: those aren't pydantic models, and keeping this
    model plain-JSON-shaped is what lets `Solution` digest cleanly
    through `canonical_digest`, AD-5)."""

    model_config = ConfigDict(frozen=True)

    excluded: Tuple[str, ...]
    route_digest: Optional[str] = None
    failed_solver_id: Optional[str] = None
    error_kind: str
    error_detail: Mapping[str, Any] = {}


def error_to_record_fields(error: Any) -> Tuple[str, Mapping[str, Any]]:
    """`(kind, detail)` for any `_TaggedError`-shaped value (`PlanError`/
    `SolveError`) -- the ONE place a live error value gets lowered into
    an `AttemptRecord`'s plain fields (no duplication across `solve.py`
    call sites)."""
    fields = getattr(error, "_fields", {})
    detail = {
        k: (v if isinstance(v, (str, int, float, bool)) or v is None else repr(v))
        for k, v in fields.items()
    }
    return error.kind, detail


class Solution(BaseModel):
    """A successful `solve()`/`execute()` result (01-interfaces
    `Solution`, 04-routing "Execution"). `eps` is the FINAL step's
    realized model error only -- every upstream step's error already
    rides in `value`'s width via `inflate` at each consuming step (02,
    audit A-1), so `total_error(value, eps)` (WO-04) is the budget-
    checked total."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    target: str
    value: Interval
    eps: float
    route: Route
    settings_digest: str
    solver_versions: Mapping[str, str]
    attempts: Tuple[AttemptRecord, ...] = ()
    cache_hit: bool = False


def route_settings_digest(route: Route, registry: "SolverRegistry") -> str:
    """Folds every step's `SolverInfo.settings_digest` (03, F1) in route
    order into ONE digest (04-routing "Execution": "fold settings
    digests ... into a Solution"). Shared by `execute()` (the field it
    stamps onto `Solution`) and `cache.py` (a cache-key component) so
    there is exactly one settings-fold implementation, not one per
    caller (house rule: no duplication)."""
    solver_map = {info.solver_id: info for info, _fn in registry}
    digests = [solver_map[step.solver_id].settings_digest for step in route.steps]
    return canonical_digest(digests)


def _check_step_output(
    info: Any, out_values: Mapping[str, float]
) -> "Result[None, SolveError]":
    for port in info.outputs:
        if port not in out_values:
            return Err(SolveError.MissingOutput(port=port))
    for port, value in out_values.items():
        if not math.isfinite(value):
            return Err(SolveError.NonFinite(port=port))
    return Ok(None)


def _make_corner_fn(info: Any, fn: Any, measured: List[float]) -> Any:
    """Builds the `corner_sweep` callback for one step: runs the real
    `SolveFn`, checks finiteness/output-completeness (audit A-4, friction
    G12), validates and collects any reported `measured_eps` (which
    replaces the declared accuracy ceiling for THIS step, 04-routing),
    and returns the plain `Mapping[str, float]` `corner_sweep` hulls."""

    def corner_fn(
        corner: Mapping[str, float],
    ) -> "Result[Mapping[str, float], SolveError]":
        res = fn(corner)
        if res.is_err:
            return res
        out = res.danger_ok  # SolveOutput
        checked = _check_step_output(info, out.values)
        if checked.is_err:
            return checked.swap_ok(dict)
        if out.measured_eps is not None:
            if not math.isfinite(out.measured_eps) or out.measured_eps < 0:
                return Err(
                    SolveError.InvalidMeasurement(
                        reason=f"measured_eps={out.measured_eps!r} for {info.solver_id}"
                    )
                )
            measured.append(out.measured_eps)
        return Ok({port: out.values[port] for port in info.outputs})

    return corner_fn


def execute(
    route: Route, registry: "SolverRegistry", known: Mapping[str, Interval]
) -> "Result[Solution, SolveError]":
    """Public `execute()` (01-interfaces): thin wrapper over
    `execute_with_attribution` that drops the failing-step attribution
    the public `SolveError`-only contract has no slot for."""
    result = execute_with_attribution(route, registry, known)
    if result.is_err:
        _solver_id, err = result.danger_err
        return Err(err)
    return result.swap_err(SolveError)


def execute_with_attribution(
    route: Route, registry: "SolverRegistry", known: Mapping[str, Interval]
) -> "Result[Solution, Tuple[Optional[str], SolveError]]":
    """Same walk as `execute()`, but on failure also reports WHICH
    step's `solver_id` raised (`None` only in the impossible zero-step
    case) -- `solve.py`'s reroute loop needs this to update its
    exclusion set; the public `execute()` signature (01-interfaces) has
    no slot for it, so this is the shared implementation both call
    into (house rule: no duplication)."""
    return _execute_impl(route, registry, known)


def _execute_impl(
    route: Route, registry: "SolverRegistry", known: Mapping[str, Interval]
) -> "Result[Solution, Tuple[Optional[str], SolveError]]":
    """Walks `route` in order (01-interfaces `execute`): per step,
    corner-sweeps eps-INFLATED inputs through the real `SolveFn`, hulls
    outputs, and charges the step's REALIZED eps (measured, when the
    solver reports one, else the declared `Accuracy.worst_over` the
    achieved hull -- the same `worst_over` the planner's estimate uses,
    FINV-4). A zero-step route (G12: target already known) returns the
    known interval at eps 0 directly."""
    solver_map = {info.solver_id: (info, fn) for info, fn in registry}
    values: Dict[str, Interval] = dict(known)
    eps_map: Dict[str, float] = {port: 0.0 for port in known}
    solver_versions: Dict[str, str] = {}
    final_eps = 0.0

    if not route.steps:
        value = values[route.target]
        _log.info(
            "execute: zero-step route for target=%s (already known)", route.target
        )
        return Ok(
            Solution(
                target=route.target,
                value=value,
                eps=0.0,
                route=route,
                settings_digest=route_settings_digest(route, registry),
                solver_versions={},
                attempts=(),
                cache_hit=False,
            )
        )

    for step in route.steps:
        info, fn = solver_map[step.solver_id]
        box = {
            port: inflate(values[port], eps_map.get(port, 0.0)) for port in info.inputs
        }
        measured: List[float] = []
        swept = corner_sweep(box, _make_corner_fn(info, fn, measured))
        if swept.is_err:
            _log.warning("execute: step %s failed: %r", step.solver_id, swept.err)
            return Err((step.solver_id, swept.danger_err))
        hull = swept.danger_ok

        if measured:
            step_eps = max(measured)
        else:
            step_eps = max(
                (info.accuracy[port].worst_over(hull[port]) for port in info.outputs),
                default=0.0,
            )
        _log.debug(
            "execute: step %s realized_eps=%s (measured=%s)",
            step.solver_id,
            step_eps,
            bool(measured),
        )

        for port, iv in hull.items():
            values[port] = iv
            eps_map[port] = step_eps
        solver_versions[step.solver_id] = info.version
        final_eps = step_eps

    value = values[route.target]
    solution = Solution(
        target=route.target,
        value=value,
        eps=final_eps,
        route=route,
        settings_digest=route_settings_digest(route, registry),
        solver_versions=solver_versions,
        attempts=(),
        cache_hit=False,
    )
    _log.info(
        "execute: succeeded target=%s eps=%s steps=%d",
        route.target,
        final_eps,
        len(route.steps),
    )
    return Ok(solution)
