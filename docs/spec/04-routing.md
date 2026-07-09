# 04 -- Routing

One sentence: routing is deterministic forward search over the solver
graph -- from the set of known ports to a target port -- minimizing
total cost subject to domain validity at every step and an accumulated
worst-case error within the caller's budget.

## Problem statement

```
plan(registry, known: {port -> Interval}, tags: frozenset[str],
     target: port, eps_budget: float,
     sense: ClaimSenses = BOTH)
  -> Result[Route, PlanError]
```

`sense` is the claim sense the target quantity will serve (audit A-3;
the pack passes its `ModelSignature` sense through one-to-one, 06);
it folds into the request digest.

Find an ordered sequence of solver steps such that:

1. every step's inputs are known initially or produced by an earlier
   step (a DAG; the graph is an AND-graph because a step needs ALL its
   inputs, so this is hypergraph reachability, not plain shortest
   path);
2. every step is in-domain for the interval hull actually reaching it
   (box subset + tag superset, 02) -- the hull INFLATED by its
   accumulated model eps (02's inflation rule; domain checks see what
   the solver will actually be swept over);
3. the accumulated worst-case error at `target` -- the half-width of
   the interval propagated with eps-inflation at every intermediate
   port, plus the final step's model eps; one error-math home in
   `feldspar-core` (02) -- is `<= eps_budget`;
4. every step serves the request's `sense`: an edge with
   `conservative_for != both` is absent unless it matches `sense`,
   and (audit A-2) a one-sided edge is admissible ONLY as the final
   step -- its outputs must include `target` -- because a downstream
   step with negative sensitivity inverts the bound. Sense-preserving
   composition through declared per-input monotonicity is future
   schema, not v1.
5. among plans satisfying 1-4, total `cost` is minimal; ties break by
   lexicographic step id order (total determinism, no map-order
   dependence).

`Route` records the steps, per-step realized domains, the predicted
eps decomposition, and total cost -- enough to execute without
re-searching and to explain "why this path" in logs.

## Algorithm (v1)

