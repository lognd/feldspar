from __future__ import annotations

"""WO-25 deliverable tests: known-answer/hand-computed and published-
table calibration unit tests for the registered `elec.si.*` signal-
integrity directions (`python/feldspar/library/signal_integrity.py`),
called THROUGH the `SolverRegistry`/`SolveFn` protocol (ports, domain
guards, marshalling exercised, not just the raw formula)."""

import math

import pytest

from feldspar.library.signal_integrity import register
from feldspar.solve import SolverRegistry


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    return registry


def _solvers() -> dict:
    registry = _registry()
    return {info.solver_id: (info, fn) for info, fn in registry}


# ---------------------------------------------------------------------------
# microstrip_z0 -- calibrated against Burkhardt, Gregg & Staniforth,
# "Calculation of PCB Track Impedance" (IPC Printed Circuit Expo 1999)
# Table 1: t=35um, h=794um, er=4.2, three widths, "Numerical Method"
# (field-solver, near-exact) column: 89.63 / 50.63 / 30.09 ohm.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "w_um,expected_numerical,rel_tol",
    [
        (450.0, 89.63, 0.015),
        (1500.0, 50.63, 0.01),
        (3300.0, 30.09, 0.01),
    ],
)
def test_microstrip_z0_matches_burkhardt_1999_table1(
    w_um, expected_numerical, rel_tol
):
    """Hammerstad-Jensen (Wadell 1991 eq. 2) reproduces Burkhardt 1999
    Table 1's field-solver column within ~1.5% at every tabulated
    width (well inside Wadell's own quoted 2% accuracy)."""
    _info, fn = _solvers()["elec.si.microstrip_z0"]
    result = fn(
        {
            "elec.si.microstrip.w": w_um * 1e-6,
            "elec.si.microstrip.h": 794e-6,
            "elec.si.microstrip.t": 35e-6,
            "elec.si.microstrip.er": 4.2,
        }
    )
    assert result.is_ok
    z0 = result.danger_ok.values["elec.si.microstrip.z0"]
    assert z0 == pytest.approx(expected_numerical, rel=rel_tol)


def test_microstrip_z0_hand_computed_exact_value():
    """Pinned exact value (this implementation's own formula, w=1500um
    h=794um t=35um er=4.2) -- a regression guard on the formula body
    itself, distinct from the published-table tolerance check above."""
    _info, fn = _solvers()["elec.si.microstrip_z0"]
    result = fn(
        {
            "elec.si.microstrip.w": 1500e-6,
            "elec.si.microstrip.h": 794e-6,
            "elec.si.microstrip.t": 35e-6,
            "elec.si.microstrip.er": 4.2,
        }
    )
    assert result.is_ok
    z0 = result.danger_ok.values["elec.si.microstrip.z0"]
    assert z0 == pytest.approx(50.24391978764052, rel=1e-9)


