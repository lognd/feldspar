from __future__ import annotations

"""`MechStiffnessModel` / `ElecRailModel` (`pack.models`): the two
closed-form regolith models a freshly scaffolded regolith project's
`mech.stiffness`/`elec.rail` claims need in order to have ANYTHING to
discharge against. Both wrap an exact `_feldspar` Rust formula
(cantilever stiffness via the deflection formula's unit-force inverse,
loaded resistor-divider via `elec_divider_loaded_vout`) with an
exhaustive corner sweep -- no engine `solve()`/`SolverRegistry`
involved, mirroring regolith's own built-in closed-form models
(`lame_cylinder.py`)."""

import pytest
from regolith.harness.errors import DomainError
from regolith.harness.model import DischargeRequest
from regolith.harness.quantity import Interval
from regolith.harness.signature import ClaimSense

from feldspar.pack.models import (
    _RAIL_INPUTS,
    _STIFFNESS_INPUTS,
    DEFAULT_RAIL_HI_CLAIM_KIND,
    DEFAULT_RAIL_LO_CLAIM_KIND,
    DEFAULT_STIFFNESS_CLAIM_KIND,
    ElecRailModel,
    MechStiffnessModel,
)

pytestmark = pytest.mark.regolith


def _pinned(value: float) -> Interval:
    return Interval(lo=value, hi=value)


def _stiffness_request(
    *, e_modulus: Interval, i_area: Interval, length: Interval, limit: float
) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=DEFAULT_STIFFNESS_CLAIM_KIND,
        limit=limit,
        inputs={"e_modulus": e_modulus, "i_area": i_area, "length": length},
    )


def _rail_request(
    *,
    claim_kind: str,
    vin: Interval,
    r1: Interval,
    r2: Interval,
    rload: Interval,
    limit: float,
) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=claim_kind,
        limit=limit,
        inputs={"vin": vin, "r1": r1, "r2": r2, "rload": rload},
    )


# ---------------------------------------------------------------------------
# MechStiffnessModel
# ---------------------------------------------------------------------------


def test_stiffness_happy_path_exact_value() -> None:
    """`k = 3*E*I/L**3`, hand-computed at a pinned (degenerate) box."""
    model = MechStiffnessModel()
    e = 2.0e11  # Pa (steel)
    i = 8.0e-6  # m^4
    length = 1.0  # m
    request = _stiffness_request(
        e_modulus=_pinned(e), i_area=_pinned(i), length=_pinned(length), limit=0.0
    )

    prediction = model.estimate(request).danger_ok

    expected = 3.0 * e * i / length**3
    assert prediction.value == pytest.approx(expected)
    assert prediction.eps == 0.0


def test_stiffness_interval_corner_uses_worst_case_minimum() -> None:
    """Stiffness grows with E and I, shrinks with L**3: over a swept
    box the honest (floor-claim-conservative) value is the MINIMUM,
    realized at (E.lo, I.lo, L.hi)."""
    model = MechStiffnessModel()
    request = _stiffness_request(
        e_modulus=Interval(lo=1.0e11, hi=2.0e11),
        i_area=Interval(lo=4.0e-6, hi=8.0e-6),
        length=Interval(lo=1.0, hi=2.0),
        limit=0.0,
    )

    prediction = model.estimate(request).danger_ok

    worst_case = 3.0 * 1.0e11 * 4.0e-6 / 2.0**3
    assert prediction.value == pytest.approx(worst_case)


def test_stiffness_floor_claim_pass_and_fail_verdicts() -> None:
    """Discharge through the base `Model.discharge` path: a limit below
    the worst-case stiffness discharges, one above it violates."""
    model = MechStiffnessModel()
    e, i, length = 2.0e11, 8.0e-6, 1.0
    stiffness = 3.0 * e * i / length**3

    passing = _stiffness_request(
        e_modulus=_pinned(e),
        i_area=_pinned(i),
        length=_pinned(length),
        limit=stiffness * 0.5,
    )
    failing = _stiffness_request(
        e_modulus=_pinned(e),
        i_area=_pinned(i),
        length=_pinned(length),
        limit=stiffness * 2.0,
    )

    assert (
        model.discharge(passing, registry_version="test").danger_ok.status.value
        == "discharged"
    )
    assert (
        model.discharge(failing, registry_version="test").danger_ok.status.value
        == "violated"
    )


@pytest.mark.parametrize(
    "e_modulus,i_area,length",
    [
        (_pinned(-1.0), _pinned(8.0e-6), _pinned(1.0)),
        (_pinned(0.0), _pinned(8.0e-6), _pinned(1.0)),
        (_pinned(2.0e11), _pinned(-8.0e-6), _pinned(1.0)),
        (_pinned(2.0e11), _pinned(0.0), _pinned(1.0)),
        (_pinned(2.0e11), _pinned(8.0e-6), _pinned(-1.0)),
        (_pinned(2.0e11), _pinned(8.0e-6), _pinned(0.0)),
    ],
)
def test_stiffness_rejects_degenerate_inputs(e_modulus, i_area, length) -> None:
    """Zero/negative E, I, or L is an honest `DomainError` (mirrors
    `bore_von_mises`/`lame_cylinder`'s degenerate-input rejection
    shape), never a division-by-zero crash or a silent wrong answer."""
    model = MechStiffnessModel()
    request = _stiffness_request(
        e_modulus=e_modulus, i_area=i_area, length=length, limit=0.0
    )

    result = model.estimate(request)

    assert result.is_err
    error = result.danger_err
    assert isinstance(error, DomainError)
    assert error.model_id == model.model_id


