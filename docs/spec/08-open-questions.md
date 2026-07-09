# 08 -- Open questions

Consolidated OPEN list. An item leaves this file only by landing in a
spec doc + implementation (same change) or by being explicitly cut in
the work order that decided it. Items marked DECIDED have owner
decisions folded into their spec home (cited per item) and exit fully
when the implementing WO lands; only their RESIDUAL is still open.

- **OPEN-1 unit algebra + uncertainty**: DECIDED (owner, 2026-07-07),
  spec home 02. Unit core is a `Dimension` exponent vector +
  conversion table in `feldspar-core`, behind a `UnitSystem` interface
  that regolith-qty MAY back when installed (built-in stays
  dependency-free, FINV-3; validated against regolith-qty in the
  pack's test session). Uncertainty representations sit behind one
  `Propagation` protocol: interval corner sweep (v1), normal with
  differentiation (delta method), quantile/decile/quartile bands
  (seeded empirical) -- every representation collapses conservatively
  to interval at the pack boundary. RESIDUAL: none; awaiting
  implementation WO.

- **OPEN-2 real geometry / model hierarchy**: DECIDED direction
  (owner, 2026-07-07), spec homes 01 and 09 (the full integration
  plan; payload ports are the carrier). The solver graph is a fidelity
  hierarchy dispatchable at any level and resolving at the cheapest
  valid one; real geometry enters as additional solvers, never a
  separate dispatch path; regolith's declarative side should be able
  to point claims at cheaper parametric solvers, not only realized
  geometry. RESIDUAL CLOSED (D96, WO-30, cycle 20): the ref-passing
  channel is `DischargeRequest.payloads: Mapping[str,
  PayloadRef{kind, digest, origin}]`, with the kind vocabulary being
  09 sec. 4's list verbatim (`geometry.parametric`,
  `geometry.realized`, `mesh`, `table`, `spectrum`, `profile`,
  `mask`, `field`, `flownet`, `plan`) -- not a restyled set, the
  contract. `ModelSignature` gains required payload kinds; digest
  resolution is an orchestrator-provided content-addressed store
  handle (feldspar never does store IO). Unblocks 09 M4/M6.

- **OPEN-3 wire executable / extraction**: DECIDED direction (owner,
  2026-07-07), spec homes 01 and 03. feldspar is both a standard
  library of engineering models and an interop layer; `feldspar-core`
  and the formula tier are Rust with PyO3 and `extern "C"` surfaces so
  subsystems can be extracted and compiled standalone (embedded
  targets included). RESIDUAL: the `feldspar-solve` stdin/stdout
  binary speaking regolith's SolverResponse schema (D-C) stays cut
  from v1 (in-process models are conformant); revisit when regolith's
  Phase E process split lands.

- **OPEN-4 fallback routing**: DECIDED (owner, 2026-07-07), spec home
  04. Default is to replan around an execution-time failure
  (deterministic exclusion set, every attempt logged per the logging
  mantra); `RoutePolicy(fallback=False)` opts out; evidence always
  reports the executed route. RESIDUAL: none; awaiting implementation
  WO.

- **OPEN-5 route/evidence caching**: DECIDED (owner, 2026-07-07),
  spec home 04. Solve cache keyed by (registry digest, request
  digest, settings digest, feldspar version); freshness is proven by
  the FINV-2 argument (the key IS the full input tuple of the pure
  solve function; time is not an input), with the one explicit
  non-digest check (tool presence re-verified on hit) called out.
  Default ON in development, opt-out for deployment. RESIDUAL: none;
  awaiting implementation WO.

- **OPEN-6 claim-kind tiering**: DECIDED (D94, WO-30, cycle 20).
  Claim kinds are owned by the claim vocabulary --
  `mech.fea.static_stress` was a bootstrap error; register under the
  closed-form kinds (`mech.static_stress`, `mech.static_deflection`).
  One model may register under MULTIPLE kinds (registry key is
  `(claim_kind, model_id)`; duplicate-id is per-kind, not global). A
  claim kind whose string contains a method/tool word is a
  registration LINT ERROR once WO-30 lands -- flip the pack's
  `claim_kind` constructor override default when it does (06/09
  sec. 5 target state realized).

