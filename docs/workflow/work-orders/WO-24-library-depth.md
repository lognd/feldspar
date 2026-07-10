# WO-24: solver library depth wave (the AD-34/D174 program, feldspar half)

Status: PARTIAL (2026-07-10 dispatch #6, branch `cycle33-pack-exposure`
-- cycle-33 PACK EXPOSURE wave: exposed 6 previously-internal-only
WO-24 directions (member capacity F2/E3/Euler, VDI 2230 bolt load
factor, weld utilization, bearing L10h) as `feldspar.pack` regolith
`Model`s via a new `_ClosedFormEngineModel` base; see its own close-out
at the bottom of this file. No new WO-24 deliverables (4/5/7)
attempted this dispatch.) (2026-07-10 dispatch #5, branch `wo24-thermal`,
worktree `.claude/worktrees/wo24-thermal`) -- landed deliverable 0
(dispatch #1, member capacity forms), deliverable -1 (dispatch #2,
`docs/benchmarks-memo.md` consolidation), deliverable 1 (dispatch
#3, bolted joints, VDI 2230 + Shigley/AISC elastic bolt-group
distribution), deliverable 8 (dispatch #3, Euler elastic column
buckling, narrow slice), deliverable 2 (dispatch #4, fillet weld
groups, Shigley/Blodgett elastic line method), deliverable 3
(dispatch #4, bearing life, ISO 281:2007 basic L10/L10h over
`std.bearings`-shaped rating records), and deliverable 6 (this
dispatch: lumped-capacitance thermal transient tier -- step
response, time-to-threshold, and periodic duty-cycle peak
temperature, Incropera ch. 5, with an in-function Bi < 0.1 honesty
gate). Deliverables 4-5, 7 RECORDED and CUT AGAIN this dispatch (not
started; out of this dispatch's exactly-one-deliverable scope, per
dispatch instruction). Deliverable 9 (ledger) done for the landed
slices.
Depends: WO-21/23 (struct tier), WO-20 (thermal-fluids wave),
WO-11/22 (symbolic core -- validity-domain predicates for every new
model), the benchmarks memo (every calibration case cites it or a
new memo section added in the same change).
Language: Rust formula/matrix homes + Python registration (the
standing split).
Spec: docs/spec 07 (library phases) + 10 (solver metamodel);
lithos:docs/spec/toolchain/32-stdlib-depth.md sec. 3 (the NORMATIVE
target list for this WO); lithos design-log 2026-07-09-cycle-31
D174.

## Goal

The solver library grows to the charter sec. 3 set, each model
under the standing law: memo-cited equations, calibration cases
within stated tolerances, symbolic validity-domain predicates, no
invented physics.

## Deliverables (each = model + citations + calibration + predicates + registration)

0. Member capacity forms (added per lithos D176, closing the
   WO-21/23 cut-1 seam consumer-side): AISC 360-16 F2 compact-
   section flexural yield (Mp = Fy*Zx, phi_b) and E3 axial
   yield/flexural-buckling basic forms, over caller-supplied section
   properties (Zx/A/r from record data) + material Fy -- cited,
   calibrated against hand-computed cases, validity predicates
   narrow (compact, braced; LTB stays the recorded WO-23 cut).
1. Bolted joints: VDI 2230-class single-bolt tier (preload, load
   factor, working-load margins) + bolt-group shear/tension
   distribution (elastic method).
2. Weld groups: elastic line method statics (fillet groups under
   in-plane + out-of-plane loading).
3. Bearing life: ISO 281 L10 form over std.bearings-shaped rating
   records.
4. Shaft/member fatigue tier: Goodman/Soderberg mean-stress with
   CITED modifying-factor tables; validity predicates narrow
   (steel, HCF) -- honesty over reach.
5. Beam/plate deflection catalog completion: the remaining Roark
   cases the memo lists as gaps.
6. Lumped thermal transient tier (RC-network step/duty responses)
   extending the WO-20 wave.
7. Drive sizing checks: belt (GT2 class tooth shear/tension
   ratings) + leadscrew (torque/efficiency/critical speed).
8. Column buckling completion (the WO-21 residual, if WO-23 did
   not absorb it -- coordinate via its close-out).
9. Docs: spec 07 phase tables, memo additions with sources, full
   close-out ledger.

## Acceptance criteria

- Every model: >= 1 memo calibration case green within stated
  tolerance; validity predicates reject out-of-domain inputs with
  the standard indeterminate reason; registered through the pack
  protocol; NOTHING uncited.
- A model that cannot be calibrated this dispatch is RECORDED and
  cut, never landed uncalibrated.
- Repo gates green; Status flipped with the ledger.

## Close-out (2026-07-09 dispatch)

**Landed** (`python/feldspar/library/member_capacity.py`,
`tests/unit/test_library_member_capacity.py`, wired into
`python/feldspar/pack/models.py::_engine_registry`):

- `mech.member.flexural_yield_capacity_f2`: AISC 360-16 sec. F2.1 eq.
  F2-1 (`phi_b*Mn = phi_b*Fy*Zx`), `phi_b = 0.90` (sec. F1) baked in
  as a code constant (not a port -- an engineering coefficient, not
  a measured quantity). Registered `@solver` pure-map direction,
  `mech.member` namespace, `Domain` box tags `{"compact", "braced",
  "steel"}` (a caller-asserted precondition this form cannot itself
  verify -- no Lb/Lp input exists on this port set; lateral-
  torsional buckling, sec. F2.2, stays the recorded WO-23 cut,
  unchanged).
- `mech.member.axial_yield_buckling_capacity_e3`: AISC 360-16 sec. E3
  eq. E3-1 (`Pn = Fcr*Ag`), eq. E3-4 (`Fe = pi^2*E/(KL/r)^2`), and
  the eq. E3-2/E3-3 branch selected by the sec. E2 User Note boundary
  (`KL/r <= 4.71*sqrt(E/Fy)`, equivalently `Fy/Fe <= 2.25`),
  `phi_c = 0.90` (sec. E1) baked in. Same registration shape; `Domain`
  box tags `{"steel", "no_slender_elements"}`, `KL/r` bounded to
  `[1, 200]` (sec. E2 User Note upper bound); torsional/flexural-
  torsional buckling (sec. E4) and slender-element reduction (sec.
  E7) NOT evaluated (named cut).
- Both close the WO-21/23 "cut 1" seam CONSUMER-side: `civil_
  utilization_h1` (`library/struct.py`) already took already-resolved
  `axial_capacity`/`moment_capacity` as caller-supplied numbers --
  these two directions are a real, cited, calibrated PRODUCER of
  those numbers (over caller-supplied Zx/Ag/E/KL-r, not a section-
  registry digest -- the registry-resolution channel itself remains
  the WO-21 close-out's unresolved cut 1, unchanged; feldspar's
  payload port surface still has no digest -> named-record channel).

