# WO-05: Planner search (Rust)

Status: todo
Depends: WO-03, WO-04
Language: Rust (`feldspar-core::search`), PyO3-exposed via `feldspar.plan`
Spec: 04 (problem statement, algorithm, determinism), FINV-1/5/8

## Goal

`plan(registry, known, tags, target, eps_budget) -> Result[Route,
PlanError]`: deterministic forward AND-graph search per 04.

## Deliverables

- Label-correcting forward search exactly per 04: achieved-port
  labels (interval, eps, cost, producing step), frontier ordered by
  (cost, solver_id), Pareto dominance pruning on (cost, eps),
  admissible termination.
- Expansion executes nothing: interval/eps estimates call the WO-04
  core routines on hull corners (FINV-4).
- `Route`: ordered steps, per-step realized domains, predicted eps
  decomposition, total cost, route digest (AD-5). Carries enough for
  WO-06 to execute without re-search and WO-10 to explain.
- `PlanError` total union: UnknownTarget, NoApplicableSolver,
  BudgetUnreachable{best_eps}, CyclicPortEquivalence (FINV-5).
- Tier-blindness: search reads cost/accuracy/domain only (FINV-8);
  the permute-tier-labels test lands here.
- Registry snapshot crossing: the frozen registry's SolverInfo set
  crosses to Rust once at freeze (marshalled, digested); search never
  calls back into Python.
- tracing spans per expansion; log every domain rejection and prune.

## Acceptance

- A 5-solver toy registry (two routes to target, one cheap/sloppy,
  one costly/tight): budget selects between them; tie-break test
  with equal-cost routes resolves lexicographically; all PlanError
  variants reachable; twice-run identical Route digests; FINV-8 test
  green.
