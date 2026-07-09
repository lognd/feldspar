# WO-22: symbolic follow-ups (R4 symbolic propagation + R5 calibration policy)

Status: todo
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