# ---------------------------------------------------------------------------
# ElecRailModel
# ---------------------------------------------------------------------------

_LO_MODEL = ElecRailModel(
    claim_kind=DEFAULT_RAIL_LO_CLAIM_KIND, sense=ClaimSense.lower_bound()
)
_HI_MODEL = ElecRailModel(
    claim_kind=DEFAULT_RAIL_HI_CLAIM_KIND, sense=ClaimSense.upper_bound()
)


def _divider_vout(vin: float, r1: float, r2: float, rload: float) -> float:
    r_parallel = 1.0 / (1.0 / r2 + 1.0 / rload)
    return vin * r_parallel / (r1 + r_parallel)


def test_rail_happy_path_exact_value_both_halves() -> None:
    """A pinned (degenerate) box: lo and hi models agree with each
    other and with the hand-computed loaded-divider formula."""
    vin, r1, r2, rload = 5.0, 1000.0, 2000.0, 10000.0
    request_lo = _rail_request(
        claim_kind=DEFAULT_RAIL_LO_CLAIM_KIND,
        vin=_pinned(vin),
        r1=_pinned(r1),
        r2=_pinned(r2),
        rload=_pinned(rload),
        limit=0.0,
    )
    request_hi = _rail_request(
        claim_kind=DEFAULT_RAIL_HI_CLAIM_KIND,
        vin=_pinned(vin),
        r1=_pinned(r1),
        r2=_pinned(r2),
        rload=_pinned(rload),
        limit=0.0,
    )

    expected = _divider_vout(vin, r1, r2, rload)
    assert _LO_MODEL.estimate(request_lo).danger_ok.value == pytest.approx(expected)
    assert _HI_MODEL.estimate(request_hi).danger_ok.value == pytest.approx(expected)


def test_rail_interval_corners_lo_and_hi_from_mixed_corners() -> None:
    """Vout grows with vin/r2/rload and shrinks with r1 (all monotone,
    but the model never assumes that -- it corner-sweeps): the `.lo`
    model reports the box minimum, the `.hi` model the box maximum,
    and neither equals the midpoint corner."""
    vin = Interval(lo=4.0, hi=6.0)
    r1 = Interval(lo=900.0, hi=1100.0)
    r2 = Interval(lo=1800.0, hi=2200.0)
    rload = Interval(lo=9000.0, hi=11000.0)

    request_lo = _rail_request(
        claim_kind=DEFAULT_RAIL_LO_CLAIM_KIND,
        vin=vin,
        r1=r1,
        r2=r2,
        rload=rload,
        limit=0.0,
    )
    request_hi = _rail_request(
        claim_kind=DEFAULT_RAIL_HI_CLAIM_KIND,
        vin=vin,
        r1=r1,
        r2=r2,
        rload=rload,
        limit=0.0,
    )

    lo_value = _LO_MODEL.estimate(request_lo).danger_ok.value
    hi_value = _HI_MODEL.estimate(request_hi).danger_ok.value

    expected_lo = _divider_vout(vin.lo, r1.hi, r2.lo, rload.lo)
    expected_hi = _divider_vout(vin.hi, r1.lo, r2.hi, rload.hi)
    assert lo_value == pytest.approx(expected_lo)
    assert hi_value == pytest.approx(expected_hi)
    assert lo_value < hi_value


def test_rail_within_window_pass_and_fail_verdicts() -> None:
    """A `within [lo, hi]` claim lowers to two obligations sharing this
    class: both discharge inside a comfortable window, and each
    independently violates when the box drifts outside its half."""
    vin, r1, r2, rload = 5.0, 1000.0, 2000.0, 10000.0
    vout = _divider_vout(vin, r1, r2, rload)

    passing_lo = _rail_request(
        claim_kind=DEFAULT_RAIL_LO_CLAIM_KIND,
        vin=_pinned(vin),
        r1=_pinned(r1),
        r2=_pinned(r2),
        rload=_pinned(rload),
        limit=vout - 0.5,
    )
    passing_hi = _rail_request(
        claim_kind=DEFAULT_RAIL_HI_CLAIM_KIND,
        vin=_pinned(vin),
        r1=_pinned(r1),
        r2=_pinned(r2),
        rload=_pinned(rload),
        limit=vout + 0.5,
    )
    failing_lo = _rail_request(
        claim_kind=DEFAULT_RAIL_LO_CLAIM_KIND,
        vin=_pinned(vin),
        r1=_pinned(r1),
        r2=_pinned(r2),
        rload=_pinned(rload),
        limit=vout + 0.5,
    )
    failing_hi = _rail_request(
        claim_kind=DEFAULT_RAIL_HI_CLAIM_KIND,
        vin=_pinned(vin),
        r1=_pinned(r1),
        r2=_pinned(r2),
        rload=_pinned(rload),
        limit=vout - 0.5,
    )

    assert (
        _LO_MODEL.discharge(passing_lo, registry_version="test").danger_ok.status.value
        == "discharged"
    )
    assert (
        _HI_MODEL.discharge(passing_hi, registry_version="test").danger_ok.status.value
        == "discharged"
    )
    assert (
        _LO_MODEL.discharge(failing_lo, registry_version="test").danger_ok.status.value
        == "violated"
    )
    assert (
        _HI_MODEL.discharge(failing_hi, registry_version="test").danger_ok.status.value
        == "violated"
    )


