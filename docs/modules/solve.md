# feldspar.solve

The registration/solve surface (01-interfaces `feldspar.solve`, 03/04):
the raw `@solver` protocol and its private shared builder, the
data models (`Citation`/`SolverInfo`/`SolveOutput`), digests, the total
error unions, the explicit `SolverRegistry`, payload ports, cost-curve
budget seeking, solver-pack discovery, and the sugar layer
(`Relation`/`Correlation`/`CoupledGroup`/table solvers) built on top of
the same one lowering path.

## solve__build

<!-- frob:describes python/feldspar/solve/_build.py::coerce_domain -->
<!-- frob:describes python/feldspar/solve/_build.py::coerce_citation -->
<!-- frob:describes python/feldspar/solve/_build.py::coerce_citations -->
<!-- frob:describes python/feldspar/solve/_build.py::coerce_accuracy -->
<!-- frob:describes python/feldspar/solve/_build.py::wrap_solve_fn -->
<!-- frob:describes python/feldspar/solve/_build.py::invoke_solve_fn -->
<!-- frob:describes python/feldspar/solve/_build.py::build_solver_info_and_fn -->

Private shared builder: the ONE place raw `SolverInfo`/`SolveFn` pairs
get assembled from author-facing (possibly sugared) arguments.
`coerce_domain`/`coerce_citation`/`coerce_citations`/`coerce_accuracy`
normalize author-facing shorthand into the strict model types;
`wrap_solve_fn` adapts a raw callable into the `SolveFn` calling
convention; `invoke_solve_fn` is the one call site that actually
invokes a `SolveFn`; `build_solver_info_and_fn` is the top-level
assembly `@solver` (`solver.py`) and `make_direction`/`Relation`/
`Correlation` (`sugar.py`) all call, so a sugar-built direction is
digest-equal to its hand-built twin by construction -- exactly one
lowering path, never a second registration route (AD-4 spirit).

## solve__models

<!-- frob:describes python/feldspar/solve/_models.py::Citation -->
<!-- frob:describes python/feldspar/solve/_models.py::ClaimSenses -->
<!-- frob:describes python/feldspar/solve/_models.py::ClaimSenses.coerce -->
<!-- frob:describes python/feldspar/solve/_models.py::SolverInfo -->
<!-- frob:describes python/feldspar/solve/_models.py::SolveOutput -->
<!-- frob:describes python/feldspar/solve/_models.py::EXACT -->

Private home for `Citation`/`ClaimSenses`/`SolverInfo`/`SolveOutput`,
split out from `solver.py` solely to break a `solver.py` <-> `_build.py`
Python import cycle; author-facing code always imports from
`feldspar.solve`, never from here. `Citation` is a method citation
(`SolverRegistry.register` enforces the citation floor, FINV-6, empty
or calibration-only is an error). `ClaimSenses` (with its `coerce`
classmethod) declares which direction(s) of a relation a solver claims
to serve. `SolverInfo` is the frozen per-solver registration record;
`SolveOutput` is the raw result a `SolveFn` returns before execution
wraps it into a `Solution`. `EXACT` is the `Accuracy(0.0, 0.0)`
constant (01-interfaces `feldspar.solve.EXACT`).

## solve_digest

<!-- frob:describes python/feldspar/solve/digest.py::settings_digest -->

Canonical-JSON -> blake3 digest facade (AD-5): the one digest
IMPLEMENTATION home is `feldspar.core.canonical_digest`; this module is
the `feldspar.solve`-side surface over it. `settings_digest` is the
`SolverInfo.settings_digest` a solver's decorator-level `settings=`
closure folds into (F1); `None` (no settings) digests just as
deterministically as a real settings model.

## solve_errors

