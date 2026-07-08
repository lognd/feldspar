# 00 -- Implementation architecture (NORMATIVE)

Where a WO body conflicts with this document, this document wins; WO
acceptance criteria stand. Mirrors the regolith architecture doc's
role (`../lithos/docs/implementation/00-architecture.md`); conventions
shared with regolith are cited, not re-argued.

## Repository layout (fixed by WO-01)

```
crates/                         cargo workspace, strict layering
  feldspar-core/                types, units, propagation, search,
                                digests; depends on nothing feldspar
  feldspar-library/             formula homes per namespace (mech,
                                thermo, ...); depends on core only;
                                every export also extern "C" (AD-3)
  feldspar-py/                  PyO3 module `_feldspar`; marshalling
                                ONLY, no logic (regolith AD-4 precedent)
python/feldspar/
  __about__.py                  the ONE version string (06)
  solve/                        registry.py, solver.py (decorator),
                                digest.py, errors.py
  plan/                         plan/execute/solve facade over core
                                search; route.py, solution.py, cache.py
  library/                      thin per-namespace registration modules
                                wrapping feldspar-library formulas
  fea/                          geometry, mesh, deck, ccx, results,
                                richardson, solver (05 stage map)
  pack/                         ALL regolith imports live here (FINV-10)
  calib/                        calibration harness (03)
tests/                          pytest; markers: fea, regolith, slow
docs/                           the contract (feldspar/ + this dir)
keys/                           dev keypair, private key gitignored (06)
```

## Architecture decisions

