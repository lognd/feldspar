# WO-05: Planner search (Rust)

Status: done
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

## Implementation notes (landed)

- `crates/feldspar-core/src/search.rs`: `SolverSummary` (the frozen
  planning-relevant `SolverInfo` snapshot -- deliberately no `tier`
  field, so FINV-8 is enforced by the type, not by convention),
  `PlanError`, `RouteStep`/`Route`, and `plan()`. A generalized
  positive-cost Dijkstra over the AND-hypergraph: per-port Pareto
  label sets (pruned by inflated-interval subset dominance), a global
  candidate frontier ordered by `(cost, solver_id, combo tie-key)`,
  terminating the instant a `target` label meets the eps budget
  (sound because all costs are positive).
- **Estimation convention**: `SolverInfo` carries no executable
  formula (only `Domain`/`Accuracy`/`cost`), and search never calls
  back into Python -- so a step's output value at each swept corner is
  estimated as the SUM of that corner's input values (a documented
  placeholder magnitude), then hulled via the real WO-04
  `corner_sweep`/`inflate`/`total_error` routines exactly as the
  executor will do with the real `SolveFn` later (FINV-4: same core
  routine, hull corners). This drives route SELECTION only; WO-06's
  executor replaces it with the real sweep before anything reaches a
  `Solution`.
- `CyclicPortEquivalence` is detected pre-search over the subgraph of
  solvers shaped like a pure port alias (exactly one input, exactly
  one output): a directed-graph cycle there (three-color DFS) is the
  concrete "cyclic port equivalence" case FINV-5 requires be total.
- `Route.total_cost` is computed by walking the winning label's step
  tree post-search and summing each distinct step once (dedup by
  `Rc` pointer identity), not by reusing the frontier's additive
  per-label cost heuristic -- which may over-count a step shared by
  two input branches of a later solver (a diamond). No diamond case
  appears in the toy/acceptance registries; noted here as a known
  limitation for the "small and layered" registries this algorithm
  targets (07).
- PyO3: `crates/feldspar-py/src/search.rs` (`_PlanSolverInput`,
  `Route`, `RouteStep`, `plan`) plus `PlanErrorRaised` in `errors.rs`.
  Python facade: `feldspar/plan/route.py` (`plan()`, `Route`,
  `RouteStep`) and `feldspar/plan/errors.py` (`PlanError`, built on
  the same `_TaggedError` base as `RegistryError`/`SolveError`).
- Tests: `crates/feldspar-core/src/search.rs` (14 Rust unit tests,
  including tier-blindness and the cycle detector) and
  `tests/unit/test_plan.py` (13 Python tests covering the full WO-05
  acceptance bar and every `02-edge-cases.md` planner row).
