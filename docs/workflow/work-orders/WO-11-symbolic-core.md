# WO-11: The symbolic core (M10, phase 1)

Status: done (2026-07-08). WO-01..10 landed first (per the prior
coordinator note); WO-11 dispatched once WO-10's `explain()`
existed. See "Closing report" at the bottom of this file for how
R2/R3 were resolved, exactly what shipped, and what was verified vs.
written-but-unverified.
Depends: WO-03 (solver protocol + registry -- the lowering target,
DONE), WO-06 (solve facade, DONE), and functionally WO-10 (for the
`explain()` acceptance golden -- see coordinator note above)
Language: native Rust symbolic kernel in `feldspar-core` (R1
decision, owner, 2026-07-08), with an optional sympy conversion
interface Python-side for import/export; everything that LANDS in
the registry is ordinary raw-protocol entries either way
Spec: 11 (the decided direction, sec. 1-3 normative; sec. 4
residuals R1-R3 must be resolved at or before dispatch, R4/R5 stay
future), 03 (registration ergonomics -- the one-protocol rule;
the amended Relation paragraph), 10 sec. 2 (authoring FORM, not a
tenth pattern), 09 sec. 8 M10

## Goal

One declared symbolic equation registers as N ordinary solver
directions, and validity domains become predicates the dispatch
boxes are derived from -- with digests, citations, determinism, and
the planner untouched.

## Deliverables

- **Symbolic Relation form**: `Relation` accepts one symbolic
  equation (canonical expression type per R1); directions are
  derived at declaration time by symbolic inversion and lowered
  through `make_direction` -- digest-equal to a hand-built twin
  (the sugar-equivalence test pattern, F-series). Non-invertible
  variables are an `Err` naming the variable; multi-branch
  inversions are an `Err` listing branches until the author declares
  one per direction (R3). Hand-written directions may coexist beside
  derived ones under the same law.
- **Canonical form + digesting**: deterministic canonicalization of
  expressions (pinned rules per R2); the canonical serialized form
  folds into the solver digest; a canonicalization-rule change is a
  loud, versioned event.
- **Symbolic domain predicates**: `Domain` optionally carries
  predicate expressions over ports; the dispatch box is DERIVED
  from predicates where boundable (else declared alongside, with
  the derivation refusing silently-wrong hulls); predicates ride
  into `SolverInfo` so the conformance kit can spot-check box
  consistency against them.
- **Provenance + explain()**: derived directions record the
  derivation (solved-for variable, branch) in provenance; citations
  are inherited from the law; `Solution.explain()` renders the
  algebraic form and the domain-admission predicate per step, still
  as pure rendering of carried data (WO-10's no-recomputation test
  extends here).
