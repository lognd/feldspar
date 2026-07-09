# 02 -- Edge-case test matrix (NORMATIVE)

Every row is a required test; the WO column says which work order
ships it. An implementer agent closing a WO greps this file for its
WO id and covers every matching row. Sourced from the lithos pressure
tests (`examples/lithos/README.md`, G12 and friends) plus systematic
enumeration of the numeric surface.

## Intervals and units (WO-02)

| case | required behavior |
|---|---|
| `Interval.new(2, 1)` | Err(InvertedInterval) |
| `Interval.new(0, inf)` / NaN bound | Err(NonFiniteBound) |
| degenerate `[x, x]` | width 0; corner sweep collapses to 1 corner |
| interval spanning 0 with eps_rel | `Accuracy.worst_over` takes max at the larger `abs` endpoint |
| `to_si(25, "degC")` | 298.15 (offset applied) |
| `"degC"` inside a compound unit at table load | Err(OffsetInCompound) |
| `"%"` ingest | scale 0.01 to unit "1" |
| unknown unit string | Err(UnknownUnit), never a guess |
| `to_si(6000, "rpm")` | 628.3185... rad/s (scale alias, G19) |
| g0-referenced ingest (`"s(Isp)"` view) | stored m/s; print restores view (G31) |
| digest of same map, two insertion orders | identical |

## Registry (WO-03)

| case | required behavior |
|---|---|
| duplicate solver_id | Err(DuplicateSolverId) |
| same port declared Pa and m by two solvers | Err(PortUnitConflict) |
| same port scalar and vector | Err(PortRankConflict) |
| citations empty or calibration-only | Err(EmptyCitations) |
| cost <= 0 | Err(NonPositiveCost) |
| accuracy keys != outputs | Err(AccuracyOutputMismatch) |
| register after freeze | Err(Frozen) |
| import-order permutation of register() calls | identical registry digest |
| solver naming an undeclared port | Err(UnknownPort) naming it (F12) |
| declare_ports twice, conflicting unit/rank | Err(DuplicatePortDecl) |
| sugar-built direction vs hand-built twin | identical SolverInfo digest (one-protocol rule) |
| bare-float return with 2 outputs | decoration-time error |
| Mapping return missing an output port | executor Err(MissingOutput(port)) (A-4) |
| SolveOutput.measured_eps negative/NaN | executor Err(InvalidMeasurement(reason)) (A-4) |
| Relation direction referencing a port outside relation ports | decoration-time error |
| table x not strictly ascending | Err(BadTable) |
| table query at exact endpoint | in-domain (closed box) |
| Correlation with accuracy_rel <= 0 | decoration-time error |

## Propagation (WO-04)

| case | required behavior |
|---|---|
| 3 interval inputs, 1 degenerate | 4 corners after dedup, sorted |
| solver Err at one corner | whole sweep Err (that corner named) |
| solver returns NaN | Err(NonFinite(port)) at executor level (WO-06 wires it) |
| non-monotone flag set | sweep still runs; eps widening is the solver's declared duty (doc-tested) |
| accumulation with eps 0, point inputs | total eps 0 exactly |
| step-2 gain k consumes step-1 output with eps e | target error tracks ~k*e via inflation, NOT ~e (the A-1 summation counterexample, pinned) |
| inflate() then domain check | subset rule applies to the INFLATED interval (04) |

## Planner (WO-05)

| case | required behavior |
|---|---|
| target already in known | zero-step Route, eps 0, cost 0 |
| eps_budget <= 0 or NaN | Err(InvalidBudget) before search |
| unknown target port | Err(UnknownTarget) |
| reachable port, budget too tight | Err(BudgetUnreachable) carrying best_eps found |
| two equal-cost routes | lexicographic winner, stable twice |
| solver whose domain box excludes the known hull | edge absent (not an error) |
| input interval PARTIALLY inside domain box | edge absent (subset rule, 02) |
| tag required by solver, missing from request | edge absent |
| `conservative_for=UPPER` edge, `sense=LOWER` request (`plan(sense=...)`, A-3) | edge absent (G4) |
| one-sided edge producing a NON-target port | edge absent (A-2 final-step-only composition rule) |
| sense permuted between two otherwise-identical requests | distinct request digests (A-3 fold) |
| cycle of port equivalences | Err(CyclicPortEquivalence), terminates |
| tier labels permuted | identical Route (FINV-8) |

