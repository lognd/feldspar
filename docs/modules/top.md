# feldspar (top-level)

The package root: `core.py` marshals the Rust-backed quantity core
(`_feldspar`) into typani `Result` values at the Python surface, and
`catalog.py` composes the one full engine catalog every solver family
registers into.

## top_core

<!-- frob:describes python/feldspar/core.py::CoreError -->
<!-- frob:describes python/feldspar/core.py::UnitError -->
<!-- frob:describes python/feldspar/core.py::DomainViolation -->
<!-- frob:describes python/feldspar/core.py::canonical_digest -->
<!-- frob:describes python/feldspar/core.py::corner_sweep -->
<!-- frob:describes python/feldspar/core.py::enumerate_corners -->
<!-- frob:describes python/feldspar/core.py::hull_from_results -->
<!-- frob:describes python/feldspar/core.py::EXACT -->

`feldspar.core` is the Rust-backed quantity core (01-interfaces
`feldspar.core`, WO-02). The frozen classes are the compiled
`_feldspar` extension's classes directly (AD-2 -- no Python mirrors);
this module's only job is marshalling `_feldspar`'s raising "checked"
primitives into the typani `Result` values 01-interfaces promises.

- `CoreError` (an `ErrorSet`): `Interval` construction failures --
  `NonFiniteBound` (a NaN/+-infinity bound) and `InvertedInterval`
  (`lo > hi`).
- `UnitError` (an `ErrorSet`): `UnitSystem` lookup/conversion failures --
  `UnknownUnit`, `IncompatibleDimensions`, `OffsetInCompound`.
- `DomainViolation`: why a `Domain.admits()` check failed, carrying
  port/tag/bound detail (01-interfaces: "DomainViolation carries
  port/tag details").
- `canonical_digest(obj)`: canonical-JSON -> blake3 digest of any value
  built from core frozen classes, pydantic models, and/or plain
  JSON-safe data (AD-5); order-independent for dict keys and
  set/frozenset contents.
- `corner_sweep(box, fn)`: evaluates `fn` at every deduplicated, sorted
  corner of `box` and hulls the per-port results (the ONE corner-sweep
  implementation, FINV-4); `fn`'s `Err` passes through unchanged.
- `enumerate_corners(box)`: the enumerate half of `corner_sweep`,
  exposed standalone for callers (e.g. `feldspar.plan.parallel`) that
  want to evaluate corners themselves (concurrently) and fold results
  with `hull_from_results`.
- `hull_from_results(results)`: the fold half of `corner_sweep` --
  hulls per-corner output maps that must be in `enumerate_corners`'
  order; deterministic (FINV-9) regardless of computation order because
  the fold is commutative/associative.
- `EXACT`: the `Accuracy(0.0, 0.0)` constant (01-interfaces) for
  solvers that carry no propagated error at all.

## top_catalog

<!-- frob:describes python/feldspar/catalog.py::build_engine_catalog -->

`build_engine_catalog()` is the ONE full engine catalog composition
(WO111b composition fix): every closed-form library family plus the FEA
and payload-step directions, registered against a fresh `SolverRegistry`
in the one canonical order, frozen. Extracted out of
`feldspar.pack.models._engine_registry` so the composition can be
exercised (and its ordering invariants tested, F12 accumulated-port-
table guard) without regolith installed -- `pack.models` delegates to
this function verbatim (NO DUPLICATION).
