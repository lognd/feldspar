from __future__ import annotations

"""WO-111 cycle-35 Class-C model-growth exposure: regolith `Model`
wrappers around the new/previously-unexposed library directions
(thermal transient, shaft critical speed, Roark circular plate, drive
acceleration torque, Gerber fatigue). Each goes through
`_ClosedFormEngineModel` -> `solve()` -> `_engine_registry()`, so these
reuse the exact hand-computed reference values the corresponding
`tests/unit/test_library_*.py` cases already proved (docs/benchmarks-memo
secs. 12/16/17/18/19) -- a mismatch here means the wrapper plumbing is
wrong, not the physics. Regolith-marked (needs a lithos checkout)."""

import math

import pytest
from regolith.harness.model import DischargeRequest
from regolith.harness.quantity import Interval

from feldspar.pack.models import (
    DEFAULT_DRIVE_ACCEL_TORQUE_CLAIM_KIND,
    DEFAULT_FATIGUE_GERBER_FACTOR_OF_SAFETY_CLAIM_KIND,
    DEFAULT_JUNCTION_TEMPERATURE_DUTY_CYCLE_CLAIM_KIND,
    DEFAULT_JUNCTION_TEMPERATURE_TRANSIENT_CLAIM_KIND,
    DEFAULT_PLATE_MAX_DEFLECTION_CLAIM_KIND,
    DEFAULT_PLATE_MAX_STRESS_CLAIM_KIND,
    DEFAULT_SHAFT_CRITICAL_SPEED_CLAIM_KIND,
    DriveAccelTorqueModel,
    FatigueGerberFactorOfSafetyModel,
    PlateMaxDeflectionModel,
    PlateMaxStressModel,
    ShaftCriticalSpeedModel,
    ThermalTransientDutyCyclePeakTemperatureModel,
    ThermalTransientStepTemperatureModel,
)

pytestmark = pytest.mark.regolith


def _pinned(value: float) -> Interval:
    return Interval(lo=value, hi=value)


def test_thermal_transient_step_temperature_reaches_one_tau_mark() -> None:
    """At t=tau the step response is at the 63.2% rise mark (memo sec.
    12.1): T = T_amb + P*R_th*(1-exp(-1))."""
    model = ThermalTransientStepTemperatureModel()
    p, r_th, c_th = 10.0, 2.0, 5.0  # tau = R*C = 10 s
    request = DischargeRequest(
        claim_kind=DEFAULT_JUNCTION_TEMPERATURE_TRANSIENT_CLAIM_KIND,
        limit=1e9,
        inputs={
            "heat.transient.t_amb": _pinned(25.0),
            "heat.transient.power": _pinned(p),
            "heat.transient.r_th": _pinned(r_th),
            "heat.transient.c_th": _pinned(c_th),
            "heat.transient.time": _pinned(10.0),
            "heat.transient.biot_number": _pinned(0.05),
        },
    )
    prediction = model.estimate(request).danger_ok
    expected = 25.0 + p * r_th * (1.0 - math.exp(-1.0))
    assert prediction.value == pytest.approx(expected, rel=1e-9)
    assert prediction.in_domain


def test_thermal_transient_duty_cycle_peak_temperature() -> None:
    """Periodic peak T_amb + P*R_th*(1-a)/(1-a*b) (memo sec. 12.3)."""
    model = ThermalTransientDutyCyclePeakTemperatureModel()
    p, r_th, c_th, t_on, t_off = 10.0, 2.0, 20.0, 2.0, 8.0  # tau = 40 s
    request = DischargeRequest(
        claim_kind=DEFAULT_JUNCTION_TEMPERATURE_DUTY_CYCLE_CLAIM_KIND,
        limit=1e9,
        inputs={
            "heat.transient.t_amb": _pinned(25.0),
            "heat.transient.power": _pinned(p),
            "heat.transient.r_th": _pinned(r_th),
            "heat.transient.c_th": _pinned(c_th),
            "heat.transient.t_on": _pinned(t_on),
            "heat.transient.t_off": _pinned(t_off),
            "heat.transient.biot_number": _pinned(0.05),
        },
    )
    prediction = model.estimate(request).danger_ok
    tau = r_th * c_th
    a = math.exp(-t_on / tau)
    b = math.exp(-t_off / tau)
    expected = 25.0 + p * r_th * (1.0 - a) / (1.0 - a * b)
    assert prediction.value == pytest.approx(expected, rel=1e-9)
    assert prediction.in_domain