- **Accuracy inheritance**: deriving from EXACT stays EXACT;
  deriving from a banded law keeps the band (the transform is
  exact algebra); anything else is a declaration error, not a
  guess (R5's calibration policy stays future -- derived directions
  cite the law's calibration unchanged in this WO).
- **Docs + ledger**: 11 marked implemented where landed; 03/10
  amendment notes flipped to cite the landed form; OPEN-15 residual
  lines updated; TODO.md ledger entries; edge-case matrix rows
  added to `02-edge-cases.md` in the same change.

## Acceptance

- A textbook law (e.g. `Q = C_d * A * sqrt(2 * dp / rho)`) declared
  once symbolically registers all its solvable directions; each is
  digest-equal to a hand-built twin; the twins' goldens prove it.
- A deliberately non-invertible declaration and a multi-branch
  declaration both fail loudly at declaration time with the named
  variable/branches.
- Domain predicates derive the dispatch box for an interval-boundable
  predicate set; an unboundable predicate without a declared box is
  a declaration error.
- Determinism: two runs (and both CI platforms) produce identical
  canonical forms and digests.
- `explain()` golden showing the algebraic step + admission
  predicate; no-recomputation test still green.
- `make check` green; conformance kit extended checks green.

## Non-goals

- Optimization, invented relations, solve-time CAS evaluation
  (11 sec. 3).
- Symbolic delta-method propagation (R4) and derived-direction
  calibration policy (R5) -- future, tracked in OPEN-15.
- Migrating the existing hand-written catalog: existing entries
  stand; symbolic declaration is available, not mandatory.

## Closing report (2026-07-08)

### R2 -- canonical simplification (RESOLVED, pinned)

Canonical form lives in `crates/feldspar-core/src/symbolic.rs`
(`Expr`, `CANON_VERSION = 1`). No `Sub`/`Div` nodes -- authoring
sugar lowers `a - b -> Add[a, Neg(b)]`, `a / b -> Mul[a,
Pow(b, Lit(-1))]` at the `Expr` builder level, so subtraction and
division never appear in the canonical tree.

Total order (`Expr::cmp`): `kind_rank` first (`Lit`=0, `Var`=1,
`Neg`=2, `Pow`=3, `Unary`=4, `Add`=5, `Mul`=6), then structurally
within a kind -- `Lit` via `f64::total_cmp` (bit-pattern IEEE total
order, so `-0.0 < 0.0`, no NaNs by construction), `Var` by byte
order, `Neg`/`Unary` recurse on the inner expression, `Pow` compares
base then exponent, `Add`/`Mul` compare operand-wise then by length.

`canonicalize()` is a bottom-up fixed point: recurse into children,
flatten nested same-kind `Add`/`Mul`, fold literal-only operands via
a FIXED left-fold in canonical order (deterministic float result,
AD-13), drop `+0.0`/`*1.0` identities and collapse a `0.0` factor,
unwrap singleton `Add`/`Mul`, sort commutative operands by `cmp`.
Deliberately does NOT distribute, collect like terms, or simplify
`sqrt(x^2)` -- confluent and idempotent by construction (tested:
`canonicalize_is_idempotent`).

Digest form: a dedicated prefix S-expression (`Expr::canonical_string`,
NOT `serde_json` of the enum) -- `V:name`, `L:<format_f64>`,
`(neg E)`, `(sqrt E)`, `(pow B X)`, `(add E...)`, `(mul E...)` --
insulated from serde representation drift and using the one
`format_f64` (ryu) home for floats. This is folded into a derived
direction's `derivation_digest` (`canonical_digest({"canon_version":
1, "form", "solved_for", "branch"})`), a PROVENANCE digest, NOT the
`SolverInfo` registry digest (see the digest-equality reconciliation
below). Any future change to `kind_rank`, flattening, identity
elimination, the literal-fold order, or `canonical_string`'s format
is a `CANON_VERSION` bump -- a loud, versioned event, per R2.

### R3 -- non-unique inversion (RESOLVED, pinned)

`invert_for(lhs, rhs, target, branch)` normalizes to `expr =
canonicalize(lhs - rhs)`, gates on `count_var(target) == 1` exactly
(0 -> `NonInvertible{Absent}`, >1 -> `NonInvertible{
MultipleOccurrences}`), then peels operations from the root down the
unique path to `target`, moving each inverse to an accumulator:
`Add` subtracts the other addends, `Mul` divides by the other
factors, `Neg` negates, `Unary(Sqrt, _)` squares (admission `>= 0`,
single `Principal` branch -- sqrt outward is unique), `Pow(base,
Lit(n))` with target in `base`: odd integer `n` yields a unique real
root (`Principal`); even integer `n` returns `Err(MultiBranch{
variable, branches: [Positive, Negative]})` unless `branch` is
supplied, never guessing. Target inside an exponent, or inside a
`UnaryFn` with no v1 inverse, is `NonInvertible{NoInverse}`.

Proven by test (`crates/feldspar-core/src/symbolic.rs` and
`tests/unit/test_symbolic.py`): `Q = C_d * A * sqrt(2*dp/rho)`
inverts cleanly (single `Principal` branch, no multi-branch case
anywhere) for all 5 variables; `E = 0.5*k*x^2` solved for `x` with
no declared branch returns `MultiBranch{variable: "x", branches:
[Positive, Negative]}`, and re-declaring with `branches={"x": "+"}`
succeeds -- the real, testable proof the Err-listing-branches path
exists and is exercised, not just designed.

### Load-bearing reconciliation: digest-equality vs. "folds into the digest"

The WO's acceptance bar ("digest-equal to a hand-built twin") and
deliverable text ("canonical form folds into the solver digest")
are in tension: `SolverRegistry.digest()` is `canonical_digest([
SolverInfo, ...])`, and every `SolverInfo` field reaches it via
`model_dump()`. Resolution (pinned): the five provenance fields
added to `SolverInfo` (`algebraic_form`, `solved_for`, `branch`,
`admission_predicate`, `derivation_digest`) are pydantic `Field(
exclude=True)` -- dropped by `model_dump()`, invisible to
`canonical_digest`/`registry.digest()`. Twin-equality holds by
construction. The "canonical form folds into a digest" requirement
is satisfied by the separate `derivation_digest` provenance field
(R2 above), which answers "did this direction's algebra change" --
a different question from "is this direction digest-identical to a
hand-built twin," and the two must not be conflated. Verified:
`tests/unit/test_symbolic.py::test_law_derived_digest_equals_hand_built_twin`
and the pre-existing `tests/unit/test_registry.py::
test_sugar_direction_digest_equals_hand_built_twin` both pass
unchanged.

### Domain predicate design decision (found during implementation, not in the original design)

`predicate_to_box`'s v1 engine only bounds a predicate that reduces
to a single-port affine form (`c*port + k <cmp> 0`); it correctly
refuses (`UnboundablePredicate`) anything nonlinear or multi-variable
rather than derive a silently-wrong hull (11 sec. 2). Symbolic
inversion's OWN admission predicates (e.g. a `sqrt`'s range
constraint) are frequently multi-variable ratios (e.g. `Q/(C_d*A)
>= 0` for the orifice law's `dp`/`rho` directions) that this engine
cannot bound. Resolution: `Relation.law()` feeds ONLY
author-declared `predicates=` into `predicate_to_box` for dispatch-
box derivation; inversion's admission predicates ride into
`SolverInfo.admission_predicate` as PROVENANCE ONLY, rendered by
`explain()`, never silently narrowing (or blocking registration of)
the dispatch box. This matches the WO's own text under "Provenance +
explain()" ("`explain()` renders ... the domain-admission predicate
per step") more precisely than the original design sketch, which had
conflated the two uses. A future WO could extend `predicate_to_box`
to a general interval-arithmetic walk (bounding multi-variable
predicates from a declared per-port box, e.g. sign-bounding a ratio
from each factor's known sign) -- tracked as a residual, not
required by this WO's acceptance bar.

### What shipped

- `crates/feldspar-core/src/symbolic.rs`: `Expr`, `UnaryFn`, `Cmp`,
  `Predicate`, `Branch`, `Inversion`, `SymbolicError`,
  `NonInvertibleReason`, `EvalError`, `canonicalize`,
  `canonical_string`, `eval`, `invert_for`, `invertible_targets`,
  `predicate_to_box`. 7 unit tests, all passing; wired into
  `crates/feldspar-core/src/lib.rs`.
- `crates/feldspar-py/src/symbolic.rs`: `PyExpr`/`PyPredicate` +
  `invert_for`/`invertible_targets`/`predicate_to_box` PyO3
  exposure, `EvalErrorRaised`/`SymbolicErrorRaised` exceptions
  (`crates/feldspar-py/src/errors.rs`), registered in
  `crates/feldspar-py/src/lib.rs`; `python/feldspar/_feldspar.pyi`
  updated to match.
- `python/feldspar/solve/errors.py`: `RegistryError.NonInvertible`/
  `.MultiBranch`/`.UnboundablePredicate`/`.EmptyDomain`.
- `python/feldspar/solve/_models.py`: `SolverInfo` gains the five
  `exclude=True` provenance fields.
- `python/feldspar/solve/_build.py`: `build_solver_info_and_fn`
  threads the five provenance kwargs (default `None`) through the
  ONE lowering path.
- `python/feldspar/solve/sugar.py`: `Relation.law(lhs, rhs,
  predicates=(), branches=None, declared_box=None)` -- derives every
  invertible target, appends `(SolverInfo, SolveFn)` pairs to the
  same `_directions` list `.direction()` populates (hand-written and
  derived directions coexist under one `Relation`, per the WO).
- `python/feldspar/core.py`: re-exports `Expr`/`Predicate`/
  `invert_for`/`invertible_targets`/`predicate_to_box`.
- `python/feldspar/plan/execute.py`: `Solution.step_algebraic_form`/
  `.step_admission_predicate`, populated only when carried (hand-
  written steps have no entry).
- `python/feldspar/plan/report.py`: `explain()`/`to_dict()` render
  the two new fields per step, `"(not carried -- hand-written
  direction)"` when absent -- pure rendering, no new computation
  (WO-10's no-recomputation test extended, still passes).
- `tests/unit/test_symbolic.py`: 15 tests (digest-equality golden,
  all-5-directions registration, non-invertible naming, multi-branch
  naming + resolution, boundable/unboundable predicate cases,
  determinism, `explain()` golden for a mixed derived+hand-written
  route, eval domain-fault-as-recoverable-value).
- `tests/unit/test_report.py`: existing golden updated for the two
  new rendered lines.

### Acceptance bar -- executed and observed

- Textbook law (`Q = C_d*A*sqrt(2*dp/rho)`) registers all 5
  directions; one is digest-equal to a hand-built twin (test
  passing). EXECUTED AND OBSERVED.
- Non-invertible declaration (`y = x + x`, solving for `x`) fails
  loudly naming the variable via `NonInvertible`. EXECUTED AND
  OBSERVED.
- Multi-branch declaration (`E = 0.5*k*x^2` solved for `x`) fails
  loudly listing `[Positive, Negative]`; declaring a branch succeeds.
  EXECUTED AND OBSERVED.
- Boundable predicate set derives a box (`Re < 2300` narrows
  `box["Re"].hi` to 2300.0); unboundable predicate without a
  compatible declared box is a declaration error. EXECUTED AND
  OBSERVED.
- Determinism: verified WITHIN this single sandbox/process (two
  independent `law()` calls, two independently-built structurally-
  equal `Expr` trees canonicalize identically). NOT independently
  re-verified across the CI platform matrix -- WRITTEN BUT
  UNVERIFIED beyond this sandbox, same limitation WO-10 recorded for
  its own determinism claims.
- `explain()` golden shows `algebraic_form:`/`admission_predicate:`
  per step for a derived direction and `"(not carried -- hand-
  written direction)"` for a hand-written one in the same route;
  no-recomputation property holds (pure rendering, same pattern as
  WO-10). EXECUTED AND OBSERVED.
- `make check`: `cargo fmt --check`, `cargo clippy --workspace
  --all-targets -- -D warnings`, `cargo test --workspace` (69 Rust
  tests total across `feldspar-core`/`feldspar-library`, including
  the 7 new symbolic tests), `ruff check`/`ruff format`,
  `lint-imports` (regolith-confinement contract kept), `ty check`
  (clean for all WO-11 code; the pre-existing `_compat.py` tomli/
  tomllib diagnostic WO-10 already flagged as unrelated is still
  present, unchanged), `pytest tests/unit` (152 passed, up from 137
  pre-WO-11). ALL EXECUTED AND OBSERVED GREEN in this sandbox.
- "Conformance kit extended checks green": WO-11 is engine-side only
  -- `python/feldspar/pack/` (WO-09's regolith conformance surface)
  wraps `mech.static_stress`/`mech.static_deflection`, neither of
  which is symbolically declared, and regolith never constructs an
  `Expr`/`Predicate` or calls `Relation.law()` directly (FINV-3/10:
  regolith imports stay confined to `feldspar.pack`). There is
  nothing WO-11-specific for the conformance kit to exercise in this
  WO; `lint-imports`' regolith-confinement contract (which WOULD
  catch a leak) stays green. Reported honestly as N/A rather than
  fabricated as tested.

### Known scope residual (not required by this WO, noted for a future one)

`predicate_to_box` bounds single-port affine predicates only;
multi-variable admission predicates from inversion (sqrt/pow
ranges) are carried as provenance but never used to narrow a
dispatch box automatically. A future WO could extend it to a general
interval-arithmetic walk over the predicate's expression tree,
sign-bounding ratios/products from each factor's declared box --
this was in the original architect design sketch's ambition but
descoped once the acceptance bar (twin-equality, named errors,
boundable/unboundable predicate split) was met without it.
