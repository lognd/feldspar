from __future__ import annotations

"""WO-111 tests: reflected-inertia drive acceleration torque
(`python/feldspar/library/drive.py`), called THROUGH the
`SolverRegistry`/`SolveFn` protocol. Calibration is an exact evaluation
of the composed Norton/Slocum closed form (docs/benchmarks-memo.md sec.
19) with a hand-computed reference case (WO111-F1: no independent worked
numeric transcribed -- the oracle is the cited relation), plus the two
limiting-case cross-checks the module docstring names."""

import pytest

from feldspar.library.drive import register
from feldspar.solve import SolverRegistry

_CASE = {
    "mech.drive.accel.j_motor": 1.0e-4,
    "mech.drive.accel.j_load": 4.0e-3,
    "mech.drive.accel.gear_ratio": 5.0,
    "mech.drive.accel.efficiency": 0.9,
    "mech.drive.accel.alpha": 100.0,
    "mech.drive.accel.t_load": 2.0,
}


def _solvers() -> dict:
    registry = SolverRegistry()
    register(registry)
    return {info.solver_id: (info, fn) for info, fn in registry}


def test_accel_torque_matches_hand_computed():
    """J_total = 1e-4 + 4e-3/25 = 2.6e-4; T = 2.6e-4*100 + 2/(5*0.9)
    = 0.026 + 0.4444444 = 0.4704444 N*m."""
    _i, fn = _solvers()["mech.drive.drive_acceleration_torque"]
    v = fn(dict(_CASE)).danger_ok.values["mech.drive.accel.torque_required"]
    assert v == pytest.approx(0.026 + 2.0 / 4.5, rel=1e-9)


def test_direct_drive_limit_sums_inertias():
    """N=1 -> reflected inertia is the plain sum J_motor+J_load, and the
    load torque reflects 1:1 through efficiency."""
    _i, fn = _solvers()["mech.drive.drive_acceleration_torque"]
    case = dict(_CASE)
    case["mech.drive.accel.gear_ratio"] = 1.0
    v = fn(case).danger_ok.values["mech.drive.accel.torque_required"]
    expected = (1.0e-4 + 4.0e-3) * 100.0 + 2.0 / (1.0 * 0.9)
    assert v == pytest.approx(expected, rel=1e-9)


def test_zero_load_inertia_limit():
    """J_load=0 -> only the motor rotor accelerates, plus reflected load
    torque."""
    _i, fn = _solvers()["mech.drive.drive_acceleration_torque"]
    case = dict(_CASE)
    case["mech.drive.accel.j_load"] = 0.0
    v = fn(case).danger_ok.values["mech.drive.accel.torque_required"]
    expected = 1.0e-4 * 100.0 + 2.0 / (5.0 * 0.9)
    assert v == pytest.approx(expected, rel=1e-9)


def test_drive_bad_inputs_honest_indeterminate():
    _i, fn = _solvers()["mech.drive.drive_acceleration_torque"]
    bad = dict(_CASE)
    bad["mech.drive.accel.gear_ratio"] = 0.5  # below the N>=1 reducer floor
    r = fn(bad)
    assert r.is_err and r.err.kind == "OutOfDomain"
