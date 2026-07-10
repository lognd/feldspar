from __future__ import annotations

"""WO-24 deliverable 2 tests: known-answer/hand-computed unit tests
for the registered `mech.weld.*` weld-group directions
(`python/feldspar/library/weld_groups.py`, docs/benchmarks-memo.md
sec. 10), called THROUGH the `SolverRegistry`/`SolveFn` protocol."""

import math

import pytest

from feldspar.library.weld_groups import register
from feldspar.solve import SolverRegistry


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    return registry


def _solvers() -> dict:
    registry = _registry()
    return {info.solver_id: (info, fn) for info, fn in registry}


# ---------------------------------------------------------------------------
# 10.1 -- elastic-line in-plane shear + torsion
# ---------------------------------------------------------------------------


def test_weld_group_inplane_shear_torsion_matches_hand_computed():
    """Memo sec. 10.1: rectangular weld pattern, Aw=0.20 m,
    Jw=0.0136 m^3, critical point (0.05, 0.03), Vx=1000, Vy=0,
    T=50 -> f=(4889.706, 183.824), |f|=4893.16 N/m (hand-computed
    exact algebra)."""
    _info, fn = _solvers()["mech.weld.weld_group_inplane_shear_torsion"]
    aw = 0.20
    jw = 0.0136
    xi, yi = 0.05, 0.03
    vx, vy, torque = 1000.0, 0.0, 50.0
    fx = vx / aw - torque * yi / jw
    fy = vy / aw + torque * xi / jw
    expected = math.hypot(fx, fy)
    result = fn(
        {
            "mech.weld.group.vx": vx,
            "mech.weld.group.vy": vy,
            "mech.weld.group.torque": torque,
            "mech.weld.group.aw": aw,
            "mech.weld.group.jw": jw,
            "mech.weld.group.xi": xi,
            "mech.weld.group.yi": yi,
        }
    )
    assert result.is_ok
    got = result.danger_ok.values["mech.weld.group.inplane_line_force"]
    assert got == pytest.approx(expected, rel=1e-9)
    assert got == pytest.approx(4893.16, rel=1e-4)


def test_weld_group_inplane_nonpositive_length_is_honest_indeterminate():
    _info, fn = _solvers()["mech.weld.weld_group_inplane_shear_torsion"]
    result = fn(
        {
            "mech.weld.group.vx": 1000.0,
            "mech.weld.group.vy": 0.0,
            "mech.weld.group.torque": 50.0,
            "mech.weld.group.aw": 0.0,
            "mech.weld.group.jw": 0.0136,
            "mech.weld.group.xi": 0.05,
            "mech.weld.group.yi": 0.03,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_weld_group_inplane_nonpositive_jw_is_honest_indeterminate():
    _info, fn = _solvers()["mech.weld.weld_group_inplane_shear_torsion"]
    result = fn(
        {
            "mech.weld.group.vx": 1000.0,
            "mech.weld.group.vy": 0.0,
            "mech.weld.group.torque": 50.0,
            "mech.weld.group.aw": 0.20,
            "mech.weld.group.jw": 0.0,
            "mech.weld.group.xi": 0.05,
            "mech.weld.group.yi": 0.03,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# 10.2 -- elastic-line out-of-plane bending
# ---------------------------------------------------------------------------


def test_weld_group_outofplane_bending_matches_hand_computed():
    """Memo sec. 10.2: M=600 N*m, Iw=0.0024 m^3, c=0.06 m ->
    f=15000.0 N/m (exact algebra)."""
    _info, fn = _solvers()["mech.weld.weld_group_outofplane_bending"]
    result = fn(
        {
            "mech.weld.group.moment": 600.0,
            "mech.weld.group.iw": 0.0024,
            "mech.weld.group.c": 0.06,
        }
    )
    assert result.is_ok
    got = result.danger_ok.values["mech.weld.group.bending_line_force"]
    assert got == pytest.approx(15000.0, rel=1e-9)


def test_weld_group_outofplane_nonpositive_iw_is_honest_indeterminate():
    _info, fn = _solvers()["mech.weld.weld_group_outofplane_bending"]
    result = fn(
        {
            "mech.weld.group.moment": 600.0,
            "mech.weld.group.iw": 0.0,
            "mech.weld.group.c": 0.06,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# 10.3 -- vector-summed peak line force vs allowable
# ---------------------------------------------------------------------------


def test_weld_group_utilization_matches_hand_computed():
    """Memo sec. 10.3: f_inplane=4893.16 N/m, f_bending=15000.0 N/m,
    leg=0.008 m -> f_peak=sqrt(4893.16^2+15000^2)=15777.9 N/m,
    throat=0.707*0.008=0.005656 m, stress=2,789,591 Pa (approx);
    allowable=145e6 Pa -> ratio~0.01924 (Valid)."""
    _info, fn = _solvers()["mech.weld.weld_group_utilization"]
    f_inplane = 4893.16
    f_bending = 15000.0
    leg_size = 0.008
    allowable = 145.0e6
    f_peak = math.hypot(f_inplane, f_bending)
    throat = 0.707 * leg_size
    expected_stress = f_peak / throat
    expected_ratio = expected_stress / allowable
    result = fn(
        {
            "mech.weld.group.inplane_line_force": f_inplane,
            "mech.weld.group.bending_line_force": f_bending,
            "mech.weld.group.leg_size": leg_size,
            "mech.weld.group.allowable_stress": allowable,
        }
    )
    assert result.is_ok
    values = result.danger_ok.values
    assert values["mech.weld.group.peak_stress"] == pytest.approx(
        expected_stress, rel=1e-9
    )
    assert values["mech.weld.group.utilization_ratio"] == pytest.approx(
        expected_ratio, rel=1e-9
    )
    assert values["mech.weld.group.utilization_ratio"] < 1.0


def test_weld_group_utilization_over_allowable_reports_ratio_above_one():
    """A small under-sized weld under large load -- honest ratio > 1,
    not a raised error (an over-utilized weld is a valid, just
    unfavorable, physical outcome)."""
    _info, fn = _solvers()["mech.weld.weld_group_utilization"]
    result = fn(
        {
            "mech.weld.group.inplane_line_force": 1.0e6,
            "mech.weld.group.bending_line_force": 0.0,
            "mech.weld.group.leg_size": 0.003,
            "mech.weld.group.allowable_stress": 1.0e6,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["mech.weld.group.utilization_ratio"] > 1.0


def test_weld_group_utilization_nonpositive_leg_size_is_honest_indeterminate():
    _info, fn = _solvers()["mech.weld.weld_group_utilization"]
    result = fn(
        {
            "mech.weld.group.inplane_line_force": 1000.0,
            "mech.weld.group.bending_line_force": 0.0,
            "mech.weld.group.leg_size": 0.0,
            "mech.weld.group.allowable_stress": 145.0e6,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_weld_group_utilization_nonpositive_allowable_is_honest_indeterminate():
    _info, fn = _solvers()["mech.weld.weld_group_utilization"]
    result = fn(
        {
            "mech.weld.group.inplane_line_force": 1000.0,
            "mech.weld.group.bending_line_force": 0.0,
            "mech.weld.group.leg_size": 0.008,
            "mech.weld.group.allowable_stress": 0.0,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
