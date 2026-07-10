# WO-21: Phase 6 library wave -- civil/structural (the `frame` consumer)

Status: PARTIAL (2026-07-09 dispatch, branch `wo21-struct`) -- landed a
real, calibrated 2D direct-stiffness `mech.struct` solver over the
`frame` payload (member stiffness assembly with optional moment
releases, reactions/member-end-forces/joint-displacements out).
Validated against 3 of the benchmarks memo's 5 closed-form cases (1.1
propped cantilever, 1.3 two-span continuous beam, 1.5 fixed-fixed
beam). NOT landed this dispatch: member design checks (AISC/Eurocode
utilization, buckling, connections), frame modal, classical
indeterminate calibration tiers, geotech records, and the lithos
calcite corpus conformance run. Full accounting against Deliverables/
Acceptance, with every cut's reason, in "Close-out" below.
Depends: WO-12 (payload ports -- `frame` is a payload kind), WO-14
(contract v2), and LITHOS WO-48 producing `frame` payloads in the
wild (HARD gate: do not dispatch before it lands; the payload
schema is Rust-sourced lithos-side, consumed here by digest).
Language: Rust formula/matrix homes + Python registration
Spec: 07 mech.struct + Phase 6 (added 2026-07-08), 09 sec. 4
(`frame` kind row), lithos:docs/spec/calcite/03-lowering.md secs. 4-5
(the payload fields + obligation shapes this discharges)

## Goal

