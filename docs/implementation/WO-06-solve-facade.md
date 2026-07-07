# WO-06: Solve facade -- execute, reroute, cache

Status: todo
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
