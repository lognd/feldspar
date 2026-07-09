# 11 -- The symbolic core (DECIDED direction, owner, 2026-07-08)

One sentence: equations, validity domains, and rules gain a SYMBOLIC
representation -- laws as data, not only as compiled function bodies
-- so directions are derived from one declared equation instead of
hand-written N times, validity domains are tracked and composed as
predicates instead of only pre-collapsed boxes, and every rule that
IS an equation can be plugged, substituted, and rendered in the
justification report as algebra, not prose.

This REVERSES two earlier positions, deliberately and by owner
decision: the 01 non-goal "symbolic math ... it does not derive new
ones" (now narrowed to optimization only) and 03's Relation
parenthetical rejecting symbolic inversion as "magic". Both files
carry amendment notes pointing here. Ledger entry: OPEN-15 (08).

## 1. What the owner decided (scope)

1. **Plugging equations.** A law may be declared ONCE as a symbolic
   equation (a `Relation` given an expression instead of N direction
   functions). Directions are DERIVED by symbolic manipulation
   (inversion, substitution) where solvable in closed form; each
   derived direction lowers AT DECLARATION TIME to the one raw
   protocol entry -- digest-stable, planner-invisible as anything
   other than an ordinary solver. The metadata-drift worry that
   motivated the old rejection is answered by construction: there is
   nothing left to drift when the N directions are derived from one
   source.
2. **Valid domains, tracked.** A domain may be declared as a
   symbolic predicate (inequalities over ports: `Re < 2300`,
   `t/D < 0.1`, `sigma < S_y`) rather than only a pre-collapsed box.
   The box+tags form remains the dispatch-time admission check (04
   unchanged); the symbolic form is carried so that (a) boxes are
   DERIVED from predicates instead of hand-collapsed, (b) route
   composition can intersect predicates exactly where boxes
   over-approximate, and (c) `explain()` renders the algebraic
   admission argument, not just numbers.
3. **All other rules, too.** Anything in the metamodel that is an
   equation or inequality -- accuracy models (`eps_abs + eps_rel *
   |v|`), conservatism/monotonicity declarations, regime guards --
   may carry its symbolic form alongside its compiled form, consumed
   by the calibration harness, the conformance kit, and the report.

## 2. What stays true (constraints, all pre-existing rules)

- **The one-protocol rule (03/10).** Symbolic declaration is an
  authoring FORM, not a tenth pattern: its builder lowers to raw
  protocol entries exactly like every sugar, digest-equal to a
  hand-built twin. Dispatch still reads cost/accuracy/domain only;
  the planner never runs a CAS at solve time.
- **Determinism (FINV).** Derived forms are canonicalized
  deterministically; the canonical serialized expression folds into
  the solver digest. Same declaration, same derived directions, same
  digests -- across runs and platforms.
- **Citations (03).** A derived direction inherits the declared
  law's citations; the derivation itself is recorded in provenance
  (which variable was solved for, which branch was taken). Algebraic
  exactness is preserved: deriving from an EXACT law yields EXACT
  directions; deriving from a law with a declared accuracy band
  keeps that band (the transform is exact; the model error is the
  law's).
- **Values, not exceptions.** An equation the engine cannot invert
  in closed form is an `Err` at declaration time naming the
  variable, never a silent partial registration; the author then
  writes that direction by hand (the existing Relation form) beside
  the derived ones.
- **Extraction (01).** Whatever engine home is chosen (residual R1
  below), derived directions must still compile into the Rust
  formula tier's extraction story -- symbolic machinery must never
  make a route less extractable than its hand-written twin.

## 3. Non-goals (still)

- Optimization (the surviving half of the old 01 non-goal): the
  planner selects among declared laws; it does not search parameter
  spaces.
- Inventing physics: symbolic derivation only TRANSFORMS declared,
  cited laws (inversion, substitution, composition); it never
  fabricates a relation that was not declared.
- Solve-time CAS evaluation: numeric evaluation stays compiled;
  symbolic work happens at declaration/registration time and in
  rendering.

## 4. Residuals (tracked as OPEN-15 in 08; R1 gates WO-11 dispatch)

- **R1 -- engine home. DECIDED (owner, 2026-07-08):** a native
  symbolic kernel inside `feldspar-core` (Rust), so feldspar
  controls exactly how the kernel interfaces with the rest of the
  library; an OPTIONAL sympy interface lives Python-side for
  conversion (import/export), not as the engine of record. This
  unblocks WO-11 dispatch.
- **R2 -- canonical simplification. RESOLVED (WO-11, 2026-07-08):**
  pinned in `crates/feldspar-core/src/symbolic.rs` (`CANON_VERSION`):
  a fixed total order over `Expr` (kind rank, then structural
  recursion; `f64::total_cmp` for literals), a bottom-up
  flatten/fold-literals/drop-identities/sort rewrite to a fixed
  point (confluent, idempotent -- distribution and like-term
  collection deliberately NOT performed), digested via a dedicated
  canonical S-expression string (`canonical_string`, not
  `serde_json` of the AST). Any change to these rules is a
  `CANON_VERSION` bump. Detail: `../implementation/
  WO-11-symbolic-core.md` closing report.
- **R3 -- non-unique inversion. RESOLVED (WO-11, 2026-07-08):**
  `invert_for` peels structurally from the equation's root to the
  target's unique occurrence (an occurrence-count gate makes
  multi-occurrence targets `NonInvertible` up front); an even-power
  target returns `Err(MultiBranch{variable, branches})` unless the
  author supplies `branch=`, never guessed. Verified: `E =
  0.5*k*x^2` solved for `x` is `MultiBranch` without a declared
  branch, succeeds with one. Detail: `../implementation/
  WO-11-symbolic-core.md` closing report.
