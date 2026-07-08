# WO-09: The regolith pack

Status: todo
Depends: WO-08
Language: Python (`feldspar/pack/` ONLY -- FINV-3/10)
Spec: 06 (all sections), regolith `20-solver-abstraction.md` D-A..D-G,
regolith WO-27

## Goal

The WO-27 deliverable: engine solvers wrapped as regolith harness
models behind the entry point, conformant from the outside.

## Deliverables

- `pack/__init__.py::register(registry)`: import-cheap (no gmsh/ccx
  probing), registers the two models; the WO-01 stub becomes real.
- `FeaStaticStressModel` / `FeaStaticDeflectionModel` per 06's table:
  claim kinds with constructor override (OPEN-6 interim), honest
  cost, `estimate` = convert intervals (the ONE converter pair,
  round-trip tested) -> engine solve -> regolith Prediction (worst-
  corner value per sense, realized eps, coverage 1.0, solver_version
  triple, settings_digest as the INV-10 channel).
- Error mapping table (one function): every feldspar SolveError ->
  regolith DomainError with message embedded; honest indeterminate.
- Tier reporting per 06 (SolverInfo.tier -> regolith reduced tier).
- Conformance session: run regolith's `tests/packs/`
  `assert_pack_conforms` from THIS repo, `regolith`-marked; plus the
  WO-27 acceptance list (thin-margin discharge via orchestrator.build,
  fat-margin closed-form still wins, uninstalled -> harness.no_model,
  evidence-hash determinism twice-run, version-bump re-keys only
  feldspar evidence).
- `make keys` output consumed by the Valid(tier) signing check (06;
  no signing logic of our own).

## Acceptance

- CI regolith job: conformance + WO-27 acceptance green against a
  checkout of ../lithos; import-linter proves no `regolith.*` import
  outside `pack/` (FINV-3); regolith's own `make check` untouched.