## Solve facade (WO-06)

| case | required behavior |
|---|---|
| step fails, alternative exists | reroute; attempts trail length 2; deterministic twice |
| step fails, fallback=False | that SolveError returned, one attempt |
| all routes fail | Err(NoRouteRemaining) with full trail |
| realized eps > declared ceiling | Err(BudgetExceeded) with numbers |
| cache: identical request twice | hit; byte-equal Solution (FINV-7) |
| cache: tool vanished since cached success | miss + re-solve -> ToolMissing value |
| cache: Solution rerouted around ToolMissing; tool since INSTALLED | miss + re-solve takes the better route (A-5 symmetric recheck) |
| cache: any SolverInfo field changed | miss (registry digest moved) |
| deterministic=False step in route | route never cached |
| threads != 1 in v1 | validation error (M5 opens it) |

## Library + calibration (WO-07)

| case | required behavior |
|---|---|
| Lame at ratio -> 1 (r_o = r_i) | outside domain box; edge absent, never a division blowup |
| cantilever at L=0 or negative | ctor/domain rejects |
| ceiling tighter than newest CalibRecord | CalibError(CeilingBusted), make check fails |
| calibrate with mismatched domains | Err(DomainMismatch) |
| extern "C" symbol table | every WO-07 formula present (dlopen smoke) |

## FEA (WO-08)

| case | required behavior |
|---|---|
| gmsh absent | import OK; solve -> ToolMissing with install guidance |
| ccx absent / FELDSPAR_CCX bogus | ToolMissing, path named |
| ccx nonzero exit | ToolFailed carrying log tail |
| timeout | Timeout value; tempdir cleaned |
| truncated .dat table | ParseFailed with line context |
| non-monotone h/h2 Richardson pair | conservative fallback eps (05), flagged in logs |
| implausible convergence order p | same fallback path |
| settings digest field-enumeration test | adding a MeshSettings field without digest fold FAILS the test |

## Pack + conformance (WO-09)

| case | required behavior |
|---|---|
| unresolved given (missing material port) | DomainError naming the port (G2 reject-unresolved rule, 06) |
| G7 fixture: idealization out-of-domain, payload channel unbuilt | honest indeterminate NAMING the missing channel (examples/lithos/tracks/hematite/sensor_boom.hema) |
| out-of-domain corner (one corner outside box) | DomainError, never partial evidence |
| twice-run identical request | byte-identical evidence hash |
| pack version bump | only feldspar-produced evidence re-keys |
| regolith uninstalled | every non-`regolith` test green (FINV-3) |

## explain() (WO-10)

| case | required behavior |
|---|---|
| explain on cached Solution | renders cache provenance; zero solver calls (mock-asserted) |
| explain after reroute | full attempt trail rendered |
| golden stability | byte-identical across runs and platforms |

## Payload ports (WO-12)

