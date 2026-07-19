from __future__ import annotations

"""WO-20 conformance tests: known-answer unit tests for the registered
`fluids` solver directions (`python/feldspar/library/fluids.py`),
called THROUGH the `SolverRegistry`/`SolveFn` protocol (never
`feldspar._feldspar.fluids_*` directly), turning the benchmarks memo's
fluid-network cases (lithos
`docs/workflow/research/2026-07-08-benchmarks-and-datasets.md` sec. 3)
into pytest conformance tests with their cited tolerances."""

import math

import pytest

from feldspar.library.fluids import register
from feldspar.solve import SolverRegistry


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    return registry


def _solvers() -> dict:
    registry = _registry()
    return {info.solver_id: (info, fn) for info, fn in registry}


def test_laminar_friction_factor_exact_floor():
    """Benchmarks memo 3.1, second anchor: Re=1000 -> f=64/Re=0.0640
    exact (Hagen-Poiseuille). Tolerance +/-0.1%."""
    _info, fn = _solvers()["fluids.laminar_friction_factor"]
    result = fn({"fluids.pipe.reynolds": 1000.0})
    assert result.is_ok
    f = result.danger_ok.values["fluids.pipe.friction_factor"]
    assert f == pytest.approx(0.0640, rel=1e-3)


def test_colebrook_root_is_self_consistent():
    """Benchmarks memo 3.1: commercial steel, D=0.1m, eps=0.045mm,
    Re=1e5. The solver's converged root must satisfy the Colebrook
    defining equation to a tight residual (independent verification:
    the analytically bisected root is f=0.02012, not the memo's rounded
    0.0195 -- see WO-20 close-out report)."""
    _info, fn = _solvers()["fluids.colebrook_friction_factor"]
    rel_rough = 0.045e-3 / 0.1
    reynolds = 1.0e5
    result = fn(
        {
            "fluids.pipe.reynolds": reynolds,
            "fluids.pipe.relative_roughness": rel_rough,
        }
    )
    assert result.is_ok
    f = result.danger_ok.values["fluids.pipe.friction_factor"]
    residual = 1.0 / math.sqrt(f) + 2.0 * math.log10(
        rel_rough / 3.7 + 2.51 / (reynolds * math.sqrt(f))
    )
    assert residual == pytest.approx(0.0, abs=1e-6)
    assert f == pytest.approx(0.02012, rel=5e-3)


# frob:tests python/feldspar/fluids/incompressible.py::colebrook_friction_factor kind="unit"
# frob:tests python/feldspar/fluids/incompressible.py::haaland_friction_factor kind="unit"
def test_haaland_matches_colebrook_within_two_percent():
    """Benchmarks memo 3.1: 'confirm Haaland within +/-2% of
    Colebrook.'"""
    solvers = _solvers()
    rel_rough = 0.045e-3 / 0.1
    reynolds = 1.0e5
    inputs = {
        "fluids.pipe.reynolds": reynolds,
        "fluids.pipe.relative_roughness": rel_rough,
    }
    f_colebrook = solvers["fluids.colebrook_friction_factor"][1](
        inputs
    ).danger_ok.values["fluids.pipe.friction_factor"]
    f_haaland = solvers["fluids.haaland_friction_factor"][1](inputs).danger_ok.values[
        "fluids.pipe.friction_factor.haaland"
    ]
    assert abs(f_haaland - f_colebrook) / f_colebrook < 0.02


# frob:tests python/feldspar/fluids/incompressible.py::series_dp kind="unit"
def test_series_network_dp_reduction():
    """Benchmarks memo 3.2, series case: h1=3.0 m, h2=2.0 m ->
    h_total=5.0 m exact."""
    _info, fn = _solvers()["fluids.series_dp"]
    result = fn({"fluids.network.dp1": 3.0, "fluids.network.dp2": 2.0})
    assert result.is_ok
    assert result.danger_ok.values["fluids.network.dp_series"] == pytest.approx(
        5.0, rel=1e-9
    )


# frob:tests python/feldspar/fluids/incompressible.py::parallel_flow kind="unit"
def test_parallel_network_flow_reduction():
    """Benchmarks memo 3.2, parallel case: two identical branches each
    Q=0.006 m^3/s -> Q_total=0.012 m^3/s exact."""
    _info, fn = _solvers()["fluids.parallel_flow"]
    result = fn({"fluids.network.q1": 0.006, "fluids.network.q2": 0.006})
    assert result.is_ok
    assert result.danger_ok.values["fluids.network.q_parallel"] == pytest.approx(
        0.012, rel=1e-9
    )