- **OPEN-7 SPICE scope**: DECIDED (owner, 2026-07-07), spec homes 03
  and 07. feldspar is the one backend; each namespace is the
  capability (`mech`, `thermo`, `elec`, ...); the electrical numeric
  tier (ngspice) lives inside feldspar's `elec` namespace, not a
  sibling pack; cross-namespace bridges must be minimal-boilerplate
  ordinary solver edges. RESIDUAL: none; regolith/11's illustrative
  `spice.ngspice` naming flagged regolith-side (sec. 7 note).

- **OPEN-8 coverage vocabulary**: DECIDED (D95, WO-30, cycle 20).
  Structured `Coverage { axes: [CoverageAxis], fraction }`, per-axis
  `domain: Interval | {values: [...]}` and `method: corners |
  grid{k per axis} | enumerated | analytic | monotone`; `fraction`
  stays as the conservative collapse. feldspar's `grid(k x m)` sweeps
  and discrete state axes (G29, G43/COPEN-7) are both first-class
  under this schema -- no engine-side redesign, only the pack's
  `estimate()` reporting a structured Coverage once WO-30 lands
  instead of the v1 bare `1.0`.

- **OPEN-9 parallel execution**: DECIDED (owner, 2026-07-07), spec
  homes 04 and 09 sec. 6. Parallelism is decoupled from expense: when
  cores are available, independent work uses them (corners,
  refinement rungs, independent route steps, calibration sweeps).
  Constraints in priority order: bit-identical order-deterministic
  assembly (determinism suite runs serial AND parallel paths),
  portability (pure-Rust threading, no platform APIs), and a serial
  cross-platform fallthrough that always exists. RESIDUAL: none;
  implementation is 09 M5.

- **OPEN-10 accuracy calibration**: DECIDED (owner, 2026-07-07), spec
  homes 03, 04, 05. Every solver must cite method sources (papers /
  handbooks / standards) and calibration evidence at registration
  (empty citations is a registration error); a calibration harness is
  cross-phase infrastructure shipping with Phase 1; `Solution.explain()`
  renders the step-by-step, citation-backed justification report so
  every point in a delivered process is defensible. RESIDUAL: none;
  awaiting implementation WO.

- **OPEN-11 time/frequency-structured ports**: DECIDED direction
  (owner, 2026-07-07), spec homes 02 (non-scalar and structured
  quantities) and 09 sec. 4. Spectra, time profiles, and masks are
  exact-by-reference hash-pinned PAYLOADS on payload ports, adopting
  regolith/02 sec. 5's settled vocabulary verbatim; claim-form
  reductions (`peak`, `rms(band)`, `settles`, `stays_within`) are
  ordinary solver edges from payload ports to ranked ports; the
  `Propagation` protocol is guarded against scalar-only assumptions
  by rule (02). Reconciled regolith-side: the ref-passing ask was
  generalized so ONE channel carries geometry refs, parametric
  descriptors, spectra, profiles, and masks
  (`lithos:docs/spec/toolchain/20-solver-abstraction.md` sec. 7
  item 3). RESIDUAL CLOSED: the channel is D96 (see OPEN-2); engine-
  side implementation is 09 M6, gating Phase 3. Cycle 21 addendum
  (D102): temporal claim-form shapes split into two families --
  `peak`/`rms(band)`/`overshoot` REDUCE to a scalar and take an
  EXTERNAL comparator (ordinary solver edges to ranked ports, as
  already recorded here); `settles`/`stays_within` are self-contained
  CONTAINMENTS (verdict-shaped, not edges to a ranked port). The
  claim-form reduction edges above should mirror this split when
  implemented.