| case | required behavior |
|---|---|
| same port declared `payload(mesh)` and `payload(spectrum)` | Err(PayloadKindConflict) -- the unit-mismatch mirror |
| payload decl with a kind outside the 09 sec. 4 table | Err(UnknownPayloadKind) naming port and kind |
| same port declared scalar and `payload(kind)` | Err(PortRankConflict) (unchanged rank rule) |
| wrong-kind PayloadRef supplied at execution | Err(PayloadKindMismatch) naming both kinds |
| declared payload port, no ref supplied | Err(MissingPayload), never a KeyError |
| ref whose digest the store cannot resolve | solver's Err(DanglingDigest) surfaces with step attribution |
| declared payload output absent from SolveOutput.payloads | Err(MissingOutput) (A-4 extended) |
| payload output varies across corners | Err(InvalidMeasurement) -- payloads are exact by reference |
| two requests differing only in a payload's digest | distinct request digests (FINV-12: a payload in a digest is its hash) |
| two refs same digest, different `origin` | identical request digests (origin is provenance, never folds) |
| cantilever geometry.parametric -> mesh -> fea | routed as two registry edges; twice-run route digest identical |
| second solve consuming the same mesh payload | mesh step is a step-cache HIT (hit count +1); mesher runs once ever |
| tier labels permuted on payload edges | identical Route (FINV-8 unchanged by payloads) |
| abstraction edge: payload feature out of domain (G7 hole-in-root) | Err(OutOfDomain) value at EXECUTION; fallback reroute lands the next tier; deterministic twice |
| one-sided abstraction edge, wrong-sense request | edge absent (A-3/G4 unchanged by payloads) |

## Budget-seeking + cost curves (WO-13)