**Calibration** (all green, hand-computed against AISC 360-16
directly -- no benchmarks-memo section exists for member design
checks, per deliverable 0's own text ("calibrated against hand-
computed cases"), unlike deliverables that name the memo explicitly):

- `test_flexural_yield_capacity_f2_matches_hand_computed`: Fy=345e6
  Pa (~50 ksi), Zx=1.639e-3 m^3 (~100 in^3) -> `phi_b*Fy*Zx` =
  508,909.5 N*m, exact arithmetic (tol rel=1e-9, the form is a pure
  product, no approximation).
- `test_axial_capacity_e3_inelastic_branch_matches_hand_computed`:
  Fy=345e6 Pa, Ag=0.01 m^2, E=200e9 Pa, KL/r=80 (inelastic branch,
  eq. E3-2 governs, `Fy/Fe=1.12 <= 2.25`) -> `phi_c*Pn` ~ 1.943e6 N,
  hand-derived via `Fe`/`Fcr` step-by-step, cross-checked against the
  function's own output (tol rel=1e-9 function-vs-hand-arithmetic,
  rel=2e-3 hand-arithmetic-vs-rounded-reference-value).
- `test_axial_capacity_e3_elastic_branch_matches_hand_computed`:
  same section, KL/r=150 (elastic branch, eq. E3-3 governs,
  `KL/r=150 > 4.71*sqrt(E/Fy)=113.4`) -> `phi_c*Pn` ~ 692,458 N, same
  cross-check shape. Both E3 branches exercised (deliverable 0's own
  text: "yield/flexural-buckling").
- Non-positive-input `OutOfDomain` cases for both forms (honest
  refusal, not a fabricated verdict).
- No calibration failures to record.

**Cuts** (named per the WO's own standing law -- "RECORDED and cut,
never landed uncalibrated" -- none of the following were started
this dispatch; capacity, not physics, is the limiter):

1. **Deliverable 1 (bolted joints)** -- not started. VDI 2230-class
   preload/load-factor tier and elastic-method bolt-group shear/
   tension distribution both need a fresh citation trail and
   calibration oracle this dispatch had no time budget for.
2. **Deliverable 2 (weld groups)** -- not started. Elastic line
   method statics for fillet groups; same reason.
3. **Deliverable 3 (bearing life)** -- not started. ISO 281 L10 form
   over `std.bearings`-shaped rating records; blocked further on the
   same named registry-resolution gap deliverable 0 works around
   (rating-record digest -> numeric C/P has no channel).
4. **Deliverable 4 (shaft/member fatigue)** -- not started.
   Goodman/Soderberg mean-stress tier with cited modifying-factor
   tables (surface finish, size, load, reliability -- each its own
   citation and calibration case); the WO's own text flags this as
   the deliverable most exposed to "honesty over reach" (steel/HCF
   only) and it was not attempted rather than rushed.
5. **Deliverable 5 (beam/plate deflection catalog completion)** --
   not started; the "remaining Roark cases the memo lists as gaps"
   requires locating and enumerating that memo's gap list first, not
   done this dispatch.
6. **Deliverable 6 (lumped thermal transient tier)** -- not started;
   extends the WO-20 thermal-fluids wave, a separate citation/
   calibration surface (RC-network step/duty responses) untouched.
7. **Deliverable 7 (drive sizing checks)** -- not started (belt
   GT2-class tooth shear/tension, leadscrew torque/efficiency/
   critical speed).
8. **Deliverable 8 (column buckling completion)** -- not started.
   NOTE: `mech.member.axial_yield_buckling_capacity_e3` (deliverable
   0, landed) already covers the AISC 360-16 E3 flexural-buckling
   basic form (`Fe`, the two `Fcr` branches) that a "column buckling"
   deliverable would likely have wanted as its core -- a future
   dispatch closing deliverable 8 should read this module first
   rather than re-deriving E3, and should scope itself to what E3
   does NOT cover (sec. E4 torsional/flexural-torsional, sec. E7
   slender elements, and any WO-21-specific "column buckling"
   residual language its own close-out used that is narrower or
   wider than sec. E3).

**LITHOS-SIDE NOTE**: nothing new escalated this dispatch beyond
what WO-21/23 already recorded (section/material CAPACITY
resolution remains the standing largest blocker for the whole
`mech.struct`/`mech.member` surface).

**Gate** (this worktree, `.claude/worktrees/wo24-library`):
`cargo fmt --all -- --check` (clean, no Rust changed this dispatch).
`uv run ruff format --check .` / `uv run ruff check .`: the two new/
changed files (`member_capacity.py`, `test_library_member_capacity.py`,
`pack/models.py`) are clean; the tool reports pre-existing failures
in unrelated files (`examples/solvers/*.py`, `scripts/*.py`,
`tests/unit/test_plan_over_library.py`) identical before and after
this change (not a regression, not touched this dispatch).
`uv run lint-imports`: 1 contract kept, 0 broken. `uv run ty check`:
230 diagnostics before AND after this change (verified via `git
stash`/`git stash pop` in this worktree) -- all pre-existing
`regolith.*`-unresolved-import diagnostics from the nested
`.claude/worktrees/` checkout's relative-path resolution gap (WO-21/
23 close-out precedent); `member_capacity.py` itself contributes
zero new diagnostics. `uv run pytest tests/ -n auto -m "not regolith
and not fea and not spice"`: 352 passed, 1 skipped, 7 errors -- the 7
errors are the documented pre-existing `tests/regolith/*` collection
failures (`ModuleNotFoundError: No module named 'regolith'`, the
same nested-worktree relative-path gap), count unchanged from the
unmodified worktree tip.

**Capacity-form API shape** (for lithos WO-65 / any future consumer):

```python
from feldspar.library.member_capacity import register
from feldspar.solve import SolverRegistry

registry = SolverRegistry()
register(registry)  # or via pack._engine_registry(), already wired

# mech.member.flexural_yield_capacity_f2
#   in:  {"mech.member.flexure.fy": float,   # Pa, yield strength
#         "mech.member.flexure.zx": float}   # m^3, plastic section modulus
#   out: {"mech.member.flexure.capacity": float}  # N*m, phi_b*Mn

# mech.member.axial_yield_buckling_capacity_e3
#   in:  {"mech.member.axial.fy": float,        # Pa
#         "mech.member.axial.ag": float,        # m^2, gross area
#         "mech.member.axial.e": float,         # Pa, Young's modulus
#         "mech.member.axial.kl_over_r": float} # dimensionless
#   out: {"mech.member.axial.capacity": float}  # N, phi_c*Pn
```

Called through the registered `SolveFn` protocol (`fn(x) ->
Result[SolveResult, SolveError]`, `.danger_ok.values[<port>]`), same
shape as every other `library.mech` direction -- not a bespoke API.
Feeding these two outputs into `feldspar.library.struct.
civil_utilization_h1`'s `axial_capacity`/`moment_capacity`
parameters closes the full chain from caller-supplied section
properties to an H1 interaction verdict, still without a registry-
digest-resolution channel in between (that channel is the standing,
unchanged blocker named in every WO-21/23/24 close-out).

**Memo sections added**: none -- deliverable 0 cites AISC 360-16
directly (sec. F2.1, E1, E2, E3), per its own text; no benchmarks-
memo section existed or was needed for this slice.

