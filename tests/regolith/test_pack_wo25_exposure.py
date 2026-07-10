from __future__ import annotations

"""WO-25 signal-integrity wave: regolith `Model` wrappers around the
`library.signal_integrity` directions (Hammerstad-Jensen microstrip,
Cohn exact stripline, exact-algebra termination sizing) that landed
complete, calibrated, cited `@solver` directions with no regolith
exposure before this wave (see `pack.models`'s "WO-25 signal-integrity
wave" section comment).

Each model here goes through `_ClosedFormEngineModel` -> `solve()` ->
`_engine_registry()`, so these tests exercise the SAME already-
calibrated formula `tests/unit/test_library_signal_integrity.py`
already proved -- reusing the exact hand-computed reference values
from those tests, not re-deriving new numbers, so a mismatch here
means the wrapper's plumbing is wrong, not the physics."""

import pytest
from regolith.harness.model import DischargeRequest
from regolith.harness.quantity import Interval
from regolith.harness.signature import ClaimSense

from feldspar.pack.models import (
    DEFAULT_AC_SHUNT_C_CLAIM_KIND,
    DEFAULT_AC_SHUNT_R_CLAIM_KIND,
    DEFAULT_MICROSTRIP_Z0_HI_CLAIM_KIND,
    DEFAULT_MICROSTRIP_Z0_LO_CLAIM_KIND,
    DEFAULT_SERIES_TERMINATION_CLAIM_KIND,
    DEFAULT_STRIPLINE_Z0_HI_CLAIM_KIND,
    DEFAULT_STRIPLINE_Z0_LO_CLAIM_KIND,
    DEFAULT_THEVENIN_TERMINATION_R1_CLAIM_KIND,
    DEFAULT_THEVENIN_TERMINATION_R2_CLAIM_KIND,
    AcShuntCapacitorModel,
    AcShuntResistorModel,
    MicrostripImpedanceModel,
    SeriesTerminationModel,
    StriplineImpedanceModel,
    TheveninTerminationR1Model,
    TheveninTerminationR2Model,
)

pytestmark = pytest.mark.regolith


def _pinned(value: float) -> Interval:
    return Interval(lo=value, hi=value)


# ---------------------------------------------------------------------------
# MicrostripImpedanceModel -- Hammerstad-Jensen
# ---------------------------------------------------------------------------


