# WO-13: budget-seeking refinement + cost curves (M3)

Status: todo
Depends: WO-12 (payload ports -- the ladder refines meshes), WO-06
(executor)
Language: Python (`feldspar/solve/`, `feldspar/fea/`)
Spec: 09 sec. 3 (NORMATIVE: refinement ladders, eps_seeking, cost
curves, per-rung caching), 09 sec. 5 (margin-driven adaptive
refinement), 04 (planner reads cost/accuracy/domain only)

## Goal

Discretized solvers own deterministic refinement ladders driven by
the remaining eps budget; the planner sees conservative cost curves;
every rung's solve caches independently.

## Deliverables

- `SolverInfo.eps_seeking` + ladder policy folded into the settings
  digest; the climb is deterministic (same budget -> same rungs ->
  same stop); ladder top-out returns the honest error carrying best
  eps achieved (feeds regolith's what-would-resolve-it family).
- Cost curves: `cost` generalizes to sampled `(eps, cost)` points
  with conservative interpolation; scalar cost = one-point curve
  (additive schema, 09 sec. 3 -- no planner redesign; assert
  dominance pruning still sound per A-1's inflated-interval rule).
- Per-rung caching proven: an h + h/2 Richardson pair is two cache
  entries; a looser later budget reuses h and skips h/2 (the 09
  sec. 3 scenario as a test).
- Pack-side margin translation (09 sec. 5): the pack model converts
  claim margin -> eps budget -> drives the seeker; honest
  indeterminate states eps achieved vs needed.
- 02-edge-cases rows: zero budget, budget met at rung 0, ladder
  exhaustion, non-monotone eps ladder (a bug -> loud error).

## Acceptance

- The FEA cantilever discharges a tight-margin claim by climbing
  exactly the rungs the budget demands, deterministically twice;
  planner never reads `tier`; `make check` green.