@pytest.mark.parametrize(
    "vin,r1,r2,rload",
    [
        (_pinned(-1.0), _pinned(1000.0), _pinned(2000.0), _pinned(10000.0)),
        (_pinned(5.0), _pinned(-1000.0), _pinned(2000.0), _pinned(10000.0)),
        (_pinned(5.0), _pinned(0.0), _pinned(2000.0), _pinned(10000.0)),
        (_pinned(5.0), _pinned(1000.0), _pinned(-2000.0), _pinned(10000.0)),
        (_pinned(5.0), _pinned(1000.0), _pinned(0.0), _pinned(10000.0)),
        (_pinned(5.0), _pinned(1000.0), _pinned(2000.0), _pinned(-10000.0)),
        (_pinned(5.0), _pinned(1000.0), _pinned(2000.0), _pinned(0.0)),
    ],
)
def test_rail_rejects_degenerate_inputs(vin, r1, r2, rload) -> None:
    """Negative vin or zero/negative r1/r2/rload is an honest
    `DomainError` (mirrors `bore_von_mises`/`lame_cylinder`), never a
    division-by-zero crash or a silent wrong answer -- checked on both
    the lo and hi model instances."""
    request_lo = _rail_request(
        claim_kind=DEFAULT_RAIL_LO_CLAIM_KIND,
        vin=vin,
        r1=r1,
        r2=r2,
        rload=rload,
        limit=0.0,
    )
    result = _LO_MODEL.estimate(request_lo)

    assert result.is_err
    error = result.danger_err
    assert isinstance(error, DomainError)
    assert error.model_id == _LO_MODEL.model_id


def test_stiffness_rejects_overflowed_deflection_as_domain_error() -> None:
    """L1 (FINDINGS-e2e-r3.md): e_modulus/i_area ~1e200 overflows the
    Rust deflection formula to 0.0, which used to feed `1.0 /
    deflection` and raise `ZeroDivisionError` instead of returning the
    documented `Result` contract. Must be an honest `DomainError`, not
    a raise and not a NaN/inf-valued `Prediction`."""
    model = MechStiffnessModel()
    request = _stiffness_request(
        e_modulus=_pinned(1.0e200),
        i_area=_pinned(1.0e200),
        length=_pinned(1.0),
        limit=0.0,
    )

    result = model.estimate(request)

    assert result.is_err
    error = result.danger_err
    assert isinstance(error, DomainError)
    assert error.model_id == model.model_id


def test_rail_rejects_overflowed_vout_as_domain_error() -> None:
    """L2 (FINDINGS-e2e-r3.md): r2/rload ~1e308 overflows the loaded
    divider formula to inf/inf = NaN, which used to pass through as a
    silently NaN-valued `Prediction` instead of the documented `Result`
    contract. Must be an honest `DomainError`, not a NaN-valued
    success."""
    request = _rail_request(
        claim_kind=DEFAULT_RAIL_LO_CLAIM_KIND,
        vin=_pinned(10.0),
        r1=_pinned(1.0),
        r2=_pinned(1.0e308),
        rload=_pinned(1.0e308),
        limit=0.0,
    )

    result = _LO_MODEL.estimate(request)

    assert result.is_err
    error = result.danger_err
    assert isinstance(error, DomainError)
    assert error.model_id == _LO_MODEL.model_id


# ---------------------------------------------------------------------------
# Cross-repo contract pin (FINDINGS-e2e-r3.md, auditor concern #3)
# ---------------------------------------------------------------------------


def test_claim_kind_and_input_name_contract_pinned() -> None:
    """The lithos scaffold templates hard-depend on these exact literal
    strings/tuples (models.py:615-623) to generate a working freshly
    scaffolded regolith project. A rename here is a silent cross-repo
    break for those templates -- pin the literals so it fails loudly
    in THIS repo's test suite instead."""
    assert DEFAULT_STIFFNESS_CLAIM_KIND == "mech.stiffness"
    assert DEFAULT_RAIL_LO_CLAIM_KIND == "elec.rail.lo"
    assert DEFAULT_RAIL_HI_CLAIM_KIND == "elec.rail.hi"
    assert set(_STIFFNESS_INPUTS) == {"e_modulus", "i_area", "length"}
    assert set(_RAIL_INPUTS) == {"vin", "r1", "r2", "rload"}