| case | required behavior |
|---|---|
| zero remaining eps budget reaches an eps_seeking step | ladder climbs to exhaustion; `Err(SolveError.LadderExhausted(best_eps, budget=0.0, rungs_tried))`, never a false success |
| budget met at rung 0 (first Richardson pair already fits) | climb stops after the mandatory 2-rung pair; zero extra rungs run |
| ladder exhaustion (every rung tried, none fits) | `Err(LadderExhausted)` carrying the best eps actually achieved -- honest indeterminate, never a silent downgrade |
| non-monotone eps ladder (a finer rung's pair reports WORSE eps) | loud `RuntimeError` -- a solver/ladder-policy bug, never a `Result` value |
| no budget context (`eps_budget=None`, bare `execute()` call) | runs exactly the fixed first pair (pre-WO-13 behavior), never seeks further |
| same budget, same registry, run twice | identical rungs climbed, identical eps, identical value (determinism) |
| looser later request over the same scalar box | reuses every already-cached coarser rung (`RungCache` hit); only strictly-finer NEW rungs run |
| `cost_curve` query at a budget tighter than every declared point | reports the finest (most expensive) point's cost -- conservative, never an under-estimate |
| `cost_curve` query at a budget looser than every declared point | reports the coarsest (cheapest) point's cost |
| scalar (non-eps-seeking) solver's cost | unaffected: planner still reads only `SolverInfo.cost`; `cost_curve` stays `None` |
| eps_seeking solver's raw body signature | `(x, eps_budget)`, tagged `.eps_seeking` on the wrapped `SolveFn` (`_build.wrap_solve_fn`); a plain/raw `SolveFn` keeps the one-argument call unchanged |

## Symbolic core (WO-11)

| case | required behavior |
|---|---|
| symbolic declaration, digest vs. hand-built twin | derived direction's `SolverInfo` digest-equal to a hand-built twin (5 provenance fields are `exclude=True`, digest-invisible) |
| symbolic declaration, all invertible targets | one `law()` call registers one direction per port with exactly one occurrence in the equation |
| non-invertible variable (0 or >1 occurrences) | `Err(RegistryError.NonInvertible)` naming the variable at declaration time; never a silent partial registration |
| multi-branch inversion (even-power target), no declared branch | `Err(RegistryError.MultiBranch)` naming the variable and listing branches (`+`/`-`); never a guessed branch |
| multi-branch inversion, branch declared | registers successfully with the chosen branch's closed form |
| domain predicate, boundable (single-port affine) | dispatch box derived, narrowing/matching the declared box side |
| domain predicate, unboundable (nonlinear/multi-var) without a compatible declared box | `Err(RegistryError.UnboundablePredicate)`, never a silently-wrong hull |
| declared box + predicates intersect to nothing | `Err(RegistryError.EmptyDomain)` |
| inversion admission predicate (e.g. sqrt range) is multi-variable | carried as `SolverInfo.admission_predicate` provenance only, rendered by `explain()`, never fed into box derivation |
| canonicalization determinism | two independently-built, structurally-equal `Expr` trees canonicalize to the same `canonical_string()`/`derivation_digest` (verified single-sandbox; cross-platform claimed by design, not independently re-verified here) |
| `eval()` domain fault (negative sqrt argument) at solve time | derived `SolveFn` returns `Err(SolveError...)`, never raises |

## Structured ports + vibration tier (WO-16)

| case | required behavior |
|---|---|
| same port declared scalar then vector (or vice versa) | `Err(RegistryError.PortRankConflict)` -- covers the WO-03 rank-mismatch row for a REAL ranked port, `mech.vibe.spectrum` |
| `mech.vibe.grms` claim's `first_mode_freq` outside the supplied spectrum payload's `freq_hz` domain | `Err(SolveError.OutOfDomain)` naming the violation -- honest error, never extrapolated/clipped |
| `first_mode_freq` exactly at a spectrum grid endpoint | looked up directly, no interpolation division-by-zero |
| mask-containment profile/mask `t` grids differ in length or values | `Err(SolveError.OutOfDomain)` (domain misalignment) -- never an implicit resample |
| profile stays within mask at every sample | `mech.vibe.mask_containment` reports `1.0` |
| profile exceeds mask at any sample | `mech.vibe.mask_containment` reports `0.0` |
| `mech.vibe.first_mode_freq` claim, beam direction's domain admits the box | closed-form beam direction wins on cost (FINV-8 tier-blind) |
| `mech.vibe.first_mode_freq` claim, beam direction's domain does NOT admit the box (e.g. density outside its declared range) | planner routes through `fea.mesh.cantilever -> fea.modal.cantilever_from_mesh` instead (fea-marked; ccx/gmsh required to execute) |
| `explain()` on a mixed derived + hand-written route | derived step renders `algebraic_form`/`admission_predicate`; hand-written step renders `"(not carried -- hand-written direction)"` |

## Coupled groups (WO-18)

| case | required behavior |
|---|---|
| `CoupledGroup(accuracy=EXACT, ...)` | raises `ValueError` at construction (EXACT forbidden for a composite, 09 sec. 4b) |
| `CoupledGroup.register()` | composite `SolverInfo.tier == "coupled"`, inputs/outputs are ONLY the declared boundary ports -- no internal member port ever appears, so the planner's graph stays a DAG |
| closure reaches `tol` within `max_iter` | `Ok(SolveOutput)`; `values` cover exactly `boundary_outputs`; `measured_eps = accuracy.eps_rel + residual` (closure residual charged into the realized eps, never derived from member `Accuracy`) |
| closure exhausts `max_iter` without `tol` | `Err(SolveError.NoConvergence(iterations=max_iter, residual=...))` -- a value; fallback rerouting (04) applies unchanged |
| same boundary inputs, two calls | identical `values` and `measured_eps` (fixed iteration order, fixed damping, no randomness -- determinism acceptance row) |
| a member solver's `SolveFn` returns `Err` mid-loop | propagates AS-IS (the member's own `SolveError` variant), never relabeled `NoConvergence` |
| a declared member id is not registered in the same registry at solve time | `RuntimeError` (catalog configuration bug, not a recoverable input -- composite `register()` cannot validate this eagerly since AD-4 registration order is arbitrary) |
| composite `SolveFn` run through `plan/execute.py`'s corner sweep | no group-specific code path -- the closure is an ordinary `(x, eps_budget) -> Result[SolveOutput, SolveError]`, so the existing per-corner call machinery applies unchanged |
| ordinary (non-`CoupledGroup`) solvers whose ports form a cycle, registered without a group | still `RegistryError`/planner `PlanError.CyclicPortEquivalence` -- unchanged by this WO (WO-05's cycle check is untouched, `tests/unit/test_plan.py`) |