def test_microstrip_impedance_lo_matches_hand_computed() -> None:
    """w=1500um, h=794um, t=35um, er=4.2 -> Z0=50.24391978764052 ohm
    (test_library_signal_integrity.py's own pinned value)."""
    model = MicrostripImpedanceModel(
        claim_kind=DEFAULT_MICROSTRIP_Z0_LO_CLAIM_KIND, sense=ClaimSense.lower_bound()
    )
    request = DischargeRequest(
        claim_kind=DEFAULT_MICROSTRIP_Z0_LO_CLAIM_KIND,
        limit=0.0,
        inputs={
            "elec.si.microstrip.w": _pinned(1500e-6),
            "elec.si.microstrip.h": _pinned(794e-6),
            "elec.si.microstrip.t": _pinned(35e-6),
            "elec.si.microstrip.er": _pinned(4.2),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(50.24391978764052, rel=1e-6)
    assert prediction.in_domain


def test_microstrip_impedance_hi_matches_hand_computed() -> None:
    model = MicrostripImpedanceModel(
        claim_kind=DEFAULT_MICROSTRIP_Z0_HI_CLAIM_KIND, sense=ClaimSense.upper_bound()
    )
    request = DischargeRequest(
        claim_kind=DEFAULT_MICROSTRIP_Z0_HI_CLAIM_KIND,
        limit=1.0e9,
        inputs={
            "elec.si.microstrip.w": _pinned(1500e-6),
            "elec.si.microstrip.h": _pinned(794e-6),
            "elec.si.microstrip.t": _pinned(35e-6),
            "elec.si.microstrip.er": _pinned(4.2),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(50.24391978764052, rel=1e-6)
    assert prediction.in_domain


# ---------------------------------------------------------------------------
# StriplineImpedanceModel -- Cohn exact
# ---------------------------------------------------------------------------


def test_stripline_impedance_lo_matches_hand_computed() -> None:
    """w=382um, b=1mm, er=3.66 -> Z0=60.34290501664108 ohm
    (test_library_signal_integrity.py's own pinned value)."""
    model = StriplineImpedanceModel(
        claim_kind=DEFAULT_STRIPLINE_Z0_LO_CLAIM_KIND, sense=ClaimSense.lower_bound()
    )
    request = DischargeRequest(
        claim_kind=DEFAULT_STRIPLINE_Z0_LO_CLAIM_KIND,
        limit=0.0,
        inputs={
            "elec.si.stripline.w": _pinned(0.382e-3),
            "elec.si.stripline.b": _pinned(1e-3),
            "elec.si.stripline.er": _pinned(3.66),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(60.34290501664108, rel=1e-6)
    assert prediction.in_domain


def test_stripline_impedance_hi_matches_hand_computed() -> None:
    model = StriplineImpedanceModel(
        claim_kind=DEFAULT_STRIPLINE_Z0_HI_CLAIM_KIND, sense=ClaimSense.upper_bound()
    )
    request = DischargeRequest(
        claim_kind=DEFAULT_STRIPLINE_Z0_HI_CLAIM_KIND,
        limit=1.0e9,
        inputs={
            "elec.si.stripline.w": _pinned(0.382e-3),
            "elec.si.stripline.b": _pinned(1e-3),
            "elec.si.stripline.er": _pinned(3.66),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(60.34290501664108, rel=1e-6)
    assert prediction.in_domain


# ---------------------------------------------------------------------------
# Termination sizing models -- exact algebra
# ---------------------------------------------------------------------------


def test_series_termination_matches_hand_computed() -> None:
    model = SeriesTerminationModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_SERIES_TERMINATION_CLAIM_KIND,
        limit=0.0,
        inputs={
            "elec.si.series_termination.z0": _pinned(50.0),
            "elec.si.series_termination.ro": _pinned(15.0),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(35.0)
    assert prediction.in_domain


def test_thevenin_termination_r1_matches_hand_computed() -> None:
    model = TheveninTerminationR1Model()
    request = DischargeRequest(
        claim_kind=DEFAULT_THEVENIN_TERMINATION_R1_CLAIM_KIND,
        limit=0.0,
        inputs={
            "elec.si.thevenin_termination.z0": _pinned(50.0),
            "elec.si.thevenin_termination.vcc": _pinned(5.0),
            "elec.si.thevenin_termination.vbias": _pinned(1.5),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(50.0 * 5.0 / 1.5)
    assert prediction.in_domain


def test_thevenin_termination_r2_matches_hand_computed() -> None:
    model = TheveninTerminationR2Model()
    request = DischargeRequest(
        claim_kind=DEFAULT_THEVENIN_TERMINATION_R2_CLAIM_KIND,
        limit=0.0,
        inputs={
            "elec.si.thevenin_termination.z0": _pinned(50.0),
            "elec.si.thevenin_termination.vcc": _pinned(5.0),
            "elec.si.thevenin_termination.vbias": _pinned(1.5),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(50.0 * 5.0 / 3.5)
    assert prediction.in_domain


def test_ac_shunt_resistor_matches_z0() -> None:
    model = AcShuntResistorModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_AC_SHUNT_R_CLAIM_KIND,
        limit=0.0,
        inputs={"elec.si.ac_shunt.z0": _pinned(75.0)},
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(75.0)
    assert prediction.in_domain


def test_ac_shunt_capacitor_matches_hand_computed() -> None:
    model = AcShuntCapacitorModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_AC_SHUNT_C_CLAIM_KIND,
        limit=0.0,
        inputs={
            "elec.si.ac_shunt.rise_time": _pinned(1.0e-9),
            "elec.si.ac_shunt.r": _pinned(50.0),
        },
    )

    prediction = model.estimate(request).danger_ok

    assert prediction.value == pytest.approx(1.0e-9 / (4.0 * 50.0))
    assert prediction.in_domain
