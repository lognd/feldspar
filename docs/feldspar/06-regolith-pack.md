# 06 -- The regolith pack

One sentence: `feldspar.pack` adapts engine solvers to regolith's
harness Model contract behind the `regolith.model_packs` entry point,
producing deterministic, attributable, signable evidence -- the WO-27
deliverable.

Contract home: `../lithos/docs/implementation/20-solver-abstraction.md`
(D-A..D-G) and `WO-27-reference-fea-pack.md`. This doc records only
the feldspar side; the regolith side is cited, not copied.

## Boundary rules

- ALL `regolith.*` imports live under `python/feldspar/pack/`
  (+ regolith-marked tests). Everything else imports and tests without
  regolith installed (regolith is an optional extra; FINV-3).
- Conversion at the boundary only: `regolith.harness.Interval` <->
  `feldspar_core.Interval` (same lo/hi semantics, one converter pair,
  round-trip tested). Core types never depend on regolith types.
- Entry point (D-B):

```toml
[project.entry-points."regolith.model_packs"]
feldspar = "feldspar.pack:register"
```

`register(registry: ModelRegistry) -> None` registers the models below
and nothing else; it must be import-cheap (no gmsh, no ccx probing --
tool discovery happens at estimate time).

## Models

Two in-process `regolith.harness.Model` subclasses (D-C's subprocess
adapter is for solvers whose WRAPPER is external; ccx is feldspar's
internal subprocess, so in-process registration is D-B-conformant):

| model | claim kind | sense | tier |
|---|---|---|---|
| `FeaStaticStressModel` | `mech.fea.static_stress` | upper | reduced |
| `FeaStaticDeflectionModel` | `mech.fea.static_deflection` | upper | reduced |

- Constructors take a `claim_kind` override so re-keying onto the
  closed-form claim kinds (for best-path tier competition in ONE
  registry graph, D-A) is a one-line change in `pack.py`. DECIDED
  (D94, WO-30, 08 OPEN-6): claim kinds are vocabulary-owned, not
  method-owned -- `mech.fea.static_stress` was a bootstrap error;
  register under `mech.static_stress` / `mech.static_deflection`.
  One model may register under multiple kinds (registry key is
  `(claim_kind, model_id)`, duplicate-id is per-kind); a method-named
  kind is a registration lint error once WO-30 lands. Target state
  (09 sec. 5): feldspar models register under the SAME kinds as
  regolith's closed-form tier and compete purely on cost; the
  override flips to this default when WO-30 ships.
- `signature.inputs` are the scalar ports of the parametric geometry,
  material, and load -- regolith's `DischargeRequest.inputs` is
  `Mapping[str, Interval]`, scalars only, which is exactly what the
  engine's corner sweep consumes. Geometry REFERENCES (WO-22 realized
  records) cross via `DischargeRequest.payloads: Mapping[str,
  PayloadRef{kind, digest, origin}]` once WO-30 lands (D96, closes
  08 OPEN-2's residual); the kind vocabulary is 09 sec. 4 verbatim.
- **Given-resolution contract** (friction G2, OPEN-13): obligations
  carry NAMES (`material: AISI_304`); the request carries scalar
  intervals. Resolution (record -> property intervals at the right
  T_env corner) is DECIDED regolith-side (D97, WO-30, 08 OPEN-13):
  an orchestrator pass evaluates records over the environment box
  (worst corner via declared per-axis monotonicity, else full-domain
  hull), extracts envelope loads via the contract IR, and turns
  unresolved names into indeterminate naming the given. feldspar's
  half of the contract is this port vocabulary, declared once here:
  `mech.geom.<family>.<param>`,
  `mech.material.{youngs_modulus, poisson, sigma_y}`,
  `mech.load.<case>` (05 naming) -- signature inputs and engine ports
  are the same strings, and the pack rejects (DomainError, honest)
  any request whose resolution regolith has not performed.
- Sense mapping: regolith `ClaimSense.upper/lower` maps one-to-one
  onto the engine's `plan(sense=...)` parameter (04, audit A-3),
  which filters `conservative_for` edges (03) -- a one-sided
  envelope edge can never discharge the wrong sense, and never
  appears mid-route (A-2).
- **Regime tags** (audit A-10, CLOSED D97(d)/WO-30): the general
  channel is `DischargeRequest.regimes: [str]`, asserted by lowering
  from claim-kind construction / net discipline; signatures declare
  `required_regimes`; missing tag = non-match (honest `no_model`).
  v1 rule remains valid as the degenerate case until WO-30 lands:
  each pack model supplies exactly the tags its registered claim
  kind's obligations GUARANTEE by construction (the WO-27 claim
  kinds are defined as linear-elastic small-deflection statics; the
  model constructor pins the tag set and it folds into the settings
  digest). A claim kind whose obligations cannot guarantee a needed
  tag must not be registered for.
