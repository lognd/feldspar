from __future__ import annotations

"""WO-111 tests: circular flat-plate uniform-load directions
(`python/feldspar/library/plate.py`), called THROUGH the
`SolverRegistry`/`SolveFn` protocol. Calibration reproduces Roark's
Formulas for Stress and Strain 8th ed. Table 11.2 cases 10a (simply-
supported) / 10b (clamped) closed forms (docs/benchmarks-memo.md sec.
17) with a hand-computed reference case, plus the published structural
cross-check that a clamped plate is stiffer and lower-stressed than the
same simply-supported plate."""

import pytest

from feldspar.library.plate import register
from feldspar.solve import SolverRegistry

# Reference case: q=10 kPa, a=0.1 m, t=5 mm, steel (E=200 GPa, nu=0.3).
_CASE = {
    "mech.plate.circular.q": 1.0e4,
    "mech.plate.circular.a": 0.1,
    "mech.plate.circular.t": 5.0e-3,
    "mech.plate.circular.e": 200.0e9,
    "mech.plate.circular.nu": 0.3,
}
# D = E t^3 / (12(1-nu^2)) = 200e9*1.25e-7/10.92 = 2289.3773 N*m.
_D = 200.0e9 * (5.0e-3) ** 3 / (12.0 * (1.0 - 0.3**2))


def _solvers() -> dict:
    registry = SolverRegistry()
    register(registry)
    return {info.solver_id: (info, fn) for info, fn in registry}


def test_ss_max_stress_matches_hand_computed():
    """sigma = 3*q*a^2*(3+nu)/(8*t^2) = 3*1e4*0.01*3.3/(8*2.5e-5) = 4.95 MPa."""
    _i, fn = _solvers()["mech.plate.plate_circular_uniform_ss_max_stress"]
    v = fn(dict(_CASE)).danger_ok.values["mech.plate.circular.ss_max_stress"]
    assert v == pytest.approx(4.95e6, rel=1e-9)


# frob:tests python/feldspar/mech/plate.py::plate_circular_uniform_clamped_max_stress kind="unit"
def test_clamped_max_stress_matches_hand_computed():
    """sigma = 3*q*a^2/(4*t^2) = 3*1e4*0.01/(4*2.5e-5) = 3.0 MPa."""
    _i, fn = _solvers()["mech.plate.plate_circular_uniform_clamped_max_stress"]
    v = fn(dict(_CASE)).danger_ok.values["mech.plate.circular.clamped_max_stress"]
    assert v == pytest.approx(3.0e6, rel=1e-9)


# frob:tests python/feldspar/mech/plate.py::plate_circular_uniform_ss_max_deflection kind="unit"
def test_ss_max_deflection_matches_hand_computed():
    """y = q*a^4*(5+nu)/(64*D*(1+nu))."""
    _i, fn = _solvers()["mech.plate.plate_circular_uniform_ss_max_deflection"]
    v = fn(dict(_CASE)).danger_ok.values["mech.plate.circular.ss_max_deflection"]
    expected = 1.0e4 * 0.1**4 * (5.0 + 0.3) / (64.0 * _D * (1.0 + 0.3))
    assert v == pytest.approx(expected, rel=1e-9)


# frob:tests python/feldspar/mech/plate.py::plate_circular_uniform_clamped_max_deflection kind="unit"
def test_clamped_max_deflection_matches_hand_computed():
    """y = q*a^4/(64*D)."""
    _i, fn = _solvers()["mech.plate.plate_circular_uniform_clamped_max_deflection"]
    v = fn(dict(_CASE)).danger_ok.values["mech.plate.circular.clamped_max_deflection"]
    expected = 1.0e4 * 0.1**4 / (64.0 * _D)
    assert v == pytest.approx(expected, rel=1e-9)


def test_simply_supported_more_severe_than_clamped():
    """Published structural relationship: the simply-supported plate has
    strictly higher peak stress AND deflection than the same clamped
    plate (why the pack wraps the SS forms as the conservative choice)."""
    s = _solvers()
    ss_sigma = s["mech.plate.plate_circular_uniform_ss_max_stress"][1](
        dict(_CASE)
    ).danger_ok.values["mech.plate.circular.ss_max_stress"]
    cl_sigma = s["mech.plate.plate_circular_uniform_clamped_max_stress"][1](
        dict(_CASE)
    ).danger_ok.values["mech.plate.circular.clamped_max_stress"]
    ss_y = s["mech.plate.plate_circular_uniform_ss_max_deflection"][1](
        dict(_CASE)
    ).danger_ok.values["mech.plate.circular.ss_max_deflection"]
    cl_y = s["mech.plate.plate_circular_uniform_clamped_max_deflection"][1](
        dict(_CASE)
    ).danger_ok.values["mech.plate.circular.clamped_max_deflection"]
    assert ss_sigma > cl_sigma
    assert ss_y > cl_y


# frob:tests python/feldspar/mech/plate.py::plate_circular_uniform_ss_max_stress kind="unit"
def test_plate_nonpositive_is_honest_indeterminate():
    _i, fn = _solvers()["mech.plate.plate_circular_uniform_ss_max_stress"]
    bad = dict(_CASE)
    bad["mech.plate.circular.t"] = 0.0
    r = fn(bad)
    assert r.is_err and r.err.kind == "OutOfDomain"
