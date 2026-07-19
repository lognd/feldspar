from __future__ import annotations

"""The reusable solver-pack conformance kit (10 sec. 3 "The conformance
kit is the product"): the M9 acceptance made a one-line call in any
pack's own test suite, `assert_solverpack_conforms(register_fn)`.
Mirrors `lithos:tests/packs/conformance.py`'s shape one level down --
registration validity, twice-run determinism, domain-honesty spot
checks, and corner-monotonicity spot checks -- all run against the
pack's OWN `register(registry) -> None` callable, composed exactly the
way `feldspar.solve.packs.load_solver_packs` composes it in production
(via a `FakeSolverPackEntryPoint`, so the calling pack needs no real
installed entry point to run this from its own CI).

Every failure is a plain `AssertionError` naming the exact rule
violated (10 sec. 3: "kit failures are constructive") -- never a bare
crash, so a pack author's pytest output already tells them what to
fix."""

from typing import Iterable, Mapping

from typani import Ok, Result

from feldspar.core import Interval
from feldspar.core import corner_sweep as _corner_sweep
from feldspar.solve.packs import (
    DEFAULT_STANDARD_NAMESPACES,
    FakeSolverPackEntryPoint,
    PackInfo,
    RegisterFn,
    load_solver_packs,
    method_named_solver_violation,
)
from feldspar.solve.registry import SolverRegistry

__all__ = ["assert_solverpack_conforms"]


def _corner_callback(fn):
    """Adapts a registered `SolveFn` (`Result[SolveOutput, SolveError]`)
    to `corner_sweep`'s `Result[Mapping[str, float], Any]` callback
    shape -- the one adapter home, used at every corner point."""

    def _call(x: Mapping[str, float]) -> "Result[Mapping[str, float], object]":
        result = fn(x)
        if result.is_err:
            return result
        return Ok(result.danger_ok.values)

    return _call


# frob:doc docs/modules/testing.md#testing_init
def assert_solverpack_conforms(
    register_fn: RegisterFn,
    *,
    name: str = "pack_under_test",
    version: str = "0.1.0",
    standard_namespaces: Iterable[str] = DEFAULT_STANDARD_NAMESPACES,
    reviewed_namespaces: Iterable[str] = (),
    corner_tol_rel: float = 1e-6,
) -> None:
    """Runs the whole M9 pack protocol against `register_fn`. Every
    assertion names the solver id and the rule it checks, so a failure
    reads as a constructive fix instruction, not a stack trace to
    decode.

    Checks (10 sec. 3):

    - the pack composes cleanly through `load_solver_packs` (namespace
      etiquette, method-named-kind lint, no duplicate solver ids --
      all already enforced there, re-asserted here as a clean
      `skipped == ()`);
    - registration validity: a non-empty domain box per solver (empty
      citations/non-positive cost/accuracy-output mismatch are already
      `SolverRegistry.register`'s own job, exercised by composing at
      all);
    - determinism smoke: an in-domain point evaluates twice to the
      BYTE-IDENTICAL `Ok` result;
    - domain honesty: a point well outside the declared box is
      rejected by `Domain.admits` (the registry path), never silently
      evaluated as if in-domain;
    - corner-monotonicity spot check: every declared-domain corner
      evaluates to a finite result, and the interior sample's value
      falls within the corners' hull (a loose tolerance spot check,
      not a monotonicity proof).
    """
    baseline = SolverRegistry()
    registry = SolverRegistry()
    outcome = load_solver_packs(
        registry,
        standard_namespaces=standard_namespaces,
        reviewed_namespaces=reviewed_namespaces,
        entry_points_override=[FakeSolverPackEntryPoint(name, version, register_fn)],
    )
    assert outcome.skipped == (), f"pack {name!r} failed to compose: {outcome.skipped}"
    assert PackInfo(name=name, version=version) in outcome.loaded, (
        f"pack {name!r} did not load"
    )

    baseline_ids = {info.solver_id for info, _fn in baseline}
    staged = [(info, fn) for info, fn in registry if info.solver_id not in baseline_ids]
    assert staged, f"pack {name!r} registered no solvers"

    for info, fn in staged:
        assert info.domain.box, f"{info.solver_id}: empty domain box"
        word = method_named_solver_violation(
            info.namespace
        ) or method_named_solver_violation(info.solver_id)
        assert word is None, f"{info.solver_id}: method-named kind {word!r}"

        interior = {port: (iv.lo + iv.hi) / 2.0 for port, iv in info.domain.box.items()}
        first = fn(interior)
        second = fn(interior)
        assert first.is_ok, f"{info.solver_id}: in-domain evaluation failed: {first}"
        assert second.is_ok, f"{info.solver_id}: second in-domain evaluation failed"
        assert dict(first.danger_ok.values) == dict(second.danger_ok.values), (
            f"{info.solver_id}: not deterministic twice-run"
        )
        for port, value in first.danger_ok.values.items():
            assert value == value and abs(value) != float("inf"), (
                f"{info.solver_id}: non-finite output at {port}: {value}"
            )

        outside = {
            port: Interval(
                iv.hi + max(abs(iv.hi), 1.0) * 10.0,
                iv.hi + max(abs(iv.hi), 1.0) * 10.0,
            )
            for port, iv in info.domain.box.items()
        }
        admits = info.domain.admits(outside, frozenset())
        assert admits.is_err, (
            f"{info.solver_id}: out-of-domain point was not rejected (domain honesty)"
        )

        hull = _corner_sweep(info.domain.box, _corner_callback(fn))
        assert hull.is_ok, f"{info.solver_id}: corner sweep failed: {hull}"
        for port, iv in hull.danger_ok.items():
            width = max(iv.hi - iv.lo, 1e-9)
            tol = corner_tol_rel * max(abs(iv.hi), abs(iv.lo), 1.0) + width
            interior_value = first.danger_ok.values.get(port)
            if interior_value is None:
                continue
            assert iv.lo - tol <= interior_value <= iv.hi + tol, (
                f"{info.solver_id}: interior value for {port} outside corner hull "
                f"(corner-monotonicity spot check)"
            )