---

## Dispatch #2 close-out (2026-07-09, branch `wo24-remainder`)

**Landed**:

- **Deliverable -1 (integrity fix)**: `docs/benchmarks-memo.md`.
  Every numbered citation this repo's tests/WO close-outs already
  used ("benchmarks memo 1.1", "sec. 3.4", "memo sec. 4.1", etc.) was
  grepped out of `tests/` and `docs/` and cross-checked against the
  source document referenced by name in the WO-20 close-out (lithos
  `docs/workflow/research/2026-07-08-benchmarks-and-datasets.md`,
  read-only reference repo). Every collected citation resolves to a
  real section in that source with matching worked numeric values
  (spot-checked sec. 1.1 against
  `test_library_struct.py::test_propped_cantilever_udl_matches_closed_form`'s
  asserted R_A/R_B/M_A). The source was copied in verbatim (section
  numbering preserved, nothing renumbered) as this repo's own
  `docs/benchmarks-memo.md`, with a provenance/audit preface added.
  **Result: zero unreconstructed citations** -- every citation this
  repo's code already made was already backed by a real, findable,
  numerically-consistent source; the integrity gap was the file's
  ABSENCE from this repo, not a fabricated or dangling citation.
  Commit: `docs(memo): consolidate benchmarks memo cited by
  WO-20/21/23/24 tests`.

**Cuts** (deliverables 1-8, RECORDED and cut again, same standing-law
reason as dispatch #1 -- capacity, not physics or missing citations,
is the limiter; the memo landing this dispatch removes what would
otherwise have been each deliverable's first blocker, so a future
dispatch starts from a real citation trail for at least the struct/
fluid/circuit-adjacent cases):

1. **Bolted joints** (VDI 2230-class preload/load-factor + elastic
   bolt-group distribution) -- not started. VDI 2230 is a standard
   this repo has not yet cited anywhere (unlike AISC/Roark/ISO
   already in the memo); a future dispatch needs to add a new memo
   section (e.g. a new "8." top-level section, per this memo's own
   "append, never renumber" rule) with the specific VDI 2230 clauses
   before landing code, plus a hand-computed or published worked
   example to calibrate against -- not attempted this dispatch.
2. **Weld groups** (elastic line method, fillet groups) -- not
   started; same shape of gap (no elastic-line-method citation or
   worked case in the memo yet; Blodgett's Design of Welded
   Structures or AISC Manual Part 8 would be the natural source).
3. **Bearing life** (ISO 281 L10) -- not started; additionally still
   blocked on the registry-resolution gap named in dispatch #1's cut
   3 and every WO-21/23 close-out (rating-record digest -> numeric
   C/P has no channel on feldspar's payload port surface).
4. **Fatigue tier** (Goodman/Soderberg + cited factor tables) --
   not started; the modifying-factor tables (surface finish, size,
   load, reliability) are each their own citation (Shigley is the
   natural source, already cited in this memo sec. 5.6 for spring
   wire -- but the fatigue factor TABLES themselves are not yet
   transcribed anywhere in this repo) and calibration oracle, not
   attempted rather than rushed, per the WO's own "honesty over
   reach" flag on this deliverable.
5. **Drive sizing** (belt GT2 + leadscrew) -- not started; no
   existing citation trail for either in this repo or the memo.
6. **Lumped thermal transient** (RC-network step/duty) -- not
   started; extends WO-20's thermal-fluids wave, a separate
   citation/calibration surface (the memo's sec. 3.4 CoolProp state
   points are property data, not a transient-response worked case).
7. **Roark deflection catalog completion** -- not started. NOTE for
   the next dispatch: this memo's sec. 2 already lists 6 canonical
   beam formulas + 2 numeric anchors (SS-UDL, SS-central-load,
   cantilever-end-load, cantilever-UDL, fixed-fixed-UDL, SS-load-at-
   a-b) and sec. 1.1/1.5 cover propped-cantilever and fixed-fixed-
   central-load frame cases -- "the remaining Roark cases the memo
   lists as gaps" (WO-24's own deliverable-5 text) should be read as
   "cases NOT in sec. 1 or 2 above" (e.g. Roark Table 8.1 cases for
   overhanging beams, non-central point loads on fixed-fixed spans,
   or multi-span unequal-span continuous beams); enumerating that gap
   list is itself unstarted work, not done this dispatch.
8. **Column buckling completion** -- not started, unchanged from
   dispatch #1's note: `mech.member.axial_yield_buckling_capacity_e3`
   (deliverable 0, landed) already covers AISC 360-16 sec. E3's
   basic flexural-buckling form; a future dispatch closing this
   deliverable should scope itself to sec. E4 (torsional/flexural-
   torsional) and sec. E7 (slender elements), not re-derive E3.

**LITHOS-SIDE NOTE**: unchanged from dispatch #1 -- the section/
material CAPACITY-resolution registry channel remains the standing
largest blocker for `mech.struct`/`mech.member`; nothing new
escalated this dispatch.

**Gate** (this worktree, `.claude/worktrees/wo24-remainder`; only
`docs/benchmarks-memo.md` and this WO file changed -- no Rust, no
Python):
`cargo fmt --all -- --check`: clean (no Rust changed).
`uv run ruff format --check .` / `uv run ruff check .`: unchanged
from dispatch #1's baseline (docs-only change, no Python touched).
`uv run lint-imports`: 1 contract kept, 0 broken (unchanged).
`uv run ty check`: verified via a fresh diagnostic count (NOT `git
stash` -- HARD RULE this dispatch; used a separate read of the
pre-change diagnostic count recorded in dispatch #1's own close-out,
230, and re-ran `ty check` post-change): 230 diagnostics, same count,
all the same pre-existing `regolith.*`-unresolved-import findings
from the nested-worktree relative-path gap; zero new diagnostics
(expected -- no Python source changed).
`uv run pytest tests/ -n auto -m "not regolith and not fea and not
spice"`: 352 passed, 1 skipped, 7 errors -- same 7 pre-existing
`tests/regolith/*` collection failures, count unchanged from dispatch
#1's own baseline (verified: no test file touched this dispatch).

**Calibration list (this dispatch)**: none new -- deliverable -1 is
a documentation consolidation, not a model; nothing to calibrate.
Deliverable 0's calibration list (dispatch #1) is unchanged and
carried forward above.

**API names for new solver directions (this dispatch)**: none new --
no solver code landed this dispatch. Deliverable 0's API shape
(dispatch #1, `mech.member.flexural_yield_capacity_f2` and
`mech.member.axial_yield_buckling_capacity_e3`) is unchanged and
documented above.

---

## Dispatch #3 close-out (2026-07-10, branch `wo24-joints`, worktree
`.claude/worktrees/wo24-joints`)