- **OPEN-13 given-resolution contract** (new 2026-07-07, friction G2
  from the lithos pressure tests, examples/lithos/README.md):
  obligations carry names (`material: AISI_304`,
  `interface_envelope(...)`); `DischargeRequest.inputs` carries
  scalar intervals; the resolution step between them (property-record
  evaluation over environment corners, envelope load extraction,
  shared port vocabulary) is unspecified regolith-side. feldspar's
  half is DECIDED and recorded in 06 (port vocabulary +
  reject-unresolved rule). CLOSED regolith-side (D97, WO-30,
  cycle 20): an orchestrator pass resolves names to intervals --
  records evaluated over the environment box (worst corner via
  declared per-axis monotonicity, else full-domain hull), envelope
  loads via the contract IR, unresolved names become indeterminate
  naming the given. feldspar's port-name vocabulary (06:
  `mech.geom.<family>.<param>`, `mech.material.*`,
  `mech.load.<case>`) is adopted as the single-homed shared registry;
  the reject-unresolved rule is the contract's other half. Regime
  tags (A-10) close alongside: `DischargeRequest.regimes: [str]`,
  asserted by lowering from claim-kind construction / net discipline;
  signatures declare `required_regimes`; missing tag = non-match
  (honest `no_model`) -- feldspar's v1 interim (tags guaranteed by
  kind construction) is the degenerate case and remains valid.
  Blocks nothing in M1 (conformance fixtures pre-resolve by hand);
  unblocks real `.hema`-to-evidence flows once WO-30 lands.

- **OPEN-14 zone/station-indexed ports** (new 2026-07-07, friction
  G23/G24 from the regen-engine stress test,
  examples/lithos/regen_engine/README.md): distributed 1-D/2-D
  quantities (wall temperature along the axis, zone-valued fields
  consumed as loads) are not routable ports. INTERIM DECIDED:
  marching solvers expose extremal boundary ports with internal,
  sense-declared reductions (09 sec. 4b); `field` payloads carry
  full results between solvers (FEA thermal load). Source side now
  DECIDED (D98, WO-33, cycle 20): `compute <name>: <kind> over
  <zones | var in [lo,hi]>` lowers to one obligation producing a
  `field` payload; consumers project (`max`, `at`, `slope`) through
  the promise chain. feldspar's extremal-port interim stays the
  discharging story until a field-producing model registers -- the
  four-bar/marching solvers, once built, produce `field` payloads on
  the D96 channel (OPEN-2); G36's slope-bound demand becomes
  expressible then. Consumer-side per-station/zone routable ports
  remain coupled to regolith's zone vocabulary (regolith/02 sec. 4);
  undesigned engine-side, blocks nothing before Phase 2's distributed
  thermal work. EXTENDED 2026-07-07 by
  the dune-buggy stress test (G36,
  examples/lithos/dune_buggy/README.md): the same shape appears
  with a CONFIG variable as the index axis instead of space --
  camber(travel), toe(travel), motion_ratio(travel) are computed
  1-D curves over suspension travel consumed by sibling claims
  (roll stiffness, bump-steer SLOPE bounds). The interim reduction
  (extremal/worst-point scalar claims over the swept domain) and
  the regolith-side ask (sec. 7 item 7, now covering zone- AND
  config-indexed computed fields) both apply unchanged.

- **OPEN-12 non-scalar quantities**: DECIDED (owner, 2026-07-07),
  spec home 02. Native support: `PortDecl` carries rank (scalar /
  complex / vector(n) / tensor(n, m) / payload(kind)), mirroring
  regolith/02 sec. 1; uncertainty is per-component; scalar reductions
  (magnitude, von Mises) are ordinary solver edges, never implicit
  casts; rank mismatch is a registration error like a unit mismatch.
  v1 registers scalar-ranked ports only, but the model is rank-native
  from the first commit. RESIDUAL: zone indexing (regolith/02 sec. 4)
  is intentionally not adopted engine-side yet -- zones stay a
  regolith-side concept until a claim needs them to cross.