# frob:tests python/feldspar/fluids/incompressible.py::pump_operating_flow kind="unit"
# frob:tests python/feldspar/fluids/incompressible.py::pump_operating_head kind="unit"
def test_pump_operating_point_matches_memo_case():
    """Benchmarks memo 3.3: H0=50m, a=2000, H_static=10m, R=3000 ->
    Q*=0.08944 m^3/s, H*=34.0 m. Tolerance +/-0.1% exact."""
    solvers = _solvers()
    _info_q, fn_q = solvers["fluids.pump_operating_flow"]
    _info_h, fn_h = solvers["fluids.pump_operating_head"]
    inputs = {
        "fluids.pump.h0": 50.0,
        "fluids.pump.a_coeff": 2000.0,
        "fluids.system.h_static": 10.0,
        "fluids.system.r_coeff": 3000.0,
    }
    result_q = fn_q(inputs)
    assert result_q.is_ok
    q_star = result_q.danger_ok.values["fluids.pump.q_star"]
    assert q_star == pytest.approx(0.08944, rel=1e-3)

    inputs_h = dict(inputs)
    inputs_h["fluids.pump.q_star"] = q_star
    result_h = fn_h(inputs_h)
    assert result_h.is_ok
    h_star = result_h.danger_ok.values["fluids.pump.h_star"]
    assert h_star == pytest.approx(34.0, rel=1e-3)


def test_npsh_available_known_answer():
    """NPSHa = (p_atm - p_vapor)/(rho*g) + static_head - friction_head.
    Standard atmosphere, cold water, flooded suction: p_atm=101325 Pa,
    p_vapor=2339 Pa (20C water), rho=998 kg/m^3, g=9.81 m/s^2,
    static_head=2.0 m, friction_head=0.5 m ->
    NPSHa = (101325-2339)/(998*9.81) + 2.0 - 0.5 = 10.108 + 1.5 = 11.61 m."""
    _info, fn = _solvers()["fluids.npsh_available"]
    result = fn(
        {
            "fluids.env.p_atm": 101325.0,
            "fluids.fluid.p_vapor": 2339.0,
            "fluids.fluid.density": 998.0,
            "fluids.env.gravity": 9.81,
            "fluids.suction.static_head": 2.0,
            "fluids.suction.friction_head": 0.5,
        }
    )
    assert result.is_ok
    npsh = result.danger_ok.values["fluids.npsh_margin"]
    expected = (101325.0 - 2339.0) / (998.0 * 9.81) + 2.0 - 0.5
    assert npsh == pytest.approx(expected, rel=1e-6)


