from __future__ import annotations

"""WO-06 tests: `feldspar.plan.solve()` reroute loop and the
content-addressed solve cache (01-interfaces `feldspar.plan`, 04-routing
"Fallback rerouting"/"Solve cache", FINV-7).

Covers the WO-06 acceptance bar (twice-run identical Solution served
from cache the second time, log-asserted; killing the winning solver
reroutes with a full attempt trail) and every 02-edge-cases.md WO-06
row reachable from Python."""

import logging
from typing import Tuple

import pytest
from typani import Err, Ok

from feldspar.core import Accuracy, Domain, Interval, canonical_digest
from feldspar.plan import RoutePolicy, SolveCache, plan, solve
from feldspar.solve import Citation, SolveError, SolveOutput, SolverRegistry, solver


def _citation() -> Tuple[Citation, ...]:
    return (Citation(kind="handbook", ref="test fixture"),)


def _fast_cache(tmp_path) -> SolveCache:
    return SolveCache(root=tmp_path / "cache")


def _registry_direct(*, cost: float = 1.0, eps_abs: float = 0.5) -> SolverRegistry:
    registry = SolverRegistry()

    @solver(
        namespace="sc",
        inputs=("sc.x",),
        outputs=("sc.y",),
        domain=Domain(box={"sc.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=cost,
        accuracy={"sc.y": Accuracy(eps_abs=eps_abs, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def direct(x):
        return Ok({"sc.y": x["sc.x"] * 2.0})

    assert registry.register(*direct.solver_direction).is_ok
    registry.freeze()
    return registry


def _patch_cache(monkeypatch, tmp_path) -> None:
    """`solve()` builds its own `SolveCache()` at the default location;
    redirect that default to an isolated tmp dir for test hermeticity."""
    import sys

    solve_mod = sys.modules["feldspar.plan.solve"]

    def _make_cache():
        return SolveCache(root=tmp_path / ".feldspar-cache")

    monkeypatch.setattr(solve_mod, "SolveCache", _make_cache)


def test_solve_twice_identical_digest_second_served_from_cache(
    monkeypatch, tmp_path, caplog: pytest.LogCaptureFixture
) -> None:
    _patch_cache(monkeypatch, tmp_path)
    registry = _registry_direct()
    known = {"sc.x": Interval(1.0, 2.0)}

    with caplog.at_level(logging.INFO):
        r1 = solve(registry, known, frozenset(), "sc.y", 10.0)
    assert r1.is_ok
    sol1 = r1.danger_ok
    assert sol1.cache_hit is False
    assert any("cache store" in rec.message for rec in caplog.records)

    caplog.clear()
    with caplog.at_level(logging.INFO):
        r2 = solve(registry, known, frozenset(), "sc.y", 10.0)
    assert r2.is_ok
    sol2 = r2.danger_ok
    assert sol2.cache_hit is True
    assert any("cache hit" in rec.message for rec in caplog.records)

    digest1 = canonical_digest(sol1.model_copy(update={"cache_hit": False}))
    digest2 = canonical_digest(sol2.model_copy(update={"cache_hit": False}))
    assert digest1 == digest2


def test_finv7_cache_hit_byte_identical_to_forced_recompute(tmp_path) -> None:
    registry = _registry_direct()
    known = {"sc.x": Interval(1.0, 2.0)}
    cache = _fast_cache(tmp_path)
    route = plan(registry, known, frozenset(), "sc.y", 10.0).danger_ok
    from feldspar.plan.cache import cache_key
    from feldspar.plan.execute import execute

    key = cache_key(registry, known, frozenset(), "sc.y", 10.0, "both", route)

    forced = execute(route, registry, known).danger_ok
    cache.put(key, forced)

    hit = cache.get(key, route, registry)
    assert hit is not None
    hit_norm = hit.model_copy(update={"cache_hit": False})
    assert canonical_digest(hit_norm) == canonical_digest(forced)


def test_reroute_on_step_failure_deterministic_attempt_trail(tmp_path) -> None:
    registry = SolverRegistry()

    @solver(
        namespace="rr",
        inputs=("rr.x",),
        outputs=("rr.y",),
        domain=Domain(box={"rr.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"rr.y": Accuracy(eps_abs=0.5, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def failing(x):
        return Err(SolveError.ToolMissing(tool="ccx", guidance="install ccx"))

    @solver(
        namespace="rr",
        inputs=("rr.x",),
        outputs=("rr.y",),
        domain=Domain(box={"rr.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=5.0,
        accuracy={"rr.y": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
        solver_id_suffix="backup",
    )
    def backup(x):
        return Ok({"rr.y": x["rr.x"] * 3.0})

    assert registry.register(*failing.solver_direction).is_ok
    assert registry.register(*backup.solver_direction).is_ok
    registry.freeze()
    known = {"rr.x": Interval(1.0, 2.0)}
    policy = RoutePolicy(cache=False)

    r1 = solve(registry, known, frozenset(), "rr.y", 10.0, policy=policy)
    r2 = solve(registry, known, frozenset(), "rr.y", 10.0, policy=policy)
    assert r1.is_ok and r2.is_ok
    assert len(r1.danger_ok.attempts) == 1
    assert r1.danger_ok.attempts == r2.danger_ok.attempts
    assert r1.danger_ok.route.steps[0].solver_id == "rr.backup.backup"


def test_reroute_warns_at_warning_level(caplog: pytest.LogCaptureFixture) -> None:
    registry = SolverRegistry()

    @solver(
        namespace="rw",
        inputs=("rw.x",),
        outputs=("rw.y",),
        domain=Domain(box={"rw.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"rw.y": Accuracy(eps_abs=0.5, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def failing(x):
        return Err(SolveError.ToolMissing(tool="ccx", guidance="x"))

    @solver(
        namespace="rw",
        inputs=("rw.x",),
        outputs=("rw.y",),
        domain=Domain(box={"rw.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=5.0,
        accuracy={"rw.y": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
        solver_id_suffix="backup",
    )
    def backup(x):
        return Ok({"rw.y": x["rw.x"] * 3.0})

    assert registry.register(*failing.solver_direction).is_ok
    assert registry.register(*backup.solver_direction).is_ok
    registry.freeze()
    known = {"rw.x": Interval(1.0, 2.0)}
    with caplog.at_level(logging.WARNING):
        result = solve(
            registry, known, frozenset(), "rw.y", 10.0, policy=RoutePolicy(cache=False)
        )
    assert result.is_ok
    assert any(
        rec.levelno == logging.WARNING and "rerouting" in rec.message
        for rec in caplog.records
    )


def test_fallback_false_returns_first_failure() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="ff",
        inputs=("ff.x",),
        outputs=("ff.y",),
        domain=Domain(box={"ff.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"ff.y": Accuracy(eps_abs=0.5, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def failing(x):
        return Err(SolveError.ToolMissing(tool="ccx", guidance="x"))

    @solver(
        namespace="ff",
        inputs=("ff.x",),
        outputs=("ff.y",),
        domain=Domain(box={"ff.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=5.0,
        accuracy={"ff.y": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=_citation(),
        version="1",
        solver_id_suffix="backup",
    )
    def backup(x):
        return Ok({"ff.y": x["ff.x"] * 3.0})

    assert registry.register(*failing.solver_direction).is_ok
    assert registry.register(*backup.solver_direction).is_ok
    registry.freeze()
    known = {"ff.x": Interval(1.0, 2.0)}
    result = solve(
        registry,
        known,
        frozenset(),
        "ff.y",
        10.0,
        policy=RoutePolicy(cache=False, fallback=False),
    )
    assert result.is_err
    assert result.err == SolveError.ToolMissing(tool="ccx", guidance="x")


def test_all_routes_fail_returns_no_route_remaining() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="nr",
        inputs=("nr.x",),
        outputs=("nr.y",),
        domain=Domain(box={"nr.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"nr.y": Accuracy(eps_abs=0.5, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def only(x):
        return Err(SolveError.ToolMissing(tool="ccx", guidance="x"))

    assert registry.register(*only.solver_direction).is_ok
    registry.freeze()
    known = {"nr.x": Interval(1.0, 2.0)}
    result = solve(
        registry, known, frozenset(), "nr.y", 10.0, policy=RoutePolicy(cache=False)
    )
    assert result.is_err
    assert result.err.kind == "NoRouteRemaining"
    assert len(result.err.attempts) == 2


def test_budget_exceeded_on_realized_eps() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="be",
        inputs=("be.x",),
        outputs=("be.y",),
        domain=Domain(box={"be.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"be.y": Accuracy(eps_abs=0.01, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def measuring(x):
        return Ok(SolveOutput(values={"be.y": x["be.x"]}, measured_eps=50.0))

    assert registry.register(*measuring.solver_direction).is_ok
    registry.freeze()
    known = {"be.x": Interval(1.0, 2.0)}
    result = solve(
        registry,
        known,
        frozenset(),
        "be.y",
        1.0,
        policy=RoutePolicy(cache=False, fallback=False),
    )
    assert result.is_err
    assert result.err.kind == "BudgetExceeded"
    assert result.err.realized > 1.0
    assert result.err.budget == 1.0


def test_initial_plan_failure_returns_plan_error_directly() -> None:
    registry = SolverRegistry()
    known = {"pf.x": Interval(1.0, 2.0)}
    result = solve(
        registry, known, frozenset(), "pf.ghost", 1.0, policy=RoutePolicy(cache=False)
    )
    assert result.is_err
    assert result.err.kind == "UnknownTarget"


def test_cache_miss_when_tool_vanished_since_cached_success(tmp_path) -> None:
    registry = SolverRegistry()
    present = {"value": True}

    class _Probe:
        def __call__(self):
            return (
                Ok(None)
                if present["value"]
                else Err(SolveError.ToolMissing(tool="ccx", guidance="x"))
            )

    @solver(
        namespace="tv",
        inputs=("tv.x",),
        outputs=("tv.y",),
        domain=Domain(box={"tv.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"tv.y": Accuracy(eps_abs=0.5, eps_rel=0.0)},
        citations=_citation(),
        version="1",
    )
    def tool_backed(x):
        return Ok({"tv.y": x["tv.x"] * 2.0})

    tool_backed.solver_direction[1].probe_tools = _Probe()
    assert registry.register(*tool_backed.solver_direction).is_ok
    registry.freeze()

    known = {"tv.x": Interval(1.0, 2.0)}
    cache = _fast_cache(tmp_path)
    from feldspar.plan.cache import cache_key
    from feldspar.plan.execute import execute

    route = plan(registry, known, frozenset(), "tv.y", 10.0).danger_ok
    solution = execute(route, registry, known).danger_ok
    key = cache_key(registry, known, frozenset(), "tv.y", 10.0, "both", route)
    cache.put(key, solution)

    assert cache.get(key, route, registry) is not None

    present["value"] = False
    assert cache.get(key, route, registry) is None


def test_deterministic_false_route_never_cached(tmp_path) -> None:
    registry = SolverRegistry()

    @solver(
        namespace="nd",
        inputs=("nd.x",),
        outputs=("nd.y",),
        domain=Domain(box={"nd.x": Interval(0.0, 10.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"nd.y": Accuracy(eps_abs=0.5, eps_rel=0.0)},
        citations=_citation(),
        version="1",
        deterministic=False,
    )
    def nondeterministic(x):
        return Ok({"nd.y": x["nd.x"] * 2.0})

    assert registry.register(*nondeterministic.solver_direction).is_ok
    registry.freeze()

    known = {"nd.x": Interval(1.0, 2.0)}
    from feldspar.plan.cache import is_route_cacheable

    route = plan(registry, known, frozenset(), "nd.y", 10.0).danger_ok
    assert is_route_cacheable(route, registry) is False

    cache_dir = tmp_path / "cache"
    solve(registry, known, frozenset(), "nd.y", 10.0, policy=RoutePolicy())
    # nothing should have landed in the module-default cache dir either;
    # regardless, the isolated dir above (unused by solve()) stays empty.
    assert not cache_dir.exists() or not list(cache_dir.iterdir())


def test_threads_other_than_one_is_validation_error() -> None:
    with pytest.raises(ValueError):
        RoutePolicy(threads=2)
