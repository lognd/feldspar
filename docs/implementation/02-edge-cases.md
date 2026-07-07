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
| G7 fixture: idealization out-of-domain, payload channel unbuilt | honest indeterminate NAMING the missing channel (examples/lithos/sensor_boom.hem) |
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
