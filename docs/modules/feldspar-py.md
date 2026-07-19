# feldspar-py (rust crate)

PyO3 module `_feldspar`: marshalling only, no logic (AD-1 layering).
Depends on `feldspar-core` and `feldspar-library`. Result-returning
methods in 01-interfaces are exposed here as raising "raw/checked"
primitives (see `errors.rs`); `python/feldspar/core.py` wraps them into
the typani `Result` values the public Python surface promises. Every
`#[pyfunction]`/wrapper class here is a thin, zero-logic pass-through to
the single Rust home of the corresponding type/formula in
`feldspar-core`/`feldspar-library` -- never a second implementation.

## py_lib

<!-- frob:describes crates/feldspar-py/src/lib.rs -->

Crate root / PyO3 module registration. WO-01 wired the `pyo3-log`
bridge (AD-8) and the tracing-span smoke test; WO-02 adds the quantity
core's frozen classes (`Interval`, `Accuracy`, `Domain`, `PortDecl`/
`Rank`, `Dimension`, `UnitSystem`) and the digest home
(`canonical_digest`, `format_f64`).

## py_errors

<!-- frob:describes crates/feldspar-py/src/errors.rs -->

Rust `Result`/`Err` -> Python exception marshalling (AD-1: this crate
is marshalling only). Each raised exception carries `(variant, ...)` so
the Python-side `feldspar/core.py` shim can reconstruct a typani
`Err(...)` value from it -- a Rust-side `Result` becomes a Python
exception at this boundary, then Python re-wraps it as the typani
`Result` the 01-interfaces surface promises callers.

## py_dimension

<!-- frob:describes crates/feldspar-py/src/dimension.rs -->

PyO3 wrapper for `feldspar_core::Dimension` (01-interfaces
`Dimension`): frozen `[i8; 7]` SI base-dimension exponent vector (m,
kg, s, A, K, mol, cd order), with `__repr__`/`__richcmp__`/`__hash__`
so it behaves like a normal frozen Python value type.

## py_interval

<!-- frob:describes crates/feldspar-py/src/interval.rs -->

PyO3 wrapper for `feldspar_core::Interval` (01-interfaces `Interval`):
frozen, ordered, hashable closed interval `[lo, hi]`.

## py_accuracy

<!-- frob:describes crates/feldspar-py/src/accuracy.rs -->

PyO3 wrapper for `feldspar_core::Accuracy` (01-interfaces `Accuracy`):
frozen model-error bound `eps(v) = eps_abs + eps_rel * |v|`.

## py_domain

<!-- frob:describes crates/feldspar-py/src/domain.rs -->

PyO3 wrapper for `feldspar_core::Domain` (01-interfaces `Domain`).
01-interfaces names the field `box` (a reserved keyword in Rust);
`r#box` is Rust's raw-identifier escape for using a keyword as a plain
identifier -- Python sees the identifier text itself, `box`, with no
`r#` artifact (examples/solvers/00_raw_protocol.py: `Domain(box={...},
tags=frozenset())`).

## py_rank

<!-- frob:describes crates/feldspar-py/src/rank.rs -->