Scope this dispatch: EXACTLY deliverable 1 (bolted joints) and
deliverable 8 (column buckling completion), per explicit dispatch
instruction ("a small scope you can fully land beats a wide one you
cut") -- deliverables 2-7 out of scope, not attempted, cuts unchanged
from dispatch #2's own text.

**(a) Landed / cut table**:

| Deliverable | Status | Notes |
|---|---|---|
| 1. Bolted joints | LANDED | VDI 2230 single-bolt tier + Shigley/AISC elastic bolt-group shear/torsion/tension |
| 8. Column buckling completion | LANDED (narrow) | Euler elastic tier only, per dispatch instruction's own suggested scope -- E4/E7 remain named cuts |
| 2-7 | CUT (unchanged) | out of this dispatch's scope; see dispatch #2 close-out above |

**(b) Branch + commits** (`wo24-joints`, worktree
`.claude/worktrees/wo24-joints`):

1. `docs(memo): add bolted-joint (VDI 2230/Shigley/AISC) and Euler
   column buckling sections` -- `docs/benchmarks-memo.md` sec. 8
   (bolted joints, subsecs 8.1-8.3) and sec. 9 (Euler column
   buckling), appended after the existing sec. 7 Sources without
   renumbering it (the memo's own append-only rule).
2. `feat(joint): add VDI 2230 single-bolt and elastic bolt-group
   directions (WO-24 deliverable 1)` --
   `python/feldspar/library/bolted_joints.py` (new),
   `tests/unit/test_library_bolted_joints.py` (new), wired into
   `python/feldspar/pack/models.py::_engine_registry`.
3. `feat(member): add Euler elastic critical buckling load direction
   (WO-24 deliverable 8)` -- extends
   `python/feldspar/library/member_capacity.py` (already registered
   via `register()`, no `pack/models.py` change needed -- same
   module, same registration call) and
   `tests/unit/test_library_member_capacity.py`.

**(c) Gates** (this worktree):
`cargo fmt --all -- --check`: no Rust changed this dispatch.
`uv run ruff format --check .` / `uv run ruff check .`: the changed
files (`bolted_joints.py`, `member_capacity.py`, `models.py`,
`test_library_bolted_joints.py`, `test_library_member_capacity.py`)
are clean; the tool reports pre-existing failures in the SAME
unrelated files dispatch #1/#2 already documented
(`examples/*.py`, `examples/solvers/*.py`, `scripts/*.py`,
`tests/unit/test_plan_over_library.py`), unchanged, not a regression.
`uv run lint-imports`: 1 contract kept, 0 broken (unchanged).
`uv run ty check`: 230 diagnostics, same count as dispatch #1's
recorded baseline (all pre-existing `regolith.*`-unresolved-import
findings from the nested-worktree relative-path gap); zero new
diagnostics from this dispatch's Python.
`uv run pytest tests/ -n auto -m "not regolith and not fea and not
spice"`: 363 passed, 1 skipped, 7 errors -- the same 7 pre-existing
`tests/regolith/*` collection failures (count unchanged); 11 new
tests this dispatch (6 bolted-joint tests already counted, +5 member-
capacity Euler tests) over the 352-passed baseline dispatch #1
recorded (352 + 11 = 363, consistent).

**(d) Memo sections added**: `docs/benchmarks-memo.md` sec. 8 (three
subsections, 8.1-8.3) and sec. 9 (one case) -- both new, appended
after sec. 7 Sources, sec. numbering of every prior section
unchanged. Sources for these: VDI 2230 Blatt 1:2015 (sec. 8.1);
Shigley's Mechanical Engineering Design 11th ed. ch. 8 sec. 8-11/8-12
(sec. 8.2/8.3, also cited for the tension case alongside AISC Manual
of Steel Construction Part 7); Timoshenko, Theory of Elastic
Stability 2nd ed. ch. 2, and Shigley 11e ch. 4 sec. 4-14 (sec. 9).

**(e) Calibration results** (all green, hand-computed exact algebra,
tolerance rel=1e-6..1e-9 -- pure closed-form, no empirical fit):

- `test_vdi2230_load_factor_matches_hand_computed`: cb=200e6,
  cp=800e6, fv=10000, fa=5000 -> phi=0.20, F_S=11000, F_KR=6000.
- `test_vdi2230_separation_when_residual_clamp_load_goes_nonpositive`:
  honest separation case (F_KR < 0), not a domain violation.
- `test_bolt_group_shear_torsion_matches_hand_computed`: 4-bolt
  rectangular pattern (a=0.05, b=0.03), Vx=1000, T=50 ->
  |F|=230.94 N.
- `test_bolt_group_tension_from_moment_matches_hand_computed`:
  2-row 4-bolt pattern, sum_y_sq=0.0064, M=800 -> F_t=5000 N.
- `test_euler_critical_buckling_load_matches_hand_computed`:
  E=200e9, I=8.0e-6, K=1.0, L=3.0 -> Pcr~1,754,600 N.
- `test_euler_critical_buckling_load_consistent_with_e3_fe`:
  cross-checks Euler `Pcr` against E3's `Fe*Ag` for the same KL/r,
  confirming both directions encode the same physics (memo sec. 9's
  own claim) -- rel=1e-6.
- Non-positive/degenerate-input `OutOfDomain` cases for all five new
  directions (honest refusal, not a fabricated verdict).
- No calibration failures to record.

**(f) New solver direction names + signatures**:

```
mech.joint.bolt_single_load_factor_vdi2230
  in:  {"mech.joint.bolt.cb": float,   # N/m, bolt stiffness
        "mech.joint.bolt.cp": float,   # N/m, clamped-parts stiffness
        "mech.joint.bolt.fv": float,   # N, preload (>=0)
        "mech.joint.bolt.fa": float}   # N, external axial load
  out: {"mech.joint.bolt.load_factor": float,          # phi
        "mech.joint.bolt.working_load": float,         # F_S, N
        "mech.joint.bolt.residual_clamp_load": float}  # F_KR, N

mech.joint.bolt_group_shear_torsion
  in:  {"mech.joint.group.n": float, "mech.joint.group.vx": float,
        "mech.joint.group.vy": float, "mech.joint.group.torque": float,
        "mech.joint.group.j_polar": float, "mech.joint.group.xi": float,
        "mech.joint.group.yi": float}
  out: {"mech.joint.group.shear_resultant": float}     # N

mech.joint.bolt_group_tension_from_moment
  in:  {"mech.joint.group.moment": float,
        "mech.joint.group.sum_y_sq": float,
        "mech.joint.group.y_critical": float}
  out: {"mech.joint.group.tension_critical": float}     # N

mech.member.euler_critical_buckling_load
  in:  {"mech.member.euler.e": float,      # Pa
        "mech.member.euler.i": float,      # m^4
        "mech.member.euler.k": float,      # dimensionless
        "mech.member.euler.length": float} # m
  out: {"mech.member.euler.pcr": float}    # N
```

All four registered `@solver` pure-map directions (10 sec. 2 pattern
1), same shape as every other `library.mech`/`library.member_capacity`
direction -- called through the registered `SolveFn` protocol
(`fn(x) -> Result[SolveResult, SolveError]`, `.danger_ok.values[<port>]`).

**Cuts named this dispatch** (unchanged scope decisions, not new
findings): deliverable 8 was scoped to the Euler elastic tier only
(the dispatch instruction's own named example) -- AISC 360-16 sec. E4
(torsional/flexural-torsional buckling) and sec. E7 (slender-element
reduction) remain NOT built, same named cut both prior close-outs
recorded; a future dispatch closing those needs its own citation
trail (E4 needs torsional/warping constants per section shape, E7
needs the lambda_r slenderness-limit tables per element type) --
neither is a small addition, unlike the Euler tier landed here.
Deliverables 2-7 (weld groups, bearing life, fatigue, deflection
catalog completion, thermal transient, drive sizing) untouched,
same reasons dispatch #2 recorded.

**LITHOS-SIDE NOTE**: unchanged -- nothing new escalated this
dispatch; the section/material CAPACITY-resolution registry channel
remains the standing largest blocker for `mech.struct`/`mech.member`
(named in every WO-21/23/24 close-out, this dispatch's two landed
directions both take fully caller-resolved numeric inputs, same
seam).

---

## Dispatch #4 close-out (2026-07-10, branch `wo24-welds`, worktree
`.claude/worktrees/wo24-welds`)

Scope this dispatch: EXACTLY deliverable 2 (weld groups) and
deliverable 3 (bearing life), per explicit dispatch instruction
("small scope, fully landed, beats wide and cut") -- deliverables
4-7 out of scope, not attempted, cuts unchanged from dispatch #2/#3's
own text.

**(a) Landed / cut table**:

| Deliverable | Status | Notes |
|---|---|---|
| 2. Weld groups | LANDED | Shigley 11e ch. 9 / Blodgett elastic line method: in-plane shear+torsion, out-of-plane bending, vector-summed peak line force vs caller-supplied allowable |
| 3. Bearing life | LANDED | ISO 281:2007 basic L10 (ball p=3, roller p=10/3) + L10->L10h at constant speed, over `std.bearings`-shaped C/P inputs |
| 4-7 | CUT (unchanged) | out of this dispatch's scope; see dispatch #2/#3 close-outs above |

**(b) Branch + commits** (`wo24-welds`, worktree
`.claude/worktrees/wo24-welds`):

1. `docs(memo): add fillet weld group and ISO 281 bearing life
   sections` -- `docs/benchmarks-memo.md` sec. 10 (weld groups,
   subsecs 10.1-10.3) and sec. 11 (bearing life, subsecs 11.1-11.3),
   appended after the existing sec. 9 Euler column buckling section
   without renumbering it (the memo's own append-only rule).
2. `feat(weld): add fillet weld group elastic line directions
   (WO-24 deliverable 2)` -- `python/feldspar/library/weld_groups.py`
   (new), `tests/unit/test_library_weld_groups.py` (new), wired into
   `python/feldspar/pack/models.py::_engine_registry`.
3. `feat(bearing): add ISO 281 basic dynamic rating life directions
   (WO-24 deliverable 3)` -- `python/feldspar/library/bearing_life.py`
   (new), `tests/unit/test_library_bearing_life.py` (new), wired into
   `python/feldspar/pack/models.py::_engine_registry`.

**(c) Gates** (this worktree):
`cargo fmt --all -- --check`: no Rust changed this dispatch.
`uv run ruff format --check .` / `uv run ruff check .`: the changed
files (`weld_groups.py`, `bearing_life.py`, `models.py`,
`test_library_weld_groups.py`, `test_library_bearing_life.py`) are
clean; the tool reports pre-existing failures in the SAME unrelated
files dispatch #1/#2/#3 already documented (`examples/*.py`,
`examples/solvers/*.py`, `scripts/*.py`,
`tests/unit/test_plan_over_library.py`), unchanged, not a
regression.
`uv run lint-imports`: 1 contract kept, 0 broken (unchanged).
`uv run ty check`: 230 diagnostics, same count as dispatch #1/#2/#3's
recorded baseline (all pre-existing `regolith.*`-unresolved-import
findings from the nested-worktree relative-path gap); zero new
diagnostics from this dispatch's Python (an initial `bearing_life.py`
draft's multi-line `# ty: ignore` comment placement broke after a
`ruff format` reflow and produced 2 spurious diagnostics -- fixed by
restructuring `register()` to bind `.solver_direction` to a local
name per direction, same single-line-ignore shape `bolted_joints.py`/
`weld_groups.py` already use, before the final count was taken).
`uv run pytest tests/ -n auto -m "not regolith and not fea and not
spice"`: 381 passed, 1 skipped, 7 errors -- the same 7 pre-existing
`tests/regolith/*` collection failures (count unchanged); 18 new
tests this dispatch (9 weld-group tests + 9 bearing-life tests) over
the 363-passed baseline dispatch #3 recorded (363 + 18 = 381,
consistent).

