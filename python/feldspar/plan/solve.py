from __future__ import annotations

"""`solve()` -- plan + execute + fallback reroute + solve cache
(01-interfaces `feldspar.plan`, WO-06, 04-routing "Fallback rerouting"/
"Solve cache"). The one entry point that ties WO-05's `plan()` and this
WO's `execute()`/`SolveCache` together into the caller-facing facade."""

from typing import TYPE_CHECKING, Iterator, Mapping, Optional, Tuple

from typani.result import Err, Ok, Result

from feldspar.core import Interval, total_error
from feldspar.logging_setup import get_logger
from feldspar.plan.cache import (
    PayloadStepCache,
    SolveCache,
    cache_key,
    is_route_cacheable,
)
from feldspar.plan.errors import PlanError
from feldspar.plan.execute import (
    AttemptRecord,
    Solution,
    error_to_record_fields,
    execute_with_attribution,
)
from feldspar.plan.policy import RoutePolicy
from feldspar.plan.route import Route, plan
from feldspar.solve._models import ClaimSenses
from feldspar.solve.errors import SolveError
from feldspar.solve.payload import PayloadRef

if TYPE_CHECKING:
    from feldspar.solve.registry import SolverRegistry

__all__ = ["solve"]

_log = get_logger(__name__)


class _ExcludingRegistryView:
    """A read-only `__iter__`-only view over `registry` that skips
    excluded solver ids -- the reroute loop's exclusion set expressed as
    a registry filter, not a registry mutation (the same frozen
    `SolverRegistry` is reused across every replan attempt, AD-4).
    `plan()` only ever calls `for info, _fn in registry`, so this is a
    complete substitute without reimplementing `SolverRegistry`."""

    def __init__(self, registry: "SolverRegistry", excluded: "frozenset[str]") -> None:
        self._registry = registry
        self._excluded = excluded

    def __iter__(self) -> Iterator[Tuple[object, object]]:
        for info, fn in self._registry:
            if info.solver_id not in self._excluded:
                yield info, fn

    def digest(self) -> str:
        return self._registry.digest()


