from __future__ import annotations

"""WO-24 deliverable 7 (leadscrew half) tests: known-answer/hand-
computed unit tests for the registered `mech.drive.leadscrew`
directions (`python/feldspar/library/leadscrew.py`), called THROUGH
the `SolverRegistry`/`SolveFn` protocol. Every case is EXACT ALGEBRA
(Shigley 11e ch. 8 sec. 8-2, square-thread power screw), hand-computed
directly in this file via `math.pi`/`math.sqrt`-free arithmetic (no
published table needed for an exact closed form -- same tier as
`test_library_member_capacity.py`'s Euler buckling case), docs/
benchmarks-memo.md sec. 15."""

import math

import pytest

from feldspar.library.leadscrew import register
from feldspar.solve import SolverRegistry

# Shared worked case, docs/benchmarks-memo.md sec. 15: F=1000 N,
# dm=10 mm, lead=2 mm (single-thread, p=2mm), f=0.15.
_F = 1000.0
_DM = 0.010
_LEAD = 0.002
_MU = 0.15


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    return registry


def _solvers() -> dict:
    registry = _registry()
    return {info.solver_id: (info, fn) for info, fn in registry}


def _hand_tr() -> float:
    return (_F * _DM / 2.0) * (
        (_LEAD + math.pi * _MU * _DM) / (math.pi * _DM - _MU * _LEAD)
    )


def _hand_tl() -> float:
    return (_F * _DM / 2.0) * (
        (math.pi * _MU * _DM - _LEAD) / (math.pi * _DM + _MU * _LEAD)
    )