def test_microstrip_z0_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["elec.si.microstrip_z0"]
    result = fn(
        {
            "elec.si.microstrip.w": 0.0,
            "elec.si.microstrip.h": 794e-6,
            "elec.si.microstrip.t": 35e-6,
            "elec.si.microstrip.er": 4.2,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# stripline_z0 -- Cohn's exact closed form; verified by the k^2+k'^2=1
# identity and a pinned hand-computed value (exact-theory calibration
# tier, mirrors member_capacity.py's euler_critical_buckling_load).
# ---------------------------------------------------------------------------


def test_stripline_z0_hand_computed_exact_value():
    """w=382um, b=1mm, er=3.66 -- pinned against this implementation's
    own Cohn/Hilberg evaluation (hand-verified k=sech(pi*w/2b)=0.8435,
    branch k>1/sqrt(2))."""
    _info, fn = _solvers()["elec.si.stripline_z0"]
    result = fn(
        {
            "elec.si.stripline.w": 0.382e-3,
            "elec.si.stripline.b": 1e-3,
            "elec.si.stripline.er": 3.66,
        }
    )
    assert result.is_ok
    z0 = result.danger_ok.values["elec.si.stripline.z0"]
    assert z0 == pytest.approx(60.34290501664108, rel=1e-9)


def test_stripline_z0_monotonically_decreases_with_width():
    """Physical sanity (Burkhardt 1999 Figure 4's own shape): a wider
    centred track always has a LOWER stripline Z0 at fixed b/er."""
    _info, fn = _solvers()["elec.si.stripline_z0"]
    widths = (0.1e-3, 0.3e-3, 0.6e-3, 1.0e-3, 2.0e-3)
    z0s = []
    for w in widths:
        result = fn(
            {
                "elec.si.stripline.w": w,
                "elec.si.stripline.b": 3e-3,
                "elec.si.stripline.er": 4.2,
            }
        )
        assert result.is_ok
        z0s.append(result.danger_ok.values["elec.si.stripline.z0"])
    assert z0s == sorted(z0s, reverse=True)


def test_stripline_z0_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["elec.si.stripline_z0"]
    result = fn(
        {"elec.si.stripline.w": 1e-4, "elec.si.stripline.b": 0.0, "elec.si.stripline.er": 4.2}
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# series_termination -- exact algebra, Rs = Z0 - Ro.
# ---------------------------------------------------------------------------


def test_series_termination_matches_hand_computed():
    _info, fn = _solvers()["elec.si.series_termination"]
    result = fn(
        {"elec.si.series_termination.z0": 50.0, "elec.si.series_termination.ro": 15.0}
    )
    assert result.is_ok
    assert result.danger_ok.values["elec.si.series_termination.rs"] == pytest.approx(
        35.0
    )


def test_series_termination_ro_exceeds_z0_is_honest_indeterminate():
    _info, fn = _solvers()["elec.si.series_termination"]
    result = fn(
        {"elec.si.series_termination.z0": 50.0, "elec.si.series_termination.ro": 90.0}
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# thevenin_termination -- exact algebra, R1||R2=Z0, divider bias.
# ---------------------------------------------------------------------------


def test_thevenin_termination_matches_hand_computed_and_recombines_to_z0():
    """Vcc=5V, Vbias=1.5V (typical GTL-class rail), Z0=50 ohm: R1 =
    50*5/1.5 = 166.667 ohm, R2 = 50*5/3.5 = 71.429 ohm; the parallel
    combination of R1/R2 must recombine to exactly Z0 (Kirchhoff
    check, not just the two formulas independently)."""
    solvers = _solvers()
    inputs = {
        "elec.si.thevenin_termination.z0": 50.0,
        "elec.si.thevenin_termination.vcc": 5.0,
        "elec.si.thevenin_termination.vbias": 1.5,
    }
    r1 = solvers["elec.si.thevenin_termination_r1"][1](inputs).danger_ok.values[
        "elec.si.thevenin_termination.r1"
    ]
    r2 = solvers["elec.si.thevenin_termination_r2"][1](inputs).danger_ok.values[
        "elec.si.thevenin_termination.r2"
    ]
    assert r1 == pytest.approx(50.0 * 5.0 / 1.5)
    assert r2 == pytest.approx(50.0 * 5.0 / 3.5)
    assert (r1 * r2) / (r1 + r2) == pytest.approx(50.0, rel=1e-9)


def test_thevenin_termination_vbias_outside_rail_is_honest_indeterminate():
    solvers = _solvers()
    bad_inputs = {
        "elec.si.thevenin_termination.z0": 50.0,
        "elec.si.thevenin_termination.vcc": 5.0,
        "elec.si.thevenin_termination.vbias": 6.0,
    }
    result = solvers["elec.si.thevenin_termination_r1"][1](bad_inputs)
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# ac_shunt_sizing -- R=Z0 exact, C=tr/(4R) named heuristic.
# ---------------------------------------------------------------------------


def test_ac_shunt_sizing_r_matches_z0():
    _info, fn = _solvers()["elec.si.ac_shunt_sizing_r"]
    result = fn({"elec.si.ac_shunt.z0": 75.0})
    assert result.is_ok
    assert result.danger_ok.values["elec.si.ac_shunt.r"] == pytest.approx(75.0)


def test_ac_shunt_sizing_c_matches_hand_computed():
    _info, fn = _solvers()["elec.si.ac_shunt_sizing_c"]
    result = fn({"elec.si.ac_shunt.rise_time": 1.0e-9, "elec.si.ac_shunt.r": 50.0})
    assert result.is_ok
    expected = 1.0e-9 / (4.0 * 50.0)
    assert result.danger_ok.values["elec.si.ac_shunt.c"] == pytest.approx(expected)


def test_ac_shunt_sizing_c_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["elec.si.ac_shunt_sizing_c"]
    result = fn({"elec.si.ac_shunt.rise_time": 0.0, "elec.si.ac_shunt.r": 50.0})
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# Registration surface.
# ---------------------------------------------------------------------------


def test_register_registers_seven_directions():
    registry = _registry()
    ids = {info.solver_id for info, _fn in registry}
    assert ids == {
        "elec.si.microstrip_z0",
        "elec.si.stripline_z0",
        "elec.si.series_termination",
        "elec.si.thevenin_termination_r1",
        "elec.si.thevenin_termination_r2",
        "elec.si.ac_shunt_sizing_r",
        "elec.si.ac_shunt_sizing_c",
    }