Calcite's structural claims discharge for real: a direct-stiffness
frame tier over `frame` payloads, member design checks
(`civil.utilization` code packs' numeric halves), deflection/drift/
modal outputs, support reactions feeding bearing-pressure claims.

## Deliverables

- `mech.struct` matrix direct stiffness (truss/beam/frame/grid, the
  07 (r) row): assemble from the payload's joints/members/releases/
  supports; per-case load application; combination sweeps as
  discrete axes (structured Coverage); reactions + member force
  diagrams + displacements out (rank-native where vector, WO-16).
- Member design checks: AISC/Eurocode-shaped interaction
  utilization, lateral-torsional and plate buckling curves (t),
  connection checks (bolt/weld groups, block shear) -- each cited
  to its manual clause, calibrated per 03; registered under the
  claim kinds calcite/03 sec. 5 names.
- Frame modal (Rayleigh/Dunkerley + eigen (r)) backing
  `mech.first_mode(structure)` (the footbridge corpus claim).
- Classical indeterminate methods (slope-deflection, moment
  distribution) as cheap tiers/calibration partners where they
  price in.
- Geotech record consumers the retaining-wall corpus names
  (Rankine/Coulomb active pressure as cited entries; soil records
  are lithos-side registry content -- wrap, never copy).
- Conformance against lithos's calcite corpus obligations
  (bus_shelter through small_office): every structural claim either
  discharges or names its honest gap in the close-out.

## Acceptance

- The small_office frame: utilization sweep over the combination
  set, deflection, drift, bearing reactions -- all discharged with
  stable digests; footbridge first-mode > 3Hz discharges at frame
  tier; planner tier-blind; citations complete.

## Close-out (2026-07-09 dispatch)

**Landed** (`crates/feldspar-library/src/mech/frame.rs`,
`crates/feldspar-py/src/library/mech.rs::mech_frame2d_solve_py`,
`python/feldspar/library/struct.py`,
`tests/unit/test_library_struct.py`):

- A general 2D direct-stiffness frame solver: axial + Euler-Bernoulli
  bending element stiffness, static condensation for an optional
  moment release (hinge) at either end, global assembly/solve
  (Gaussian elimination, partial pivoting), and reaction/member-end-
  force recovery. Rust home per the WO header ("Rust formula/matrix
  homes"); exposed via a thin PyO3 marshalling wrapper (this is a
  variable-size matrix assemble/solve, not a single-formula law, so it
  does NOT fit the sibling formulas' `extern "C"` shape -- see cut
  below).
- `python/feldspar/library/struct.py::solve_frame_payload`: parses a
  `FramePayload`-shaped dict (calcite/03 sec. 4 field list verbatim),
  derives member geometry from the categorical `orientation` field
  (`horizontal`/`vertical` only -- see cut below), applies a
  documented ENGINEERING-DEFAULT (rigid) when a member's `Releases` is
  empty (recorded in the result's `assumptions` list, never silent),
  converts distributed (UDL) member loads to fixed-end forces, and
  calls the Rust solver. Registered as ONE `mech.struct.frame2d`
  `SolverRegistry` direction (`mech.struct` namespace, `frame` payload
  in, `table`-kind result payload out -- reused the existing `table`
  payload kind rather than minting a new `frame_result` kind, since
  `tests/unit/test_payload.py` pins the 09 sec. 4 `PAYLOAD_KINDS` list
  verbatim and a new kind string needs a spec-table change outside
  this WO's scope).
- Validation: 3 of the benchmarks memo sec. 1 closed-form cases (1.1
  propped cantilever UDL, 1.3 two-span continuous beam UDL, 1.5
  fixed-fixed beam central point load) reproduced to +/-0.1%
  (reactions/moments) and +/-0.5% (deflection) as Rust unit tests
  AND as Python `solve_frame_payload` tests over synthetic
  `FramePayload`-shaped fixtures (`tests/unit/test_library_struct.py`).
  A hinge-release sanity check (zero moment recovered at a released
  end) is an additional Rust unit test. PyNite/OpenSeesPy were NOT
  used (module-scope decision: the 3 validated cases have closed-form
  textbook answers, an adequate oracle for this slice's scope; no
  runtime or dev dependency on either was added).

**Cuts** (named, not silently dropped):

1. **Section/material property resolution.** A `RecordRef`'s digest
   (section/material) cannot be turned into a numeric EA/EI here:
   `PayloadResolver` resolves content-addressed PAYLOAD refs, not
   named REGISTRY records, and no such resolution channel exists in
   feldspar's current payload port surface. The registered
   `mech.struct.frame2d` direction therefore honestly
   `SolveError.OutOfDomain`s on EVERY frame payload today (see
   `test_registry_direction_honestly_indeterminates_on_unresolved_refs`),
   even one whose refs carry a real digest -- `solve_frame_payload`
   itself takes already-resolved `{member_id: {ea, ei}}` as a
   documented seam for whoever builds the missing channel. This is
   the single largest blocker to the Acceptance criteria (the
   small_office/footbridge corpus runs need this resolved first) and
   should be its own follow-up WO.
2. **Inclined/point member geometry.** `FrameMember.orientation` is a
   categorical descriptor (`horizontal`/`vertical`/`inclined`/
   `point`), never a resolved angle -- `JointAt` names a grid/level
   DATUM, not a numeric coordinate (calcite/03 sec. 4). A true plane
   truss (benchmarks memo 1.4, diagonal members) or a portal-frame
   sway case (1.2, needs the actual column/beam layout) cannot be
   assembled from the payload alone. `solve_frame_payload` honestly
   errors on `inclined`/`point` members. This narrows real coverage
   to orthogonal (beam/column) frames until a resolved-coordinate
   payload channel lands upstream (lithos-side).
3. **Support-fixity default.** An empty `Support.fixity` list (the
   payload's "unresolved" state) is left as an honest
   `SolveError.OutOfDomain` -- unlike member releases (where "rigid"
   is a universally-safe default for continuous framing), there is no
   single safe default across pin/fixed/roller, so this never guesses
   (per the WO's own text).
4. **Member design checks** (AISC/Eurocode interaction utilization,
   lateral-torsional/plate buckling curves, bolt/weld/block-shear
   connection checks) -- blocked on cut 1 (needs section CAPACITY,
   not just EA/EI). Not started.
5. **Frame modal** (Rayleigh/Dunkerley + eigen), backing
   `mech.first_mode(structure)` -- not started; the footbridge corpus
   claim is unreached.
6. **Classical indeterminate calibration tiers** (slope-deflection,
   moment distribution) -- not started. The cycle-28 v2 research memo's
   fixed-base portal cross-check (slope-deflection oracle) was not
   built; the direct-stiffness solver's correctness instead rests on
   the 3 closed-form benchmark cases above.
7. **Geotech record consumers** (Rankine/Coulomb active pressure for
   the retaining-wall corpus) -- not started.
8. **`civil.utilization`/`story_drift`/`bearing_pressure`/`first_mode`
   claim kinds** -- not registered; the one direction produces raw
   displacements/reactions/end-forces only (module docstring "SCOPE").
9. **Lithos calcite corpus conformance run** (bus_shelter through
   small_office) -- not run; blocked on cuts 1, 2, and 4-8.
10. **3D/grid elements, shear deformation (Timoshenko), the
    benchmarks memo's cases 1.2 (portal sway) and 1.4 (plane truss)**
    -- not built/validated (1.2 needs resolved member layout beyond
    orientation categories; 1.4 needs resolved angles, cut 2).

**Gate**: `cargo fmt --all -- --check`, `cargo clippy --workspace
--all-targets -- -D warnings`, `cargo test --workspace` (31 lib tests
+ 1 extern-C smoke, all green, including 5 new `mech::frame` tests),
`uv run ruff format --check`/`ruff check` (clean), `uv run
lint-imports` (contract kept), `uv run pytest tests/ -n auto -m "not
regolith and not fea and not spice"` (311 passed, 0 failed -- the 6
`tests/regolith/*` collection errors are PRE-EXISTING/environmental:
identical on the unmodified worktree before this dispatch, caused by
the `regolith` extra's `../lithos` relative path not resolving from a
nested `.claude/worktrees/` checkout, not a regression). `make
typecheck` (`ty`) has 9 pre-existing `regolith.*`-unresolved-import
diagnostics in this worktree for the same reason (verified via `git
stash` against the unmodified branch tip, which has 10 -- one fewer
after this change, not more); `python/feldspar/library/struct.py`
itself contributes zero typecheck diagnostics.

**WO-23 cross-note (2026-07-09)**: the two named residuals this
close-out flagged as "a follow-up WO should pick up" -- tributary/
`on [...]` load-path resolution (cut named inline in
`solve_frame_payload`'s `frame_load_untargeted`-shaped error) and a
first `civil.utilization` numeric slice -- were picked up by WO-23
(its own close-out has the full accounting). Cut 1 (section/
material CAPACITY resolution) is UNCHANGED and remains the largest
open blocker for both WOs alike.
