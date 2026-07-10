# WO-23: tributary load paths + resolved-frame consumption (WO-21 completion half)

Status: PARTIAL (2026-07-09 dispatch, branch `wo23-load-paths`) --
landed tributary-transfer load-path resolution, demand extraction,
and a SCOPED `civil.utilization` combined axial-flexure numeric
check, all Python-side in the existing `mech.struct.frame2d` module
(no Rust changes needed -- the tributary/demand/utilization work is
ordinary scalar arithmetic over the solver's existing outputs, not a
new matrix-assembly primitive). Full accounting in "Close-out"
below.
Depends: WO-21 (the direct-stiffness `mech.struct.frame2d` tier,
landed PARTIAL -- read its Close-out first: this WO is its two named
residuals made dispatchable), WO-12 (payload ports). LITHOS side:
the `frame` payload (calcite/03) is unchanged this WO -- consume it
as-is by digest; the lithos section-search engine (its cycle-30
WO-55/56) resolves `section: free` and is NOT this repo's concern
beyond producing resolvable member sections.
Language: Rust formula/matrix homes + Python registration (the
WO-21 split).
Spec: docs/spec (07 mech.struct Phase 6; 09 sec. 4 `frame` kind);
lithos:docs/spec/calcite/03-lowering.md secs. 4-5 (Bearing/
tributary vocabulary + the utilization/deflection obligation
shapes); lithos:docs/workflow/work-orders/WO-48-calcite-lowering.md
close-out (the `frame_load_untargeted` gap this closes, recorded
from the consumer side); lithos design-log 2026-07-09-cycle-31 D173.

## Goal

Member demands become derivable when loads arrive through
`Bearing(tributary=...)` transfer records rather than direct
`on [...]` targets: the load-path analysis walks tributary
transfers to member line/point loads, feeds the landed frame2d
tier, and `civil.utilization`/`mech.deflection` claims over
RESOLVED members (fixed or search-pinned sections) discharge to
real verdicts instead of `frame_load_untargeted` deferrals.

## Deliverables

1. **Tributary resolution**: `Bearing(tributary=<width|area>)`
   transfers resolve to member-distributed loads (deterministic:
   declared tributary geometry x the source load intensity; no
   inferred tributary widths -- a member whose tributary is not
   declared stays honestly deferred with the existing reason).
   Load-path walk is cited evidence content (which transfers, which
   sources, per member).
2. **Demand extraction**: resolved member demands (moment/shear/
   axial envelopes from the frame2d solve under the resolved load
   set) exposed to the utilization check surface WO-21 landed.
3. **Design-check completion (scoped)**: the `civil.utilization`
   numeric half for the benchmark-covered member classes (flexure +
   combined axial-flexure per the memo's cited code equations;
   buckling stays a recorded residual if the calibration tier for
   it is not achievable this dispatch -- name it, never guess it).
4. **Calibration**: the remaining benchmarks-memo closed-form cases
   relevant to distributed/tributary loading; every solver result
   within the memo's stated tolerance or the case is a recorded
   failure, never absorbed.
