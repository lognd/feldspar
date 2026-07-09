# The feldspar pressure fixtures -- geometry + edge-case friction log

Target-syntax lithos projects originally written IN THE FELDSPAR
REPO (its `examples/lithos/`) to pressure the solver seam, each
annotated with `G-nn` friction anchors. MIGRATED HERE cycle 27
(D148, owner directive: one corpus, single-sourced in lithos and
mirrored into feldspar's `examples/lithos/`). During migration every
file was brought to current spec (the draft-era `mech.max`/
`.max`/`.min` spellings became sense-driven `peak`, two claims
adopted the landed D98 compute-field forms, layout fixed) -- the
whole set now checks with ZERO diagnostics. The G-nn logs below and
in each project README are feldspar's friction history, kept
verbatim except for RESOLVED annotations; `sec. 7` in them means
`feldspar:docs/spec/08-open-questions.md`'s regolith-ask table and
`lithos:docs/spec/toolchain/20-solver-abstraction.md` sec. 7.

New homes:

- `tracks/hematite/manifold.hema` -- the direct hit: thick-wall
  cylinder, fat + thin margin through ONE claim kind, material
  records, affine units.
- `tracks/hematite/sensor_boom.hema` -- the geometry gauntlet:
  bent-flange cantilever with a hole in the root region, interface
  loads at mid-span, a modal claim.
- `tracks/cuprite/psu_enclosure.cupr` -- cross-domain: dissipation
  -> enclosure air rise -> derating; swept efficiency;
  ripple-in-band.
- `systems/reaction_wheel/` -- the big mixed project (4 files);
  findings G13-G21 in its README.
- `systems/regen_engine/` -- the cross-domain torture test
  (regen-cooled thruster, 5 files): strong coupling, distributed
  fields, fluid circuits, empirical stability; findings G22-G33 in
  its README -- including the two deepest LITHOS gaps ever found
  (fluid-circuit language -> fluorite; computed zone fields ->
  D98/WO-33; both since resolved).
- `systems/dune_buggy/` -- the whole-vehicle stress test (26 files,
  all four language tracks): findings G34-G43 in its README. (The
  old SOLVER-TRACE.md route/gate mapping was retired at migration,
  owner directive -- every gate it tracked is now a scheduled
  feldspar WO; git history keeps it.)

## Findings (each fixed item is folded into the cited spec section
in this same change; open items carry their blocker)

- **G1 (FIXED, 09 sec. 4a + 02): idealization is a solver.** Real
  claims are about realized geometry ("the bent flange's tip"); no
  closed form consumes that. The mapping real-geometry ->
  parametric-family-scalars is an ordinary registered edge (an
  ABSTRACTION SOLVER): geometry payload in, family scalar ports out,
  with a declared conservative eps -- idealization error IS that
  edge's model error, so the 02 error split needs no third term --
  and a domain over geometry FEATURES (solid root region, aspect
  ratio, hole clearance). Payload domains are checked at EXECUTION
  (a box over scalars cannot express "no hole within 15mm of the
  root"); an out-of-domain payload is a SolveError value that the
  fallback reroute (04) turns into "try the next tier". Planning is
  therefore optimistic over abstraction edges; determinism is
  unaffected (same payload -> same check result).
- **G2 (OPEN, regolith ask, sec. 7 item 4): given-resolution
  contract.** Obligations carry `material: AISI_304` (a NAME);
  `DischargeRequest.inputs` is `Mapping[str, Interval]` (verified in
  `harness/model.py`). SOMETHING must resolve records -> scalar
  interval ports before the request, and the resolution rules
  (which corner of T_env, which record fields) are unspecified
  regolith-side. feldspar declares its required port vocabulary (06);
  the resolution step is regolith's.
- **G3 (FIXED, 02): affine units.** `degC` is scale AND offset; the
  WO-02 conversion table gains an offset column, offsets are legal
  at ingest/print ONLY, and offset units are banned inside derived/
  compound units (`K/W` fine, `degC/W` rejected at table load).
- **G4 (FIXED, 03): sense-aware conservatism.** Interface loads land
  mid-span; families have fixed load cases. An envelope/abstraction
  edge that relocates a load (to the tip) is conservative for UPPER
  deflection/stress claims and WRONG for lower-bound claims
  (stiffness, first_mode). Such edges declare which claim sense
  their conservatism serves; the opposite sense is out-of-domain.
- **G5 (FIXED, 07 materials + 06): property records are table
  solvers.** `E: f(T) interval` lowers to a table-solver edge
  `thermo.temperature -> mech.material.youngs_modulus`, so the
  ordinary corner discipline handles the T_env worst corner; material
  ports are OUTPUTS of record edges, not free givens.
- **G6 (confirms OPEN-6)**: `hoop_fat` and `hoop_thin` are ONE claim
  kind at two margins; the tier decision is entirely margin-driven --
  unified claim kinds are load-bearing, not cosmetic.
- **G7 (fixture requirement, WO-09/02-edge-cases)**: the
  hole-in-root-region part must produce (a) idealization edge
  out-of-domain, (b) reroute to FEA-on-realized-geometry, (c) TODAY
  -- with the payload channel unbuilt -- an honest indeterminate
  NAMING the missing channel. Never a silently-wrong cantilever
  answer. This exact fixture is a conformance test.
- **G8 (confirms OPEN-11)**: `first_mode` and `rms(band)` claims give
  M6 its concrete fixtures; no new design needed.
- **G9 (fixture, Phase 2)**: convection correlations' published
  Ra/Re ranges as Domains, with conduction-only conservative
  fallthrough -- tier competition inside one namespace.
- **G10 (confirms OPEN-8)**: the efficiency `forall` is ONE swept
  obligation whose grid coverage the bare-float
  `Prediction.coverage` cannot state.
- **G11 (FIXED, 02): dimensionless ports.** Efficiency/ratio ports
  need unit `"1"` (dimensionless) in the table; `%` is an ingest
  alias for 0.01.
- **G12 (FIXED, implementation/02-edge-cases.md + 03/04): the
  numeric edge-case matrix.** Notables that changed spec text:
  `SolveError.NonFinite` (a solver returning NaN/inf is caught by
  the executor, value not crash); target-already-known returns a
  ZERO-STEP Route (value = known interval, eps 0, cost 0), not an
  error; `eps_budget <= 0` and negative `cost` are request/
  registration errors. Full matrix with WO assignments in
  `docs/spec/toolchain/02-edge-cases.md`.