PyO3 wrapper for `feldspar_core::Rank` and `PortDecl` (01-interfaces
`Rank`, `PortDecl`). `Rank` is a Rust enum with per-variant payloads
(`Vector(n)`, `Tensor(n, m)`); PyO3 0.22's data-carrying "complex enum"
support is new enough that this takes the lower-risk, well-understood
path: one frozen class tagged by `kind`, with optional fields for the
variant's payload, plus `scalar()`/`complex()`/`vector(n)`/`tensor(n,
m)`/`payload(kind)` constructors mirroring the enum's shape. Flagged as
a WO-02 deviation in the closing report -- worth revisiting once a
native complex-enum binding is verified stable at the pinned pyo3
version.

## py_units

<!-- frob:describes crates/feldspar-py/src/units.rs -->

PyO3 wrapper for `feldspar_core::BuiltinUnitSystem` (01-interfaces
`UnitSystem`): the built-in, dependency-free `UnitSystem`
implementation.

## py_digest

<!-- frob:describes crates/feldspar-py/src/digest.rs -->

PyO3 wrapper for the digest home (AD-5): `canonical_digest`,
`format_f64`. `canonical_digest` marshals via `pythonize` into
`serde_json::Value`, whose object type is a `BTreeMap` by default (no
`preserve_order` feature anywhere in this workspace) -- so a Python
`dict`'s insertion order never affects the digest (02-edge-cases WO-02
row).

## py_propagation

<!-- frob:describes crates/feldspar-py/src/propagation.rs -->

PyO3 wrapper for `feldspar_core::{corner_sweep, inflate, total_error}`
(01-interfaces WO-04 section): the executor (WO-06) and planner
estimator (WO-05) call these SAME symbols (FINV-4). `enumerate_corners`/
`hull_from_results` (WO-15, 09 sec. 6) split `corner_sweep` into its
enumerate and fold halves so `feldspar.plan.parallel` can dispatch the
(GIL-bound, so only Python-side, not Rust-thread) per-corner `SolveFn`
callback concurrently and still fold through the ONE core hull
routine. `PyNormal` wraps a Gaussian for `delta_propagate_symbolic`/
`delta_propagate_numeric` (linearized delta-method propagation).

## py_search

<!-- frob:describes crates/feldspar-py/src/search.rs -->

PyO3 wrapper for `feldspar_core::search` (01-interfaces `feldspar.plan`,
WO-05). The frozen registry snapshot crosses ONCE per `plan()` call as
a `Vec<PySolverInput>` built by `python/feldspar/plan/route.py` from
`SolverRegistry.__iter__()`; nothing here calls back into Python during
search itself (04-routing: "search never calls back into Python").

## py_symbolic

<!-- frob:describes crates/feldspar-py/src/symbolic.rs -->

PyO3 wrapper for `feldspar_core::symbolic` (11 "the symbolic core",
WO-11). Exposes the canonical `Expr` AST, `Predicate`, and the
declaration-time algebra primitives (`invert_for`, `invertible_targets`,
`predicate_to_box`) to Python. `Cmp` is deliberately kept as a plain
`str` ("lt"/"le"/"gt"/"ge") rather than a wrapped enum type, matching
how other small closed enums (e.g. `tier`) cross the boundary as
strings elsewhere in this crate.

## py_library_mod

<!-- frob:describes crates/feldspar-py/src/library/mod.rs -->

PyO3 wrappers for `feldspar_library`, split by namespace: `mech`,
`fluids`, `heat`, `elec`. Marshalling only, no logic (AD-1 layering).
`pub use` re-exports keep `crate::library::X` paths (used by
`feldspar-py/src/lib.rs`'s pymodule registration) IDENTICAL to before
the namespace split.

## py_library_mech

<!-- frob:describes crates/feldspar-py/src/library/mech.rs -->

PyO3 wrappers for `feldspar_library::mech` (WO-07): marshalling only,
no logic. Python-visible names carry a `mech_` prefix to keep the flat
`_feldspar` namespace collision-free with future namespaces (thermo,
fluids, ...). E.g. wraps `feldspar_library::mech::rect_second_moment`
(Gere, *Mechanics of Materials*, 9th ed., App. E).

## py_library_fluids

<!-- frob:describes crates/feldspar-py/src/library/fluids.rs -->

PyO3 wrappers for `feldspar_library::fluids` (WO-20): marshalling only,
no logic -- same thin pass-through contract as `library::mech`.

## py_library_heat

<!-- frob:describes crates/feldspar-py/src/library/heat.rs -->

PyO3 wrappers for `feldspar_library::heat` (WO-20, widened WO-142):
marshalling only, no logic -- same thin pass-through contract as
`library::mech`. WO-142 adds thin wrappers for
`heat_gnielinski_nusselt`, `heat_laminar_nusselt`,
`heat_churchill_chu_horizontal_cylinder_nusselt`/
`heat_churchill_chu_vertical_plate_nusselt`, and the NTU-effectiveness
family (`heat_ntu_from_ua`, `heat_effectiveness_parallel_flow`,
`heat_effectiveness_counterflow`,
`heat_effectiveness_shell_and_tube_one_pass`,
`heat_hx_rate_from_effectiveness`, `heat_hx_outlet_temp`).

## py_library_elec

<!-- frob:describes crates/feldspar-py/src/library/elec.rs -->

PyO3 wrappers for `feldspar_library::elec` (WO-17): marshalling only,
no logic -- same thin pass-through contract as `library::mech`. Wraps
`divider_loaded_vout` and `rc_step_response` (Sedra & Smith,
*Microelectronic Circuits*, for citation).
