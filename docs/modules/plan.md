# feldspar.plan

The planner/execution facade (WO-05, WO-06, WO-10, WO-15): route search
over the frozen registry, execution of a planned route through real
solvers, the content-addressed solve/payload-step caches, fallback
rerouting, parallel corner-sweep dispatch, and justification-report
rendering.

## plan_cache

<!-- frob:describes python/feldspar/plan/cache.py::request_digest -->
<!-- frob:describes python/feldspar/plan/cache.py::cache_key -->
<!-- frob:describes python/feldspar/plan/cache.py::is_route_cacheable -->
<!-- frob:describes python/feldspar/plan/cache.py::solution_to_jsonable -->
<!-- frob:describes python/feldspar/plan/cache.py::solution_from_jsonable -->
<!-- frob:describes python/feldspar/plan/cache.py::SolveCache -->
<!-- frob:describes python/feldspar/plan/cache.py::SolveCache.get -->
<!-- frob:describes python/feldspar/plan/cache.py::SolveCache.put -->
<!-- frob:describes python/feldspar/plan/cache.py::PayloadStepCache -->
<!-- frob:describes python/feldspar/plan/cache.py::PayloadStepCache.key -->
<!-- frob:describes python/feldspar/plan/cache.py::PayloadStepCache.get -->
<!-- frob:describes python/feldspar/plan/cache.py::PayloadStepCache.put -->

Content-addressed `Solution` cache under `.feldspar/cache/` (AD-9,
FINV-7): the cache key IS the tuple `(registry_digest, request_digest,
settings_digest, feldspar_version)` FINV-2 says a solve's answer is a
pure function of, so a stale hit would be a determinism violation.
`request_digest`/`cache_key` compute the digest components;
`is_route_cacheable` checks tool-presence freshness (the one
non-digest check, re-verified on every hit); `solution_to_jsonable`/
`solution_from_jsonable` round-trip a `Solution` through JSON.
`SolveCache` is the flat key-value store for whole-`Solution` results
(`get`/`put`); `PayloadStepCache` is the analogous per-payload-step
cache (`key`/`get`/`put`) that lets a repeated mesh/deck step reuse a
prior run instead of recomputing.

## plan_errors

<!-- frob:describes python/feldspar/plan/errors.py::PlanError -->
<!-- frob:describes python/feldspar/plan/errors.py::PlanError.InvalidBudget -->
<!-- frob:describes python/feldspar/plan/errors.py::PlanError.UnknownTarget -->
<!-- frob:describes python/feldspar/plan/errors.py::PlanError.NoApplicableSolver -->
<!-- frob:describes python/feldspar/plan/errors.py::PlanError.BudgetUnreachable -->
<!-- frob:describes python/feldspar/plan/errors.py::PlanError.CyclicPortEquivalence -->

`PlanError` is the planner's total error union (01-interfaces
`feldspar.plan`, WO-05, FINV-5), built on the shared `_TaggedError`
base (same idiom as `solve.errors.RegistryError`/`SolveError`, no
duplication). Its variants: `InvalidBudget`, `UnknownTarget`,
`NoApplicableSolver`, `BudgetUnreachable` (carries a payload),
`CyclicPortEquivalence`. Every variant is reachable via
`tests/unit/test_plan.py` (FINV-5).

## plan_execute

<!-- frob:describes python/feldspar/plan/execute.py::AttemptRecord -->
<!-- frob:describes python/feldspar/plan/execute.py::error_to_record_fields -->
<!-- frob:describes python/feldspar/plan/execute.py::Solution -->
<!-- frob:describes python/feldspar/plan/execute.py::Solution.explain -->
<!-- frob:describes python/feldspar/plan/execute.py::Solution.to_dict -->
<!-- frob:describes python/feldspar/plan/execute.py::route_settings_digest -->
<!-- frob:describes python/feldspar/plan/execute.py::execute -->
<!-- frob:describes python/feldspar/plan/execute.py::execute_with_attribution -->

