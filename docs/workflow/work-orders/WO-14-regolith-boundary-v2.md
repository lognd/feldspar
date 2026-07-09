# WO-14: regolith boundary v2 (M4 -- kinds, coverage, payload channel, givens/regimes)

Status: done (2026-07-08)
Depends: WO-09 (pack, done), WO-12 (payload ports). Lithos-side
WO-30 is DONE, so this is dispatchable the moment WO-12 lands --
it was the only regolith gate.
Language: Python (`feldspar/pack/`)
Spec: 06 (the pack contract; its target-state notes), 08 OPEN-6/8/
13 + A-10 (all DECIDED with WO-30), 09 sec. 5;
lithos:docs/spec/toolchain/20-solver-abstraction.md sec. 8 (D94-D97
NORMATIVE)

## Goal

The pack speaks contract v2: closed-form claim kinds (deny-list
lint live), structured Coverage, the `DischargeRequest.payloads`
ref channel, resolved givens by the shared port vocabulary, and
regime tags via `required_regimes`.

## Deliverables

- Kind re-key complete (OPEN-6 target state): registrations under
  `mech.static_stress`/`mech.static_deflection` etc.; the
  `claim_kind` constructor override default FLIPPED; method-word
  kind strings are a registration lint error.
- Structured `Coverage { axes, fraction }` reported from real sweep
  shapes (grid k x m, enumerated discrete axes, corners) instead of
  the v1 bare `1.0`; conservative collapse preserved.
- `DischargeRequest.payloads` consumed: payload-kind matching in
  signature selection (a model needing an absent payload is honest
  `no_model`); digests resolved through the orchestrator store
  handle only.
- Given resolution (D97/OPEN-13): the 06 port vocabulary
  (`mech.geom.<family>.<param>`, `mech.material.*`,
  `mech.load.<case>`) is the shared registry; reject-unresolved
  rule enforced with the constructive error naming the given.
- Regime channel (A-10): `ModelSignature.required_regimes`; missing
  tag = non-match; the v1 kind-construction interim remains the
  degenerate case (tests keep it valid).
- Conformance: re-run against the lithos `tests/packs/` suite
  (lithos WO-27's surface) and record results in the close-out.

## Acceptance

- The lithos conformance suite passes against this pack; a
  grid-swept solve's evidence states per-axis coverage; a
  payload-needing model no-matches honestly without payloads;
  regime-gated dispatch proven both ways.

## Close-out (2026-07-08)

- Kind re-key: found ALREADY at target state in `pack/models.py`
  (`DEFAULT_STRESS_CLAIM_KIND = "mech.static_stress"`,
  `DEFAULT_DEFLECTION_CLAIM_KIND = "mech.static_deflection"`, landed
  with the original `feat(pack)` commit) -- the method-word lint
  itself lives regolith-side (`registry.method_named_kind_violation`,
  WO-30) and is exercised by the re-run conformance suite. No code
  change needed; verified, not re-litigated.
- Structured Coverage: `pack.models._structured_coverage()` builds a
  `CoverageAxis` per non-degenerate (`lo != hi`) scalar input, method
  `corners` (the engine's corner sweep IS full-corners coverage of
  each swept axis); pinned inputs contribute none. Wired into both
  existing models' `Prediction.coverage_axes` and the new payload
  model's. `fraction` unchanged (`coverage=1.0`, the conservative
  collapse). Grid/enumerated-axis reporting stays the generic
  regolith-side fixture's job (`test_pack_contract_v2.py`
  `_SweepingModel`) -- no feldspar solver direction sweeps a grid or
  discrete axis internally today, so there is nothing for the pack to
  report beyond corners; escalated as a residual for whichever future
  WO adds one.