- `cost` declares the honest relative expense (FEA is the expensive
  tier; the cheaper closed-form tier must keep winning fat-margin
  selections -- WO-27 acceptance).
- `estimate(request)` maps to the engine: convert intervals, run the
  registered FEA direction with corner sweep, return a regolith
  `Prediction` with:
  - `value` = worst-corner value (per claim sense),
  - `eps` = realized Richardson eps (05),
  - `coverage` = 1.0 (full corner sweep; regolith's coverage is a bare
    float -- the closed-form precedent),
  - `solver_version` = `feldspar <version> / ccx <v> / gmsh <v>`,
  - `settings_digest` = the engine digest. This is the sanctioned
    INV-10 channel: a non-None `Prediction.settings_digest` OVERRIDES
    the request's digest inside the shared `Model.discharge`
    (`../lithos/python/regolith/harness/model.py`) -- no `discharge()`
    override, no parallel margin rule (D-A).
- Failures: missing/failed tools and out-of-domain corners map to
  regolith `DomainError` with the feldspar error message embedded --
  honest indeterminate, never violated, never an exception. (regolith
  errors are constructor-imported inside `pack/`; the mapping table
  lives in one function.)
- Planned (09 M3, not v1): **margin-driven adaptive refinement** --
  the request carries the claim's limit, so the model translates the
  margin needed into an eps budget and drives the engine's
  budget-seeking refinement (09 sec. 3): refine until `value + eps`
  closes the claim or the ladder tops out, then honest indeterminate
  stating eps achieved vs needed (regolith's "what would resolve it"
  diagnostic family). Accuracy stays automatic -- the knob-turning is
  inside the model, driven by the margin, deterministically.
- Planned (09 M4, regolith-gated): richer inputs (parametric
  descriptors, WO-22 realized-geometry refs, spectra/masks) cross as
  hash-pinned payloads on the D96 `DischargeRequest.payloads` channel
  once WO-30 lands; engine-side they are payload ports (09 sec. 4),
  so the pack adapter stays a converter, never a second dispatch
  path.
- Tier reporting: `SolverInfo.tier` (09 sec. 1) maps onto regolith's
  closed-form/reduced/full ladder in evidence, so regolith users read
  one tier vocabulary.

## Identity, determinism, signing

- Pack identity: regolith's plugin loader records
  `(pack_name="feldspar", pack_version=<distribution version>)` and
  `Model.discharge` folds it into the evidence hash (D-D). feldspar
  single-sources its version in `feldspar.__about__` and pyproject
  reads it from there -- the entry-point distribution version IS that
  string (one home).
- Determinism: same `DischargeRequest` twice -> byte-identical
  evidence hash. Load-bearing inputs: routing determinism (04), mesh
  seed + settings digest (05), `OMP_NUM_THREADS=1`.
- Signing (D-E/WO-21): signing is CONSUMER-side machinery -- the
  orchestrator attaches attestations when a key is configured;
  feldspar's obligations are to (a) keep evidence deterministic so the
  content address is stable, (b) ship a development keypair under
  `keys/` (private key gitignored pattern documented, generated by
  `make keys`) for the conformance suite's `Valid(tier)` check, and
  (c) never write signing logic of its own (NO DUPLICATION with
  `harness/attest.py`).

## Conformance (the actual point of WO-27)

feldspar's test session runs regolith's pack-protocol suite from the
OUTSIDE (`../lithos/tests/packs/` `assert_pack_conforms` +
`registry_with_pack` helpers), marked `regolith` and skipped when
regolith is not installed. Green conformance from a separate repo is
the proof that the WO-20/21 contract holds for a real external
consumer. Acceptance additionally asserts (WO-27):

- thin-margin claim: closed-form tier indeterminate -> feldspar
  discharges through `orchestrator.build`;
- fat-margin claim: closed-form tier still selected (cost ordering);
- pack uninstalled: honest `harness.no_model`, zero regolith changes;
- evidence-hash determinism, twice-run;
- pack version bump re-keys ONLY feldspar-produced evidence.