5. **Conformance run readiness**: a fixture `frame` payload with
   tributary transfers + resolved sections discharging end-to-end
   through the pack protocol (the lithos-side five-design corpus
   run itself is lithos WO-65, not this WO -- but the fixture must
   mirror a real corpus member's shape, cite which).
6. **Docs**: spec 07 Phase 6 updates, WO-21 close-out cross-note,
   this WO's ledger.

## Acceptance criteria

- The fixture payload's utilization/deflection claims produce
  Valid/Violated (not indeterminate) with the load-path walk in
  evidence; removing the tributary declaration reverts to the
  honest deferral.
- Calibration cases green within memo tolerances; failures (if
  any) recorded with numbers.
- No invented physics, no invented tributary geometry, no code
  equations without the memo/citation trail (this repo's standing
  law).
- Repo checks green (its own make/test gates); Status flipped with
  a full close-out ledger.

## Close-out (2026-07-09 dispatch)

**Landed** (`python/feldspar/library/struct.py`,
`tests/unit/test_library_struct.py`):

- `resolve_tributary_loads(transfers, source_intensities, load_case,
  member_lengths_m)`: turns a `Bearing(tributary=width|area)`
  transfer record (calcite/02 sec. 5-6 `std.civil` vocabulary -- a
  companion input the caller assembles from the `structure ...
  transfers:` block, since `FramePayload` itself, calcite/03 sec. 4,
  carries no transfer list) into an ordinary `distributed`-kind
  `FrameLoad` dict, deterministically: `width` tributary x pressure
  intensity = UDL directly; `area` tributary x pressure intensity =
  resultant force, spread over the RECEIVING member's own resolved
  length. Any transfer kind other than `Bearing`, or a `Bearing` with
  no declared `tributary`, contributes NOTHING (the `frame_load_
  untargeted` honest-deferral posture, WO-48 close-out verbatim) --
  no inferred width/area, ever. Every resolved transfer's evidence
  (id, from/to member, tributary kind/value, source intensity,
  derived UDL, citation) is returned alongside the loads and threaded
  into `solve_frame_payload`'s new `load_path` result key.
- `solve_frame_payload` gained optional `transfers`/
  `source_intensities` parameters (default empty, fully backward
  compatible -- every WO-21 test passes unmodified): when supplied,
  tributary-derived loads are merged into the existing `loads` list
  BEFORE the pre-existing load-application loop runs, so there is no
  second load-application code path to keep in sync.
- `extract_member_demands(result)`: reduces the solver's raw local
  6-component member-end-force vector (`[n1, v1, m1, n2, v2, m2]`,
  `crates/feldspar-library/src/mech/frame.rs`'s documented local DOF
  order) to a per-member `{axial, shear, moment}` worst-case envelope
  across both ends (deliverable 2).
- `civil_utilization_h1(axial_demand, moment_demand, axial_capacity,
  moment_capacity)`: the AISC 360-16 Ch. H sec. H1.1 eq. H1-1a/H1-1b
  combined axial-flexure interaction ratio, over caller-supplied
  ALREADY-RESOLVED design capacities (the same "out-of-band resolved
  numbers" seam `section_material`'s `ea`/`ei` already uses) --
  `Valid` iff ratio <= 1.0. This is the flexure + combined
  axial-flexure numeric half named in deliverable 3; buckling
  (lateral-torsional/plate/global) and connection checks (bolt/weld/
  block-shear) are NOT built (see Cuts).
- Fixture (deliverable 5): `test_small_office_g2_ab_girder_
  tributary_fixture_discharges_end_to_end` mirrors the lithos calcite
  corpus's `small_office` second-floor girder `G2_AB`
  (`examples/lithos/systems/small_office/frame.calx`), whose entire
  resolvable demand arrives ONLY via `d2_g2:
  Bearing(tributary=43.2m2) (Deck2 -> G2_AB)` -- the exact
  "girder-under-slab" shape the WO-48 close-out's ARCHITECTURAL
  FINDING names as the unclosed gap. Proves both acceptance-criterion
  halves: Valid/Violated discharge WITH the load-path walk in
  evidence, and reversion to the honest zero-load deferral when
  `tributary` is removed.

**Calibration** (deliverable 4, all green, `_TOL = 1e-3`):

- `test_tributary_width_transfer_reproduces_benchmarks_memo_1_1`:
  a `width`-tributary transfer (pressure=2 kPa x width=5 m = 10
  kN/m) reproduces benchmarks memo 1.1's own w=10 kN/m propped-
  cantilever closed-form result EXACTLY (reactions + fixed-end
  moment) -- proof the tributary-derived load enters the SAME load-
  application path as a direct declaration, not a second, divergent
  one.
- `test_tributary_area_transfer_spreads_resultant_over_member_length`:
  hand-computed arithmetic check (1 kPa x 30 m^2 = 30 kN / 6 m = 5
  kN/m), cross-checked against the same closed-form reaction
  formulas.
- `test_civil_utilization_h1_matches_hand_computed_interaction` /
  `..._violated_over_unity`: hand-computed AISC 360-16 H1-1a/H1-1b
  arithmetic (both branches, both a Valid and a Violated case).
- No calibration failures to record.

**Cuts** (named, not silently dropped):

1. **Section/material CAPACITY resolution** (needed for a real
   `civil_utilization_h1` call, as opposed to proving its arithmetic
   over caller-supplied numbers) -- still the WO-21 close-out's cut
   1, unchanged this dispatch: no registry-resolution channel exists
   in feldspar's payload port surface. `civil_utilization_h1` takes
   ALREADY-RESOLVED `axial_capacity`/`moment_capacity` (the same
   documented seam as `ea`/`ei`), same posture as WO-21.
2. **Buckling** (lateral-torsional, plate, member/frame global) --
   named residual per the WO's own text ("stays a recorded residual
   if the calibration tier for it is not achievable this dispatch");
   not started. No AISC LTB/Cb-curve calibration oracle was built
   this dispatch to check it against.
3. **Connection checks** (bolt/weld groups, block shear) -- not
   started; blocked on cut 1 (needs connection capacity records) and
   out of this WO's named deliverable 3 scope line ("flexure +
   combined axial-flexure").
4. **`Pinned`/`Moment`/`Roller`/`BasePlate` transfers never carry a
   `tributary=` in calcite's vocabulary** (calcite/02 sec. 5-6) --
   `resolve_tributary_loads` only recognizes `Bearing`; this is a
   spec-vocabulary fact, not a scope cut, but recorded so a future
   agent does not "helpfully" widen the kind check without checking
   the language grammar first.
5. **`transfers`/`source_intensities` are NOT part of the
   `FramePayload` schema** (calcite/03 sec. 4 unchanged, per this
   WO's own header -- "the `frame` payload is unchanged this WO").
   They are a companion input this module documents as an
   out-of-band seam, exactly like `section_material`. A caller today
   (the lithos orchestrator, or a future feldspar registration
   direction) must assemble `transfers` from the `structure ...
   transfers:` declaration and `source_intensities` from the
   resolved `loads:` block itself -- NEITHER assembly step is built
   here (out of scope: this WO's `Language:` header is "Rust
   formula/matrix homes + Python registration", i.e. the SOLVER side
   of this seam, not the lithos-side producer of its inputs).
6. **The registered `mech.struct.frame2d` `SolverRegistry` direction
   is untouched** -- it still honestly indeterminates on every frame
   payload (WO-21 close-out cut 1, unchanged); `resolve_tributary_
   loads`/`civil_utilization_h1` are exercised via `solve_frame_
   payload` and standalone, the same posture WO-21 established for
   `solve_frame_payload` itself.
7. **Lithos calcite corpus conformance run** (lithos WO-65, per this
   WO's own header) -- not run here; this WO's fixture proves the
   MECHANISM against a synthetic, fully-resolved mirror of one real
   corpus member (`small_office` `G2_AB`), not the real corpus build.

**LITHOS-SIDE ESCALATIONS** (recorded per dispatch instructions --
frame-payload fields wished for, not invented):

- The `frame` payload (calcite/03 sec. 4) carries no `transfers`
  list of its own; a lithos-side producer wanting to hand this
  module a ready `transfers` array (rather than the caller
  reassembling one from the `structure` declaration on every call)
  would need calcite/03 sec. 4's schema extended with a `transfers:
  [{id, kind, from, to, tributary}]` field, or an adjacent payload
  kind. NOT invented here -- this WO's header states the payload is
  unchanged this WO; recording the ask for whoever owns L4 next
  (lithos WO-65 or a calcite/03 schema-growth WO).
- Section/material CAPACITY records (yield strength, plastic section
  modulus, `phi`-factors) have no resolution channel feldspar-side
  (WO-21 cut 1, restated) -- the SAME registry-resolution channel a
  future WO must build for `ea`/`ei` should carry capacity fields
  too, so `civil_utilization_h1` stops needing an out-of-band
  caller-supplied capacity.

**Gate** (from this dispatch's worktree,
`.claude/worktrees/wo23-load-paths`): `cargo fmt --all -- --check`
clean; `cargo clippy --workspace --all-targets -- -D warnings` clean;
`cargo test --workspace` green (1 extern-C smoke + 0 lib tests
changed -- no Rust touched this WO; the smoke test's first run in a
fresh worktree target dir failed on a "cdylib not yet built" race,
identical to the ordinary `cargo build` -> `cargo test` two-step,
green on rebuild, not a regression); `uv run ruff format --check` /
`ruff check` clean on both touched files; `uv run lint-imports`
contract kept; `uv run ty check` clean on `struct.py`; `uv run
pytest tests/unit/test_library_struct.py -q` 20/20 green (11 WO-21 +
9 WO-23); `uv run pytest tests/ -n auto -m "not regolith and not fea
and not spice"` 346 passed, 1 skipped, 7 collection errors -- the
SAME 7 `tests/regolith/*` pre-existing/environmental errors WO-21's
close-out already documented (nested-worktree relative-path
resolution), not a regression (net +35 passed over WO-21's
documented 311, matching this WO's +9 new tests plus WO-21's own
count drifting with an unrelated intervening dispatch's test
additions -- verified the 7 error module names are identical to
WO-21's list).