**(d) Memo sections added**: `docs/benchmarks-memo.md` sec. 10
(three subsections, 10.1-10.3) and sec. 11 (three subsections,
11.1-11.3) -- both new, appended after sec. 9, sec. numbering of
every prior section unchanged. Sources: Shigley's Mechanical
Engineering Design 11th ed. ch. 9 sec. 9-5/9-6 (weld-line unit
section properties, in-plane and bending); Blodgett, Design of
Weldments, sec. 4.3-4.4 (same elastic-line treatment); AWS D1.1/
D1.1M Structural Welding Code -- Steel and AISC 360-16 sec. J2.4
(0.707*leg-size effective throat convention) for sec. 10.3's
utilization check; ISO 281:2007, Rolling bearings -- Dynamic load
ratings and rating life, sec. 6.2 eq. 4/eq. 5, for sec. 11.

**(e) Calibration results** (all green, hand-computed exact algebra,
tolerance rel=1e-6..1e-9 -- pure closed-form, no empirical fit):

- `test_weld_group_inplane_shear_torsion_matches_hand_computed`:
  Aw=0.20 m, Jw=0.0136 m^3, critical point (0.05, 0.03), Vx=1000,
  Vy=0, T=50 -> |f|=4893.16 N/m.
- `test_weld_group_outofplane_bending_matches_hand_computed`:
  M=600 N*m, Iw=0.0024 m^3, c=0.06 m -> f=15,000.0 N/m.
- `test_weld_group_utilization_matches_hand_computed`:
  f_inplane=4893.16 N/m, f_bending=15,000.0 N/m, leg=0.008 m,
  allowable=145e6 Pa -> stress=2,789,591 Pa, ratio=0.01924 (Valid).
- `test_weld_group_utilization_over_allowable_reports_ratio_above_one`:
  honest ratio > 1.0 case, not a raised error.
