# WO-06: Solve facade -- execute, reroute, cache

Status: done
Depends: WO-05
Language: Python (`feldspar/plan/`), core sweep via WO-04
Spec: 04 (execution, fallback, cache, determinism), FINV-1/5/7, AD-9

## Goal

`execute(route, known)` and `solve(...)` with default fallback
rerouting and the content-addressed solve cache.

## Deliverables

- `execute`: walk route in order; per-step exact corner sweep via
  the WO-04 core symbols; hull outputs; charge realized eps
  (measured replaces declared when the solver reports one); fold
  settings digests and solver versions into `Solution` per 04.
- Post-execution budget re-check -> `BudgetExceeded` with numbers.
- `solve` = plan + execute + reroute loop per 04: exclusion set,
  deterministic replan, full attempt trail on final failure;
  `RoutePolicy(fallback=..., cache=..., threads=...)` frozen model
  (threads honored serially until M5 -- value 1 only, validated).
- Solve cache per 04/AD-9: key from (registry digest, request
  digest, settings digest, feldspar version); `.feldspar/cache/`
  CAS; tool-presence re-verification on hit for tool-backed steps;
  never caches `deterministic=False` steps' routes.
- Logging: reroutes (warn), every cache hit/miss with key components
  (info), per-step eps charges (debug).
- Tests: FINV-7 property (hit byte-equals forced recompute); reroute
  determinism (inject failing solver, same trail twice); fallback=
  False returns first failure; each SolveError variant.

## Acceptance

- Toy registry end-to-end: solve twice -> identical Solution digest,
  second run served from cache (log-asserted); kill the winning
  solver -> rerouted result with trail; `make check` green.

## Implementation notes (landed)

- `python/feldspar/plan/execute.py`: `AttemptRecord` (plain JSON-safe
  kind/detail fields, never a live `PlanError`/`SolveError` object, so
  `Solution` digests cleanly through `canonical_digest`, AD-5),
  `Solution`, `route_settings_digest()` (the ONE settings-fold shared
  by `execute()`'s `Solution.settings_digest` and `cache.py`'s cache
  key, no duplication), and `execute()`. The real per-step corner
  sweep replaces WO-05's sum surrogate (FINV-4: same `corner_sweep`/
  `inflate`/`total_error` core routines the planner used to estimate);
  a step's realized eps is `max(measured_eps ...)` when the solver
  reports one, else `max(Accuracy.worst_over(hull) for output)` -- the
  SAME `worst_over` the planner's estimate used. `execute()`'s public
  signature returns `Result[Solution, SolveError]` exactly per
  01-interfaces; internally it wraps `execute_with_attribution()`,
  which ALSO reports the failing step's `solver_id` -- `solve.py`'s
  reroute loop needs that for its exclusion set, and inventing a
  second executor to recover it would duplicate the whole walk.
- `python/feldspar/plan/solve.py`: the reroute loop. Exclusion is
  expressed as `_ExcludingRegistryView` (an `__iter__`-only filter
  over the same frozen `SolverRegistry`, never a mutation) fed back
  into WO-05's `plan()` each iteration -- deterministic because
  `plan()` already is. Every attempt (plan failure, step failure,
  post-execution budget bust) appends one `AttemptRecord`; on final
  failure the trail rides in `SolveError.NoRouteRemaining(attempts)`,
  on eventual success it rides in the returned `Solution.attempts` --
  so a reroute is reconstructable from the return value alone, not
  just the logs (though every reroute is also logged at WARNING).
  Post-execution budget re-check uses `total_error(value, eps)` (the
  same WO-04 routine `search.rs` uses for the planner's estimate).
- `python/feldspar/plan/cache.py`: a flat content-addressed store
  under `.feldspar/cache/<key>.json` (AD-9); `cache_key()` folds
  `(registry.digest(), request_digest, route_settings_digest,
  feldspar.__about__.__version__)` through ONE more
  `canonical_digest` call (byte-stable, order-independent, AD-5) --
  matching 04-routing's freshness argument exactly. Stored payload is
  a hand-written JSON encode/decode of `Solution` (manual, not
  `canonical_digest`'s one-way fold), since `Interval`/`Domain` are
  PyO3 frozen classes with no pydantic JSON serializer; round-tripped
  via their direct constructors. `is_route_cacheable()` guards every
  cache read/write against `deterministic=False` steps. Tool-presence
  re-verification (audit A-5's symmetric recheck) is implemented as an
  extension point: a `SolveFn` MAY carry an optional `probe_tools() ->
  Result[None, SolveError]` attribute (no `tool` concept exists on the
  frozen `SolverInfo` yet -- that lands with WO-08); a plain solver
  without one is always treated as present. `SolveCache.get()` returns
  `None` (miss) if any tool the cached route used has since vanished,
  or any tool whose absence caused a cached exclusion has since
  reappeared.
- `python/feldspar/plan/policy.py`: `RoutePolicy` (frozen pydantic
  model); `threads` is field-validated to exactly `1` in v1 (M5 opens
  it, 09 sec. 6).
- Tests: `tests/unit/test_execute.py` (declared-vs-measured eps
  charging, zero-step route, NaN/missing-output/invalid-measurement/
  solver-Err-passthrough) and `tests/unit/test_solve_cache.py`
  (twice-run identical-digest-second-from-cache acceptance test,
  log-asserted; FINV-7 cache-hit-equals-forced-recompute; reroute
  determinism; reroute-logs-at-warning; `fallback=False`; all-routes-
  fail -> `NoRouteRemaining`; `BudgetExceeded`; initial-plan-failure
  passthrough; tool-vanished cache miss; `deterministic=False` never
  cached; `threads != 1` validation).
