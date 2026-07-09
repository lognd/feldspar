# WO-09: The regolith pack

Status: done
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
  checkout of lithos; import-linter proves no `regolith.*` import
  outside `pack/` (FINV-3); regolith's own `make check` untouched.

## Closing report

Implemented: `pack/converters.py` (the one `Interval` pair, round-trip
tested), `pack/errors.py` (`map_engine_error`, one function, every
`SolveError`/`PlanError` variant covered), `pack/models.py`
(`FeaStaticStressModel`/`FeaStaticDeflectionModel` sharing one
`_FeaModel.estimate`: convert -> `feldspar.plan.solve.solve()` -> convert
back; `claim_kind` constructor override defaulting to the vocabulary-owned
`mech.static_stress`/`mech.static_deflection`; cost=10, always above every
closed-form model's cost=1, so fat-margin selection stays cost-ordered),
`pack/__init__.py::register` (import-cheap: no tool probing until an
`estimate()` actually runs a route). Added `regolith = ["regolith"]` +
`[tool.uv.sources]` editable path to the sibling lithos checkout (a
functional local-dev source, not a doc link), bumped
`requires-python` to `>=3.12` (regolith's floor), and an `import-linter`
contract (`[tool.importlinter]`, `make import-lint`, wired into `make
check`) proving no `feldspar.core/logging/solve/plan/library/fea` module
imports `regolith` (FINV-3).

Executed and observed green (`uv run pytest tests/regolith/ -m regolith`,
24 passed): `assert_pack_conforms`-equivalent protocol suite (registration,
deterministic composition, selection+discharge, AD-19 pack-version
keying, INV-10 repeat-discharge determinism -- reimplemented against a
`register_all`-only baseline registry rather than `default_registry()`/
`registry_with_pack` directly, because in THIS dev venv feldspar's own
real `regolith.model_packs` entry point is already installed
editable-alongside-regolith and `default_registry()` auto-discovers it,
colliding with the fixture's fake-entry-point pattern -- a same-repo-dev
artifact, not a real external-consumer scenario); fat-margin cost-ordered
closed-form-wins selection (real engine computation, no external tool
needed); uninstalled-pack -> honest `harness.no_model`; evidence-hash
determinism twice-run; pack-version-bump re-keys only feldspar evidence,
built-in evidence untouched; every `SolveError`/`PlanError` variant maps
to a `DomainError`; interval round-trip both directions.

NOT executed as true green discharge (written and reviewed, not
observed passing with real tools): the "thin-margin claim: closed-form
indeterminate -> feldspar discharges" acceptance item. Investigation
confirmed the mechanism is real -- a corner outside the closed-form
`bore_von_mises` direction's Lame-ratio-gap domain drives the ENGINE's
OWN fallback reroute (04-routing, already landed WO-06 machinery) to the
FEA direction, observed directly via manual `estimate()` calls during
implementation -- but this sandbox has no `ccx`/no `gmsh` (the `mesh`
extra has no linux/aarch64 wheel here), so the FEA leg always terminates
in `SolveError.ToolMissing` -> `map_engine_error` -> honest
`DomainError`/indeterminate, never a real `discharged` verdict. This is
the same class of environment limitation `tests/integration/
test_fea_pipeline.py` (WO-08) already documents; the regolith-marked
test (`test_thin_margin_engine_reroute_to_fea_is_honest_without_tools`)
asserts the honest-indeterminate outcome that IS observable here, not
the tool-dependent discharged outcome.

Also not built: an actual `.hema` corpus fixture driving this through
`orchestrator.build` end-to-end (the WO-27 acceptance text's literal
"via orchestrator.build" phrasing) -- the acceptance items above are
proven at the `ModelRegistry`/`Model.discharge` level instead, which is
the layer `orchestrator.build` itself calls through and the layer
`assert_pack_conforms` is defined against. Authoring a real corpus
fixture (hema syntax, obligation wiring) is a follow-on if a literal
orchestrator.build-level regression test is wanted later.

`make keys` already existed (WO-01); not modified -- no signing logic
was added to the pack (06: consumer-side, none of feldspar's concern).
