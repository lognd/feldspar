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

- [ ] Interval, Accuracy, Rank, PortDecl, Domain, Dimension, UnitSystem
- [ ] canonical_digest, format_f64
- [ ] CoreError, UnitError variants

## WO-03 solver protocol + registry

- [ ] SolverRegistry, @solver decorator, make_direction
- [ ] Relation, Correlation, table_solver_1d/2d
- [ ] RegistryError variants

## WO-04 propagation + error accumulation (Rust)

- [ ] corner_sweep, inflate, total_error
- [ ] eps-inflation accumulation (FINV-4, audit A-1)

## WO-05 planner search (Rust)

- [ ] plan(), Route, RouteStep
- [ ] PlanError variants

## WO-06 solve facade: execute, reroute, cache

- [ ] execute(), solve(), RoutePolicy
- [ ] content-addressed cache under .feldspar/cache/ (AD-9, FINV-7)
- [ ] SolveError variants

## WO-07 library/mech formulas + calib harness

- [ ] feldspar-library mech namespace formulas + extern "C"
- [ ] feldspar.calib: calibrate(), check_ceilings(), CalibRecord

## WO-08 FEA pipeline

- [ ] geometry, mesh, deck, ccx, results, richardson
- [ ] find_ccx(), run_ccx()
- [ ] fea.solver.register(registry)

## WO-09 regolith pack + conformance

- [ ] feldspar.pack: real register() replacing WO-01 no-op stub
- [ ] mech.static_stress / mech.static_deflection model registration
- [ ] conformance suite against regolith WO-27

## WO-10 explain() + acceptance close-out

- [ ] Solution.explain(), Solution.to_dict()
- [ ] M1 acceptance close-out against regolith WO-27's list
