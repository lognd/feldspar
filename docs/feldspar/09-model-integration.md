# 09 -- Model integration: one hierarchy from table lookup to FEA

One sentence: FEA -- and SPICE, and every future discretized solver --
is an ordinary model at a far point on the granularity/expense axis,
so this doc makes granularity, expense, and accuracy first-class
searchable metadata and plans the integration in milestones; dispatch
never special-cases a tier.

This is the full plan the 06 pack contract and the 07 capability map
hang off: 06 is the regolith-facing slice of it, 07 is the content
that flows through it.

## 1. The axis, formalized

A solver's **tier** is descriptive metadata on `SolverInfo`:

```
tier: table | closed_form | reduced | discretized | coupled
```

- `table` -- interpolated lookups (property tables, Kt charts,
  friction-factor charts digitized).
- `closed_form` -- algebraic formulas (the 07 catalog's bulk).
- `reduced` -- reduced-order numerics: matrix stiffness, lumped
  networks, modal superposition, eigen solves.
- `discretized` -- meshed/stepped field or circuit solves: FEA (ccx),
  SPICE (ngspice), FD conduction.
- `coupled` -- multiphysics co-solves via CoupledGroup (sec. 4b).

**Rule: dispatch never branches on tier.** The planner reads only
cost, accuracy, and domain (04); tier exists for logs, justification
reports, calibration pairing (a tier calibrates against a higher
tier), and regolith's tier vocabulary at the pack boundary. This is
the "FEA is just a model" principle made enforceable: a test asserts
the planner is tier-blind.

Exactly four things actually vary along the axis, and each has one
mechanism:

| varies | mechanism |
|---|---|
| cost magnitude | `cost` scalar, later `cost(eps)` curve (sec. 3) |
| accuracy source | declared ceiling vs measured per-solve (sec. 2) |
| settings richness | the one settings-digest discipline (03) |
| input payloads | payload ports (sec. 4) |

Everything else -- registration, domains, corner sweeps, digests,
caching, rerouting, citations -- is identical by construction.

## 2. Accuracy: declared ceilings, measured eps, one contract

- Every solver declares an `Accuracy` ceiling per output, backed by
  calibration citations (03). The planner searches on ceilings.
- A **measuring** solver (FEA via Richardson, 05; any solver with an
  internal error estimator) replaces the ceiling with its realized
  eps at execution. Realized eps above the ceiling is `BudgetExceeded`
  -- the ceiling is a promise, not a hint.
- Closed-form and table solvers are the degenerate case: realized
  eps == declared eps. One accumulation rule handles both (02); there
  is no "FEA path" through the error math.

## 3. Granularity: refinement is INSIDE one solver

Rejected: registering `fea_coarse` / `fea_fine` as separate solvers.
That multiplies registry rows, splits calibration evidence, and makes
the planner enumerate what is really one knob. Instead:

- A discretized solver owns a deterministic **refinement ladder**
  (characteristic length h, h/2, h/4, ...; timestep; mesh order). The
  ladder policy folds into the settings digest.
- **Budget-seeking** (`eps_seeking=True` on `SolverInfo`): the
  executor passes the remaining eps budget; the solver climbs the
  ladder until its measured eps fits or a declared refinement limit
  is hit (then an honest error carrying the best eps achieved --
  feeding regolith's "what would resolve it" diagnostic family,
  regolith/07 sec. 4). The climb is deterministic: same budget, same
  ladder, same stop.
- **Cost curves**: a budget-seeker declares cost at sampled eps
  points; the planner interpolates conservatively. v1 keeps the
  scalar `cost` (a one-point curve); the curve is additive schema,
  not a redesign.
- **Per-rung caching**: the solve cache (04) keys each rung's solve
  independently (the rung's settings are in the digest), so an
  h-and-h/2 Richardson pair is two cache entries -- a later request
  with a looser budget reuses the h solve and skips h/2, and the dev
  loop pays each mesh once ever.

## 4. Payload ports: one mechanism for geometry, spectra, and fields

Ports today carry uncertain scalars (02). The integration plan adds
**payload ports**: ports whose value is a content-addressed,
hash-pinned payload rather than a number. Declared payload kinds:

```
geometry.parametric   frozen pydantic family params (05 geometry.py)
geometry.realized     STEP ref + topology summary (regolith WO-22 record)
layout.realized       elec placed/routed board content: board outline
                      ref, placements, routed segments, copper summary,
                      .kicad_pcb content hash (regolith WO-24/WO-42
                      record, AD-25)
mesh                  MeshData digest (05 mesh.py output)
table                 interpolation table ref (property data)
spectrum | profile | mask   regolith/02 sec. 5 time/frequency objects
field                 discretized result field (nodal/element arrays)
flownet               fluid-circuit topology (fluorite lowering,
                      ../lithos/docs/fluorite/03-lowering.md)
plan                  manufacturing plan artifact (planner solvers,
                      10 sec. 5)
```

- Payload ports type-check by KIND exactly as scalar ports check by
  unit: connecting `mesh` to `spectrum` is a registration error.
- Payloads are NOT an expensive-tier mechanism (friction G14): Miner
  damage, bearing L10, and Miles' equation are closed-form solvers
  consuming `spectrum`/`profile` payloads. Any tier reads payloads.
- Payloads are content-addressed, so digests, caching, determinism,
  and evidence hashing extend without new rules -- a payload in a
  digest is its hash.
- Uncertainty does not propagate THROUGH a payload; a payload is
  exact by reference. Spread enters where scalars enter (loads,
  material properties, dimensions of parametric families).

Two consequences that pay for the mechanism:

- **Meshing becomes a graph step**: `geometry.* -> mesh` is a solver
  direction, so one mesh feeds static, modal, and thermal solves (the
  vibration tier reuses the static mesh for free), and mesh settings
  stop being private to one solver.
- **This is OPEN-2, OPEN-11, and OPEN-12's carrier in one design**:
  realized geometry, parametric descriptors, spectra/masks for
  time-domain claims, and result fields all cross the graph -- and
  the regolith boundary, on the D96 `DischargeRequest.payloads`
  channel (WO-30) -- as the same kind of thing.

### 4a. Abstraction solvers (friction G1)

The bridge from real geometry to the parametric families is itself a
solver: an **abstraction edge** consumes a geometry payload and
produces family scalar ports (`geometry.realized ->
mech.geom.cantilever.*`). Three rules make it safe:

- Its declared eps IS the idealization error (02) -- conservative,
  cited, calibrated like any accuracy claim (compare idealized vs
  FEA-on-real over sampled geometry, 03 harness).
- Its domain is over geometry FEATURES (solid root region, aspect
  ratio limits, hole clearances) and is checked at EXECUTION -- a
  scalar box cannot express "no hole within the root band". An
  out-of-domain payload is a `SolveError` value; the fallback
  reroute (04) then tries the next tier (FEA on the realized ref).
  Planning is optimistic over abstraction edges; determinism holds
  (same payload digest -> same check result).
- It is usually one-sided: declare `conservative_for` (03) so an
  envelope idealization can never serve the wrong claim sense.

This is how `sensor_boom.hema`'s flange claim resolves cheaply when
the geometry is clean and escapes to FEA when the hole invades the
root region (fixture G7) -- with no claim naming any solver.

### 4b. Coupled groups (friction G22; tier="coupled" defined)

Strong two-way coupling (the regen-wall loop: hot-gas convection <->
wall conduction <-> coolant convection <-> bulk rise) cannot be an
edge ordering, and G20's envelope trick is uselessly conservative for
distributed couplings. The design (target shape:
`examples/solvers/06_coupled_groups.py`; scheduled M8):

- A **CoupledGroup** = member solver ids + a deterministic
  fixed-point closure (fixed damping, fixed iteration order, tol/
  max_iter in the settings digest), registered as ONE composite
  SolverInfo over the group's BOUNDARY ports. The internal cycle
  never enters the graph: the planner's world stays a DAG, and
  cyclic port dependence among ordinary solvers remains a
  registration error.
- **Composite accuracy is calibrated as a unit.** Member eps values
  do not compose linearly through a fixed point, so deriving group
  eps from members is forbidden -- as is EXACT. The closure residual
  at convergence charges into the realized eps (SolveOutput
  measured_eps channel).
- Non-convergence is `SolveError.NoConvergence` (M8 adds the
  variant) -- a value; fallback rerouting and honest indeterminate
  apply unchanged.
- Corner sweeps run at the group boundary (the loop solves once per
  corner); `conservative_for` applies to the composite.

Interim reductions (friction G24): 1-D distributed solvers (station
marching) expose EXTREMAL boundary ports (max wall temp, throat
flux) with the reduction internal and sense-declared; per-station
routable quantities wait on zone/station ports (OPEN-14).

Non-scalar QUANTITIES (vectors, tensors -- OPEN-12) are not payloads:
they are ranked scalar bundles with per-component uncertainty, native
in the port model (02, non-scalar quantities). The rule of thumb:
if it has uncertainty, it is a ranked quantity; if it is exact by
reference, it is a payload.

## 5. The pack seam (what 06 inherits from this plan)

- **Claim kinds** (OPEN-6, DECIDED D94/WO-30): feldspar's numeric
  models register under the SAME claim kinds as regolith's
  closed-form tier and compete purely on cost in the one best-path
  graph (regolith D-A) -- kinds are vocabulary-owned, one model may
  register under multiple kinds (per-kind duplicate rule). The
  `claim_kind` constructor override is the interim until WO-30 ships
  and flips the default.
- **Margin-driven adaptive refinement**: `DischargeRequest` carries
  the claim's limit, so the pack model translates the margin needed
  into an eps budget and drives a budget-seeking solver (sec. 3)
  against it: refine until `value + eps` closes the claim or the
  ladder tops out -- then honest indeterminate stating the eps
  achieved vs needed. Accuracy stays automatic (regolith/07 sec. 4:
  no fidelity knobs); the knob-turning is inside the model, driven by
  the margin, deterministically.
- **Coverage** (OPEN-8, DECIDED D95/WO-30): sweep results map onto
  regolith's structured `Coverage { axes: [CoverageAxis], fraction }`
  (per-axis `domain`/`method: corners | grid{k per axis} |
  enumerated | analytic | monotone`); until WO-30 ships, corners +
  bare `1.0`, the closed-form precedent.
- **Tier reporting**: the pack maps `tier` metadata onto regolith's
  closed-form/reduced/full ladder in evidence, so regolith users read
  one vocabulary.

## 6. Execution resources (DECIDED 2026-07-07, closes OPEN-9)

Parallelism is decoupled from expense: if the machine has the cores,
any independent work may use them -- corner solves, refinement-ladder
rungs, independent route steps, calibration sweeps. Constraints, in
priority order:

1. **Determinism**: assembly is order-deterministic (sorted corner
   order, sorted digest folds -- never arrival order). The parallel
   and serial paths must be bit-identical; the determinism suite runs
   both.
2. **Portability**: pure-Rust threading (std / rayon) in
   `feldspar-core`, no platform-specific APIs; external tools keep
   their own determinism guards (`OMP_NUM_THREADS=1` for ccx stays --
   ccx-internal threading changes summation order, which parallelism
   across ccx RUNS does not).
3. **Fallthrough**: a serial path always exists on every platform
   (thread count 1 is a configuration, not a build variant).

## 7. Calibration closes the loop, bidirectionally

- Downward: closed-form oracles validate discretized implementations
  (05 known-answer discipline) -- "is the FEA right?"
- Upward: discretized tiers calibrate closed-form and table ceilings
  over sampled domains (03 harness) -- "is the formula's declared
  eps honest outside the textbook regime?"

Both directions emit content-addressed calibration runs cited in
`SolverInfo.citations`, so every tier's accuracy claim is evidence,
and the 07 catalog grows with its defensibility built in.

## 8. Milestones

Each becomes a WO in `implementation/` when scheduled; only M1 is
committed scope now (WO-27 / Phase 1).

- **M1 (v1)**: scalar ports; two FEA directions with declared
  ceilings + measured Richardson eps; tier metadata present and
  dispatch-blind by test; serial execution.
- **M2**: payload ports (parametric geometry + mesh kinds);
  mesh-as-a-graph-step; per-rung solve caching.
- **M3**: `eps_seeking` + cost curves; margin-driven adaptive
  refinement in the pack models.
- **M4** (regolith-gated, unblocked by WO-30/D94-D97): claim-kind
  unification, structured coverage encoding, `DischargeRequest.
  payloads` ref channel across the boundary.
- **M5**: parallel corners/rungs per sec. 6; determinism suite runs
  serial and parallel paths.
- **M6**: structured ports (spectrum/profile/mask payloads + ranked
  quantities) unblocking the vibration tier (07 Phase 3); ccx modal
  reuses the M2 mesh step.
- **M7**: second discretized family (ngspice under `elec`)
  instantiating the same pattern -- the proof the plan generalizes.
- **M8**: CoupledGroup (sec. 4b): composite registration, closure
  driver, NoConvergence variant, unit-calibration rule enforced
  (EXACT rejected for coupled tier); the regen-wall loop
  (`examples/solvers/06`) is the acceptance fixture.
- **M9**: solver-pack plugin system + conformance kit (10 sec. 3):
  `feldspar.solver_packs` entry point, sorted composition,
  `feldspar.testing.assert_solverpack_conforms`, namespace
  etiquette checks; acceptance = an out-of-repo toy pack passing
  the kit from its own CI.
- **M10** (owner-decided direction 2026-07-08, spec home 11 /
  OPEN-15): the symbolic core -- symbolic Relation declarations
  with derived directions, symbolic domain predicates (boxes
  derived, predicates carried), derivation-aware `explain()`;
  WO-11, dispatch gated on the engine-home residual (11 R1).
