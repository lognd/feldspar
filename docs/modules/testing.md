# feldspar.testing

The reusable solver-pack conformance kit (10 sec. 3 "The conformance kit
is the product"): a one-line call any pack's own test suite makes to
validate itself.

## testing_init

<!-- frob:describes python/feldspar/testing/__init__.py::assert_solverpack_conforms -->

`assert_solverpack_conforms(register_fn, ...)` runs the whole M9 pack
protocol against `register_fn`, mirroring `lithos:tests/packs/
conformance.py`'s shape one level down: composition validity through
`load_solver_packs` (namespace etiquette, method-named-kind lint, no
duplicate solver ids), registration validity (non-empty domain box per
solver), twice-run determinism, domain-honesty spot checks, and
corner-monotonicity spot checks -- all run against the pack's own
`register(registry) -> None` callable composed exactly the way
`feldspar.solve.packs.load_solver_packs` composes it in production (via
a `FakeSolverPackEntryPoint`, so the calling pack needs no real
installed entry point to run this from its own CI). Every failure is a
plain `AssertionError` naming the exact rule violated (10 sec. 3: "kit
failures are constructive") -- never a bare crash.