- **R4 -- symbolic propagation. DECIDED (owner closure directive,
  2026-07-08, `lithos:docs/workflow/design-log/2026-07-08-cycle-27.md`
  D146):** the delta-method `Propagation` implementation (02) gains
  a symbolic-derivative mode: where a step's law is a symbolic
  `Relation`, derivatives come from the kernel's differentiation
  over the canonical AST; otherwise numeric differencing (the
  existing path) -- one Propagation protocol, mode chosen per step,
  never per solve. `CANON_VERSION` folds into every digest the
  symbolic mode touches (a canonicalization change re-keys exactly
  the affected results). RESOLVED (WO-22, landed 2026-07-08):
  `feldspar_core::symbolic::differentiate` (product/chain/power
  rules over the existing node set, canonicalized output) and
  `feldspar_core::propagation::{Normal, DerivativeMode,
  delta_propagate}` (first-order delta-method combination, per-input
  symbolic/numeric mode). `CANON_VERSION` is now exposed Python-side
  (`feldspar.core.CANON_VERSION`) and folds into `Relation.law()`'s
  derivation digest (fixing a prior hardcoded-literal gap). SCOPE
  NOTE: wiring `Normal` propagation into the executor/planner's
  route-level representation choice (`execute()`/`plan()`) remains
  an explicit, not-yet-scheduled residual for a future milestone WO
  -- doc 02 marks `Normal` "Planned, not v1" and no milestone WO in
  `docs/workflow/README.md`'s dependency graph schedules that
  integration; WO-22 lands the protocol-level building blocks only.
  Detail: `WO-22-symbolic-followups.md` closing report.
- **R5 -- calibration interplay. DECIDED (owner closure directive,
  2026-07-08, same ledger):** a DERIVED direction inherits the
  declared law's CITATIONS but never its calibration EVIDENCE; the
  calibration harness re-sweeps derived directions over the mapped
  domain automatically (the inversion is exact, but domain corners
  map nonlinearly, so the sweep is the honest floor -- and it is
  cheap: the law is closed-form by construction). `Accuracy(0,0)`
  exact laws are exempt (nothing to measure; the A-7 rule). RESOLVED
  (WO-22, landed 2026-07-08): `Relation.law()` drops
  `kind="calibration"` citations on every derived direction while
  keeping all other kinds; `feldspar.calib.harness.resweep_derived`/
  `resweep_all_derived` supply the re-sweep evidence (an algebraic-
  identity residual check over the derived direction's own domain);
  `check_ceilings` re-sweeps a derived direction with no calibration
  citation live and reports UNCALIBRATED (non-blocking) only if the
  re-sweep itself cannot produce evidence. Detail:
  `WO-22-symbolic-followups.md` closing report.

## 5. Implementation

WO-11 (`../implementation/WO-11-symbolic-core.md`) LANDED
2026-07-08. Milestone M10 phase 1 (09 sec. 8) implemented: sec. 1-3
above are now backed by a real `feldspar-core::symbolic` kernel,
`feldspar.solve.sugar.Relation.law(...)`, and
`Solution.explain()`/`to_dict()` rendering of the algebraic form and
admission predicate per step. R4 (symbolic propagation) and R5
(calibration interplay) are RESOLVED (sec. 4, WO-22, landed
2026-07-08); OPEN-15 (08) records the closure.