# frob:tests python/feldspar/fluids/incompressible.py::joukowsky_dp kind="unit"
def test_joukowsky_water_hammer_dp():
    """Joukowsky: dp = rho*a*dV. Water rho=1000, wave speed a=1200 m/s
    (typical steel pipe), instantaneous closure dV=2 m/s ->
    dp = 1000*1200*2 = 2.4e6 Pa exact."""
    _info, fn = _solvers()["fluids.joukowsky_dp"]
    result = fn(
        {
            "fluids.fluid.density": 1000.0,
            "fluids.transient.wave_speed": 1200.0,
            "fluids.transient.delta_velocity": 2.0,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["fluids.transient.hammer_dp"] == pytest.approx(
        2.4e6, rel=1e-9
    )


# ---------------------------------------------------------------------------
# Compressible tier (D141): isentropic + normal shock + Fanno, and the
# regime-tag routing proof (incompressible entries carry the
# incompressible tag, compressible entries the compressible tag; a
# beyond-regime gas case must not silently reuse the incompressible
# friction-factor entry).
# ---------------------------------------------------------------------------


# frob:tests python/feldspar/fluids/compressible.py::isentropic_stagnation_temp_ratio kind="unit"
# frob:tests python/feldspar/fluids/compressible.py::isentropic_stagnation_pressure_ratio kind="unit"
def test_isentropic_stagnation_ratios_known_case():
    """Air, k=1.4, M=0.5: T0/T = 1 + 0.2*0.25 = 1.05;
    p0/p = 1.05^(1.4/0.4) = 1.05^3.5 = 1.1858 (Anderson ch. 3)."""
    solvers = _solvers()
    inputs = {"fluids.compressible.mach": 0.5, "fluids.gas.gamma": 1.4}
    t_ratio = solvers["fluids.isentropic_stagnation_temp_ratio"][1](
        inputs
    ).danger_ok.values["fluids.compressible.stagnation_temp_ratio"]
    p_ratio = solvers["fluids.isentropic_stagnation_pressure_ratio"][1](
        inputs
    ).danger_ok.values["fluids.compressible.stagnation_pressure_ratio"]
    assert t_ratio == pytest.approx(1.05, rel=1e-9)
    assert p_ratio == pytest.approx(1.05**3.5, rel=1e-9)


# frob:tests python/feldspar/fluids/compressible.py::normal_shock_mach2 kind="unit"
# frob:tests python/feldspar/fluids/compressible.py::normal_shock_pressure_ratio kind="unit"
def test_normal_shock_known_case():
    """Air, k=1.4, M1=2.0: M2 = sqrt((1+0.2*4)/(1.4*4-0.2)) =
    sqrt(1.8/5.4) = 0.5774; p2/p1 = 1 + (2*1.4/2.4)*(4-1) = 4.5
    (Anderson ch. 3, standard M1=2 normal-shock table entry)."""
    solvers = _solvers()
    inputs = {"fluids.compressible.mach_upstream": 2.0, "fluids.gas.gamma": 1.4}
    m2 = solvers["fluids.normal_shock_mach2"][1](inputs).danger_ok.values[
        "fluids.compressible.mach_downstream"
    ]
    p_ratio = solvers["fluids.normal_shock_pressure_ratio"][1](inputs).danger_ok.values[
        "fluids.compressible.shock_pressure_ratio"
    ]
    assert m2 == pytest.approx(0.5774, rel=1e-3)
    assert p_ratio == pytest.approx(4.5, rel=1e-9)


def test_fanno_function_matches_choking_definition():
    """At M=1 the Fanno function is exactly 0.0 (the choking point by
    definition -- Anderson ch. 3 / Shapiro vol. 1 ch. 6)."""
    _info, fn = _solvers()["fluids.fanno_function"]
    result = fn({"fluids.compressible.mach": 1.0, "fluids.gas.gamma": 1.4})
    assert result.is_ok
    value = result.danger_ok.values["fluids.compressible.fanno_function"]
    assert value == pytest.approx(0.0, abs=1e-9)


def test_compressible_and_incompressible_entries_carry_distinct_regime_tags():
    """D141 regime-routing proof: the incompressible friction-factor
    entries carry the 'incompressible' domain tag, the compressible
    entries carry 'compressible' -- never both, so a gas subnet beyond
    the incompressible (low-Mach) regime routes to the compressible
    entry instead of silently reusing the incompressible one, and vice
    versa (proven both ways)."""
    solvers = _solvers()
    incompressible_ids = [
        "fluids.laminar_friction_factor",
        "fluids.colebrook_friction_factor",
        "fluids.haaland_friction_factor",
    ]
    compressible_ids = [
        "fluids.isentropic_stagnation_temp_ratio",
        "fluids.isentropic_stagnation_pressure_ratio",
        "fluids.normal_shock_mach2",
        "fluids.normal_shock_pressure_ratio",
        "fluids.fanno_function",
    ]
    for solver_id in incompressible_ids:
        info, _fn = solvers[solver_id]
        assert "incompressible" in info.domain.tags
        assert "compressible" not in info.domain.tags
    for solver_id in compressible_ids:
        info, _fn = solvers[solver_id]
        assert "compressible" in info.domain.tags
        assert "incompressible" not in info.domain.tags


# frob:tests python/feldspar/fluids/incompressible.py::darcy_dp kind="unit"
def test_darcy_weisbach_dp_matches_hand_computed_case():
    """Darcy-Weisbach dp = f * (L/D) * (rho * v^2 / 2): f=0.02, L=100m,
    D=0.1m, rho=1000 kg/m^3, v=2 m/s -> dp = 0.02*1000*1000*2 = 40000 Pa
    (hand-computed, not cited from the benchmarks memo -- exact closed
    form, no empirical fit)."""
    _info, fn = _solvers()["fluids.darcy_dp"]
    result = fn(
        {
            "fluids.pipe.friction_factor": 0.02,
            "fluids.pipe.length": 100.0,
            "fluids.pipe.diameter": 0.1,
            "fluids.fluid.density": 1000.0,
            "fluids.pipe.velocity": 2.0,
        }
    )
    assert result.is_ok
    expected = 0.02 * (100.0 / 0.1) * (1000.0 * 2.0**2 / 2.0)
    assert result.danger_ok.values["fluids.pipe.dp"] == pytest.approx(
        expected, rel=1e-9
    )


# frob:tests python/feldspar/fluids/incompressible.py::minor_loss_dp kind="unit"
def test_minor_loss_dp_matches_hand_computed_case():
    """Minor-loss dp = k * rho * v^2 / 2: k=1.5, rho=1000 kg/m^3,
    v=3 m/s -> dp = 1.5*1000*9/2 = 6750 Pa (hand-computed exact closed
    form)."""
    _info, fn = _solvers()["fluids.minor_loss_dp"]
    result = fn(
        {
            "fluids.fitting.k_factor": 1.5,
            "fluids.fluid.density": 1000.0,
            "fluids.pipe.velocity": 3.0,
        }
    )
    assert result.is_ok
    expected = 1.5 * 1000.0 * 3.0**2 / 2.0
    assert result.danger_ok.values["fluids.fitting.dp"] == pytest.approx(
        expected, rel=1e-9
    )
