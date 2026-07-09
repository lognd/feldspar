# WO-12: payload ports (M2)

Status: done (2026-07-08)
Depends: WO-03/06 (registry + facade, done), WO-08 (the mesh/geometry
stages this graduates into graph steps)
Language: Python (`feldspar/solve/`, `feldspar/fea/`) + Rust only if
digest helpers need a core home
Spec: 09 secs. 4/4a (payload ports, abstraction solvers -- NORMATIVE,
incl. the kind table with `frame`), 02 (payloads are exact by
reference), 03 (settings digests), FINV-2; scheduled by 09 sec. 8
(M2) + the 2026-07-08 closure re-review (08).

## Goal

Ports may carry content-addressed payloads: `PortDecl` gains
`payload(kind)` rank; kind checking at registration mirrors unit
checking; meshing becomes a graph step; per-rung/per-payload solve
caching keys on payload digests.

## Deliverables

- `PortDecl` payload rank + kind strings from 09 sec. 4 VERBATIM
  (the table is the single home; includes `frame`); connecting
  mismatched kinds is a registration error with the same shape as a
  unit mismatch (01-interfaces extension recorded there in the same
  change).
- Payload values are `{kind, digest, origin}` refs; digest folding
  into request/solve digests (a payload in a digest is its hash --
  09 sec. 4); no store IO in feldspar (orchestrator-provided
  resolver handle, the D96/OPEN-2 contract).
- `geometry.parametric` + `mesh` kinds live: the WO-08 mesh stage
  registers as a `geometry.* -> mesh` solver direction; static FEA
  consumes the mesh payload; one mesh feeds multiple solves
  (assert: modal-ready).
- Abstraction-edge support (09 sec. 4a): execution-time domain
  checks over payload features returning `SolveError` values;
  `conservative_for` honored; optimistic planning deterministic.
- Per-payload cache keying (04 cache extended); twice-run digest
  equality tests; 02-edge-cases rows for kind mismatch, missing
  payload, dangling digest.

## Acceptance

- A cantilever solve routes geometry.parametric -> mesh -> fea with
  each stage a registry edge; same-mesh reuse proven by cache-hit
  count; planner remains tier-blind by test; all digests stable
  across runs.

## Closing report (2026-07-08)

### What landed

- `feldspar/solve/payload.py`: `PAYLOAD_KINDS` (09 sec. 4 VERBATIM,
  incl. `frame`), `PayloadRef {kind, digest, origin}`,
  `PayloadResolver` protocol (resolve + store; the D96/OPEN-2
  orchestrator handle -- no store IO in feldspar), and
  `payload_feature_violation` for 4a execution-time checks.
- Registration kind checking mirrors unit checking:
  `RegistryError.PayloadKindConflict` / `UnknownPayloadKind` in
  `declare_ports` (01-interfaces extension recorded in this change).
- Pipeline channel: `SolveOutput.payloads`; `payloads=` on
  `plan`/`execute`/`solve`; execution-time `PayloadKindMismatch`/
  `MissingPayload`/`DanglingDigest` error values; payload outputs
  corner-invariance-checked and fed downstream; a payload in any
  digest folds as its hash (`request_digest`, FINV-12 enforcement
  entered in 00-architecture).
- `PayloadStepCache` (04-routing "Solve cache" extension recorded):
  per-rung/per-payload step caching for deterministic payload-
  touching steps, A-5 per-step tool recheck, contract-level hit/miss
  counters.
- `feldspar/fea/payload_steps.py`: `fea.mesh.cantilever`
  (`geometry.parametric -> mesh`, gmsh) and
  `fea.static_deflection.cantilever_from_mesh` (mesh + scalars ->
  deflection, single-mesh, declared ceiling); `register(registry,
  resolver)` declares the module port table and closes SolveFns over
  the resolver.

### Acceptance status

- geometry.parametric -> mesh -> fea, each stage a registry edge:
  EXECUTED GREEN via the stub twin
  (tests/unit/test_payload_pipeline.py) and the real module's
  registration+planning test (no tools needed); real gmsh/ccx
  execution rides tests/integration/test_fea_payload_steps.py
  (`fea`-marked), written per the standing WO-08/09/10 posture --
  this sandbox has neither ccx nor a gmsh wheel (aarch64).
- Same-mesh reuse by cache-hit count: EXECUTED GREEN (stub twin:
  static then modal, mesher runs once, `hits == 1`; modal-ready
  asserted by the second consumer reading the same mesh digest).
- Planner tier-blind by test: EXECUTED GREEN (tier permutation over
  payload edges -> identical route digest).
- All digests stable across runs: EXECUTED GREEN (route digest,
  request digest, step-cache entries byte-equal twice).
- 02-edge-cases WO-12 rows: all 15 rows covered by
  tests/unit/test_payload.py + test_payload_pipeline.py.

### Notes and residuals

- Rust: no core changes needed -- `Rank::Payload(String)` existed
  (WO-02 reserved arm); the search stays payload-unaware via width-0
  placeholder labels from `plan()`. Digest helpers stayed in Python
  (`canonical_digest` suffices), per the WO's "Rust only if" clause.
- Payload TARGETS (a solve whose target port is a payload) are out
  of M2 scope: claims discharge on scalars; the boundary channel is
  M4 (WO-14).
- F12 ordering seam: `fea/payload_steps.register` declares its port
  table; the declaration-free WO-07/WO-08 modules must register
  FIRST in a combined catalog (or declare their ports). Port-table
  unification belongs to WO-14's boundary work; documented in the
  module docstring.
- The `fea`-marked integration file uses a generous planning budget
  (1e10): the M1 sum-surrogate estimate scales the static
  direction's eps_rel ceiling by ~youngs_modulus at planning time.
  The pre-existing WO-08 fea-marked tests (never executed, standing
  TODO note) pass eps_budget=1e-2 and would hit BudgetUnreachable at
  planning under the same surrogate -- flagged here rather than
  silently edited (their fix belongs to the standing "run fea tests
  in a tooled environment" item).