- **OPEN-15 the symbolic core** (new 2026-07-08): DECIDED direction
  (owner, 2026-07-08), spec home 11. feldspar gains symbolic
  capabilities: equations declarable as data (`Relation` given one
  symbolic equation; directions DERIVED at declaration time, lowering
  to the one raw protocol, digest-stable, citations inherited),
  validity domains tracked as symbolic predicates (dispatch boxes
  DERIVED from them; predicates carried for composition and
  `explain()`), and rules represented symbolically wherever they are
  equations/inequalities (accuracy models, regime guards). AMENDS the
  01 non-goal (now optimization-only) and 03's Relation parenthetical
  (symbolic-inversion rejection reversed) -- both files carry the
  amendment notes. Constraints unchanged: one-protocol rule, digest
  determinism, citation floor, no solve-time CAS, no invented
  physics. R1 engine home DECIDED (owner, 2026-07-08): native Rust
  kernel in `feldspar-core`, with an optional sympy conversion
  interface Python-side -- WO-11 dispatch unblocked.

  WO-11 LANDED 2026-07-08. R2 canonical-simplification pinning:
  RESOLVED -- a fixed total order + flatten/fold/identity-elimination
  rewrite to a fixed point, `CANON_VERSION`-gated, digested via a
  dedicated canonical S-expression string (never `serde_json` of the
  AST). R3 explicit branch selection: RESOLVED -- structural
  peeling with an occurrence gate (`NonInvertible` for 0/>1
  occurrences), even-power targets returning a named `MultiBranch`
  listing branches unless the author declares one, never guessed.
  Full resolution detail, including the digest-equality-vs-folds-
  into-digest reconciliation and the predicate-to-box scope decision
  found during implementation: `docs/workflow/work-orders/
  WO-11-symbolic-core.md` closing report. R4 and R5: DECIDED
  (owner closure directive, 2026-07-08; normative text 11 sec. 4;
  scheduled WO-22) -- symbolic-derivative mode inside the one
  Propagation protocol with CANON_VERSION digest folding (R4);
  derived directions inherit citations but re-sweep calibration
  over the mapped domain, Accuracy(0,0) exempt (R5). NOTHING in
  OPEN-15 remains open.

## Closure re-review (2026-07-08, owner directive; lithos cycle 27)

Every residual above was re-checked under the owner's
close-everything directive
(`lithos:docs/workflow/design-log/2026-07-08-cycle-27.md` D146).
Dispositions that STAND with their recorded gates (no new evidence
exists; each is a named-gate deferral, not an open design): OPEN-3's
`feldspar-solve` process binary (gate: regolith's Phase E process
split), OPEN-12's zone-indexing residual and OPEN-14's per-station
routable ports (gate: Phase 2 distributed-thermal demand; design
shape already pinned -- `field` payloads + projection edges,
extremal ports until then). Everything else in this file is DECIDED
with implementation scheduled: the full forward queue is
`docs/workflow/work-orders/` WO-12..WO-22 (see workflow README),
covering M2-M9, the Phase 2 library wave (compressible entries
included -- lithos D141 makes gas-network delivery a demanded
tier), the civil/structural wave (lithos D133/D139: the `frame`
payload consumer, 07 Phase 6), and the R4/R5 symbolic follow-ups.

## Audit ledger (2026-07-07 full-spec audit, A-nn)

Findings from the pre-implementation spec audit. FIXED items are
folded into the cited spec homes in the same change (house rule);
none is open unless marked.

- **A-1 (FIXED, 02/04/01-interfaces/WO-04): eps accumulation was
  unsound.** Summing model eps scalars along a route ignores
  downstream sensitivity (a gain-k step turns upstream eps e into
  k*e). Accumulation is now BY INFLATION: consumed intermediate
  ports are widened by their producing step's eps before the corner
  sweep, so upstream error rides the consuming solver's actual
  sensitivity; total error at target = final half-width + final
  step's eps. Exact for corner-monotone chains (the existing
  contract); non-monotone solvers already owe widened eps.
  `accumulate_step` is replaced by `inflate` + `total_error`.
  Dominance pruning becomes (cost, inflated-interval subset).
- **A-2 (FIXED, 03/04): one-sided edges mid-route were unsound.**
  A `conservative_for != both` output through a downstream step with
  negative sensitivity inverts the bound. v1: one-sided edges are
  admissible only as the FINAL route step; per-input monotone-sign
  metadata (sense-preserving composition) is future schema.
- **A-3 (FIXED, 04/01-interfaces/06): plan/solve had no claim-sense
  parameter** although the edge-case matrix and G4 require
  sense-based edge filtering. Added `sense: ClaimSenses = BOTH`,
  folded into the request digest; the pack passes its
  ModelSignature sense through one-to-one.