def test_torque_raise_matches_hand_computed():
    """F=1000 N, dm=0.010 m, lead=0.002 m, f=0.15 ->
    TR = (F*dm/2)*((lead+pi*f*dm)/(pi*dm-f*lead)) ~ 1.07862 N*m."""
    _info, fn = _solvers()["mech.drive.leadscrew_torque_raise"]
    expected = _hand_tr()
    assert expected == pytest.approx(1.07862, rel=1e-4)
    result = fn(
        {
            "mech.drive.leadscrew.force": _F,
            "mech.drive.leadscrew.dm": _DM,
            "mech.drive.leadscrew.lead": _LEAD,
            "mech.drive.leadscrew.friction": _MU,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "mech.drive.leadscrew.torque_raise"
    ] == pytest.approx(expected, rel=1e-9)


def test_torque_raise_degenerate_geometry_is_honest_indeterminate():
    """pi*dm <= f*l -- a non-physical geometry (friction/lead
    swamping the mean circumference), not a fabricated division."""
    _info, fn = _solvers()["mech.drive.leadscrew_torque_raise"]
    result = fn(
        {
            "mech.drive.leadscrew.force": _F,
            "mech.drive.leadscrew.dm": 0.001,
            "mech.drive.leadscrew.lead": 0.09,
            "mech.drive.leadscrew.friction": 0.5,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_torque_raise_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["mech.drive.leadscrew_torque_raise"]
    result = fn(
        {
            "mech.drive.leadscrew.force": 0.0,
            "mech.drive.leadscrew.dm": _DM,
            "mech.drive.leadscrew.lead": _LEAD,
            "mech.drive.leadscrew.friction": _MU,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_torque_lower_matches_hand_computed():
    """Same case -> TL = (F*dm/2)*((pi*f*dm-lead)/(pi*dm+f*lead))
    ~ 0.42768 N*m (positive: this screw IS self-locking)."""
    _info, fn = _solvers()["mech.drive.leadscrew_torque_lower"]
    expected = _hand_tl()
    assert expected == pytest.approx(0.42761, rel=1e-4)
    result = fn(
        {
            "mech.drive.leadscrew.force": _F,
            "mech.drive.leadscrew.dm": _DM,
            "mech.drive.leadscrew.lead": _LEAD,
            "mech.drive.leadscrew.friction": _MU,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "mech.drive.leadscrew.torque_lower"
    ] == pytest.approx(expected, rel=1e-9)


def test_torque_lower_can_be_negative_not_self_locking():
    """Low friction (f=0.02) with the same dm/lead -> TL negative
    (the screw back-drives without applied torque): a real physical
    outcome, not an error."""
    _info, fn = _solvers()["mech.drive.leadscrew_torque_lower"]
    result = fn(
        {
            "mech.drive.leadscrew.force": _F,
            "mech.drive.leadscrew.dm": _DM,
            "mech.drive.leadscrew.lead": _LEAD,
            "mech.drive.leadscrew.friction": 0.02,
        }
    )
    assert result.is_ok
    tl = result.danger_ok.values["mech.drive.leadscrew.torque_lower"]
    assert tl < 0.0


def test_efficiency_matches_hand_computed():
    """e = F*lead/(2*pi*TR) ~ 0.29508 for the same worked case."""
    _info, fn = _solvers()["mech.drive.leadscrew_efficiency"]
    tr = _hand_tr()
    expected = (_F * _LEAD) / (2.0 * math.pi * tr)
    assert expected == pytest.approx(0.29511, rel=1e-4)
    result = fn(
        {
            "mech.drive.leadscrew.force": _F,
            "mech.drive.leadscrew.lead": _LEAD,
            "mech.drive.leadscrew.torque_raise": tr,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["mech.drive.leadscrew.efficiency"] == pytest.approx(
        expected, rel=1e-9
    )


def test_efficiency_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["mech.drive.leadscrew_efficiency"]
    result = fn(
        {
            "mech.drive.leadscrew.force": _F,
            "mech.drive.leadscrew.lead": _LEAD,
            "mech.drive.leadscrew.torque_raise": 0.0,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_self_locking_margin_matches_hand_computed():
    """f - tan(lambda) = 0.15 - lead/(pi*dm) ~ 0.08634 (positive: this
    screw is self-locking, consistent with TL>0 above)."""
    _info, fn = _solvers()["mech.drive.leadscrew_self_locking_margin"]
    tan_lambda = _LEAD / (math.pi * _DM)
    expected = _MU - tan_lambda
    assert expected == pytest.approx(0.08634, rel=1e-3)
    result = fn(
        {
            "mech.drive.leadscrew.dm": _DM,
            "mech.drive.leadscrew.lead": _LEAD,
            "mech.drive.leadscrew.friction": _MU,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "mech.drive.leadscrew.self_locking_margin"
    ] == pytest.approx(expected, rel=1e-9)


def test_self_locking_margin_negative_when_low_friction():
    """f=0.02 with the same dm/lead -> margin negative (NOT
    self-locking), consistent with the negative TL case above."""
    _info, fn = _solvers()["mech.drive.leadscrew_self_locking_margin"]
    result = fn(
        {
            "mech.drive.leadscrew.dm": _DM,
            "mech.drive.leadscrew.lead": _LEAD,
            "mech.drive.leadscrew.friction": 0.02,
        }
    )
    assert result.is_ok
    margin = result.danger_ok.values["mech.drive.leadscrew.self_locking_margin"]
    assert margin < 0.0


def test_collar_torque_matches_hand_computed():
    """F=1000 N, fc=0.15, dc=0.020 m -> Tc = F*fc*dc/2 = 1.5 N*m
    (exact)."""
    _info, fn = _solvers()["mech.drive.leadscrew_collar_torque"]
    result = fn(
        {
            "mech.drive.leadscrew.force": 1000.0,
            "mech.drive.leadscrew.collar_friction": 0.15,
            "mech.drive.leadscrew.collar_dc": 0.020,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "mech.drive.leadscrew.collar_torque"
    ] == pytest.approx(1.5, rel=1e-9)


def test_collar_torque_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["mech.drive.leadscrew_collar_torque"]
    result = fn(
        {
            "mech.drive.leadscrew.force": 0.0,
            "mech.drive.leadscrew.collar_friction": 0.15,
            "mech.drive.leadscrew.collar_dc": 0.020,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
