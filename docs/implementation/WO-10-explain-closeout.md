# WO-10: explain() and M1 close-out

Status: done
Depends: WO-06, WO-09
Language: Python (`feldspar/plan/report.py`)
Spec: 04 (justification report), 03 (citations), 09 sec. 8 M1

## Goal

The justification report, and the milestone gate: everything M1
promised, verified and documented.

## Deliverables

- `Solution.explain() -> str` (and `to_dict()` for machine use):
  per-step solver, method citations, domain admission (box + tags +
  actual hull), propagated interval, charged eps, running
  accumulation; route-level cost, eps-vs-budget decomposition,
  reroute trail, cache provenance. Pure rendering of carried data --
  a test asserts no recomputation (mock solvers, no calls during
  explain).
- Deterministic output (stable ordering/formatting; golden test).
- Close-out sweep: TODO.md ledger driven to zero for WO-01..10 or
  cuts recorded per house rule; every FINV row's enforcement exists
  and is cited from the test suite; docs/ reconciled with any drift
  (same-change rule); README quickstart (install, register, solve,
  explain) written against the real API.
- File the M2+ WO stubs decision: confirm with owner before
  drafting WO-11+ (scope gate, 09 sec. 8).

## Acceptance

- `explain()` golden for the toy registry and for a real FEA solve
  (fea-marked); FINV table audit checklist committed; `make check`,
  CI matrix, and the regolith conformance job all green on the same
  commit -- that commit closes regolith WO-27 from feldspar's side.

## Closing report (2026-07-08)

- `Solution.explain()`/`to_dict()` land in `python/feldspar/plan/
  report.py`, called as zero-arg methods on `Solution`
  (01-interfaces). `Solution` (WO-06) is extended with `step_eps`/
  `step_citations`/`step_declared_domain`/`eps_budget` -- captured at
  execution time from the frozen registry's declared metadata, never
  from a `SolveFn` call -- so the report is provably pure rendering
  (`tests/unit/test_report.py::test_explain_makes_no_solver_calls`).
  This is a small, additive extension of WO-06's carried data, not a
  new API; the cache's JSON round-trip (`plan/cache.py`) was updated
  in the same change so a cache hit's report is identical to a fresh
  solve's.
- `RouteStep.realized_domain` is the PLANNER's inflated-hull ESTIMATE
  at plan time (04-routing "Algorithm (v1)"), not the executor's exact
  corner-swept input hull for that step -- the two can differ for any
  step past the first. `explain()`/`to_dict()` render this honestly
  (labeled, not silently treated as the executed hull); `Solution`
  carries no separate "actual executed input hull per step" field to
  render instead. Flagged as a pre-existing WO-06 data-shape gap, not
  something WO-10 papered over.
- Toy-registry golden: `tests/unit/test_report.py` -- executed,
  passing, byte-exact string comparison plus a twice-run stability
  test.
- Real-FEA golden: `tests/integration/test_report_fea.py`, `fea`-
  marked. Written correctly per spec (registers `fea.static_deflection
  .cantilever`, checks every report section renders, checks the cache-
  hit path) but NOT EXECUTED in this sandbox -- no `gmsh`/`ccx`
  binaries available, the same situation `test_fea_pipeline.py`
  (WO-08/WO-09) documented. This is written-but-unverified-by-
  execution, not a fabricated pass.
- FINV audit: `docs/implementation/FINV-audit.md`. FINV-1..8/10/11
  each have an inline test citation (two missing citations were added
  in this change: `test_plan.py::test_plan_twice_yields_identical_
  route_digest` for FINV-1, `test_solve_cache.py::test_solve_twice_
  identical_digest_second_served_from_cache` for FINV-7).
  FINV-9 (parallel==serial) and FINV-12 (payload content-addressing)
  are recorded as explicit scope cuts: neither has ANY M1 code to
  enforce yet (M5 and M2 respectively, 09 sec. 8) -- not a WO-10 gap.
- README quickstart added and RUN against the real API before being
  committed (verbatim script, `/tmp` transcript not included but the
  script in the README is the exact one executed).
- `make check` verified stage-by-stage: `ruff check` clean, import-
  linter contract kept, `pytest -m "not regolith and not fea"` green
  (139 passed), `cargo fmt --check`/`cargo clippy -D warnings` clean.
  `uv run ty check python/` reports 2 diagnostics in `feldspar/
  _compat.py` (an unresolved `tomli` import + a stale `ty: ignore`) --
  confirmed PRE-EXISTING via `git stash -u` against the tree before
  this WO's changes, so `make check`'s aggregate target does not go
  green end-to-end, but nothing in WO-10's diff caused or touches
  that failure.
- NOT verified from this sandbox, and NOT claimed as met: the CI
  matrix running green on this exact commit (no CI runner available
  here). `tests/regolith/` (regolith-marked, `pytest -m regolith`) WAS
  run locally and passes (24 passed) -- the editable `../lithos`
  install is present -- but that is a local run, not the CI-matrix or
  "regolith conformance job on the same commit" acceptance clause
  itself, which requires infrastructure this sandbox does not have.
- M2+ WO stubs decision: `WO-11-symbolic-core.md` already carries an
  owner decision (2026-07-08) predating this close-out; this WO's
  scope-gate clause is satisfied by that existing decision. WO-11's
  files were not touched by this WO.