- `test_l10_ball_matches_hand_computed`: C=14,000 N (a 6205-class
  `std.bearings` record's `dynamic_load_kn=14.0`), P=2,000 N ->
  L10=343.0 million revolutions.
- `test_l10_roller_matches_hand_computed`: C=50,000 N, P=10,000 N ->
  L10=5^(10/3)=213.7470 million revolutions.
- `test_l10h_matches_hand_computed`: L10=343.0, n=1,800 rpm ->
  L10h=3,175.93 hours.
- `test_l10_then_l10h_composed_matches_hand_computed`: chains the
  ball-L10 direction's output into the L10h direction through two
  separate `SolveFn` calls, confirming the caller-composition seam
  works end to end.
- Non-positive/degenerate-input `OutOfDomain` cases for all six new
  directions (honest refusal, not a fabricated verdict).
- No calibration failures to record (one arithmetic slip caught
  during drafting: an initial hand-computed weld in-plane resultant
  and roller-bearing `L10` exponent value were wrong by
  transcription error, not a formula error -- both corrected in the
  module docstring, memo sections, and tests together before this
  close-out, verified via `python3 -c` cross-check against the
  registered solver's own output).

**(f) New solver direction names + signatures**:

```
mech.weld.weld_group_inplane_shear_torsion
  in:  {"mech.weld.group.vx": float, "mech.weld.group.vy": float,
        "mech.weld.group.torque": float, "mech.weld.group.aw": float,
        "mech.weld.group.jw": float, "mech.weld.group.xi": float,
        "mech.weld.group.yi": float}
  out: {"mech.weld.group.inplane_line_force": float}   # N/m

mech.weld.weld_group_outofplane_bending
  in:  {"mech.weld.group.moment": float, "mech.weld.group.iw": float,
        "mech.weld.group.c": float}
  out: {"mech.weld.group.bending_line_force": float}   # N/m

mech.weld.weld_group_utilization
  in:  {"mech.weld.group.inplane_line_force": float,
        "mech.weld.group.bending_line_force": float,
        "mech.weld.group.leg_size": float,
        "mech.weld.group.allowable_stress": float}
  out: {"mech.weld.group.peak_stress": float,          # Pa
        "mech.weld.group.utilization_ratio": float}    # dimensionless

mech.bearing.bearing_basic_rating_life_l10_ball
mech.bearing.bearing_basic_rating_life_l10_roller
  in:  {"mech.bearing.dynamic_rating": float,   # N (C)
        "mech.bearing.equivalent_load": float}  # N (P)
  out: {"mech.bearing.l10": float}   # millions of revolutions

mech.bearing.bearing_basic_rating_life_l10h
  in:  {"mech.bearing.l10": float, "mech.bearing.speed_rpm": float}
  out: {"mech.bearing.l10h": float}   # hours
```

All six registered `@solver` pure-map directions (10 sec. 2 pattern
1), same shape as every other `library.mech`/`library.member_capacity`/
`library.bolted_joints` direction -- called through the registered
`SolveFn` protocol (`fn(x) -> Result[SolveResult, SolveError]`,
`.danger_ok.values[<port>]`).

**Cuts named this dispatch** (unchanged scope decisions, not new
findings): weld-line unit section properties (`Aw`/`Jw`/`Iw`) for
standard weld patterns (rectangular, circular, C-shaped groups --
Blodgett Table 4 / Shigley Table 9-1/9-2) are NOT transcribed --
CALLER-SUPPLIED, same "caller-resolved aggregate" seam
`bolt_group_shear_torsion`'s `j_polar` uses. The allowable weld
stress (AWS D1.1 electrode-classification table) is NOT derived --
CALLER-SUPPLIED. The ISO 281 sec. 6.1 combined-load `P = X*Fr+Y*Fa`
equivalent-load reduction and the sec. 6.3 `a1`/`aISO` life-
modification factors are NOT built -- `P` is CALLER-SUPPLIED, basic
(unmodified) `L10`/`L10h` only. Static-load safety (`C0/P0`, ISO 76)
is NOT evaluated. Deliverables 4-7 (fatigue tier, deflection catalog
completion, thermal transient, drive sizing) untouched, same reasons
dispatch #2 recorded.

**LITHOS-SIDE NOTE**: unchanged -- nothing new escalated this
dispatch; the section/material CAPACITY-resolution registry channel
remains the standing largest blocker for `mech.struct`/`mech.member`
(named in every WO-21/23/24 close-out). The `std.bearings` record
shape (`dynamic_load_kn`/`static_load_kn`) read this dispatch as a
reference (lithos:stdlib/std.bearings/records/deep_groove_ball.toml,
read-only) confirms the same "caller-resolved numeric input, no
registry-digest-resolution channel" seam applies to bearing C/C0
values exactly like it does to AISC section properties -- consistent
with, not a new instance of, the standing blocker.

---

## Dispatch #5 close-out (2026-07-10, branch `wo24-thermal`, worktree
`.claude/worktrees/wo24-thermal`)

**Landed** (`python/feldspar/library/thermal_transient.py`,
`tests/unit/test_library_thermal_transient.py`, wired into
`python/feldspar/pack/models.py::_engine_registry`, memo sec. 12):

- `heat.transient.biot_number_from_convection`: `Bi = h*Lc/k`
  (Incropera & DeWitt, Fundamentals of Heat and Mass Transfer, 7th
  ed., ch. 5 sec. 5.1 eq. 5.10) -- a small convenience direction, no
  criterion applied itself.
- `heat.transient.step_temperature`: single-node lumped-capacitance
  step response, `T(t) = T_amb + P*R_th*(1 - exp(-t/tau))`, `tau =
  R_th*C_th` (Incropera ch. 5 sec. 5.2, same governing ODE as memo
  sec. 4.1's electrical RC step response).
- `heat.transient.time_to_threshold`: algebraic inversion of the
  step response for elapsed time, `t = -tau*ln(1 -
  (T_thresh-T_amb)/(P*R_th))`; `OutOfDomain` (honest refusal, not a
  fabricated time) when the asymptotic steady rise never reaches the
  threshold.
- `heat.transient.duty_cycle_peak_temperature`: the VRM case --
  periodic square-wave power (dissipation `P` at duty `t_on/(t_on+
  t_off)`), closed-form periodic-steady-state PEAK temperature,
  `T_peak = T_amb + P*R_th*(1-a)/(1-a*b)`, `a=exp(-t_on/tau)`,
  `b=exp(-t_off/tau)`, derived by direct superposition/fixed-point
  solution of the SAME lumped ODE (not a separate empirical
  correlation) -- lets a caller check "does T_j stay below a limit"
  under duty-cycled dissipation.

**Validity predicate (the honesty core, per dispatch instruction)**:
every direction above takes a CALLER-ASSERTED `biot_number` port and
`OutOfDomain`-rejects at/above `Bi = 0.1` (Incropera ch. 5 sec. 5.1
eq. 5.10, the lumped-capacitance criterion), enforced IN-FUNCTION
(`_reject_biot`, one shared home, NO DUPLICATION) rather than only as
a domain `tags` label -- a numeric Bi value is available to check,
unlike `member_capacity.py`'s boolean compact/braced preconditions.
This module does not derive `h`/`Lc`/`k` itself (a second citation
surface for convection correlations, out of scope); a caller either
asserts a known/measured Bi directly, or computes it via
`biot_number_from_convection` first. Constant properties and
single-node lumping are the other two Incropera ch. 5 sec. 5.1
preconditions, recorded as named cuts (not separately gated at
runtime beyond Bi, matching the WO's "validity predicates narrow"
instruction -- Bi is the ONE checkable numeric gate; constant
properties has no numeric signal to check against without a second
temperature-dependence model, which would be new physics, not a
predicate).

**Named cuts** (module docstring, verbatim reasons):

1. Multi-node (Cauer/Foster RC-ladder) thermal networks are OUT --
   every direction is SINGLE-NODE (one `R_th`, one `C_th`, one
   ambient). A die-to-case-to-heatsink-to-ambient stack with
   materially different per-stage time constants needs a coupled
   multi-node solve; applying this module's forms to such a stack
   would UNDER-predict peak temperature (falsely fast equilibration).
   Not attempted this dispatch.
2. `C_th` (thermal capacitance, `rho*V*c`) has no PRODUCER direction
   in this repo -- CALLER-SUPPLIED, same seam shape as
   `member_capacity.py`'s caller-supplied `Zx`/`Ag`/`r` (unlike
   `R_th`, which `heat.py` can already produce from conduction/
   convection geometry -- these transient directions COMPOSE with
   `heat.py`'s existing resistance outputs through the plan graph,
   they do not recompute them).
3. Temperature-dependent properties are NOT modeled -- constant
   `R_th`/`C_th`/(convective `h` feeding Bi) is a standing lumped-
   capacitance precondition (Incropera's own assumption set), named
   but not separately runtime-gated beyond the Bi check.

**Claim-kind naming rationale** (read lithos `python/regolith/
harness/signature.py` and `python/regolith/harness/models/
lumped_thermal.py` read-only, per dispatch instruction): lithos
already registers `thermo.junction_temperature` (WO-26 D105b) for
the STEADY form, `T_j = T_amb + P*R_theta`, an upper-bound
`ClaimSense`. This module's `step_temperature` is that SAME physics'
transient generalization (the steady form is its `t -> infinity`
limit). So a future lithos-side model pack should register a
transient junction-temperature claim under names that PARALLEL,
never collide with, the existing steady kind:
`thermo.junction_temperature_transient` (step/threshold forms) and
`thermo.junction_temperature_duty_cycle` (the periodic peak form,
the VRM case) -- both upper-bound claims, both needing their own
`NumericReducedTierModel` subclass on the lithos side (out of this
feldspar-only dispatch's scope; named here so the naming decision
predates that pack rather than being invented ad hoc when it lands).
This closes the WO's "name your directions so a thermal claim can
actually route" instruction: the feldspar-side port names
(`heat.transient.*`) and the lithos-side claim-kind names above are
now BOTH decided and cross-referenced in each other's docstrings.

**Calibration** (`docs/benchmarks-memo.md` sec. 12, all green):

- 12.1 step response at `t=tau` (63.2% mark) and `t=5*tau` (99.3%
  mark): exact closed-form (`exp`), tol rel 1e-9.
- 12.2 time-to-threshold: threshold set to the exact 12.1 one-tau
  rise so the inverted time recovers `tau` itself as a self-check;
  tol rel 1e-9.
- 12.3 duty-cycle peak temperature (`t_on=2.0s`, `t_off=8.0s`,
  `tau=40.0s`): tol rel 1e-9. Two limiting-case derivation checks
  verified by direct substitution: `t_off -> 0` recovers the 12.1
  step-response asymptote (`P*R_th`) exactly; switching period `<<
  tau` recovers the standard average-power duty-derating heuristic
  (`P*d*R_th`) to 5 significant figures.
- Honest-indeterminate cases: non-positive `R_th`/`C_th`/`power`,
  unreachable threshold, high Biot (>= 0.1) on every direction,
  degenerate zero-length duty cycle.

**Gate** (this worktree, `.claude/worktrees/wo24-thermal`):
`uv run ruff format --check .` / `uv run ruff check .`: the three
new/changed files (`thermal_transient.py`,
`test_library_thermal_transient.py`, `pack/models.py`) are clean;
pre-existing failures in unrelated files (`examples/*.py`,
`scripts/*.py`, `tests/unit/test_plan_over_library.py`) identical
before and after this change. `uv run lint-imports`: 1 contract
kept, 0 broken. `uv run ty check`: 230 diagnostics, unchanged from
the documented dispatch #1 baseline (same nested-worktree
`regolith.*`-unresolved-import gap; `thermal_transient.py`
contributes zero new diagnostics). `uv run pytest tests/ -n auto -m
"not regolith and not fea and not spice"`: 395 passed (14 of them
this dispatch's new thermal-transient tests; the remainder reflects
cumulative suite growth across dispatches #1-4), 1 skipped, 7 errors
-- the 7 errors are the same documented pre-existing `tests/
regolith/*` collection failures (`ModuleNotFoundError: No module
named 'regolith'`), count unchanged.

**LITHOS-SIDE NOTE**: nothing new escalated beyond the naming
rationale above (which is a recorded DECISION, not an escalation --
no lithos-side ambiguity was found, `signature.py`'s `ClaimSense`/
`ModelSignature` shape already supports the parallel naming directly,
no new harness mechanism needed).

---

## Dispatch #6 close-out (2026-07-10, branch `cycle33-pack-exposure`,
worktree `.worktrees/cycle33-pack-exposure`)

Scope this dispatch: cycle-33's PACK EXPOSURE queue item (lithos
design-log 2026-07-10-cycle-32 F112 + 2026-07-10-cycle-33 opener) --
NOT a new WO-24 deliverable. Deliverables 4 (fatigue), 5 (Roark
deflection catalog completion), and 7 (drive sizing) remain UNSTARTED,
same reasons dispatches #2-#5 already recorded (no existing citation
trail for fatigue factor tables or drive-sizing standards; the Roark
gap list itself is unenumerated) -- not attempted this dispatch, whose
scope was exposure of ALREADY-LANDED directions, not new physics.

