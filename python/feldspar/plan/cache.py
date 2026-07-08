from __future__ import annotations

"""Content-addressed `Solution` cache under `.feldspar/cache/` (AD-9,
04-routing "Solve cache", FINV-7). The freshness argument (stated once
in 04-routing) is that the cache key IS the tuple
`(registry_digest, request_digest, settings_digest, feldspar_version)`
FINV-2 says a solve's answer is a pure function of -- so a stale hit
would be a determinism violation, not a caching bug. The one non-digest
freshness check is tool presence (04-routing "Corollaries"), re-verified
symmetrically on every hit."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional, Sequence

from typani.result import Result

from feldspar.__about__ import __version__
from feldspar.core import Domain, Interval
from feldspar.logging import get_logger
from feldspar.plan.execute import AttemptRecord, Solution, route_settings_digest
from feldspar.plan.route import Route, RouteStep
from feldspar.solve._models import ClaimSenses
from feldspar.solve.digest import canonical_digest

if TYPE_CHECKING:
    from feldspar.solve.registry import SolverRegistry

__all__ = ["SolveCache", "cache_key", "is_route_cacheable", "request_digest"]

_log = get_logger(__name__)

_DEFAULT_CACHE_DIR = Path(".feldspar") / "cache"


def request_digest(
    known: Mapping[str, Interval],
    tags: "frozenset[str] | set[str]",
    target: str,
    eps_budget: float,
    sense: "ClaimSenses | str",
) -> str:
    """`known` intervals + `tags` + `target` + `eps_budget` + `sense`
    (04-routing "Solve cache" cache-key components; `sense` folds in per
    audit A-3)."""
    payload = {
        "known": {port: {"lo": iv.lo, "hi": iv.hi} for port, iv in known.items()},
        "tags": sorted(tags),
        "target": target,
        "eps_budget": eps_budget,
        "sense": ClaimSenses.coerce(sense).value,
    }
    return canonical_digest(payload)


def cache_key(
    registry: "SolverRegistry",
    known: Mapping[str, Interval],
    tags: "frozenset[str] | set[str]",
    target: str,
    eps_budget: float,
    sense: "ClaimSenses | str",
    route: Route,
) -> str:
    """`blake3(registry_digest || request_digest || settings_digest ||
    feldspar_version)` (04-routing "Solve cache", AD-9) -- computed via
    ONE more `canonical_digest` fold over the same four components, since
    `canonical_digest` already gives byte-stable, order-independent
    hashing (AD-5) rather than reimplementing string concatenation."""
    reg_digest = registry.digest()
    req_digest = request_digest(known, tags, target, eps_budget, sense)
    settings_dig = route_settings_digest(route, registry)
    key = canonical_digest(
        {
            "registry_digest": reg_digest,
            "request_digest": req_digest,
            "settings_digest": settings_dig,
            "feldspar_version": __version__,
        }
    )
    _log.info(
        "cache key components: registry_digest=%s request_digest=%s "
        "settings_digest=%s feldspar_version=%s -> key=%s",
        reg_digest,
        req_digest,
        settings_dig,
        __version__,
        key,
    )
    return key


def is_route_cacheable(route: Route, registry: "SolverRegistry") -> bool:
    """A route containing any `deterministic=False` step is NEVER cached
    (04-routing "Solve cache" corollaries)."""
    solver_map = {info.solver_id: info for info, _fn in registry}
    return all(solver_map[step.solver_id].deterministic for step in route.steps)


def _interval_to_json(iv: Interval) -> Dict[str, float]:
    return {"lo": iv.lo, "hi": iv.hi}


def _interval_from_json(data: Mapping[str, float]) -> Interval:
    return Interval(data["lo"], data["hi"])


def _domain_to_json(domain: Domain) -> Dict[str, Any]:
    return {
        "box": {port: _interval_to_json(iv) for port, iv in domain.box.items()},
        "tags": sorted(domain.tags),
    }


def _domain_from_json(data: Mapping[str, Any]) -> Domain:
    return Domain(
        box={port: _interval_from_json(iv) for port, iv in data["box"].items()},
        tags=set(data["tags"]),
    )


def _route_step_to_json(step: RouteStep) -> Dict[str, Any]:
    return {
        "solver_id": step.solver_id,
        "realized_domain": _domain_to_json(step.realized_domain),
        "predicted_eps": step.predicted_eps,
        "cost": step.cost,
    }


def _route_step_from_json(data: Mapping[str, Any]) -> RouteStep:
    return RouteStep(
        solver_id=data["solver_id"],
        realized_domain=_domain_from_json(data["realized_domain"]),
        predicted_eps=data["predicted_eps"],
        cost=data["cost"],
    )


def _route_to_json(route: Route) -> Dict[str, Any]:
    return {
        "target": route.target,
        "steps": [_route_step_to_json(s) for s in route.steps],
        "predicted_eps": route.predicted_eps,
        "total_cost": route.total_cost,
        "digest": route.digest,
    }


def _route_from_json(data: Mapping[str, Any]) -> Route:
    return Route(
        target=data["target"],
        steps=tuple(_route_step_from_json(s) for s in data["steps"]),
        predicted_eps=data["predicted_eps"],
        total_cost=data["total_cost"],
        digest=data["digest"],
    )


def _attempt_to_json(attempt: AttemptRecord) -> Dict[str, Any]:
    return {
        "excluded": list(attempt.excluded),
        "route_digest": attempt.route_digest,
        "failed_solver_id": attempt.failed_solver_id,
        "error_kind": attempt.error_kind,
        "error_detail": dict(attempt.error_detail),
    }


def _attempt_from_json(data: Mapping[str, Any]) -> AttemptRecord:
    return AttemptRecord(
        excluded=tuple(data["excluded"]),
        route_digest=data["route_digest"],
        failed_solver_id=data["failed_solver_id"],
        error_kind=data["error_kind"],
        error_detail=data["error_detail"],
    )


def solution_to_jsonable(solution: Solution) -> Dict[str, Any]:
    """Manual (not `canonical_digest`) JSON lowering of a `Solution` --
    round-trippable, unlike `canonical_digest`'s one-way fold -- so the
    cache can store AND reconstruct the exact `Interval`/`Domain`/
    `Route` objects `Solution` carries (PyO3 frozen classes have no
    pydantic JSON serializer, `feldspar.core._to_jsonable`'s doc note)."""
    return {
        "target": solution.target,
        "value": _interval_to_json(solution.value),
        "eps": solution.eps,
        "route": _route_to_json(solution.route),
        "settings_digest": solution.settings_digest,
        "solver_versions": dict(solution.solver_versions),
        "attempts": [_attempt_to_json(a) for a in solution.attempts],
        "cache_hit": solution.cache_hit,
    }


def solution_from_jsonable(data: Mapping[str, Any]) -> Solution:
    return Solution(
        target=data["target"],
        value=_interval_from_json(data["value"]),
        eps=data["eps"],
        route=_route_from_json(data["route"]),
        settings_digest=data["settings_digest"],
        solver_versions=dict(data["solver_versions"]),
        attempts=tuple(_attempt_from_json(a) for a in data["attempts"]),
        cache_hit=data["cache_hit"],
    )


def _tools_still_consistent(
    route: Route, registry: "SolverRegistry", excluded: Sequence[str]
) -> bool:
    """A-5's symmetric tool-presence recheck. Tool-BACKED solvers (WO-08+)
    opt in by attaching an optional `probe_tools() -> Result[None,
    SolveError]` attribute to their `SolveFn` (a WO-06-era extension
    point -- no `tool` concept exists on the frozen `SolverInfo` yet,
    03/WO-08); a plain (non-tool) `SolveFn` has none and is always
    treated as present. Returns `False` (miss) if a tool the cached
    route actually used has since vanished, OR a tool whose absence
    caused one of the cached `excluded` exclusions has since appeared
    (a fresh solve would now take a better route)."""
    solver_map = {info.solver_id: fn for info, fn in registry}

    for step in route.steps:
        fn = solver_map.get(step.solver_id)
        probe = getattr(fn, "probe_tools", None)
        if probe is not None:
            result: "Result[None, Any]" = probe()
            if result.is_err:
                _log.info(
                    "cache recheck miss: tool used by %s has vanished", step.solver_id
                )
                return False

    for solver_id in excluded:
        fn = solver_map.get(solver_id)
        probe = getattr(fn, "probe_tools", None)
        if probe is not None:
            result = probe()
            if result.is_ok:
                _log.info(
                    "cache recheck miss: tool for previously-excluded %s "
                    "is present again",
                    solver_id,
                )
                return False

    return True


class SolveCache:
    """A flat content-addressed store under `.feldspar/cache/` (AD-9):
    filename IS the cache key, so `get`/`put` are pure key-value
    lookups -- no index, no eviction (04-routing: nothing invalidates by
    time, because time is not an input)."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self._root = root if root is not None else _DEFAULT_CACHE_DIR

    def _path(self, key: str) -> Path:
        return self._root / f"{key}.json"

    def get(
        self, key: str, route: Route, registry: "SolverRegistry"
    ) -> Optional[Solution]:
        """Cache hit only if the blob exists AND the A-5 tool-presence
        recheck passes; a stale-tool blob is treated as a miss (never
        deleted -- a future run whose tools match again is still valid,
        FINV-7)."""
        path = self._path(key)
        if not path.exists():
            _log.info("cache miss: key=%s (no entry)", key)
            return None
        data = json.loads(path.read_text())
        solution = solution_from_jsonable(data)
        excluded = solution.attempts[-1].excluded if solution.attempts else ()
        if not _tools_still_consistent(route, registry, excluded):
            _log.info("cache miss: key=%s (tool presence changed)", key)
            return None
        _log.info("cache hit: key=%s", key)
        return solution.model_copy(update={"cache_hit": True})

    def put(self, key: str, solution: Solution) -> None:
        """Never called for a `deterministic=False`-containing route --
        `solve.py` guards via `is_route_cacheable` before reaching here
        (04-routing corollary), so this is a plain unconditional store."""
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = solution_to_jsonable(solution.model_copy(update={"cache_hit": False}))
        path.write_text(json.dumps(payload, sort_keys=True))
        _log.info("cache store: key=%s", key)