def test_shaft_critical_speed_matches_closed_form() -> None:
    """k=1e6, m=2 -> n_c = sqrt(k/m)*60/(2*pi) (memo sec. 16.1)."""
    model = ShaftCriticalSpeedModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_SHAFT_CRITICAL_SPEED_CLAIM_KIND,
        limit=0.0,
        inputs={
            "mech.critical_speed.stiffness": _pinned(1.0e6),
            "mech.critical_speed.mass": _pinned(2.0),
        },
    )
    prediction = model.estimate(request).danger_ok
    expected = math.sqrt(1.0e6 / 2.0) * 60.0 / (2.0 * math.pi)
    assert prediction.value == pytest.approx(expected, rel=1e-9)
    assert prediction.in_domain


def test_plate_max_stress_matches_hand_computed() -> None:
    """SS circular plate, memo sec. 17.1 reference case -> 4.95 MPa."""
    model = PlateMaxStressModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_PLATE_MAX_STRESS_CLAIM_KIND,
        limit=1e12,
        inputs={
            "mech.plate.circular.q": _pinned(1.0e4),
            "mech.plate.circular.a": _pinned(0.1),
            "mech.plate.circular.t": _pinned(5.0e-3),
            "mech.plate.circular.e": _pinned(200.0e9),
            "mech.plate.circular.nu": _pinned(0.3),
        },
    )
    prediction = model.estimate(request).danger_ok
    assert prediction.value == pytest.approx(4.95e6, rel=1e-9)
    assert prediction.in_domain


def test_plate_max_deflection_matches_hand_computed() -> None:
    """SS circular plate center deflection, memo sec. 17.2."""
    model = PlateMaxDeflectionModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_PLATE_MAX_DEFLECTION_CLAIM_KIND,
        limit=1.0,
        inputs={
            "mech.plate.circular.q": _pinned(1.0e4),
            "mech.plate.circular.a": _pinned(0.1),
            "mech.plate.circular.t": _pinned(5.0e-3),
            "mech.plate.circular.e": _pinned(200.0e9),
            "mech.plate.circular.nu": _pinned(0.3),
        },
    )
    prediction = model.estimate(request).danger_ok
    d = 200.0e9 * (5.0e-3) ** 3 / (12.0 * (1.0 - 0.3**2))
    expected = 1.0e4 * 0.1**4 * (5.0 + 0.3) / (64.0 * d * (1.0 + 0.3))
    assert prediction.value == pytest.approx(expected, rel=1e-9)
    assert prediction.in_domain


def test_drive_accel_torque_matches_hand_computed() -> None:
    """Reflected-inertia acceleration torque, memo sec. 19 -> 0.47044 N*m."""
    model = DriveAccelTorqueModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_DRIVE_ACCEL_TORQUE_CLAIM_KIND,
        limit=1e9,
        inputs={
            "mech.drive.accel.j_motor": _pinned(1.0e-4),
            "mech.drive.accel.j_load": _pinned(4.0e-3),
            "mech.drive.accel.gear_ratio": _pinned(5.0),
            "mech.drive.accel.efficiency": _pinned(0.9),
            "mech.drive.accel.alpha": _pinned(100.0),
            "mech.drive.accel.t_load": _pinned(2.0),
        },
    )
    prediction = model.estimate(request).danger_ok
    assert prediction.value == pytest.approx(0.026 + 2.0 / 4.5, rel=1e-9)
    assert prediction.in_domain


def test_fatigue_gerber_factor_of_safety_matches_hand_computed() -> None:
    """Gerber nf = 16*(sqrt(1.25)-1) = 1.88854 (memo sec. 18)."""
    model = FatigueGerberFactorOfSafetyModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_FATIGUE_GERBER_FACTOR_OF_SAFETY_CLAIM_KIND,
        limit=0.0,
        inputs={
            "mech.fatigue.gerber.se": _pinned(100.0e6),
            "mech.fatigue.gerber.sut": _pinned(400.0e6),
            "mech.fatigue.gerber.sigma_a": _pinned(50.0e6),
            "mech.fatigue.gerber.sigma_m": _pinned(50.0e6),
        },
    )
    prediction = model.estimate(request).danger_ok
    assert prediction.value == pytest.approx(16.0 * (math.sqrt(1.25) - 1.0), rel=1e-9)
    assert prediction.in_domain