**Inventory** (`_engine_registry()` internal directions vs
`feldspar.pack.register()`'s regolith `Model`s, before this dispatch):
6 models exposed (`FeaStaticStressModel`, `FeaStaticDeflectionModel`,
`FeaStaticDeflectionFromGeometryModel`, `MechStiffnessModel`,
`ElecRailModel` x2) against >20 internal `@solver` directions across
`library.mech`/`member_capacity`/`bolted_joints`/`weld_groups`/
`bearing_life`/`thermal_transient`/`fluids`/`heat`/`thermo` --
dispatches #1/#3/#4/#5's WO-24 deliverables (member capacity, bolted
joints, weld groups, bearing life, thermal transient) had NO regolith
exposure at all: reachable inside feldspar's own planner, invisible to
a lithos discharge.

**Landed** (`python/feldspar/pack/models.py`,
`python/feldspar/pack/__init__.py`,
`tests/regolith/test_pack_wo24_exposure.py`, `README.md`): a new
`_ClosedFormEngineModel(_FeaModel)` base (cost=1, non-ccx/gmsh
`solver_version`, `_FeaModel.__init__` generalized with an
`engine_tags` param so a non-FEA direction's own `Domain.tags` --not
the FEA-hardcoded `{"linear_elastic","small_deflection"}`-- reaches
`plan()`) and six concrete `Model` subclasses over it, each binding an
already-registered, already-calibrated WO-24 direction's TOP-LEVEL
output to a new claim kind:

| model | claim kind | wraps |
|---|---|---|
| `MemberFlexuralCapacityModel` | `mech.member.flexural_capacity` | `member_capacity.flexural_yield_capacity_f2` (AISC 360-16 F2.1) |
| `MemberAxialCapacityModel` | `mech.member.axial_capacity` | `member_capacity.axial_yield_buckling_capacity_e3` (AISC 360-16 E3) |
| `EulerBucklingLoadModel` | `mech.member.euler_buckling_load` | `member_capacity.euler_critical_buckling_load` (Timoshenko/Shigley) |
| `BoltLoadFactorModel` | `mech.joint.bolt_load_factor` | `bolted_joints.bolt_single_load_factor_vdi2230` (VDI 2230 Blatt 1) |
| `WeldUtilizationModel` | `mech.weld.utilization` | `weld_groups.weld_group_utilization` (Shigley/Blodgett/AWS D1.1) |
| `BearingRatingLifeModel` | `mech.bearing.rating_life_hours` | `bearing_life.bearing_basic_rating_life_l10h` (ISO 281:2007) |

No physics reimplemented -- every model routes through
`_engine_registry()` + `feldspar.plan.solve.solve()`, the SAME code
path `_FeaModel` already used, over the direction's already-registered
`@solver` function.

**Named residuals** (NOT half-landed -- deliberately not exposed as
separate top-level claims, full reasoning in `pack/models.py`'s
"cycle-33 pack-exposure wave" section comment):

1. `bolt_group_shear_torsion` / `bolt_group_tension_from_moment` --
   per-bolt force components with no producer for their own allowable
   in this repo (caller-supplied), so no sense-bearing claim limit
   exists yet to discharge against.
2. `weld_group_inplane_shear_torsion` / `weld_group_outofplane_bending`
   -- intermediate unit line forces (N/m) `weld_group_utilization`
   (exposed) already composes into the one meaningful stress-ratio
   claim; exposing them separately would invite comparing a line force
   against a stress limit, an honest-but-useless claim shape.
3. `bearing_basic_rating_life_l10_ball` / `_l10_roller` -- `L10`
   (millions of revolutions) is the same chain one step short of
   `L10h` (exposed), the unit an actual duty-cycle claim limit is
   stated in.
4. `thermal_transient.py` (all four directions) -- dispatch #5's own
   close-out already decided their lithos-side claim-kind names
   (`thermo.junction_temperature_transient`/`_duty_cycle`) belong to a
   FUTURE lithos-side model pack with its own `NumericReducedTierModel`
   subclass, explicitly out of feldspar's `pack` module's scope;
   exposing them here would contradict that recorded decision, not
   extend it.

**Environment note** (not a code change, a dev-setup fix any future
dispatch in a `.worktrees/`-style feldspar worktree should reuse):
`pyproject.toml`'s `regolith = { path = "../lithos", editable = true }`
resolves relative to the worktree root, so a worktree at
`.worktrees/<name>/` needs a real or symlinked `.worktrees/lithos`
sibling (this dispatch used `ln -s /home/logan/projects/lithos
.worktrees/lithos`) for `uv sync --extra regolith` to succeed --
without it, `make install`/`make install-regolith` fail outright
(previous dispatches worked around this by treating the resulting
`tests/regolith/*` collection failures as an accepted 7-error baseline
instead; this dispatch's baseline has ZERO such errors because the
symlink was created first).

**Gate** (this worktree): `cargo fmt --all -- --check`: clean (no Rust
changed). `cargo clippy --workspace --all-targets -- -D warnings`:
clean. `cargo test --workspace`: all green (after `cargo build
--workspace` first -- the cdylib-vs-test-binary build-order issue is a
pre-existing environment artifact, not a regression; a raw `cargo test
--workspace` run first hits it, a `cargo build --workspace` first
resolves it, unrelated to any change this dispatch made). `uv run ruff
format --check python/ tests/` / `uv run ruff check python/ tests/`:
clean. `uv run lint-imports`: 1 contract kept, 0 broken. `uv run ty
check python/`: 0 diagnostics (the `.worktrees/lithos` symlink fix
above resolves what prior dispatches recorded as a 230-diagnostic
nested-worktree gap -- an environment improvement, not a code effect).
`uv run pytest tests/ -n auto -m "not regolith and not fea and not
spice"`: 413 passed (baseline unchanged, no non-regolith test file
touched). `uv run pytest tests/regolith/ -m regolith`: 75 passed (69
baseline + 6 new `test_pack_wo24_exposure.py` cases), 0 errors.

**Calibration** (all green, reusing exact reference values from the
dispatches that originally landed and calibrated each direction --
`tests/regolith/test_pack_wo24_exposure.py`, tolerance rel 1e-3..1e-6,
matching the corresponding `tests/unit/test_library_*.py` case's own
tolerance): flexural capacity (Fy=345e6, Zx=1.639e-3 -> 508,909.5 N*m),
axial capacity inelastic branch (Fy=345e6, Ag=0.01, E=200e9, KL/r=80 ->
~1.943e6 N), Euler buckling (E=200e9, I=8.0e-6, K=1.0, L=3.0 ->
~1,754,600 N), VDI 2230 load factor (cb=200e6, cp=800e6, fv=10000,
fa=5000 -> phi=0.20), weld utilization (f_inplane=4893.16,
f_bending=15000.0, leg=0.008, allowable=145e6 -> ratio=0.01924),
bearing L10h (L10=343.0, n=1800 rpm -> 3,175.93 hours). No calibration
failures.

**Cuts named this dispatch**: WO-24 deliverables 4 (shaft/member
fatigue), 5 (Roark deflection catalog completion), and 7 (drive
sizing) remain UNSTARTED -- out of this dispatch's exposure-only scope
(explicit dispatch instruction: "Do NOT expose half-landed
directions... A direction you cannot finish with honest calibration
gets SKIPPED WHOLE"; this dispatch's own remit was PACK EXPOSURE plus
"as many [WO-24 remainder directions] as you can complete PROPERLY" --
the exposure inventory and wiring consumed this dispatch's full scope,
so 4/5/7 were not attempted rather than rushed, same standing law
dispatches #2-#5 already applied to themselves). The four
`thermal_transient.py` residual reason is a recorded DECISION
(dispatch #5), not a new finding.

**LITHOS-SIDE NOTE**: nothing new escalated -- the six new claim kinds
(`mech.member.flexural_capacity`, `mech.member.axial_capacity`,
`mech.member.euler_buckling_load`, `mech.joint.bolt_load_factor`,
`mech.weld.utilization`, `mech.bearing.rating_life_hours`) are NEW
vocabulary this dispatch introduces (OPEN-6 interim pattern, same as
every existing claim kind here) -- a lithos-side scaffold wanting to
assert one of these claims needs its own vocabulary-side registration
of the kind name, unchanged process from how `mech.stiffness`/
`elec.rail.lo`/`elec.rail.hi` were already adopted.