- **A-4 (FIXED, 01-interfaces/04): SolveError union was not total**
  over behaviors the edge-case matrix demands. Added
  `MissingOutput(port)` and `InvalidMeasurement(reason)`
  (FINV-5).
- **A-5 (FIXED, 04/FINV-7): cache tool-presence check was
  asymmetric.** A Solution cached after rerouting around a
  ToolMissing failure was served even once the tool appeared,
  violating hit==recompute. The presence recheck now runs both ways
  (tools used must remain present; tools whose absence caused
  exclusions must remain absent), read from the cached attempt
  trail.
- **A-6 (FIXED, 00-architecture AD-13/WO-07): cross-platform float
  determinism.** Platform libm makes cross-platform byte-identical
  goldens unkeepable; all transcendentals go through one
  deterministic pure-Rust libm.
- **A-7 (FIXED, 03/FINV-6): EXACT vs the calibration floor.**
  `Accuracy(0,0)` declares real-arithmetic exactness and is exempt
  from calibration citations (nothing to measure); still banned for
  coupled and table tiers.
- **A-8 (FIXED, 01-interfaces): the M1 port table is now enumerated
  normatively** -- the exact strings are load-bearing at the pack
  seam (06's never-renames rule) and were previously scattered.
- **A-9 (FIXED, 04/01-interfaces/examples): interface drift.**
  `execute` signature, Solution's attempts/cache_hit fields,
  frozenset tags, Interval ctor semantics (raising `__init__` for
  literals vs Result `.new` for untrusted data), example 04's
  nonexistent DischargeRequest fields -- all reconciled.
- **A-10 (CLOSED, 06 + OPEN-13, D97(d), WO-30): regime tags have
  no boundary channel.** v1 rule pinned in 06 (tags guaranteed by
  claim-kind construction, folded into settings digest) is the
  degenerate case of the regolith-side channel: `DischargeRequest.
  regimes: [str]`, asserted by lowering from claim-kind construction
  / net discipline; signatures declare `required_regimes`; missing
  tag = non-match (honest `no_model`).

## Regolith work orders (regolith side, cycle 20-21; unblocks noted per item above)

Normative text: `lithos:docs/spec/toolchain/20-solver-abstraction.md`
sec. 8 and design-logs `2026-07-07-cycle-2{0,1}.md`.

| WO | contents | unblocks feldspar |
|---|---|---|
| WO-30 | pack contract v2 (D94-D97, one schema bump) | kind re-key (OPEN-6), structured coverage (OPEN-8), payload ports (OPEN-2/11/12, M4/M6), given resolution + regime channel (OPEN-13/A-10) |
| WO-31/32 | fluorite front end + lowering (`flownet` payload) | fluids/prop catalog gets a live source of truth |
| WO-33 | computed fields (D98) | `field` payload producers/consumers (OPEN-14) |
| WO-34 | routed runs (D99) | harness-length givens for elec claims (G42, cuprite `harness:`/`run`) |
| WO-35 | elec pin-mux + real-KiCad gate | regolith-internal, no feldspar dependency |

Dispatch order (D101): WO-29 remainder and WO-30 first (parallel);
then WO-31 -> WO-32; WO-33/35 in the gaps; WO-34 last.

Cycle 21 zero-shot sweep closed the remaining shapes: D102 (temporal
claim-form split, folded into OPEN-11 above), D103 (expression givens
resolve entity-field refs through the entity DB into `Given.refs`),
D104 (name-keyed conformance bounds), D105 (sweep-domain claim lines
+ reduced-tier base API + plan payloads + waiver match-set diffs) --
none of these require feldspar-side redesign beyond what is recorded
above. Standalone affirmation (unchanged): nothing in cycles 20-21
couples feldspar to lithos -- the pack adapter (06) stays one
optional directory, FINV-3 and the OPEN-3 extraction direction are
untouched, and the shared vocabulary (port names, payload kinds,
claim kinds) costs non-lithos consumers nothing since feldspar's
strings are the registry.
