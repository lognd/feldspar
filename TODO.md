# feldspar M1 ledger

Every WO flips its entries here in the same change (docs/implementation/README.md
ground rules). Checked = done and accepted; unchecked = not started or in
progress.

## WO-01 scaffolding

- [x] cargo workspace: feldspar-core, feldspar-library, feldspar-py crates
- [x] rust-toolchain.toml pinned, workspace lints, deny.toml
- [x] python/feldspar/ package skeleton (__about__.py, solve/, plan/,
      library/, fea/, pack/, calib/) with docstring stubs
- [x] tests/ tree with fea/regolith/slow markers registered
- [x] pyproject.toml: maturin backend, mesh/regolith extras,
      regolith.model_packs entry point -> feldspar.pack:register
- [x] Makefile: install, build, test, lint, format, typecheck, coverage,
      check, keys
- [x] logging/ subpackage (get_logger, dictConfig, formatter, filter,
      config.toml); pyo3-log bridge in feldspar-py; tracing in core;
      smoke test (Rust span -> Python logging)
- [x] .gitignore: house baseline + .feldspar/, keys/* private pattern
- [x] CI: five AD-12 jobs present and syntactically valid
- [x] TODO.md ledger (this file)

## WO-02 quantity core (Rust)

- [x] Interval, Accuracy, Rank, PortDecl, Domain, Dimension, UnitSystem
- [x] canonical_digest, format_f64
- [x] CoreError, UnitError, DomainViolation variants
- [x] BuiltinUnitSystem seeded table (M1 port units + mm/MPa/kN/GPa/%
      aliases + degC/degF/rpm/deg/s(Isp) edge cases + K/W compound)
- [x] PyO3 exposure: frozen classes, __repr__/__hash__/equality
- [x] feldspar/core.py: typani Result marshalling over the raising
      _feldspar primitives (Interval.new/point, Domain.admits,
      UnitSystem.dimension_of/to_si/from_si)
- [x] proptest property tests (interval, domain subset, digest order,
      unit round-trips) + Python smoke tests (tests/unit/test_core.py)

## WO-03 solver protocol + registry

- [x] SolverInfo, Citation, ClaimSenses, SolveOutput, EXACT
- [x] @solver decorator (F10/F11/F13/F14/F15/F16 coercions), NO global state
- [x] sugar.py: make_direction, Relation, table_solver_1d/2d, Correlation,
      CoupledGroup (M8 shape only, closure NotImplementedError)
- [x] SolverRegistry: register/declare_ports/freeze/digest/__iter__/port_table
- [x] RegistryError (all variants), SolveError (total union, NoConvergence
      reserved for M8)
- [x] core.py fix: canonical_digest handles nested PyO3 frozen instances
      and plain pydantic-dumped enums (WO-02 ambiguity closed)
- [x] core.py fix: Domain's Python field renamed port_box -> box
      (01-interfaces uses `box`; WO-02 regression caught by examples/)
- [x] tests/unit/test_registry.py: every RegistryError/SolveError variant,
      import-order permutation, citation floor, sugar==hand-built digest
- [x] `.unwrap()` -> `.danger_ok` fixed in examples/solvers/*.py by
      coordinator (63afd0e)

## WO-04 propagation + error accumulation (Rust)

- [x] Propagation trait + Interval strategy (to_interval() identity)
- [x] enumerate_corners: deduplicated, sorted, degenerate-collapsing
      cartesian product over a box of named intervals
- [x] corner_sweep: generic over any per-corner error type E; short-
      circuits on first Err; hulls per-port results
- [x] inflate(iv, eps), total_error(out_hull, model_eps) -- the ONE
      accumulation-rule home (FINV-4, audit A-1); no eps summation
      anywhere
- [x] PyO3 exposure: corner_sweep/inflate/total_error in feldspar.core,
      shared by WO-05 (planner) and WO-06 (executor)
- [x] proptest: hull contains all corners, dedup count, degenerate ==
      single evaluation
- [x] gain-counterexample test (02-edge-cases WO-04): k=1000, e=0.1 ->
      target error ~100, not ~0.1 (Rust unit test + Python integration
      test, both pass)

## WO-05 planner search (Rust)

- [x] plan(), Route, RouteStep
- [x] PlanError variants (InvalidBudget, UnknownTarget,
      NoApplicableSolver, BudgetUnreachable, CyclicPortEquivalence)
- [x] label-correcting forward AND-graph search: Pareto dominance
      pruning on (cost, inflated interval), frontier ordered by
      (cost, solver_id, combo tie-key)
- [x] PyO3 exposure: `_feldspar.plan`, `_PlanSolverInput`, `Route`,
      `RouteStep`, `PlanErrorRaised`; `feldspar.plan.plan()` facade
- [x] FINV-8 tier-blindness test (permuted tiers -> identical route
      digest) + zero-step/tie-break/determinism/all-PlanError-variant
      tests (crates/feldspar-core/src/search.rs,
      tests/unit/test_plan.py)

## WO-06 solve facade: execute, reroute, cache

- [x] execute(), solve(), RoutePolicy
- [x] content-addressed cache under .feldspar/cache/ (AD-9, FINV-7)
- [x] SolveError variants

## WO-07 library/mech formulas + calib harness

- [x] feldspar-library mech namespace formulas + extern "C"
- [x] feldspar.calib: calibrate(), check_ceilings(), CalibRecord

## WO-08 FEA pipeline

- [x] geometry, mesh, deck, ccx, results, richardson
- [x] find_ccx(), run_ccx()
- [x] fea.solver.register(registry)

## WO-09 regolith pack + conformance

- [x] feldspar.pack: real register() replacing WO-01 no-op stub
- [x] mech.static_stress / mech.static_deflection model registration
- [x] conformance suite against regolith WO-27

## WO-10 explain() + acceptance close-out

- [x] Solution.explain(), Solution.to_dict() (`plan/report.py`; pure
      rendering, no solver/registry calls -- `Solution` extended with
      `step_eps`/`step_citations`/`step_declared_domain`/`eps_budget`
      so the report never recomputes)
- [x] explain() golden: toy registry (`tests/unit/test_report.py`,
      byte-exact string golden + no-recomputation test) and a real FEA
      solve (`tests/integration/test_report_fea.py`, `fea`-marked --
      written per spec, NOT executed in this sandbox: no gmsh/ccx, same
      as WO-08/WO-09)
- [x] FINV audit checklist (`docs/implementation/FINV-audit.md`):
      FINV-1..8/10/11 test-cited; FINV-9/12 recorded as scope cuts
      (M5/M2, not yet applicable)
- [x] README quickstart (install/register/solve/explain), run against
      the real API before committing
- [x] M1 acceptance close-out against regolith WO-27's list: `make
      check`'s lint/import-lint/test/cargo stages verified green
      locally; `ty check` blocked by a PRE-EXISTING tomli/tomllib
      diagnostic in `_compat.py` unrelated to this WO (confirmed via
      `git stash -u` against the pre-WO-10 tree); CI matrix and the
      regolith conformance job cannot be verified from inside this
      sandbox in the sense a real CI run would -- not claimed as met,
      see WO-10's closing report
