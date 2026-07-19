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
import os
import tempfile
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from typani.result import Result

from feldspar.__about__ import __version__
from feldspar.core import Domain, Interval
from feldspar.logging_setup import get_logger
from feldspar.plan.execute import AttemptRecord, Solution, route_settings_digest
from feldspar.plan.route import Route, RouteStep
from feldspar.solve._models import Citation, ClaimSenses, SolverInfo
from feldspar.solve.digest import canonical_digest
from feldspar.solve.payload import PayloadRef

if TYPE_CHECKING:
    from feldspar.solve.registry import SolverRegistry

__all__ = [
    "PayloadStepCache",
    "SolveCache",
    "cache_key",
    "is_route_cacheable",
    "request_digest",
]

_log = get_logger(__name__)

_DEFAULT_CACHE_DIR = Path(".feldspar") / "cache"
_DEFAULT_STEP_CACHE_DIR = _DEFAULT_CACHE_DIR / "steps"


def _atomic_write_text(path: Path, text: str) -> None:
    """Writes `text` to `path` atomically: write to a sibling temp file
    in the same directory, then `os.replace()` it into place. A
    concurrent/interrupted writer to the same `path` can never leave a
    torn/interleaved blob behind -- readers see either the old content
    or the whole new content, never a partial write (M3, cycle-29
    audit)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _load_cache_json(path: Path) -> Optional[Any]:
    """Reads and parses a cache blob, degrading to `None` (a miss) on a
    corrupt/torn file instead of raising -- a malformed blob (e.g. from
    a killed writer predating the atomic-write fix, or external
    tampering) must never crash a solve that could simply recompute
    (M3, cycle-29 audit)."""
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning(
            "cache blob at %s is corrupt/unreadable, treating as miss: %s", path, exc
        )
        return None


# frob:doc docs/modules/plan.md#plan_cache
def request_digest(
    known: Mapping[str, Interval],
    tags: "frozenset[str] | set[str]",
    target: str,
    eps_budget: float,
    sense: "ClaimSenses | str",
    payloads: Optional[Mapping[str, PayloadRef]] = None,
) -> str:
    """`known` intervals + `tags` + `target` + `eps_budget` + `sense`
    (04-routing "Solve cache" cache-key components; `sense` folds in per
    audit A-3). A known payload port folds in as `port -> digest` only
    -- a payload in a digest IS its hash (09 sec. 4, FINV-12); `kind`
    is fixed by the port declaration and `origin` is provenance, so
    neither can change the answer and neither folds."""
    payload = {
        "known": {port: {"lo": iv.lo, "hi": iv.hi} for port, iv in known.items()},
        "tags": sorted(tags),
        "target": target,
        "eps_budget": eps_budget,
        "sense": ClaimSenses.coerce(sense).value,
        "payloads": {port: ref.digest for port, ref in (payloads or {}).items()},
    }
    return canonical_digest(payload)


# frob:doc docs/modules/plan.md#plan_cache
def cache_key(
    registry: "SolverRegistry",
    known: Mapping[str, Interval],
    tags: "frozenset[str] | set[str]",
    target: str,
    eps_budget: float,
    sense: "ClaimSenses | str",
    route: Route,
    payloads: Optional[Mapping[str, PayloadRef]] = None,
) -> str:
    """`blake3(registry_digest || request_digest || settings_digest ||
    feldspar_version)` (04-routing "Solve cache", AD-9) -- computed via
    ONE more `canonical_digest` fold over the same four components, since
    `canonical_digest` already gives byte-stable, order-independent
    hashing (AD-5) rather than reimplementing string concatenation."""
    reg_digest = registry.digest()
    req_digest = request_digest(known, tags, target, eps_budget, sense, payloads)
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


# frob:doc docs/modules/plan.md#plan_cache
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


def _citation_to_json(citation: Citation) -> Dict[str, Any]:
    return {"kind": citation.kind, "ref": citation.ref, "note": citation.note}


def _citation_from_json(data: Mapping[str, Any]) -> Citation:
    return Citation(kind=data["kind"], ref=data["ref"], note=data["note"])


# frob:doc docs/modules/plan.md#plan_cache
def solution_to_jsonable(solution: Solution) -> Dict[str, Any]:
    """Manual (not `canonical_digest`) JSON lowering of a `Solution` --
    round-trippable, unlike `canonical_digest`'s one-way fold -- so the
    cache can store AND reconstruct the exact `Interval`/`Domain`/
    `Route` objects `Solution` carries (PyO3 frozen classes have no
    pydantic JSON serializer, `feldspar.core._to_jsonable`'s doc note).
    Includes the WO-10 `explain()`/`to_dict()` rendering data
    (`step_eps`/`step_citations`/`step_declared_domain`/`eps_budget`)
    so a cache hit renders an identical justification report to a fresh
    solve (FINV-7: a hit must equal a recompute)."""
    return {
        "target": solution.target,
        "value": _interval_to_json(solution.value),
        "eps": solution.eps,
        "route": _route_to_json(solution.route),
        "settings_digest": solution.settings_digest,
        "solver_versions": dict(solution.solver_versions),
        "attempts": [_attempt_to_json(a) for a in solution.attempts],
        "cache_hit": solution.cache_hit,
        "step_eps": dict(solution.step_eps),
        "step_citations": {
            sid: [_citation_to_json(c) for c in cs]
            for sid, cs in solution.step_citations.items()
        },
        "step_declared_domain": {
            sid: _domain_to_json(d) for sid, d in solution.step_declared_domain.items()
        },
        "eps_budget": solution.eps_budget,
    }


# frob:doc docs/modules/plan.md#plan_cache
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
        step_eps=dict(data.get("step_eps", {})),
        step_citations={
            sid: tuple(_citation_from_json(c) for c in cs)
            for sid, cs in data.get("step_citations", {}).items()
        },
        step_declared_domain={
            sid: _domain_from_json(d)
            for sid, d in data.get("step_declared_domain", {}).items()
        },
        eps_budget=data.get("eps_budget"),
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


# frob:doc docs/modules/plan.md#plan_cache
class SolveCache:
    """A flat content-addressed store under `.feldspar/cache/` (AD-9):
    filename IS the cache key, so `get`/`put` are pure key-value
    lookups -- no index, no eviction (04-routing: nothing invalidates by
    time, because time is not an input)."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self._root = root if root is not None else _DEFAULT_CACHE_DIR

    def _path(self, key: str) -> Path:
        return self._root / f"{key}.json"

    # frob:doc docs/modules/plan.md#plan_cache
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
        data = _load_cache_json(path)
        if data is None:
            _log.info("cache miss: key=%s (corrupt blob)", key)
            return None
        solution = solution_from_jsonable(data)
        excluded = solution.attempts[-1].excluded if solution.attempts else ()
        if not _tools_still_consistent(route, registry, excluded):
            _log.info("cache miss: key=%s (tool presence changed)", key)
            return None
        _log.info("cache hit: key=%s", key)
        return solution.model_copy(update={"cache_hit": True})

    # frob:doc docs/modules/plan.md#plan_cache
    def put(self, key: str, solution: Solution) -> None:
        """Never called for a `deterministic=False`-containing route --
        `solve.py` guards via `is_route_cacheable` before reaching here
        (04-routing corollary), so this is a plain unconditional store."""
        path = self._path(key)
        payload = solution_to_jsonable(solution.model_copy(update={"cache_hit": False}))
        _atomic_write_text(path, json.dumps(payload, sort_keys=True))
        _log.info("cache store: key=%s", key)


#: One cached step result: `(hull, produced payload refs, realized eps)`.
StepEntry = Tuple[Dict[str, Interval], Dict[str, PayloadRef], float]


# frob:doc docs/modules/plan.md#plan_cache
class PayloadStepCache:
    """Per-step cache for payload-touching steps (WO-12; the 09 secs.
    3-4 per-rung/per-payload discipline, extending 04-routing "Solve
    cache"). Keyed on the step's identity tuple -- `solver_id`,
    `version`, `settings_digest`, the inflated scalar input box, and
    each payload input's DIGEST (a payload in a digest is its hash,
    FINV-12) -- plus `feldspar_version`; per FINV-2 that is everything
    a deterministic step's output is a function of, so the SolveCache
    freshness argument carries over verbatim. The point of the per-step
    grain: two SOLVES with different targets (static and modal) share
    the mesh step's entry, so one mesh is paid for once ever (09 sec.
    4 "one mesh feeds multiple solves").

    `hits`/`misses` counters are part of the contract (the WO-12
    acceptance proves same-mesh reuse BY cache-hit count), not debug
    conveniences."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self._root = root if root is not None else _DEFAULT_STEP_CACHE_DIR
        self.hits = 0
        self.misses = 0

    def _path(self, key: str) -> Path:
        return self._root / f"{key}.json"

    # frob:doc docs/modules/plan.md#plan_cache
    def key(
        self,
        info: SolverInfo,
        box: Mapping[str, Interval],
        payload_inputs: Mapping[str, PayloadRef],
    ) -> str:
        """The step-grain cache key; see the class docstring for the
        component-by-component freshness argument."""
        return canonical_digest(
            {
                "solver_id": info.solver_id,
                "version": info.version,
                "settings_digest": info.settings_digest,
                "box": {port: {"lo": iv.lo, "hi": iv.hi} for port, iv in box.items()},
                "payloads": {port: ref.digest for port, ref in payload_inputs.items()},
                "feldspar_version": __version__,
            }
        )

    # frob:doc docs/modules/plan.md#plan_cache
    def get(
        self,
        key: str,
        probe_tools: "Optional[Callable[[], Result[None, Any]]]" = None,
    ) -> Optional[StepEntry]:
        """A hit requires the blob AND (for tool-backed steps) a passing
        `probe_tools` -- A-5's argument applied per step: a recompute
        would fail `ToolMissing` when the tool has vanished, so a hit
        must not paper over that (the miss lets the real failure
        surface). Counts exactly one hit or miss per call."""
        path = self._path(key)
        if not path.exists():
            self.misses += 1
            _log.info("step cache miss: key=%s (no entry)", key)
            return None
        if probe_tools is not None and probe_tools().is_err:
            self.misses += 1
            _log.info("step cache miss: key=%s (tool vanished)", key)
            return None
        data = _load_cache_json(path)
        if data is None:
            self.misses += 1
            _log.info("step cache miss: key=%s (corrupt blob)", key)
            return None
        hull = {port: _interval_from_json(iv) for port, iv in data["hull"].items()}
        refs = {port: PayloadRef(**ref) for port, ref in data["payloads"].items()}
        self.hits += 1
        _log.info("step cache hit: key=%s", key)
        return hull, refs, data["step_eps"]

    # frob:doc docs/modules/plan.md#plan_cache
    def put(
        self,
        key: str,
        hull: Mapping[str, Interval],
        payloads: Mapping[str, PayloadRef],
        step_eps: float,
    ) -> None:
        """Executor-guarded like `SolveCache.put`: only deterministic,
        payload-touching steps reach here (execute.py's participation
        check), so this is a plain unconditional store."""
        path = self._path(key)
        entry = {
            "hull": {port: _interval_to_json(iv) for port, iv in hull.items()},
            "payloads": {port: ref.model_dump() for port, ref in payloads.items()},
            "step_eps": step_eps,
        }
        _atomic_write_text(path, json.dumps(entry, sort_keys=True))
        _log.info("step cache store: key=%s", key)
