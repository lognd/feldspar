# WO-10: explain() and M1 close-out

Status: todo
Depends: WO-06, WO-09
Language: Python (`feldspar/plan/report.py`)
Spec: 04 (justification report), 03 (citations), 09 sec. 8 M1

## Goal

The justification report, and the milestone gate: everything M1
promised, verified and documented.

## Deliverables

- `Solution.explain() -> str` (and `to_dict()` for machine use):
  per-step solver, method citations, domain admission (box + tags +
  actual hull), propagated interval, charged eps, running
  accumulation; route-level cost, eps-vs-budget decomposition,
  reroute trail, cache provenance. Pure rendering of carried data --
  a test asserts no recomputation (mock solvers, no calls during
  explain).
- Deterministic output (stable ordering/formatting; golden test).
- Close-out sweep: TODO.md ledger driven to zero for WO-01..10 or
  cuts recorded per house rule; every FINV row's enforcement exists
  and is cited from the test suite; docs/ reconciled with any drift
  (same-change rule); README quickstart (install, register, solve,
  explain) written against the real API.
- File the M2+ WO stubs decision: confirm with owner before
  drafting WO-11+ (scope gate, 09 sec. 8).

## Acceptance

- `explain()` golden for the toy registry and for a real FEA solve
  (fea-marked); FINV table audit checklist committed; `make check`,
  CI matrix, and the regolith conformance job all green on the same
  commit -- that commit closes regolith WO-27 from feldspar's side.
