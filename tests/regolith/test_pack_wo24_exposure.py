from __future__ import annotations

"""Cycle-33 pack-exposure wave: regolith `Model` wrappers around the
WO-24 library-depth directions (`member_capacity.py`/`bolted_joints.py`/
`weld_groups.py`/`bearing_life.py`) that landed complete, calibrated,
cited `@solver` directions with no regolith exposure before this wave
(see `pack.models`'s "cycle-33 pack-exposure wave" section comment).

Each model here goes through `_ClosedFormEngineModel` -> `solve()` ->
`_engine_registry()`, so these tests exercise the SAME already-
calibrated formula the corresponding `tests/unit/test_library_*.py`
case already proved -- reusing the exact hand-computed reference
values from those tests/the WO-24 close-out ledger (docs/workflow/
work-orders/WO-24-library-depth.md), not re-deriving new numbers, so a
mismatch here means the wrapper's plumbing is wrong, not the physics."""

import pytest
from regolith.harness.model import DischargeRequest
from regolith.harness.quantity import Interval

from feldspar.pack.models import (
    DEFAULT_BEARING_RATING_LIFE_CLAIM_KIND,
    DEFAULT_BOLT_LOAD_FACTOR_CLAIM_KIND,
    DEFAULT_EULER_BUCKLING_LOAD_CLAIM_KIND,
    DEFAULT_MEMBER_AXIAL_CAPACITY_CLAIM_KIND,
    DEFAULT_MEMBER_FLEXURAL_CAPACITY_CLAIM_KIND,
    DEFAULT_WELD_UTILIZATION_CLAIM_KIND,
    BearingRatingLifeModel,
    BoltLoadFactorModel,
    EulerBucklingLoadModel,
    MemberAxialCapacityModel,
    MemberFlexuralCapacityModel,
    WeldUtilizationModel,
)

pytestmark = pytest.mark.regolith


def _pinned(value: float) -> Interval:
    return Interval(lo=value, hi=value)


# ---------------------------------------------------------------------------
# MemberFlexuralCapacityModel -- AISC 360-16 F2.1
# ---------------------------------------------------------------------------


def test_member_flexural_capacity_matches_hand_computed() -> None:
    """Fy=345e6 Pa, Zx=1.639e-3 m^3 -> phi_b*Fy*Zx = 508,909.5 N*m
    (WO-24 close-out dispatch #1's own hand-computed case)."""
    model = MemberFlexuralCapacityModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_MEMBER_FLEXURAL_CAPACITY_CLAIM_KIND,
        limit=0.0,
        inputs={
            "mech.member.flexure.fy": _pinned(345e6),
            "mech.member.flexure.zx": _pinned(1.639e-3),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(508_909.5, rel=1e-6)
    assert prediction.in_domain


# ---------------------------------------------------------------------------
# MemberAxialCapacityModel -- AISC 360-16 E3
# ---------------------------------------------------------------------------


def test_member_axial_capacity_inelastic_branch_matches_hand_computed() -> None:
    """Fy=345e6, Ag=0.01, E=200e9, KL/r=80 (inelastic eq. E3-2 branch)
    -> phi_c*Pn ~ 1.943e6 N (WO-24 close-out dispatch #1's case)."""
    model = MemberAxialCapacityModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_MEMBER_AXIAL_CAPACITY_CLAIM_KIND,
        limit=0.0,
        inputs={
            "mech.member.axial.fy": _pinned(345e6),
            "mech.member.axial.ag": _pinned(0.01),
            "mech.member.axial.e": _pinned(200e9),
            "mech.member.axial.kl_over_r": _pinned(80.0),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(1.943e6, rel=2e-3)
    assert prediction.in_domain


# ---------------------------------------------------------------------------
# EulerBucklingLoadModel
# ---------------------------------------------------------------------------


def test_euler_buckling_load_matches_hand_computed() -> None:
    """E=200e9, I=8.0e-6, K=1.0, L=3.0 -> Pcr ~ 1,754,600 N (WO-24
    close-out dispatch #3's own case)."""
    model = EulerBucklingLoadModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_EULER_BUCKLING_LOAD_CLAIM_KIND,
        limit=0.0,
        inputs={
            "mech.member.euler.e": _pinned(200e9),
            "mech.member.euler.i": _pinned(8.0e-6),
            "mech.member.euler.k": _pinned(1.0),
            "mech.member.euler.length": _pinned(3.0),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(1_754_600, rel=1e-3)
    assert prediction.in_domain


# ---------------------------------------------------------------------------
# BoltLoadFactorModel -- VDI 2230
# ---------------------------------------------------------------------------


def test_bolt_load_factor_matches_hand_computed() -> None:
    """cb=200e6, cp=800e6, fv=10000, fa=5000 -> phi=0.20 (WO-24
    close-out dispatch #3's own case)."""
    model = BoltLoadFactorModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_BOLT_LOAD_FACTOR_CLAIM_KIND,
        limit=0.0,
        inputs={
            "mech.joint.bolt.cb": _pinned(200e6),
            "mech.joint.bolt.cp": _pinned(800e6),
            "mech.joint.bolt.fv": _pinned(10000.0),
            "mech.joint.bolt.fa": _pinned(5000.0),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(0.20, rel=1e-6)
    assert prediction.in_domain


# ---------------------------------------------------------------------------
# WeldUtilizationModel
# ---------------------------------------------------------------------------


def test_weld_utilization_matches_hand_computed() -> None:
    """f_inplane=4893.16 N/m, f_bending=15,000.0 N/m, leg=0.008 m,
    allowable=145e6 Pa -> ratio=0.01924 (WO-24 close-out dispatch #4's
    own case)."""
    model = WeldUtilizationModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_WELD_UTILIZATION_CLAIM_KIND,
        limit=1.0,
        inputs={
            "mech.weld.group.inplane_line_force": _pinned(4893.16),
            "mech.weld.group.bending_line_force": _pinned(15_000.0),
            "mech.weld.group.leg_size": _pinned(0.008),
            "mech.weld.group.allowable_stress": _pinned(145e6),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(0.01924, rel=2e-3)
    assert prediction.in_domain


# ---------------------------------------------------------------------------
# BearingRatingLifeModel -- ISO 281 L10h
# ---------------------------------------------------------------------------


def test_bearing_rating_life_matches_hand_computed() -> None:
    """L10=343.0 (millions of rev), n=1,800 rpm -> L10h=3,175.93 hours
    (WO-24 close-out dispatch #4's own case)."""
    model = BearingRatingLifeModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_BEARING_RATING_LIFE_CLAIM_KIND,
        limit=0.0,
        inputs={
            "mech.bearing.l10": _pinned(343.0),
            "mech.bearing.speed_rpm": _pinned(1800.0),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(3175.93, rel=1e-4)
    assert prediction.in_domain