- **AD-1 Rust core.** Core types, unit algebra, propagation, error
  accumulation, and the planner search live in `feldspar-core` from
  day one (04's scaling argument). Python never reimplements them.
- **AD-2 no Python mirrors.** Core types cross via PyO3 as frozen
  classes with the same field names (02); there is no parallel
  pydantic copy of a core type to desync. Pydantic v2 frozen models
  are for Python-side config/artifacts only (MeshSettings, Route
  views, pack conversions).
- **AD-3 extractable library crate.** `feldspar-library` is
  `no_std`-compatible where feasible, exposes every formula through
  Rust and `extern "C"`, and never depends on feldspar-py or Python.
  This is the 01 extraction commitment made structural.
- **AD-4 explicit registries.** No import-time global registration;
  module-level `register(registry)` functions populate explicit
  `SolverRegistry` objects (03; regolith D-B precedent). Import order
  can never change behavior.
- **AD-5 one digest home.** Canonical-JSON -> blake3 in
  `feldspar.solve.digest` (Python) backed by the core implementation;
  every settings/route/cache digest goes through it (03, 04).
- **AD-6 optional extras.** `pyproject` extras: `mesh` (gmsh),
  `regolith` (the pack seam), `props` (CoolProp, Phase 2). Heavy
  imports are lazy; a missing extra is a solve-time error VALUE, an
  importable module always (05). ccx is an external binary, not a
  dependency.
- **AD-7 typani + errors as values.** Fallible operations return
  typani `Result[T, E]` with ErrorSet variants (Rust side:
  `thiserror`, no `anyhow` in library crates); exceptions are
  programmer bugs only. Error unions are TOTAL: every variant named
  in the spec exists in code (04's PlanError/SolveError lists).
- **AD-8 logging.** Rust `tracing` (span per plan/execute/solve, log
  every route decision, domain rejection, reroute, cache hit/miss,
  eps charge), bridged via pyo3-log; Python module loggers +
  dictConfig per `~/.claude/refs/logging.md`. Never `print`.
- **AD-9 cache storage.** The solve cache (04) is a content-addressed
  file store under `.feldspar/cache/` (key = digest, value =
  canonical-JSON Solution), gitignored; no daemon, no sqlite --
  portable and inspectable. Eviction is manual (`feldspar cache gc`
  later); correctness never depends on eviction.
- **AD-10 parallelism.** rayon behind a thread-count setting
  (1 = serial path); parallel and serial assemble results in sorted
  order and must be bit-identical (09 sec. 6). No platform APIs.
- **AD-11 build.** maturin builds `feldspar-py` into the wheel; one
  distribution `feldspar`, version single-sourced from
  `__about__.py` (06). Pinned stable Rust toolchain; workspace lints.
- **AD-12 CI jobs.** (a) make check (ruff, mypy, pytest sans
  markers); (b) cargo fmt/clippy/test; (c) determinism twice-run
  (byte-identical Solution digests, serial AND parallel); (d)
  `regolith` extra job: install ../lithos regolith + run `regolith`-
  marked tests incl. the conformance suite; (e) `fea` job with
  ccx+gmsh installed for known-answer tests.
- **AD-13 deterministic transcendentals.** All transcendental math
  in `feldspar-core` and `feldspar-library` goes through one
  deterministic pure-Rust implementation (the `libm` crate), never
  the platform libm behind `std` floats, whose results differ across
  OS/architecture. Basic IEEE-754 arithmetic (+, -, *, /, sqrt) is
  bit-determined by the standard and exempt. Without this,
  cross-platform byte-identical Solution digests and `explain()`
  goldens (FINV-1; 02-edge-cases WO-10) are unkeepable (audit A-6).

## Invariants (FINV ledger)

Every guarantee, with enforcement. New guarantees enter this table in
the same change as their implementation (regolith house rule D-G).

| id | invariant | enforced by |
|---|---|---|
| FINV-1 | Determinism: same registry contents + same request => byte-identical Route and Solution digests, across platforms | sorted registry iteration, BTree core types, lexicographic tie-breaks, sorted corner order (04), AD-13 libm; CI twice-run job + platform matrix |
| FINV-2 | Settings-digest honesty: everything that can change an answer folds into the settings digest (regolith INV-10 verbatim) | digest helper single home (AD-5); FEA settings fold test (05); code review rule |
| FINV-3 | regolith is optional and one-way: all `regolith.*` imports under `feldspar/pack/`; everything else imports and tests without it | import-linter contract in CI; `regolith`-marked tests |
| FINV-4 | One error-math home: exactly one corner-sweep and one inflate/total-error implementation per uncertainty representation, in core; accumulation is by eps-INFLATION, never eps summation (02, audit A-1) | grep-able single symbol; planner estimate calls the same core routine (04); gain-counterexample test (02-edge-cases WO-04) |
| FINV-5 | Totality: out-of-domain, unknown port, budget-unreachable, tool-missing are error VALUES from total unions; never exceptions, never extrapolation | typani ErrorSet exhaustiveness tests per variant (04) |
| FINV-6 | Citation floor: registration with empty method citations errs; declared non-zero Accuracy ceilings carry calibration citations (EXACT is exempt, 03/A-7) | `SolverRegistry.register` check (03); calib harness ledger test |
| FINV-7 | Cache freshness: cache key == the full input tuple of the pure solve function; a hit equals a recompute; tool-presence recheck is SYMMETRIC (vanished AND newly-appeared, 04/A-5) | key derivation from FINV-1/2 digests only (04); property test: hit vs forced recompute byte-equal; tool-appeared miss test |
| FINV-8 | Tier-blind dispatch: planner reads cost/accuracy/domain only, never `tier` (09 sec. 1) | unit test: permuting tier labels changes no Route |
| FINV-9 | Parallel == serial: bit-identical Solutions at any thread count | CI determinism job runs both (AD-12c) |
| FINV-10 | Boundary conversion only: core types never depend on regolith types; one converter pair, round-trip tested (06) | import-linter + round-trip tests |
| FINV-11 | Coherent-SI storage: values are stored/computed/digested in coherent SI; conversion at ingest/print only (02) | UnitSystem API shape (no convert on stored values); table validation vs regolith-qty in pack tests |
| FINV-12 | Payloads cross by content address: a payload in any digest is its hash; payload kinds type-check like units (09 sec. 4) | payload port registration checks; digest tests (lands with 09 M2, enters table then) |

## Language assignment (per WO `Language:` header)

Rust: WO-02 (core types/units), WO-04 (propagation/accumulation),
WO-05 (search), WO-07 (formula homes). Python: WO-03 (registry
facade), WO-06 (solve facade/cache), WO-08 (FEA pipeline), WO-09
(pack), WO-10 (explain/report). Mixed WOs say which half is which.

## Tooling

`make` targets: install, build (maturin develop), test, lint, format,
typecheck, coverage, check, keys. frob for edit staging/outline per
house rules. `.gitignore` per house baseline + `.feldspar/`, `keys/*`
private pattern.
