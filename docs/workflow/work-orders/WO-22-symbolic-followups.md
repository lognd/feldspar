# WO-22: symbolic follow-ups (R4 symbolic propagation + R5 calibration policy)

Status: done
Depends: WO-11 (symbolic core, done), WO-04 (Propagation protocol),
WO-07 (calibration harness)
Language: Rust (`feldspar-core::symbolic` differentiation) + Python
(Propagation mode, harness policy)
Spec: 11 sec. 4 R4/R5 (DECIDED 2026-07-08 -- the normative text),
08 OPEN-15 closure record, 02 (Propagation protocol), 03
(calibration floor + A-7 exactness rule)

## Goal

The two decided symbolic residuals land: delta-method propagation
takes symbolic derivatives where laws are symbolic, and derived
directions get the inherit-citations/re-sweep-calibration policy.

## Deliverables

- Kernel differentiation over the canonical `Expr` AST (product/
  chain/power rules over the existing node set; canonicalized
  output; property tests against numeric differencing on random
  boxes); any rewrite-rule change bumps `CANON_VERSION`.
- Propagation symbolic mode (R4): per-step mode selection (symbolic
  where the step's law is a `Relation`, numeric otherwise) inside
  the ONE protocol; `CANON_VERSION` folded into affected digests;
  determinism suite covers both modes.
- Derived-direction calibration policy (R5): registration of a
  derived direction copies citations, DROPS calibration evidence,
  and enqueues the automatic mapped-domain re-sweep in the
  calibration harness; `Accuracy(0,0)` laws exempt; a derived
  direction whose re-sweep has not run reports its ceiling as
  UNCALIBRATED (honest, blocks nothing at community tier).
- 08's OPEN-15 entry flips fully CLOSED in the same change.

## Acceptance

- Symbolic vs numeric derivative agreement within tolerance on the
  library's Relation set; a derived direction's evidence shows the
  re-swept calibration, not the parent's; digests stable across
  runs and CANON_VERSION-sensitive by test; `make check` green.

## Closing report (landed 2026-07-08)

**R4 -- symbolic propagation.**
`feldspar_core::symbolic::differentiate` (`crates/feldspar-core/src/
symbolic.rs`) adds product/chain/power-rule differentiation over the
existing `Expr` node set (`Var`/`Lit`/`Neg`/`Add`/`Mul`/`Pow`/
`Unary(Sqrt)`), canonicalizing its output. It is a NEW operation, not
a canonicalization-RULE change, so it does not itself bump
`CANON_VERSION` (11 sec. 4 R2 stands unmodified) -- but `CANON_VERSION`
is now exposed to Python (`_feldspar.CANON_VERSION`, re-exported as
`feldspar.core.CANON_VERSION`) and `Relation.law()`'s
`derivation_digest` was fixed to fold the REAL constant in (it
previously hardcoded a literal `1`), so a future canonicalization
change now visibly re-keys every derivation digest as designed.

`feldspar_core::propagation` gains the `Normal` (mean/stddev)
representation (`impl Propagation for Normal`, conservative
`to_interval()` at a documented `NORMAL_TO_INTERVAL_SIGMA = 3.0`) and
`delta_propagate`: first-order delta-method combination
(`sqrt(sum((partial * stddev)^2))`) over a `DerivativeMode` chosen PER
INPUT -- `Symbolic { expr }` (kernel `differentiate` + `eval`) or
`Numeric { eval, h }` (central finite difference) -- matching 11 sec.
4's "mode chosen per step, never per solve," one `Propagation`
protocol. PyO3-exposed as `Normal`, `delta_propagate_symbolic`,
`delta_propagate_numeric` (`feldspar.core`). Property/determinism
tests: symbolic vs. numeric agreement on the orifice law, bit-stable
repeated runs, mixed per-input modes.

SCOPE NOTE (escalated, not invented): wiring `Normal` propagation into
the executor/planner/`Solution` (route-level choice between `Interval`
and `Normal` representations, WO-06/WO-05 territory) is explicitly
OUT of this WO's scope -- doc 02 itself marks `Normal` "Planned, not
v1," WO-04 deliberately left the `Propagation` trait room without a
stub, and no milestone WO in `docs/workflow/README.md`'s dependency
graph schedules that executor-level integration yet. WO-22 lands the
protocol-level building blocks (differentiation kernel, `Normal`
type, `delta_propagate`) that a future milestone WO wires into
`execute()`/`plan()`; that milestone is a new residual to be named by
the owner, not invented here.

**R5 -- calibration interplay.**
`Relation.law()` (`python/feldspar/solve/sugar.py`) now builds each
derived direction's citations by filtering the parent's citations to
DROP `kind="calibration"` entries while keeping every other kind
(paper/handbook/standard) verbatim -- the inherited-citations, dropped-
calibration-evidence split R5 decides. `SolverInfo` gained two
`exclude=True` provenance fields, `law_lhs`/`law_rhs` (threaded through
`_build.build_solver_info_and_fn`), carrying the ORIGINAL declared
equation for re-sweep use only (never dispatch, never digested).

`feldspar.calib.harness` gained `resweep_derived` (verifies the
algebraic identity `lhs == rhs` at sampled points over the derived
direction's own -- possibly nonlinearly mapped -- domain, using the
derived direction's OWN computed value; the residual IS the honest-
floor calibration evidence, since a freshly-derived direction has no
natural external reference solver) and `resweep_all_derived` (batch
version, writes a `CalibRecord` per derived non-EXACT direction to a
records dir). `check_ceilings` now treats a derived direction with no
calibration citation as a live re-sweep-and-check (not a hard
`NoRecord` error): if the re-sweep produces evidence, the existing
ceiling-busted rule applies unchanged; if it cannot (e.g. empty
domain), the direction is reported UNCALIBRATED via a log line and
does not block -- the decided "honest, blocks nothing at community
tier" policy. `Accuracy(0,0)` laws never reach this path (A-7: no
non-EXACT ports to check).

Tests: `tests/unit/test_wo22_symbolic_followups.py` (14 new tests);
existing suite (154 tests) unaffected. `crates/feldspar-core/src/
propagation.rs` and `symbolic.rs` gained Rust-side property/
determinism tests for both R4 pieces.

`make check` equivalent green on this environment: `cargo test
--workspace`, `cargo clippy --workspace --all-targets` (`-D
clippy::all`), `cargo fmt --check`, `pytest` (168 passed), `ruff
check`/`ruff format --check`, `ty check` (only the 5 pre-existing
`regolith` extra-not-installed errors, unrelated to this change),
`lint-imports`. `08-open-questions.md` OPEN-15 and `11-symbolic.md`
sec. 4/5 updated in the same change to record R4/R5 as RESOLVED.
