from __future__ import annotations

"""WO-111 tests: shaft critical (whirl) speed directions
(`python/feldspar/library/critical_speed.py`), called THROUGH the
`SolverRegistry`/`SolveFn` protocol. Calibration is an exact evaluation
of Shigley's Mechanical Engineering Design 11th ed. ch. 7 eq. 7-22
(stiffness) / eq. 7-23 (Rayleigh single-mass) closed forms
(docs/benchmarks-memo.md sec. 16), plus a physical cross-check that the
stiffness and static-deflection views of ONE mass agree (WO111-F1: no
independent worked numeric transcribed -- the oracle is the cited
formula itself, same known-answer pattern the WO-24 tests use)."""

import math

from feldspar.library.critical_speed import G_STANDARD, register
from feldspar.solve import SolverRegistry


def _solvers() -> dict:
    registry = SolverRegistry()
    register(registry)
    return {info.solver_id: (info, fn) for info, fn in registry}


# frob:tests python/feldspar/mech/critical_speed.py::shaft_critical_speed_from_stiffness kind="unit"
def test_critical_speed_from_stiffness_matches_closed_form():
    """k=1e6 N/m, m=2 kg -> omega_c = sqrt(5e5), n_c = omega_c*60/(2*pi)."""
    _info, fn = _solvers()["mech.critical_speed.shaft_critical_speed_from_stiffness"]
    result = fn(
        {"mech.critical_speed.stiffness": 1.0e6, "mech.critical_speed.mass": 2.0}
    )
    assert result.is_ok
    expected = math.sqrt(1.0e6 / 2.0) * 60.0 / (2.0 * math.pi)
    assert result.danger_ok.values["mech.critical_speed.rpm"] == expected


# frob:tests python/feldspar/mech/critical_speed.py::shaft_critical_speed_rayleigh_single_mass kind="unit"
def test_critical_speed_rayleigh_matches_closed_form():
    """delta=1 mm -> n_c = (30/pi)*sqrt(g/delta)."""
    _info, fn = _solvers()[
        "mech.critical_speed.shaft_critical_speed_rayleigh_single_mass"
    ]
    result = fn({"mech.critical_speed.static_deflection": 1.0e-3})
    assert result.is_ok
    expected = (30.0 / math.pi) * math.sqrt(G_STANDARD / 1.0e-3)
    assert result.danger_ok.values["mech.critical_speed.rayleigh_rpm"] == expected


def test_stiffness_and_rayleigh_agree_for_one_mass():
    """A single mass with static deflection delta has lateral stiffness
    k = m*g/delta; both directions must then report ONE critical speed
    (the physical consistency cross-check, independent of either
    formula's internal algebra)."""
    solvers = _solvers()
    m = 2.0
    delta = 1.0e-3
    k = m * G_STANDARD / delta
    _i1, stiff_fn = solvers["mech.critical_speed.shaft_critical_speed_from_stiffness"]
    _i2, ray_fn = solvers[
        "mech.critical_speed.shaft_critical_speed_rayleigh_single_mass"
    ]
    n_stiff = stiff_fn(
        {"mech.critical_speed.stiffness": k, "mech.critical_speed.mass": m}
    ).danger_ok.values["mech.critical_speed.rpm"]
    n_ray = ray_fn({"mech.critical_speed.static_deflection": delta}).danger_ok.values[
        "mech.critical_speed.rayleigh_rpm"
    ]
    assert abs(n_stiff - n_ray) < 1e-9 * n_ray


def test_critical_speed_nonpositive_is_honest_indeterminate():
    solvers = _solvers()
    _i1, stiff_fn = solvers["mech.critical_speed.shaft_critical_speed_from_stiffness"]
    r1 = stiff_fn(
        {"mech.critical_speed.stiffness": 0.0, "mech.critical_speed.mass": 2.0}
    )
    assert r1.is_err and r1.err.kind == "OutOfDomain"
    _i2, ray_fn = solvers[
        "mech.critical_speed.shaft_critical_speed_rayleigh_single_mass"
    ]
    r2 = ray_fn({"mech.critical_speed.static_deflection": 0.0})
    assert r2.is_err and r2.err.kind == "OutOfDomain"
