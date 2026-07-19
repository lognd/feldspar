# feldspar-core (rust crate)

The dependency-free quantity core (AD-1): frozen value types, unit
algebra, error propagation, digesting, and planner search. Depends on
nothing else in the workspace; `feldspar-library` and `feldspar-py`
build on top of it. See `docs/spec/*/01-interfaces.md` for the exact
public surface these types implement and `docs/spec/*/13-invariants.md`
for FINV-1..12.

## core_lib

<!-- frob:describes crates/feldspar-core/src/lib.rs -->

Crate root: re-exports the frozen quantity core (`Interval`,
`Accuracy`, `Domain`, `PortDecl`/`Rank`, `Dimension`, `UnitSystem`, the
digest home) and the propagation/search modules built on top of it.
`tracing` is pulled in with the `log-always` feature (AD-8) so every
span/event emitted here also flows through the `log` crate facade
regardless of whether a `tracing::Subscriber` is installed -- this is
what lets `feldspar-py`'s `pyo3-log` bridge forward it into Python
logging without this crate knowing PyO3 exists.

## core_dimension

<!-- frob:describes crates/feldspar-core/src/dimension.rs -->

`Dimension`: a vector of integer exponents over the seven SI base
dimensions, ordered `[length, mass, time, current, temperature,
amount, luminous_intensity]` (m, kg, s, A, K, mol, cd; 02-quantities
"Unit algebra"). `mul`/`div` are the componentwise sum/difference that
give the dimension of a product/quotient of two quantities.
`DIMENSIONLESS` is the all-zero constant.

## core_interval

<!-- frob:describes crates/feldspar-core/src/interval.rs -->

`Interval`: the v1 uncertain-value representation (02-quantities
"Values are uncertain") -- a closed interval `[lo, hi]`, frozen, always
`lo <= hi`, both finite. This is the worst-case-bounds uncertainty
representation that crosses the pack boundary; every propagation
routine in `propagation.rs` produces and consumes `Interval` values.

## core_accuracy

<!-- frob:describes crates/feldspar-core/src/accuracy.rs -->

`Accuracy`: a solver's declared model-error bound (02-quantities "The
error split"), `eps(v) = eps_abs + eps_rel * |v|`. This is distinct
from input-uncertainty propagation (`Interval`/`propagation.rs`):
`Accuracy` is the solver's own claimed inaccuracy, folded in as the
final step's model eps by `total_error`.

## core_domain

<!-- frob:describes crates/feldspar-core/src/domain.rs -->

`Domain`: where a solver may be trusted (02-quantities "Domains").
Carries the admissible input box plus any tags a solver's domain is
conditioned on (e.g. "compressible"/"incompressible" regime tags).
`DomainViolation` explains WHY an `admits()` check failed, carrying
enough port/tag detail for a caller to act on the rejection
(01-interfaces).

## core_rank

<!-- frob:describes crates/feldspar-core/src/rank.rs -->

`Rank` and `PortDecl`: non-scalar quantity shape declarations
(02-quantities "Non-scalar and structured quantities"). `Rank` is a
Rust enum with per-variant payloads (`Scalar`, `Complex`, `Vector(n)`,
`Tensor(n, m)`); the `Payload` arm is reserved for the M2 payload-port
feature (09 sec. 4) so registration code can match exhaustively today
without a breaking enum change later. `PortDecl` pairs a port name with
its declared `Rank`.

## core_units

<!-- frob:describes crates/feldspar-core/src/units.rs -->

`UnitSystem`: unit label -> `(Dimension, scale-to-coherent-SI)`,
ingest/print conversion ONLY (02-quantities "Unit algebra", FINV-11).
`BuiltinUnitSystem` is this crate's dependency-free default table;
`regolith-qty` may back the same protocol when regolith is installed
(FINV-3). Each table entry computes `to_si(v) = v * scale + offset` and
`from_si(v) = (v - offset) / scale`; only ingest/print-legal (affine)
units carry a nonzero `offset` (degC, degF) -- every derived/compound
unit must be built from zero-offset components (FINV-11, G3).

