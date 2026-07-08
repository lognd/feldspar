from __future__ import annotations

"""WO-10 `fea`-marked golden: `Solution.explain()`/`to_dict()` against a
REAL FEA solve (`fea.static_deflection.cantilever`, WO-08), not just the
toy registry (`tests/unit/test_report.py`) -- the acceptance bar
explicitly names both. This asserts SHAPE (every required section is
present and the reported values are self-consistent) rather than a
byte-exact golden string, because a real gmsh/ccx solve's measured
Richardson eps is machine/tool-version dependent (mesh generator and
solver floating-point paths are not bit-reproducible across gmsh/ccx
builds, only feldspar's OWN math is, 04-routing "Determinism"'s scope
is the engine, not the external tools it shells out to).

Written correctly per spec but NOT EXECUTED in the sandbox this WO was
implemented in -- no `ccx`, no `gmsh` (same situation WO-08/WO-09
documented in `tests/integration/test_fea_pipeline.py`). This is a
written-but-unverified-by-execution test, not a fabricated pass."""

import pytest

from feldspar.core import Interval
from feldspar.fea.solver import register as register_fea
from feldspar.library.mech import register as register_mech
from feldspar.plan import solve
from feldspar.solve import SolverRegistry

pytestmark = pytest.mark.fea


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register_mech(registry)
    register_fea(registry)
    registry.freeze()
    return registry


def test_explain_renders_real_fea_solve() -> None:
    registry = _registry()
    known = {
        "mech.geom.cantilever.length": Interval(0.50, 0.50),
        "mech.geom.cantilever.width": Interval(0.040, 0.042),
        "mech.geom.cantilever.height": Interval(0.060, 0.060),
        "mech.material.youngs_modulus": Interval(6.8e10, 7.1e10),
        "mech.material.poisson": Interval(0.33, 0.33),
        "mech.load.tip_force": Interval(1.0e3, 1.2e3),
    }
    solution = solve(
        registry,
        known=known,
        tags={"linear_elastic", "small_deflection"},
        target="mech.deflection.tip",
        # The planner's PRE-execution eps estimate is a deliberately
        # crude "sum surrogate" over raw input point values (04-routing
        # "Algorithm (v1)"), not a physical propagation -- with
        # `mech.material.youngs_modulus` (~1e10 Pa) among this step's
        # inputs, that surrogate is astronomically large regardless of
        # the real (Richardson-measured) FEA error. A tight budget here
        # would raise `PlanError.BudgetUnreachable` before a route is
        # even found; the REAL accuracy gate is `solve()`'s POST-
        # execution recheck against the caller's budget (04-routing
        # "Execution": "a route whose realized FEA eps busts the
        # ceiling returns BudgetExceeded"). This loose budget exercises
        # that real gate rather than the surrogate's pre-check.
        eps_budget=1e12,
    ).danger_ok

    text = solution.explain()
    as_dict = solution.to_dict()

    # Route reached the discretized tier (the whole point of the tight
    # budget in this fixture, examples/03_fea_cantilever.py).
    assert any("fea." in step.solver_id for step in solution.route.steps)

    # Every rendered section is present.
    assert "Solution for target='mech.deflection.tip'" in text
    assert "route:" in text
    assert "eps_budget=" in text  # solve() stamped it (unlike execute())
    assert "cache_hit=" in text

    # Citations render for the FEA step (calibration + method, 03/FINV-6).
    fea_steps = [s for s in as_dict["route"]["steps"] if "fea." in s["solver_id"]]
    assert fea_steps
    assert fea_steps[0]["citations"]  # non-empty, FINV-6 floor

    # Second solve is a cache hit -- provenance renders correctly (04
    # "Solve cache").
    again = solve(
        registry,
        known=known,
        tags={"linear_elastic", "small_deflection"},
        target="mech.deflection.tip",
        eps_budget=1e12,
    ).danger_ok
    assert again.cache_hit is True
    assert "cache_hit=True" in again.explain()

    # Pure rendering: explain()/to_dict() are read-only over `Solution`.
    assert solution.explain() == text
    assert solution.to_dict() == as_dict