- D96 payload channel: added the `PayloadRef` converter pair
  (`pack/converters.py`, mirrors the `Interval` pair exactly),
  resolved the F12 ordering seam WO-12 flagged (`_engine_registry()`
  now registers `feldspar.fea.payload_steps` LAST, after the
  declaration-free `library.mech`/`fea.solver` modules -- verified
  harmless to the two existing scalar models, since neither ever
  supplies the geometry payload input `plan()` would need to route
  through the new mesh edges), and added
  `FeaStaticDeflectionFromGeometryModel` (`payload_kinds` declared,
  registered as pack model #3). ESCALATED RESIDUAL (not feldspar's to
  fix, named rather than invented around): `regolith.orchestrator.
  discharge.discharge_one` never threads a `PayloadStore`/resolver
  handle down to `Model.estimate` -- `DischargeRequest.payloads`
  carries only refs (kind/digest/origin), and nothing in the harness
  or orchestrator layer resolves a digest to bytes on a model's
  behalf. So today a payload-needing pack model can prove the D96
  SELECTION half honestly (no-match absent the payload, matched
  present) but every matched discharge is `indeterminate` via
  `pack.payload_bridge.NoStoreResolver`, which reports
  `SolveError.ToolMissing("regolith.orchestrator.payload_store", ...)`
  -- never a silent success, never an exception, never feldspar doing
  its own storage IO (06's rule honored to the letter). Closing this
  needs a regolith-side WO threading `PayloadStore.resolver()` (or
  equivalent) through `Model.discharge`/`estimate`; out of scope here
  (lithos is read-only reference for this WO).
- Given resolution (D97/OPEN-13): feldspar's half was already
  DECIDED and recorded verbatim in `docs/spec/06-regolith-pack.md`
  ("Given-resolution contract"/the port vocabulary); the
  reject-unresolved rule is regolith-side (`orchestrator.translate`)
  and is exercised, green, by the re-run conformance suite
  (`test_unresolved_given_produces_indeterminate_naming_the_given`).
  No feldspar code change needed.
- Regime channel (A-10/D97): `_FeaModel.__init__` gained a
  `required_regimes: tuple[str, ...] = ()` parameter threaded to
  `ModelSignature.required_regimes`; default `()` preserves the v1
  degenerate case (every existing conformance request, none of which
  ever sets `DischargeRequest.regimes`, keeps matching unchanged --
  verified by `test_default_required_regimes_is_the_v1_degenerate_
  case`). `test_regime_channel_dispatches_both_ways`
  (`tests/regolith/test_pack_boundary_v2.py`) proves an overridden
  model no-matches without the tag and matches with it.
- eps-budget rider: fixed. `tests/integration/test_fea_pipeline.py`'s
  three `eps_budget=1e-2` cantilever-deflection calls (lines 102/188/
  195 pre-fix) bumped to `1e10` (WO-12's own generous planning
  budget for the identical direction) -- the M1 sum-surrogate scales
  the direction's `eps_rel` ceiling by the corner-summed magnitude,
  dominated by `youngs_modulus` (~1e10-1e11), so `1e-2` is
  `PlanError.BudgetUnreachable` before any tool runs. Every
  assertion in the file still checks the REALIZED `fea_solution.eps`/
  `abs(fea_value - oracle_value)`, so nothing the tests verify was
  weakened; could not execute end-to-end here (no ccx/gmsh,
  aarch64), same standing posture as the rest of the WO-08 `fea`-
  marked file.
- New tests: `tests/regolith/test_pack_boundary_v2.py` (coverage,
  regime channel, payload channel -- 6 tests) and two round-trip
  cases added to `tests/regolith/test_pack_converters.py`.
- Conformance: re-ran `lithos:tests/packs/` (the real repo at
  `../lithos`, symlinked) against this pack's venv -- 34/34 passed,
  including `test_feldspar_conformance.py` (feldspar's own real
  distribution) and the generic `test_pack_contract_v2.py` D94-D97
  fixture suite.
- Gates: `make check` green (`cargo fmt`, `ruff format`/`check`,
  `lint-imports` -- regolith imports still confined to `feldspar.
  pack` -- `ty check`, `cargo test --workspace` 61+9+7+1 passed,
  `pytest tests/ -n auto -m "not regolith and not fea"` 193 passed).
  `pytest tests/ -m "not fea"` (includes `regolith`-marked) 225
  passed, 9 deselected (`fea`-only) locally.