<!-- frob:describes python/feldspar/solve/errors.py::RegistryError -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.DuplicateSolverId -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.PortUnitConflict -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.PortRankConflict -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.UnknownPort -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.DuplicatePortDecl -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.EmptyCitations -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.NonPositiveCost -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.AccuracyOutputMismatch -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.Frozen -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.BadTable -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.PayloadKindConflict -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.UnknownPayloadKind -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.NonInvertible -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.MultiBranch -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.UnboundablePredicate -->
<!-- frob:describes python/feldspar/solve/errors.py::RegistryError.EmptyDomain -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.ToolMissing -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.ToolFailed -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.Timeout -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.ParseFailed -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.OutOfDomain -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.NonFinite -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.OutputOutOfDomain -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.MissingOutput -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.InvalidMeasurement -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.BudgetExceeded -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.NoRouteRemaining -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.PayloadKindMismatch -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.MissingPayload -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.LadderExhausted -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.NoConvergence -->
<!-- frob:describes python/feldspar/solve/errors.py::SolveError.DanglingDigest -->

`RegistryError`/`SolveError` are the TOTAL error unions of 03/04
(01-interfaces, FINV-5), both small tagged-value classes built on the
shared `_TaggedError` base (kind/fields/eq/hash/repr machinery in one
home). `RegistryError` variants cover registration-time rejections:
duplicate/conflicting solver ids and port declarations
(`DuplicateSolverId`, `PortUnitConflict`, `PortRankConflict`,
`UnknownPort`, `DuplicatePortDecl`), citation/cost/accuracy validation
(`EmptyCitations`, `NonPositiveCost`, `AccuracyOutputMismatch`),
registry lifecycle (`Frozen`), table/payload validation (`BadTable`,
`PayloadKindConflict`, `UnknownPayloadKind`), and relation invertibility
(`NonInvertible`, `MultiBranch`, `UnboundablePredicate`, `EmptyDomain`).
`SolveError` variants cover solve-time failures: external tool issues
(`ToolMissing`, `ToolFailed`, `Timeout`), parsing/domain/output problems
(`ParseFailed`, `OutOfDomain`, `NonFinite`, `OutputOutOfDomain`,
`MissingOutput`, `InvalidMeasurement`), budget/routing exhaustion
(`BudgetExceeded`, `NoRouteRemaining`, `LadderExhausted`), payload
mismatches (`PayloadKindMismatch`, `MissingPayload`), and convergence/
digest integrity (`NoConvergence`, `DanglingDigest`).

## solve_packs

<!-- frob:describes python/feldspar/solve/packs.py::SolverPackEntryPoint -->
<!-- frob:describes python/feldspar/solve/packs.py::SolverPackEntryPoint.name -->
<!-- frob:describes python/feldspar/solve/packs.py::SolverPackEntryPoint.load -->
<!-- frob:describes python/feldspar/solve/packs.py::SolverPackEntryPoint.dist -->
<!-- frob:describes python/feldspar/solve/packs.py::FakeSolverPackEntryPoint -->
<!-- frob:describes python/feldspar/solve/packs.py::FakeSolverPackEntryPoint.name -->
<!-- frob:describes python/feldspar/solve/packs.py::FakeSolverPackEntryPoint.load -->
<!-- frob:describes python/feldspar/solve/packs.py::FakeSolverPackEntryPoint.dist -->
<!-- frob:describes python/feldspar/solve/packs.py::PackInfo -->
<!-- frob:describes python/feldspar/solve/packs.py::DuplicateSolverId -->
<!-- frob:describes python/feldspar/solve/packs.py::NamespaceViolation -->
<!-- frob:describes python/feldspar/solve/packs.py::MethodNamedSolverId -->
<!-- frob:describes python/feldspar/solve/packs.py::PackRegisterRaised -->
<!-- frob:describes python/feldspar/solve/packs.py::MalformedSolverPack -->
<!-- frob:describes python/feldspar/solve/packs.py::PortDeclarationFailed -->
<!-- frob:describes python/feldspar/solve/packs.py::RegistrationRejected -->
<!-- frob:describes python/feldspar/solve/packs.py::SolverPackLoadOutcome -->
<!-- frob:describes python/feldspar/solve/packs.py::method_named_solver_violation -->
<!-- frob:describes python/feldspar/solve/packs.py::load_solver_packs -->
<!-- frob:describes python/feldspar/solve/packs.py::pack_composition_digest -->
<!-- frob:describes python/feldspar/solve/packs.py::SOLVER_PACK_ENTRY_POINT_GROUP -->
<!-- frob:describes python/feldspar/solve/packs.py::DEFAULT_STANDARD_NAMESPACES -->

