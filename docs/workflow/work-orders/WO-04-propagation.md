# WO-04: Propagation and error accumulation (Rust)

Status: todo
Depends: WO-02
Language: Rust (`feldspar-core`), PyO3-exposed
Spec: 02 (error split, uncertainty representations), FINV-4, 09 sec. 6

## Goal

The ONE implementation of the corner sweep and the accumulation rule
-- the engine's error math, shared verbatim by planner estimates and
executor exact sweeps (04).

## Deliverables

- `Propagation` trait with the Interval strategy: deterministic
  deduplicated sorted corner enumeration, per-corner evaluation via a
  callback, hull assembly; explicit `to_interval()` identity. Trait
  shape must not assume scalar-only (02's OPEN-11 guard) or
  Interval-only (Normal/Quantile are M-later; leave trait room, no
  stubs).
- Error-math home (02, audit A-1): `inflate(iv, eps)` -- every
  consumed intermediate port is inflated by its producing step's eps
  before sweep and domain checks -- and `total_error(out_hull,
  model_eps)` = half-width + FINAL step's model eps, the
  budget-checked quantity. NO eps summation along routes exists
  anywhere. Property-tested: monotone in inputs, zero for exact
  point/exact solver, and the gain-counterexample row
  (02-edge-cases WO-04).
- Corner-monotonicity contract surface: sweep is exact iff declared
  monotone; non-monotone solvers' widened-eps obligation documented
  at the trait.
- Serial execution now; the rayon parallel path is M5 (AD-10) -- but
  assembly is written sorted-order from day one so M5 is a drop-in.
- PyO3 exposure for the executor (WO-06) and planner estimates
  (WO-05) to share the same symbols (FINV-4).
- proptest: hull contains all corner results; dedup correctness;
  sweep of degenerate intervals equals single evaluation.

## Acceptance

- cargo tests green incl. property suite; a Python-side call
  sweeping a 3-input box hits 8 corners deduplicated and sorted, and
  the inflate/total_error math of a 2-step toy route (including a
  gain != 1 second step) matches hand arithmetic.