Forward-chaining label-correcting search ("uniform-cost over
AND-nodes"):

- State: the set of achieved ports, each labeled with (interval, the
  producing step's model eps, cost so far, producing step). The
  label's INFLATED interval (`inflate(interval, eps)`, 02) is what
  downstream domain checks and sweeps consume.
- Frontier: applicable solvers (all inputs achieved, domain valid),
  ordered by (cost so far + step cost, solver_id).
- Expansion executes NOTHING: intervals are propagated through the
  step's declared accuracy and the corner-sweep hull bound is
  estimated from the inflated input hulls (the executor later
  computes the exact sweep; the planner's estimate uses the same core
  routine on hull corners so it cannot disagree in kind).
- Dominance pruning: a label is dropped iff another label for the
  same port is <= in cost AND its inflated interval is a SUPERSET of
  the other's inflated interval (subset dominance subsumes the eps
  comparison exactly: half-width of the inflated interval IS
  half-width + eps, the budget-checked quantity; and subset is what
  every downstream consumer sees). Both axes matter because a
  cheaper-but-sloppier path may bust the budget.
- Terminate when `target` has a label meeting the budget and no
  frontier entry can beat its cost (costs are positive; admissible).

This is exponential in pathological port graphs; real registries are
small and layered (07). If that assumption breaks, the fix belongs in
`feldspar-core` (bitset port sets, memoized subset domination), not in
API changes -- which is exactly why search lives in Rust from day one
(AD-1).

The planner must be TOTAL over its error union: unknown target port,
no applicable solver, budget unreachable (best eps found reported),
and cyclic port equivalences all return distinct `PlanError` variants,
never a wrong route and never an exception.

Degenerate cases are defined, not errors (friction G12): a target
that is already known returns a ZERO-STEP Route (value = the known
interval, eps 0, cost 0) -- callers compose without special-casing;
`eps_budget <= 0` is a request-validation error before search.

## Execution

`execute(route, registry, known) -> Result[Solution, SolveError]`
walks the route in order: corner sweep per step over eps-INFLATED
inputs (02), calls the `SolveFn` per deduplicated corner, checks
every returned value finite (NaN/inf -> `SolveError.NonFinite`, a
value, friction G12), checks every declared output present
(`SolveError.MissingOutput`, audit A-4) and any reported
`measured_eps` finite and non-negative
(`SolveError.InvalidMeasurement`), hulls outputs, charges realized
eps (which for FEA replaces the declared ceiling, 05).
Payload-domain checks (abstraction edges, 09 sec. 4a) also run
here -- an out-of-domain payload is an ordinary `SolveError` the
fallback reroute handles. Output:

```python
class Solution(BaseModel):              # frozen
    target: PortName
    value: Interval                     # propagated output interval
    eps: float                          # final step's realized model
                                        # error (upstream eps already
                                        # in value's width, 02)
    route: Route
    settings_digest: str                # folded from every step (03)
    solver_versions: Mapping[str, str]  # step id -> version
    attempts: tuple[AttemptRecord, ...] # reroute trail (below)
    cache_hit: bool                     # cache provenance (below)
```

`solve(...)` = `plan(...)` then `execute(...)`; it re-checks the
realized eps against the budget after execution (a route whose
realized FEA eps busts the ceiling returns `BudgetExceeded` with the
numbers, honest over optimistic).

## Fallback rerouting (DECIDED 2026-07-07, closes OPEN-4)

Failure of a step at execution time (tool missing, ccx crash,
realized eps busting the ceiling) is a `SolveError` value, and the
DEFAULT is to replan: `solve()` adds the failed `solver_id` to an
exclusion set, re-runs `plan()` over the remaining graph, and
executes the new route. This repeats until success or no route
remains, at which point the LAST error plus the full attempt trail is
returned -- honest indeterminate, never a silent downgrade.

- Rerouting is deterministic: same registry, same request, same
  failures => same exclusion sequence => same final route (the plan
  search is already deterministic; the exclusion set is derived state,
  not policy).
- EVERY attempt is logged: the failed step, the error variant, the
  exclusion set, the replacement route and its predicted eps/cost --
  at warning level for the failure, info for the replan (the logging
  mantra: reroutes must be reconstructable from logs alone).
- `RoutePolicy(fallback=False)` disables it for callers that need
  strict single-route predictability; the pack keeps the default ON
  and reports the EXECUTED route's digest in evidence (06), so
  evidence always describes what actually ran.

## Solve cache (DECIDED 2026-07-07, closes OPEN-5)

The engine caches `Solution`s, keyed by the tuple of digests:

```
cache_key = blake3(registry_digest      # sorted SolverInfo contents,
                                        #   versions, citations
                || request_digest       # known intervals + tags +
                                        #   target + eps budget + sense
                || settings_digest      # folded from every step (03)
                || feldspar_version)
```

**Freshness argument** (the proof obligation, stated once here and
enforced by test): FINV-2 says a solve's answer is a pure function of
(registry contents, request, settings, code version). The cache key
is exactly that tuple, digested. Therefore a stale hit would require
two different answers for identical key inputs -- which is a
determinism violation, not a caching bug; any input that could change
an answer WITHOUT changing the key is already a FINV-2 breach caught
by the twice-run determinism tests. Nothing is invalidated by time,
because time is not an input.

Corollaries that keep the argument honest:

- Tool versions (gmsh, ccx) fold into settings digests (05), so a
  tool upgrade changes the key. Tool PRESENCE does not, and the
  presence check is SYMMETRIC (audit A-5): a cached success must not
  be returned when a tool its route uses has since vanished, AND a
  cached Solution whose attempt trail rerouted around a
  `ToolMissing` failure must not be returned once that tool has
  since appeared -- a fresh solve would take the better route, and a
  hit must equal a recompute (FINV-7). Cache hits therefore
  re-verify (cheap discovery, no execution) that every tool the
  executed route uses is still present and every tool whose absence
  caused an exclusion is still absent; otherwise miss. The
  `Solution.attempts` trail carries the exclusion causes, so the
  check reads cached data only. This is the one non-digest freshness
  check and it is explicit.
- Non-deterministic solvers (`deterministic=False`) are never cached.
- Every hit and miss is logged with the key components (mantra).
- Default ON for development (the same pathways recur constantly),
  opt-out via `RoutePolicy(cache=False)` for deployments where lookup
  cost or storage dominates. regolith keeps its own evidence cache;
  the two never share storage (the pack boundary passes values, not
  cache entries).

**Per-payload step cache** (WO-12; the 09 secs. 3-4 per-rung/
per-payload discipline): beside the Solution cache, DETERMINISTIC
payload-touching steps also cache at STEP grain
(`.feldspar/cache/steps/`, `PayloadStepCache`), keyed on the step's
own purity tuple -- `solver_id`, `version`, `settings_digest`, the
inflated scalar input box, each payload input's DIGEST (a payload in
a digest is its hash, FINV-12), and `feldspar_version`. The
freshness argument above carries over verbatim at the smaller grain.
The step grain is what makes one mesh feed multiple solves: two
requests with different targets have different Solution keys but
share the mesh step's entry, so a mesh (later: a refinement rung,
09 sec. 3) is paid for once ever. `get()` applies the A-5 tool
recheck per step (a recompute would fail `ToolMissing`, so a hit
must not paper over a vanished tool); known payload ports fold into
`request_digest` as their hashes; the hit/miss counters are
contract-level (the WO-12 acceptance proves same-mesh reuse by hit
count).

## Justification report (DECIDED 2026-07-07, part of OPEN-10)

`Solution.explain()` renders the step-by-step engineering argument:
for each step in order -- the solver, its method citations (03), the
domain check that admitted it (box + tags, with the actual hull), the
propagated interval and charged eps, and the accumulation running
total; plus route-level cost, the eps decomposition against the
budget, any reroute trail, and cache provenance. Everything it prints
is already carried by `Route`/`Solution`; the report is a rendering,
not a recomputation -- so it can never disagree with the evidence.

## Determinism

Same registry contents, same request => identical Route and identical
`Solution` digests. Enforced by: sorted registry iteration, BTree core
types, tie-breaking rule above, deduplicated sorted corner order, and
the settings-digest discipline (FINV-1/FINV-2). This is what makes the
pack's evidence hashes reproducible (06) -- routing determinism is not
a nicety, it is load-bearing for regolith's cache AND for the solve
cache's freshness argument above.

Parallel execution (DECIDED 2026-07-07, closes OPEN-9): parallelism
is decoupled from expense -- when cores are available, independent
work uses them (corner solves, refinement rungs, independent route
steps, calibration sweeps), at every tier, not just the expensive
one. Three ordered constraints (full policy: 09 sec. 6):

1. determinism -- assembly is order-deterministic (sorted corner
   order, sorted digest folds, never arrival order); parallel and
   serial results are bit-identical, and the determinism suite runs
   both paths;
2. portability -- pure-Rust threading (std/rayon) only, no
   platform-specific APIs;
3. fallthrough -- the serial path always exists on every platform
   (thread count 1 is configuration, not a build variant).
