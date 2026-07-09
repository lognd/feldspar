from __future__ import annotations

"""WO-17 acceptance: "planner tier-blindness test extended to the elec
namespace" -- the FINV-8 permutation test (`tests/unit/test_plan.py`'s
`test_finv8_tier_blindness_permuted_tiers_yield_identical_route`)
re-run against the REAL registered `elec`/`elec.ngspice` directions
instead of a toy registry, proving the same guarantee holds for the
actual M7 solvers, not just a synthetic fixture.

A dedicated file (not an addition to `tests/unit/test_plan.py`) on
purpose: WO-16/WO-20 run in parallel against other tiers and may touch
that shared file too; this keeps the WO-17 extension collision-free."""

from feldspar.core import Interval
from feldspar.elec.solver import divider as ngspice_divider
from feldspar.library.elec import divider_loaded
from feldspar.plan import plan
from feldspar.solve import SolverRegistry


def _registry_with_tiers(
    closed_form_tier: str, discretized_tier: str
) -> SolverRegistry:
    """Registers the real `elec.divider_loaded` (closed form) and
    `elec.ngspice.divider` (discretized) directions under WHATEVER tier
    strings the caller passes -- so the only thing that changes between
    the two calls in the test below is the `tier` label, never cost/
    accuracy/domain."""
    registry = SolverRegistry()

    closed_info, closed_fn = divider_loaded.solver_direction  # type: ignore[attr-defined]
    closed_info_relabeled = closed_info.model_copy(update={"tier": closed_form_tier})
    result_a = registry.register(closed_info_relabeled, closed_fn)
    _ = result_a.danger_ok

    ngspice_info, ngspice_fn = ngspice_divider.solver_direction  # type: ignore[attr-defined]
    ngspice_info_relabeled = ngspice_info.model_copy(update={"tier": discretized_tier})
    result_b = registry.register(ngspice_info_relabeled, ngspice_fn)
    _ = result_b.danger_ok

    registry.freeze()
    return registry


def _known() -> "dict[str, Interval]":
    return {
        "elec.source.vin": Interval(10.0, 10.0),
        "elec.divider.r1": Interval(10e3, 10e3),
        "elec.divider.r2": Interval(10e3, 10e3),
        "elec.divider.rl": Interval(100e3, 100e3),
    }


def test_finv8_tier_blindness_elec_permuted_tiers_yield_identical_route():
    """The planner reads cost/accuracy/domain only, never `tier` (FINV-
    8, 09 sec. 1): with the real elec closed-form (cost=1e-7) and
    ngspice (cost=5.0) directions registered under one claim kind,
    permuting which string labels which direction's `tier` must not
    change which one wins the route (cost=1e-7 always beats cost=5.0
    regardless of what the tier strings say)."""
    registry_a = _registry_with_tiers("closed_form", "discretized")
    registry_b = _registry_with_tiers("discretized", "closed_form")

    route_a = plan(
        registry_a,
        _known(),
        frozenset({"linear", "small_signal"}),
        "elec.divider.vout",
        1e10,
    ).danger_ok
    route_b = plan(
        registry_b,
        _known(),
        frozenset({"linear", "small_signal"}),
        "elec.divider.vout",
        1e10,
    ).danger_ok

    assert route_a.digest == route_b.digest
    assert [s.solver_id for s in route_a.steps] == [s.solver_id for s in route_b.steps]
    # The cheap closed-form direction wins in BOTH permutations, proving
    # the win was never decided by the tier label.
    assert route_a.steps[0].solver_id == "elec.divider_loaded"