## core_error

<!-- frob:describes crates/feldspar-core/src/error.rs -->

`CoreError` and `UnitError`: the TOTAL error variants for the quantity
core (01-interfaces `feldspar.core`, FINV-5 -- error values, never
exceptions). `CoreError` covers `Interval` construction failures;
`UnitError` covers `UnitSystem` lookup and table-construction failures.
Both are exhaustively matched by callers rather than ever being raised
as panics.

## core_digest

<!-- frob:describes crates/feldspar-core/src/digest.rs -->

The ONE digest home (AD-5): canonical-JSON -> blake3, hex-encoded.
Every settings/route/cache digest in the workspace goes through
`canonical_digest`. `serde_json::Value` (and anything serializing
through it) stores object keys in a `BTreeMap` by default (no
`preserve_order` feature enabled anywhere in the workspace), so two
maps built in different insertion orders serialize identically --
this is what makes the digest map-order stable (02-edge-cases WO-02
row) without any extra sorting step here.

## core_propagation

<!-- frob:describes crates/feldspar-core/src/propagation.rs -->

The ONE corner-sweep and accumulation-rule home (FINV-4, audit A-1),
shared verbatim by planner estimates (WO-05) and executor exact sweeps
(WO-06) via PyO3 (`corner_sweep`, `inflate`, `total_error`).
02 "The error split": input uncertainty propagates by evaluating a
solver at every corner of its input box and hulling the results; model
error is a separate, solver-declared `Accuracy` ceiling. Accumulation
along a route is BY INFLATION (`inflate`), never by summing eps
scalars -- summing is unsound the instant a step's gain differs from 1
(`y = 1000*x` turns an upstream eps of 0.1 into 100; a sum reports
~0.1). `total_error` is the budget-checked quantity at a target:
propagated half-width (already carrying every upstream eps through the
route's real sensitivities, under inflation) plus the FINAL step's own
model eps.

## core_search

<!-- frob:describes crates/feldspar-core/src/search.rs -->

Planner search (WO-05, 04-routing): deterministic forward AND-graph
search from known ports to a target port, minimizing cost subject to
domain validity and an eps budget (FINV-1/5/8). M1 estimation
convention: since a `SolverInfo` snapshot carries no executable formula
(only `Domain`, `Accuracy`, and `cost`) and search never calls back
into Python, a step's output value at each corner is estimated as the
SUM of that corner's input values, then hulled via `corner_sweep`
exactly like the executor later hulls the REAL sweep (FINV-4: same
core routine, hull corners). This is a documented placeholder
magnitude used only to drive route SELECTION; WO-06's executor
replaces it with the real `SolveFn` sweep before anything is reported
to a caller.

## core_symbolic

<!-- frob:describes crates/feldspar-core/src/symbolic.rs -->

The symbolic-equation kernel (11 "The symbolic core"; WO-11, M10).
Laws-as-data: a physical law is declared ONCE as a canonical `Expr` and
its N solver directions are DERIVED by closed-form inversion at
declaration time, each lowering to an ordinary raw-protocol entry (10
sec. 2: an authoring FORM, not a tenth pattern). This module does
ALGEBRA ONLY -- canonicalize, invert, derive a dispatch box from
predicates, and evaluate a frozen `Expr` numerically; registration-
lowering (building `(SolverInfo, SolveFn)` pairs) lives Python-side in
`feldspar.solve.sugar`, which calls these primitives, keeping twin-
equality defined by the single `_build` path (03). Non-goals (11 sec.
3): no optimization, no invented relations, no solve-time CAS
manipulation -- `Expr::eval` is compiled numeric evaluation of a FROZEN
tree, like a table solver interpolating, not a CAS.

## core_property_tests

<!-- frob:describes crates/feldspar-core/tests/property.rs -->

Property-based test suite for the quantity core (proptest), plus the
crate's integration-test binding for TEST003 (frob:tests). Exercises
`Domain::new`/`Domain::admits`/`canonical_digest` and other core
invariants across generated inputs, not just fixed example cases.