`feldspar.solver_packs` discovery + composition -- the M9 plug-and-play
seam (10 sec. 3): a solver pack is an ordinary Python distribution
exposing one entry point in the group `feldspar.solver_packs` whose
target is a bare `register(registry) -> None` callable.
`SolverPackEntryPoint` is the real `importlib.metadata` entry-point
protocol (`name`/`load`/`dist`); `FakeSolverPackEntryPoint` is the test/
conformance-kit double implementing the same protocol without a real
installed entry point. `PackInfo` records one loaded pack's identity.
The `*Violation`/`*Rejected`/`*Raised`/`Malformed*`/`*Failed` classes
(`DuplicateSolverId`, `NamespaceViolation`, `MethodNamedSolverId`,
`PackRegisterRaised`, `MalformedSolverPack`, `PortDeclarationFailed`,
`RegistrationRejected`) are the typed skip reasons a bad pack is
recorded under -- never a crash, never a silent partial load.
`SolverPackLoadOutcome` is the overall composition result;
`method_named_solver_violation` is the namespace-etiquette lint;
`load_solver_packs` runs the whole discovery+composition pipeline
(deterministic: built-ins first, then discovered packs in sorted-
entry-point-name order, each staged onto a scratch registry first);
`pack_composition_digest` digests the resulting composition.
`SOLVER_PACK_ENTRY_POINT_GROUP` is the one entry-point group string
every out-of-repo solver pack registers through; `DEFAULT_STANDARD_
NAMESPACES` are the standard built-in namespaces a pack may upstream
into through review but never squat on outright.

## solve_payload

<!-- frob:describes python/feldspar/solve/payload.py::PayloadRef -->
<!-- frob:describes python/feldspar/solve/payload.py::PayloadResolver -->
<!-- frob:describes python/feldspar/solve/payload.py::PayloadResolver.resolve -->
<!-- frob:describes python/feldspar/solve/payload.py::PayloadResolver.store -->
<!-- frob:describes python/feldspar/solve/payload.py::resolver_cache_identity -->
<!-- frob:describes python/feldspar/solve/payload.py::payload_feature_violation -->
<!-- frob:describes python/feldspar/solve/payload.py::PAYLOAD_KINDS -->

Payload ports (WO-12, 09 sec. 4): the content-addressed, exact-by-
reference value carried by a `PortDecl` whose `Rank` is
`Rank.payload(kind)`. `PAYLOAD_KINDS` (module constant, quoted verbatim
from spec) is the one place the kind vocabulary lives on the Python
side. `PayloadRef` is `{kind, digest, origin}` -- exact by reference, so
its digest folds into a request/solve digest as just that ref (no store
IO happens in feldspar). `PayloadResolver` is the `Protocol` an
orchestrator-provided resolver implements (`resolve`/`store`);
`resolver_cache_identity` derives the cache-identity key for a given
resolver instance; `payload_feature_violation` builds the typed error
for an unsupported payload feature. `PAYLOAD_KINDS` is the one
place the payload kind vocabulary lives on the Python side (quoted
verbatim from spec).

## solve_registry

<!-- frob:describes python/feldspar/solve/registry.py::SolverRegistry -->
<!-- frob:describes python/feldspar/solve/registry.py::SolverRegistry.declare_ports -->
<!-- frob:describes python/feldspar/solve/registry.py::SolverRegistry.register -->
<!-- frob:describes python/feldspar/solve/registry.py::SolverRegistry.get -->
<!-- frob:describes python/feldspar/solve/registry.py::SolverRegistry.freeze -->
<!-- frob:describes python/feldspar/solve/registry.py::SolverRegistry.is_frozen -->
<!-- frob:describes python/feldspar/solve/registry.py::SolverRegistry.digest -->
<!-- frob:describes python/feldspar/solve/registry.py::SolverRegistry.port_table -->