def solve(
    registry: "SolverRegistry",
    known: Mapping[str, Interval],
    tags: "frozenset[str] | set[str]",
    target: str,
    eps_budget: float,
    sense: "ClaimSenses | str" = ClaimSenses.BOTH,
    policy: "RoutePolicy | None" = None,
    payloads: Optional[Mapping[str, PayloadRef]] = None,
    step_cache: Optional[PayloadStepCache] = None,
) -> "Result[Solution, SolveError | PlanError]":
    """`plan()` then `execute()` (01-interfaces `solve`), with:

    - a post-execution budget re-check (`SolveError.BudgetExceeded` if
      the REALIZED eps busts `eps_budget` -- honest over optimistic,
      04-routing "Execution");
    - default fallback rerouting on any step failure: the failing
      `solver_id` joins an exclusion set and `plan()` reruns
      deterministically over the remaining graph (04-routing "Fallback
      rerouting"), `RoutePolicy(fallback=False)` disables this;
    - the content-addressed solve cache (04-routing "Solve cache",
      AD-9), default ON via `RoutePolicy(cache=True)`, skipped entirely
      for routes containing a `deterministic=False` step.

    Every attempt (successful or not) is appended to the returned/final
    `Solution.attempts`/`SolveError.NoRouteRemaining(attempts)` trail,
    so a reroute is fully reconstructable from the return value alone,
    not just the logs (though every reroute is ALSO logged at WARNING,
    per the logging mantra).

    WO-12: `payloads` names the request's known payload-port refs (they
    fold into the request digest as their hashes, FINV-12, and pass to
    every step exact-by-reference); payload-touching deterministic steps
    go through the per-step `PayloadStepCache` (default-constructed when
    `policy.cache` and none is injected; inject one to observe hit
    counts or share a root across solves)."""
    if policy is None:
        policy = RoutePolicy()
    resolved_sense = ClaimSenses.coerce(sense)
    cache = SolveCache() if policy.cache else None
    if step_cache is None and policy.cache:
        step_cache = PayloadStepCache()
    excluded: "frozenset[str]" = frozenset()
    attempts: list = []

    while True:
        view = _ExcludingRegistryView(registry, excluded)
        plan_result = plan(
            view,  # ty: ignore[invalid-argument-type]
            known,
            tags,
            target,
            eps_budget,
            resolved_sense,
            payloads,
        )
        if plan_result.is_err:
            perr = plan_result.danger_err
            kind, detail = error_to_record_fields(perr)
            attempts.append(
                AttemptRecord(
                    excluded=tuple(sorted(excluded)),
                    route_digest=None,
                    failed_solver_id=None,
                    error_kind=kind,
                    error_detail=detail,
                )
            )
            if not excluded:
                # first attempt: no reroute has happened yet, return the
                # plan error directly (nothing to report a trail about).
                _log.warning("solve: initial plan failed: %r", perr)
                return Err(perr)
            _log.warning(
                "solve: no route remains after %d exclusion(s): %r", len(excluded), perr
            )
            return Err(SolveError.NoRouteRemaining(attempts=tuple(attempts)))

        route: Route = plan_result.danger_ok

        cache_hit_key = None
        cacheable = policy.cache and is_route_cacheable(route, registry)
        if cache is not None and cacheable:
            cache_hit_key = cache_key(
                registry,
                known,
                tags,
                target,
                eps_budget,
                resolved_sense,
                route,
                payloads,
            )
            cached = cache.get(cache_hit_key, route, registry)
            if cached is not None:
                return Ok(cached)

        exec_result = execute_with_attribution(
            route, registry, known, payloads, step_cache
        )
        if exec_result.is_err:
            failing_id, serr = exec_result.danger_err
            kind, detail = error_to_record_fields(serr)
            attempts.append(
                AttemptRecord(
                    excluded=tuple(sorted(excluded)),
                    route_digest=route.digest,
                    failed_solver_id=failing_id,
                    error_kind=kind,
                    error_detail=detail,
                )
            )
            if not policy.fallback:
                _log.warning("solve: step failed, fallback disabled: %r", serr)
                return Err(serr)
            failing_id = failing_id or (
                route.steps[-1].solver_id if route.steps else None
            )
            if failing_id is None:
                _log.warning(
                    "solve: step failed with no attributable solver id: %r", serr
                )
                return Err(SolveError.NoRouteRemaining(attempts=tuple(attempts)))
            excluded = excluded | {failing_id}
            _log.warning(
                "solve: rerouting after failure of %s: %r (exclusion set now %s)",
                failing_id,
                serr,
                sorted(excluded),
            )
            continue

        solution = exec_result.danger_ok
        realized = total_error(solution.value, solution.eps)
        if realized > eps_budget:
            budget_err = SolveError.BudgetExceeded(realized=realized, budget=eps_budget)
            kind, detail = error_to_record_fields(budget_err)
            attempts.append(
                AttemptRecord(
                    excluded=tuple(sorted(excluded)),
                    route_digest=route.digest,
                    failed_solver_id=route.steps[-1].solver_id if route.steps else None,
                    error_kind=kind,
                    error_detail=detail,
                )
            )
            if not policy.fallback:
                _log.warning(
                    "solve: budget exceeded, fallback disabled: %r", budget_err
                )
                return Err(budget_err)
            failing_id = route.steps[-1].solver_id
            excluded = excluded | {failing_id}
            _log.warning(
                "solve: rerouting after budget-exceeded on %s: realized=%s budget=%s",
                failing_id,
                realized,
                eps_budget,
            )
            continue

        solution = solution.model_copy(
            update={"attempts": tuple(attempts), "eps_budget": eps_budget}
        )
        if cache is not None and cacheable and cache_hit_key is not None:
            cache.put(cache_hit_key, solution)
        _log.info(
            "solve: succeeded target=%s eps=%s realized=%s attempts=%d cache_hit=%s",
            target,
            solution.eps,
            realized,
            len(attempts),
            solution.cache_hit,
        )
        return Ok(solution)
