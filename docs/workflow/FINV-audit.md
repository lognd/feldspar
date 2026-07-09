# FINV audit checklist (WO-10 close-out)

Cross-reference: every FINV row in the canonical table
(`00-architecture.md` sec. with the FINV-1..12 table) against the test
(or explicit test-suite reason for absence) that enforces it. WO-10's
acceptance requires this list exist and be findable; it is re-derived,
not re-defined -- the table in `00-architecture.md` remains the one
normative source.

| FINV | Enforced by |
|------|-------------|
| FINV-1 (determinism: byte-identical Route/Solution digests) | `tests/unit/test_plan.py::test_plan_twice_yields_identical_route_digest`, `tests/unit/test_registry.py::test_registry_digest_stable_and_folds_every_solver`, `tests/unit/test_report.py::test_explain_golden_is_stable_across_two_runs` (WO-10: explain()/to_dict() output is also byte-stable, not just the digests it renders) |
| FINV-2 (settings-digest honesty) | `tests/unit/test_fea_solver.py` (`_fold_settings_digest` field-by-field fold tests) |
| FINV-3 (regolith optional/one-way) | `tests/regolith/` (`regolith`-marked), import-linter contract `regolith imports confined to feldspar.pack` (`pyproject.toml`, checked by `make check`'s `import-lint` stage) |
| FINV-4 (one error-math home, eps-inflation not summation) | `tests/unit/test_propagation.py` (gain-counterexample, hull/dedup properties); `feldspar.plan.report` reuses the SAME `total_error`/`inflate` core symbols rather than re-deriving eps math (no separate test needed, grep-able single-symbol argument per the table's own enforcement column) |
| FINV-5 (totality of error unions) | `tests/unit/test_registry.py::test_*` (RegistryError exhaustiveness), `tests/unit/test_plan.py` (every PlanError variant reachable), `tests/unit/test_registry.py` (SolveError exhaustiveness, see file docstring) |
| FINV-6 (citation floor) | `tests/unit/test_registry.py` (empty/calibration-only citation rejection), `tests/unit/test_calib.py` (calibration ledger) |
| FINV-7 (cache freshness: hit == recompute, symmetric tool-presence) | `tests/unit/test_solve_cache.py::test_solve_twice_identical_digest_second_served_from_cache`, `::test_reroute_on_step_failure_deterministic_attempt_trail`, `::test_deterministic_false_route_never_cached`; WO-10 extends the cached `Solution` JSON shape (`plan/cache.py::solution_to_jsonable`) to round-trip `step_eps`/`step_citations`/`step_declared_domain`/`eps_budget` so a cache hit's `explain()` is identical to a fresh solve's -- covered by the same twice-run test (both calls compare full `Solution` equality, which now includes those fields) |
| FINV-8 (tier-blind dispatch) | `tests/unit/test_plan.py::test_finv8_tier_blindness_permuted_tiers_yield_identical_route` |
| FINV-9 (parallel == serial) | NOT YET ENFORCEABLE: parallel execution is M5 scope (09 sec. 8), not implemented in M1. `RoutePolicy.threads` exists as a field (WO-06) but the executor is serial-only; there is nothing to run "both paths" against yet. Recorded as a scope cut here, not silently skipped -- re-check when M5 lands. |
| FINV-10 (boundary conversion only) | `tests/unit/` pack converter round-trip tests (`pack/converters.py` callers), import-linter contract (same as FINV-3) |
| FINV-11 (coherent-SI storage) | `tests/unit/test_core.py` (UnitSystem round-trips; no convert-on-stored-value API surface to begin with) |
| FINV-12 (payload content-addressing) | NOT YET APPLICABLE: payload ports land with M2 (09 sec. 8); the table itself notes "enters table then." No M1 code claims this invariant yet. |

## Scope cuts recorded here (not silently dropped)

- FINV-9: cannot be test-enforced until M5's parallel executor exists.
- FINV-12: cannot be test-enforced until M2's payload ports exist.

Both are pre-existing, correctly-deferred M1 scope boundaries (09 sec.
8), not WO-10 gaps -- listed here only so the audit table has an
explicit answer for every FINV number rather than a silent omission.
