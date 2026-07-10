# WO-24: solver library depth wave (the AD-34/D174 program, feldspar half)

Status: PARTIAL (2026-07-09 dispatch #2, branch `wo24-remainder`,
worktree `.claude/worktrees/wo24-remainder`) -- landed deliverable 0
(prior dispatch, member capacity forms) and deliverable -1 (this
dispatch: `docs/benchmarks-memo.md`, the memo consolidation).
Deliverables 1-8 RECORDED and CUT AGAIN this dispatch (not started;
same capacity limit as the prior dispatch -- see Close-out below,
"Dispatch #2 close-out" section, for reasons). Deliverable 9 (ledger)
done for the landed slices.
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
