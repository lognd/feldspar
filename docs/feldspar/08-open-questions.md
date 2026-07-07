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
  geometry. RESIDUAL (regolith-blocked): the ref-passing channel --
  `DischargeRequest.inputs` is scalar intervals; parametric
  descriptors and WO-22 realized-geometry refs cannot cross yet. Ask
  recorded regolith-side:
  `../cad/docs/implementation/20-solver-abstraction.md` sec. 7.
  feldspar's parametric families remain the v1 stand-in.

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

- **OPEN-6 claim-kind tiering**: pack models register fea-specific
  claim kinds; competing in one best-path graph with closed-form
  models may require sharing their kinds (D-A). Constructor override
  exists, and the target state (register under the SAME kinds,
  compete on cost) is recorded in 09 sec. 5 / 06; needs a
  regolith-side decision on kind naming + a duplicate-model-id
  ruling for one model under two kinds. Ask recorded regolith-side:
  `../cad/docs/implementation/20-solver-abstraction.md` sec. 7.

- **OPEN-7 SPICE scope**: DECIDED (owner, 2026-07-07), spec homes 03
  and 07. feldspar is the one backend; each namespace is the
  capability (`mech`, `thermo`, `elec`, ...); the electrical numeric
  tier (ngspice) lives inside feldspar's `elec` namespace, not a
  sibling pack; cross-namespace bridges must be minimal-boilerplate
  ordinary solver edges. RESIDUAL: none; regolith/11's illustrative
  `spice.ngspice` naming flagged regolith-side (sec. 7 note).

- **OPEN-8 coverage vocabulary**: regolith `Prediction.coverage` is a
  bare float; grid(k) sweeps (regolith/07 sec. 2 names `corners`,
  `grid(k)`, `analytic`) have no schema encoding. v1 sweeps corners
  only and reports 1.0 (the closed-form precedent). Sweep semantics
  fold into the fidelity-hierarchy direction (OPEN-2). Ask recorded
  regolith-side:
  `../cad/docs/implementation/20-solver-abstraction.md` sec. 7.

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
  (`../cad/docs/implementation/20-solver-abstraction.md` sec. 7
  item 3). RESIDUAL: that regolith channel decision; engine-side
  implementation is 09 M6, gating Phase 3.

- **OPEN-13 given-resolution contract** (new 2026-07-07, friction G2
  from the lithos pressure tests, examples/lithos/README.md):
  obligations carry names (`material: AISI_304`,
  `interface_envelope(...)`); `DischargeRequest.inputs` carries
  scalar intervals; the resolution step between them (property-record
  evaluation over environment corners, envelope load extraction,
  shared port vocabulary) is unspecified regolith-side. feldspar's
  half is DECIDED and recorded in 06 (port vocabulary +
  reject-unresolved rule). Ask recorded regolith-side:
  `../cad/docs/implementation/20-solver-abstraction.md` sec. 7
  item 4. Blocks nothing in M1 (conformance fixtures pre-resolve by
  hand); blocks real `.hem`-to-evidence flows.

- **OPEN-14 zone/station-indexed ports** (new 2026-07-07, friction
  G23/G24 from the regen-engine stress test,
  examples/lithos/regen_engine/README.md): distributed 1-D/2-D
  quantities (wall temperature along the axis, zone-valued fields
  consumed as loads) are not routable ports. INTERIM DECIDED:
  marching solvers expose extremal boundary ports with internal,
  sense-declared reductions (09 sec. 4b); `field` payloads carry
  full results between solvers (FEA thermal load). The REAL design
  -- per-station/zone routable ports -- is coupled to regolith's
  zone vocabulary (regolith/02 sec. 4) and the computed-zone-field
  language ask (regolith sec. 7 item 7). Undesigned; blocks nothing
  before Phase 2's distributed thermal work. EXTENDED 2026-07-07 by
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
- **A-10 (RECORDED, 06 + regolith sec. 7 item 4): regime tags have
  no boundary channel.** v1 rule pinned in 06 (tags guaranteed by
  claim-kind construction, folded into settings digest); the general
  channel joins the given-resolution ask.
