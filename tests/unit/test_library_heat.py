from __future__ import annotations

"""WO-20 conformance tests: known-answer unit tests for the registered
`heat` solver directions (`python/feldspar/library/heat.py`), called
THROUGH the `SolverRegistry`/`SolveFn` protocol."""

import pytest

from feldspar.library.heat import register
from feldspar.solve import SolverRegistry


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    return registry


def _solvers() -> dict:
    registry = _registry()
    return {info.solver_id: (info, fn) for info, fn in registry}


# frob:tests python/feldspar/heat kind="integration"
def test_plane_wall_resistance_known_answer():
    """R = L/(k*A). L=0.1 m, k=0.8 W/m-K (brick), A=2.0 m^2 ->
    R = 0.1/(0.8*2.0) = 0.0625 K/W."""
    _info, fn = _solvers()["heat.plane_wall_resistance"]
    result = fn(
        {
            "heat.wall.thickness": 0.1,
            "heat.wall.conductivity": 0.8,
            "heat.wall.area": 2.0,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["heat.wall.resistance"] == pytest.approx(
        0.0625, rel=1e-9
    )


def test_cylindrical_wall_resistance_known_answer():
    """R = ln(r2/r1)/(2*pi*k*L). r1=0.05 m, r2=0.06 m, k=50 W/m-K
    (steel pipe), L=1.0 m."""
    import math

    _info, fn = _solvers()["heat.cylindrical_wall_resistance"]
    result = fn(
        {
            "heat.cylinder.inner_radius": 0.05,
            "heat.cylinder.outer_radius": 0.06,
            "heat.cylinder.conductivity": 50.0,
            "heat.cylinder.length": 1.0,
        }
    )
    assert result.is_ok
    expected = math.log(0.06 / 0.05) / (2 * math.pi * 50.0 * 1.0)
    assert result.danger_ok.values["heat.cylinder.resistance"] == pytest.approx(
        expected, rel=1e-9
    )


def test_series_resistance_and_rate():
    """Composite wall: R1=0.0625, R2=0.02 K/W in series -> R=0.0825
    K/W; delta_T=50K -> q = 50/0.0825 = 606.06 W."""
    solvers = _solvers()
    r_result = solvers["heat.series_resistance"][1](
        {"heat.network.r1": 0.0625, "heat.network.r2": 0.02}
    )
    assert r_result.is_ok
    r_total = r_result.danger_ok.values["heat.network.r_series"]
    assert r_total == pytest.approx(0.0825, rel=1e-9)

    q_result = solvers["heat.rate_from_resistance"][1](
        {"heat.network.delta_temp": 50.0, "heat.network.resistance": r_total}
    )
    assert q_result.is_ok
    assert q_result.danger_ok.values["heat.network.rate"] == pytest.approx(
        50.0 / 0.0825, rel=1e-9
    )


def test_dittus_boelter_nusselt_known_answer():
    """Nu = 0.023 * Re^0.8 * Pr^0.4 (heating). Re=1e5, Pr=5.0 ->
    Nu = 0.023 * 1e5^0.8 * 5^0.4."""
    _info, fn = _solvers()["heat.dittus_boelter_nusselt_heating"]
    result = fn(
        {"heat.internal_flow.reynolds": 1.0e5, "heat.internal_flow.prandtl": 5.0}
    )
    assert result.is_ok
    expected = 0.023 * (1.0e5) ** 0.8 * (5.0) ** 0.4
    assert result.danger_ok.values["heat.internal_flow.nusselt"] == pytest.approx(
        expected, rel=1e-9
    )


def test_dittus_boelter_domain_rejects_below_validity_reynolds():
    """The published validity box requires Re >= 1e4 (Incropera ch. 8);
    a call below that is out of the registered Domain."""
    info, _fn = _solvers()["heat.dittus_boelter_nusselt_heating"]
    assert info.domain.box["heat.internal_flow.reynolds"].lo == pytest.approx(1e4)
