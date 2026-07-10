from __future__ import annotations

"""WO-24 deliverable 6 tests: known-answer/hand-computed unit tests for
the registered `heat.transient` lumped-capacitance directions
(`python/feldspar/library/thermal_transient.py`), called THROUGH the
`SolverRegistry`/`SolveFn` protocol (ports, domain guards, and the
Biot-number honesty gate exercised, not just the raw formula).
Fixture values and expected results match docs/benchmarks-memo.md
sec. 12."""

import math

import pytest

from feldspar.library.thermal_transient import register
from feldspar.solve import SolverRegistry

_T_AMB = 298.15
_POWER = 5.0
_R_TH = 20.0
_C_TH = 2.0
_TAU = _R_TH * _C_TH
_BI_OK = 0.05


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    return registry


def _solvers() -> dict:
    registry = _registry()
    return {info.solver_id: (info, fn) for info, fn in registry}


# ---------------------------------------------------------------------------
# Biot-number convenience direction
# ---------------------------------------------------------------------------


def test_biot_number_from_convection_matches_hand_computed():
    _info, fn = _solvers()["heat.transient.biot_number_from_convection"]
    result = fn(
        {
            "heat.transient.convection_coefficient": 10.0,
            "heat.transient.characteristic_length": 0.01,
            "heat.transient.conductivity": 200.0,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["heat.transient.biot_number"] == pytest.approx(
        10.0 * 0.01 / 200.0, rel=1e-9
    )


def test_biot_number_from_convection_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["heat.transient.biot_number_from_convection"]
    result = fn(
        {
            "heat.transient.convection_coefficient": 0.0,
            "heat.transient.characteristic_length": 0.01,
            "heat.transient.conductivity": 200.0,
        }
    )
    assert result.is_err


# ---------------------------------------------------------------------------
# Step response (memo sec. 12.1)
# ---------------------------------------------------------------------------


def test_step_temperature_one_tau_matches_hand_computed():
    _info, fn = _solvers()["heat.transient.step_temperature"]
    result = fn(
        {
            "heat.transient.t_amb": _T_AMB,
            "heat.transient.power": _POWER,
            "heat.transient.r_th": _R_TH,
            "heat.transient.c_th": _C_TH,
            "heat.transient.time": _TAU,
            "heat.transient.biot_number": _BI_OK,
        }
    )
    assert result.is_ok
    expected = _T_AMB + 100.0 * (1.0 - math.exp(-1.0))
    assert expected == pytest.approx(361.36205588, rel=1e-6)
    assert result.danger_ok.values["heat.transient.temperature"] == pytest.approx(
        expected, rel=1e-9
    )


def test_step_temperature_five_tau_matches_hand_computed():
    _info, fn = _solvers()["heat.transient.step_temperature"]
    result = fn(
        {
            "heat.transient.t_amb": _T_AMB,
            "heat.transient.power": _POWER,
            "heat.transient.r_th": _R_TH,
            "heat.transient.c_th": _C_TH,
            "heat.transient.time": 5.0 * _TAU,
            "heat.transient.biot_number": _BI_OK,
        }
    )
    assert result.is_ok
    expected = _T_AMB + 100.0 * (1.0 - math.exp(-5.0))
    assert result.danger_ok.values["heat.transient.temperature"] == pytest.approx(
        expected, rel=1e-9
    )


def test_step_temperature_rejects_high_biot():
    _info, fn = _solvers()["heat.transient.step_temperature"]
    result = fn(
        {
            "heat.transient.t_amb": _T_AMB,
            "heat.transient.power": _POWER,
            "heat.transient.r_th": _R_TH,
            "heat.transient.c_th": _C_TH,
            "heat.transient.time": _TAU,
            "heat.transient.biot_number": 0.5,
        }
    )
    assert result.is_err


def test_step_temperature_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["heat.transient.step_temperature"]
    result = fn(
        {
            "heat.transient.t_amb": _T_AMB,
            "heat.transient.power": _POWER,
            "heat.transient.r_th": 0.0,
            "heat.transient.c_th": _C_TH,
            "heat.transient.time": _TAU,
            "heat.transient.biot_number": _BI_OK,
        }
    )
    assert result.is_err


# ---------------------------------------------------------------------------
# Time-to-threshold (memo sec. 12.2)
# ---------------------------------------------------------------------------


def test_time_to_threshold_recovers_tau():
    _info, fn = _solvers()["heat.transient.time_to_threshold"]
    threshold_rise = 100.0 * (1.0 - math.exp(-1.0))
    result = fn(
        {
            "heat.transient.t_amb": _T_AMB,
            "heat.transient.power": _POWER,
            "heat.transient.r_th": _R_TH,
            "heat.transient.c_th": _C_TH,
            "heat.transient.t_threshold": _T_AMB + threshold_rise,
            "heat.transient.biot_number": _BI_OK,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["heat.transient.time_to_threshold"] == pytest.approx(
        _TAU, rel=1e-6
    )


def test_time_to_threshold_unreachable_is_honest_indeterminate():
    """T_threshold above the asymptotic steady state (P*R_th=100.0 K
    rise) is never reached -- must be an honest `OutOfDomain`, not a
    fabricated (e.g. infinite or NaN) time."""
    _info, fn = _solvers()["heat.transient.time_to_threshold"]
    result = fn(
        {
            "heat.transient.t_amb": _T_AMB,
            "heat.transient.power": _POWER,
            "heat.transient.r_th": _R_TH,
            "heat.transient.c_th": _C_TH,
            "heat.transient.t_threshold": _T_AMB + 150.0,
            "heat.transient.biot_number": _BI_OK,
        }
    )
    assert result.is_err


def test_time_to_threshold_rejects_high_biot():
    _info, fn = _solvers()["heat.transient.time_to_threshold"]
    result = fn(
        {
            "heat.transient.t_amb": _T_AMB,
            "heat.transient.power": _POWER,
            "heat.transient.r_th": _R_TH,
            "heat.transient.c_th": _C_TH,
            "heat.transient.t_threshold": _T_AMB + 50.0,
            "heat.transient.biot_number": 0.2,
        }
    )
    assert result.is_err


# ---------------------------------------------------------------------------
# Duty-cycle peak temperature (memo sec. 12.3)
# ---------------------------------------------------------------------------


def test_duty_cycle_peak_temperature_matches_hand_computed():
    _info, fn = _solvers()["heat.transient.duty_cycle_peak_temperature"]
    result = fn(
        {
            "heat.transient.t_amb": _T_AMB,
            "heat.transient.power": _POWER,
            "heat.transient.r_th": _R_TH,
            "heat.transient.c_th": _C_TH,
            "heat.transient.t_on": 2.0,
            "heat.transient.t_off": 8.0,
            "heat.transient.biot_number": _BI_OK,
        }
    )
    assert result.is_ok
    a = math.exp(-2.0 / _TAU)
    b = math.exp(-8.0 / _TAU)
    expected = _T_AMB + 100.0 * (1.0 - a) / (1.0 - a * b)
    assert expected == pytest.approx(320.19825866, rel=1e-6)
    assert result.danger_ok.values[
        "heat.transient.duty_peak_temperature"
    ] == pytest.approx(expected, rel=1e-9)


def test_duty_cycle_peak_temperature_continuous_limit_matches_step_asymptote():
    """t_off -> 0 (duty -> 1) recovers the ordinary step response's
    steady-state asymptote, P*R_th (memo sec. 12.3 limiting case)."""
    _info, fn = _solvers()["heat.transient.duty_cycle_peak_temperature"]
    result = fn(
        {
            "heat.transient.t_amb": _T_AMB,
            "heat.transient.power": _POWER,
            "heat.transient.r_th": _R_TH,
            "heat.transient.c_th": _C_TH,
            "heat.transient.t_on": 1000.0 * _TAU,
            "heat.transient.t_off": 1e-9,
            "heat.transient.biot_number": _BI_OK,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "heat.transient.duty_peak_temperature"
    ] == pytest.approx(_T_AMB + 100.0, rel=1e-6)


def test_duty_cycle_peak_temperature_quasi_steady_matches_average_power():
    """Switching period << tau recovers the average-power duty
    derating heuristic, P*d*R_th (memo sec. 12.3 limiting case)."""
    _info, fn = _solvers()["heat.transient.duty_cycle_peak_temperature"]
    t_on = 0.001
    t_off = 0.004
    duty = t_on / (t_on + t_off)
    result = fn(
        {
            "heat.transient.t_amb": _T_AMB,
            "heat.transient.power": _POWER,
            "heat.transient.r_th": _R_TH,
            "heat.transient.c_th": _C_TH,
            "heat.transient.t_on": t_on,
            "heat.transient.t_off": t_off,
            "heat.transient.biot_number": _BI_OK,
        }
    )
    assert result.is_ok
    expected_quasi = _T_AMB + _POWER * duty * _R_TH
    assert result.danger_ok.values[
        "heat.transient.duty_peak_temperature"
    ] == pytest.approx(expected_quasi, rel=1e-3)


def test_duty_cycle_peak_temperature_rejects_high_biot():
    _info, fn = _solvers()["heat.transient.duty_cycle_peak_temperature"]
    result = fn(
        {
            "heat.transient.t_amb": _T_AMB,
            "heat.transient.power": _POWER,
            "heat.transient.r_th": _R_TH,
            "heat.transient.c_th": _C_TH,
            "heat.transient.t_on": 2.0,
            "heat.transient.t_off": 8.0,
            "heat.transient.biot_number": 0.3,
        }
    )
    assert result.is_err


def test_duty_cycle_peak_temperature_degenerate_zero_period_is_indeterminate():
    _info, fn = _solvers()["heat.transient.duty_cycle_peak_temperature"]
    result = fn(
        {
            "heat.transient.t_amb": _T_AMB,
            "heat.transient.power": _POWER,
            "heat.transient.r_th": _R_TH,
            "heat.transient.c_th": _C_TH,
            "heat.transient.t_on": 0.0,
            "heat.transient.t_off": 0.0,
            "heat.transient.biot_number": _BI_OK,
        }
    )
    assert result.is_err
