# WO-14: regolith boundary v2 (M4 -- kinds, coverage, payload channel, givens/regimes)

Status: todo
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
