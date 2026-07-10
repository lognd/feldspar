from __future__ import annotations

"""WO-24 deliverable 1 tests: known-answer/hand-computed unit tests
for the registered `mech.joint.*` bolted-joint directions
(`python/feldspar/library/bolted_joints.py`, docs/benchmarks-memo.md
sec. 8), called THROUGH the `SolverRegistry`/`SolveFn` protocol."""

import math

import pytest

from feldspar.library.bolted_joints import register
from feldspar.solve import SolverRegistry


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    return registry


def _solvers() -> dict:
    registry = _registry()
    return {info.solver_id: (info, fn) for info, fn in registry}


# ---------------------------------------------------------------------------
# 8.1 -- VDI 2230 single-bolt tier
# ---------------------------------------------------------------------------


def test_vdi2230_load_factor_matches_hand_computed():
    """Memo sec. 8.1: cb=200e6, cp=800e6, fv=10000, fa=5000 ->
    phi=0.20, F_S=11000, F_KR=6000 (exact algebra)."""
    _info, fn = _solvers()["mech.joint.bolt_single_load_factor_vdi2230"]
    result = fn(
        {
            "mech.joint.bolt.cb": 200.0e6,
            "mech.joint.bolt.cp": 800.0e6,
            "mech.joint.bolt.fv": 10_000.0,
            "mech.joint.bolt.fa": 5_000.0,
        }
    )
    assert result.is_ok
    values = result.danger_ok.values
    assert values["mech.joint.bolt.load_factor"] == pytest.approx(0.20, rel=1e-9)
    assert values["mech.joint.bolt.working_load"] == pytest.approx(11_000.0, rel=1e-9)
    assert values["mech.joint.bolt.residual_clamp_load"] == pytest.approx(
        6_000.0, rel=1e-9
    )


def test_vdi2230_separation_when_residual_clamp_load_goes_nonpositive():
    """A large enough external load drives F_KR <= 0 -- the direction
    reports this honestly rather than raising (a separated joint is a
    valid physical outcome, not a domain violation)."""
    _info, fn = _solvers()["mech.joint.bolt_single_load_factor_vdi2230"]
    result = fn(
        {
            "mech.joint.bolt.cb": 200.0e6,
            "mech.joint.bolt.cp": 800.0e6,
            "mech.joint.bolt.fv": 1_000.0,
            "mech.joint.bolt.fa": 100_000.0,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["mech.joint.bolt.residual_clamp_load"] < 0.0


def test_vdi2230_nonpositive_stiffness_is_honest_indeterminate():
    _info, fn = _solvers()["mech.joint.bolt_single_load_factor_vdi2230"]
    result = fn(
        {
            "mech.joint.bolt.cb": 0.0,
            "mech.joint.bolt.cp": 800.0e6,
            "mech.joint.bolt.fv": 1_000.0,
            "mech.joint.bolt.fa": 500.0,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_vdi2230_negative_preload_is_honest_indeterminate():
    _info, fn = _solvers()["mech.joint.bolt_single_load_factor_vdi2230"]
    result = fn(
        {
            "mech.joint.bolt.cb": 200.0e6,
            "mech.joint.bolt.cp": 800.0e6,
            "mech.joint.bolt.fv": -1.0,
            "mech.joint.bolt.fa": 500.0,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# 8.2 -- elastic bolt-group shear + torsion
# ---------------------------------------------------------------------------


def test_bolt_group_shear_torsion_matches_hand_computed():
    """Memo sec. 8.2: 4-bolt rectangular pattern, a=0.05, b=0.03,
    r_i=0.058310, J=0.0136, critical bolt (0.05, 0.03), Vx=1000,
    Vy=0, T=50 -> F=(139.706, 183.824), |F|=230.94 N."""
    _info, fn = _solvers()["mech.joint.bolt_group_shear_torsion"]
    a, b = 0.05, 0.03
    r = math.hypot(a, b)
    j_polar = 4.0 * r * r
    result = fn(
        {
            "mech.joint.group.n": 4.0,
            "mech.joint.group.vx": 1000.0,
            "mech.joint.group.vy": 0.0,
            "mech.joint.group.torque": 50.0,
            "mech.joint.group.j_polar": j_polar,
            "mech.joint.group.xi": a,
            "mech.joint.group.yi": b,
        }
    )
    assert result.is_ok
    fx = 1000.0 / 4.0 - 50.0 * b / j_polar
    fy = 0.0 + 50.0 * a / j_polar
    expected = math.hypot(fx, fy)
    assert expected == pytest.approx(230.94, rel=1e-3)
    assert result.danger_ok.values["mech.joint.group.shear_resultant"] == pytest.approx(
        expected, rel=1e-9
    )


def test_bolt_group_shear_torsion_nonpositive_j_is_honest_indeterminate():
    _info, fn = _solvers()["mech.joint.bolt_group_shear_torsion"]
    result = fn(
        {
            "mech.joint.group.n": 4.0,
            "mech.joint.group.vx": 1000.0,
            "mech.joint.group.vy": 0.0,
            "mech.joint.group.torque": 50.0,
            "mech.joint.group.j_polar": 0.0,
            "mech.joint.group.xi": 0.05,
            "mech.joint.group.yi": 0.03,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# 8.3 -- elastic bolt-group tension from moment
# ---------------------------------------------------------------------------


def test_bolt_group_tension_from_moment_matches_hand_computed():
    """Memo sec. 8.3: 2-row 4-bolt pattern, y=+/-0.04, sum_y_sq=0.0064,
    M=800 -> F_t=5000 N at y_critical=0.04 (exact algebra)."""
    _info, fn = _solvers()["mech.joint.bolt_group_tension_from_moment"]
    result = fn(
        {
            "mech.joint.group.moment": 800.0,
            "mech.joint.group.sum_y_sq": 0.0064,
            "mech.joint.group.y_critical": 0.04,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "mech.joint.group.tension_critical"
    ] == pytest.approx(5000.0, rel=1e-9)


def test_bolt_group_tension_from_moment_nonpositive_sum_is_honest_indeterminate():
    _info, fn = _solvers()["mech.joint.bolt_group_tension_from_moment"]
    result = fn(
        {
            "mech.joint.group.moment": 800.0,
            "mech.joint.group.sum_y_sq": 0.0,
            "mech.joint.group.y_critical": 0.04,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