The WO-06 execution facade (01-interfaces `feldspar.plan`, 04-routing
"Execution"): walks a planned `Route` in order, running the real
`SolveFn` corner sweep per step (replacing the planner's sum-surrogate
estimate with the exact sweep via the same core `corner_sweep`/
`inflate`/`total_error` routines, FINV-4). `AttemptRecord` logs one
solver attempt (success or failure); `error_to_record_fields` converts
an error into that record's fields. `Solution` is the executed result
(`explain()` renders the justification text, `to_dict()` the dict
form). `route_settings_digest` computes the settings component of the
cache key. `execute`/`execute_with_attribution` are the two entry
points (the latter also returns per-step attempt attribution).

## plan_parallel

<!-- frob:describes python/feldspar/plan/parallel.py::parallel_corner_sweep -->

`parallel_corner_sweep` (WO-15, 09 sec. 6): the parallel-dispatch
counterpart to `feldspar.core.corner_sweep`. Since a Python `SolveFn`
callback is GIL-bound, the only place additional cores help is
dispatching that callback across corners in Python (not Rust threading
inside `corner_sweep` itself); `thread_count <= 1` is the always-
present serial fallthrough (AD-10) running the identical enumerate/fold
code path. Determinism (FINV-9): corners are enumerated once in
`enumerate_corners` order and folded via `hull_from_results` in that
same order regardless of completion order, so the result is bit-
identical to the serial path.

## plan_policy

<!-- frob:describes python/feldspar/plan/policy.py::RoutePolicy -->

`RoutePolicy` (01-interfaces `feldspar.plan`, WO-06, 04-routing):
solve-time behavior toggles -- `fallback` (default reroute-on-failure),
`cache` (default ON content-addressed solve cache, AD-9), `threads`
(M5 stub; only `1` is valid in v1, anything else is a request-
validation error caught at construction).

## plan_report

<!-- frob:describes python/feldspar/plan/report.py::render_to_dict -->
<!-- frob:describes python/feldspar/plan/report.py::render_explain -->

`Solution.explain()`/`Solution.to_dict()` rendering (WO-10,
04-routing "Justification report"): pure rendering over fields already
carried by a `Solution` (`step_eps`/`step_citations`/
`step_declared_domain`/`eps_budget`), so this report can never
disagree with the evidence. `render_explain` and `render_to_dict`
build the same intermediate step-record list so the string and dict
forms can never drift against each other; every float in
`render_explain`'s text goes through `feldspar.core.format_f64` for a
byte-stable golden string.

## plan_route

<!-- frob:describes python/feldspar/plan/route.py::RouteStep -->
<!-- frob:describes python/feldspar/plan/route.py::Route -->
<!-- frob:describes python/feldspar/plan/route.py::plan -->

`RouteStep`, `Route`, `plan()` -- the planner search facade over
`feldspar-core::search` (01-interfaces `feldspar.plan`, WO-05,
04-routing). `plan()` marshals the frozen `SolverRegistry` into the
Rust-side search snapshot once per call and re-wraps the raising
`_feldspar.plan` primitive into a typani `Result[Route, PlanError]`
(same raw/checked marshalling pattern as `feldspar.core`). `Route` is
an ordered sequence of `RouteStep`s.

## plan_solve

<!-- frob:describes python/feldspar/plan/solve.py::_ExcludingRegistryView.digest -->
<!-- frob:describes python/feldspar/plan/solve.py::solve -->

`solve()` -- plan + execute + fallback reroute + solve cache
(01-interfaces `feldspar.plan`, WO-06, 04-routing "Fallback rerouting"/
"Solve cache"): the one entry point tying `plan()` and `execute()`/
`SolveCache` together into the caller-facing facade.
`_ExcludingRegistryView.digest` computes the registry digest for a
view of the registry with one solver excluded (the fallback-reroute
retry path).