`SolverRegistry`: explicit, non-global-state solver/port registration
(AD-4, 01-interfaces). `declare_ports` pre-declares a family's port
vocabulary (the F12 accumulated-port-table guard); `register` adds one
solver after validating citations/cost/accuracy/port consistency;
`get` looks up a registered solver by id; `freeze`/`is_frozen` lock the
registry against further registration once composition is complete;
`digest` computes the FINV-7 whole-registry content digest; `port_table`
exposes the declared port vocabulary. Every registration, rejection,
and freeze is logged with the relevant id.

## solve_seeking

<!-- frob:describes python/feldspar/solve/seeking.py::CostPoint -->
<!-- frob:describes python/feldspar/solve/seeking.py::CostCurve -->
<!-- frob:describes python/feldspar/solve/seeking.py::CostCurve.scalar -->
<!-- frob:describes python/feldspar/solve/seeking.py::CostCurve.cost_for_budget -->

`CostPoint`/`CostCurve` -- the WO-13 cost-curve schema (09 sec. 3): a
budget-seeking solver's `SolverInfo.cost_curve` generalizes the scalar
`cost` field to sampled `(eps, cost)` points, with a CONSERVATIVE
lookup by remaining eps budget. `CostCurve.scalar` builds a degenerate
single-point curve (the common case); `CostCurve.cost_for_budget`
reproduces a real ladder's stopping rule (cheapest declared rung whose
eps fits the budget) so dominance pruning stays sound. Additive schema
only -- the Rust planner still reads only `SolverInfo.cost` for pruning.

## solve_solver

<!-- frob:describes python/feldspar/solve/solver.py::solver -->
<!-- frob:describes python/feldspar/solve/solver.py::F -->

The `@solver` decorator -- the raw registration surface (01-interfaces
`feldspar.solve`, 03). A solver-authoring module builds its
`SolverInfo`/`SolveFn` pairs at IMPORT time via `@solver` with no global
registry access, then exposes a single `register(registry) -> None`
function the catalog loader calls explicitly (AD-4): permuting import/
registration order across modules can never change which solvers exist
or their digest (FINV-1). `F` is the generic `TypeVar` the decorator
uses to preserve the wrapped callable's signature.

## solve_sugar

<!-- frob:describes python/feldspar/solve/sugar.py::make_direction -->
<!-- frob:describes python/feldspar/solve/sugar.py::Relation -->
<!-- frob:describes python/feldspar/solve/sugar.py::Relation.direction -->
<!-- frob:describes python/feldspar/solve/sugar.py::Relation.law -->
<!-- frob:describes python/feldspar/solve/sugar.py::Relation.register -->
<!-- frob:describes python/feldspar/solve/sugar.py::table_solver_1d -->
<!-- frob:describes python/feldspar/solve/sugar.py::table_solver_2d -->
<!-- frob:describes python/feldspar/solve/sugar.py::Correlation -->
<!-- frob:describes python/feldspar/solve/sugar.py::Correlation.formula -->
<!-- frob:describes python/feldspar/solve/sugar.py::Correlation.register -->
<!-- frob:describes python/feldspar/solve/sugar.py::CoupledGroup -->
<!-- frob:describes python/feldspar/solve/sugar.py::CoupledGroup.register -->

The DX-settled sugar layer (03 "Registration ergonomics"):
`make_direction`, `Relation`, `table_solver_1d`/`table_solver_2d`,
`Correlation`, `CoupledGroup`. Every builder calls the same
`_build.build_solver_info_and_fn` the `@solver` decorator uses -- one
lowering path, sugar-built digest-equal to hand-built. `make_direction`
builds a single-direction `SolverInfo`/`SolveFn` pair from a plain
function. `Relation` declares an invertible law once (`direction`
picks one solvable direction, `law` is the underlying equation,
`register` emits every invertible direction as a solver). `table_
solver_1d`/`table_solver_2d` build interpolation-table-backed solvers.
`Correlation` wraps a fitted empirical formula (`formula` the raw
callable, `register` emits it). `CoupledGroup` registers a set of
solvers that share simultaneous-equation coupling (`register` emits the
group).
