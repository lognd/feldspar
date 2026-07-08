from __future__ import annotations

"""WO-07 tests: known-answer unit tests for the registered `mech`
solver directions (`python/feldspar/library/mech.py`), called THROUGH
the `SolverRegistry`/`SolveFn` protocol (never `feldspar._feldspar.mech_*`
directly), so ports, domain guards, and marshalling are exercised, not
just the raw Rust math."""

import math

import pytest

from feldspar.core import Domain
from feldspar.library.mech import register
from feldspar.solve import SolverRegistry
from feldspar.solve.errors import SolveError


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    return registry


def _solvers() -> dict:
    """id -> (info, fn) for every registered mech direction."""
    registry = _registry()
    return {info.solver_id: (info, fn) for info, fn in registry}


def test_rect_second_moment_known_answer():
    """Gere, Mechanics of Materials 9e, App. E: I = b*h^3/12 for a
    rectangular cross-section. width=0.04 m, height=0.06 m ->
    I = 0.04 * 0.06**3 / 12 = 7.2e-7 m^4."""
    _info, fn = _solvers()["mech.rect_second_moment"]
    result = fn({"mech.section.width": 0.04, "mech.section.height": 0.06})
    assert result.is_ok
    expected = 0.04 * 0.06**3 / 12
    assert result.danger_ok.values["mech.section.second_moment"] == pytest.approx(
        expected, rel=1e-9
    )


def test_cantilever_tip_deflection_known_answer():
    """Gere, Mechanics of Materials, 9th ed., Table (cantilever,
    concentrated load at free end); see also Young & Budynas, Roark's
    Formulas for Stress and Strain, 8th ed., Table 8.1 (secondary
    handbook citation). delta = F*L^3/(3*E*I) with F=1000 N, L=0.5 m,
    E=7e10 Pa (aluminum), I=7.2e-7 m^4."""
    _info, fn = _solvers()["mech.cantilever_tip_deflection"]
    force = 1000.0
    length = 0.5
    youngs_modulus = 7e10
    second_moment = 7.2e-7
    result = fn(
        {
            "mech.load.tip_force": force,
            "mech.geom.cantilever.length": length,
            "mech.material.youngs_modulus": youngs_modulus,
            "mech.section.second_moment": second_moment,
        }
    )
    assert result.is_ok
    expected = force * length**3 / (3 * youngs_modulus * second_moment)
    assert result.danger_ok.values["mech.deflection.tip"] == pytest.approx(
        expected, rel=1e-9
    )


def test_cantilever_required_youngs_modulus_round_trip():
    """Gere, Mechanics of Materials, 9th ed., Table (cantilever,
    concentrated load at free end); see also Young & Budynas, Roark's
    Formulas for Stress and Strain, 8th ed., Table 8.1 (secondary
    handbook citation). Inverting delta = F*L^3/(3*E*I) for E and
    feeding the deflection computed by the forward direction back in
    must recover the original E to float precision -- the WO-07
    multi-direction round-trip demonstration."""
    solvers = _solvers()
    force = 1000.0
    length = 0.5
    youngs_modulus = 7e10
    second_moment = 7.2e-7

    _fwd_info, fwd_fn = solvers["mech.cantilever_tip_deflection"]
    fwd_result = fwd_fn(
        {
            "mech.load.tip_force": force,
            "mech.geom.cantilever.length": length,
            "mech.material.youngs_modulus": youngs_modulus,
            "mech.section.second_moment": second_moment,
        }
    )
    assert fwd_result.is_ok
    deflection = fwd_result.danger_ok.values["mech.deflection.tip"]

    _inv_info, inv_fn = solvers["mech.cantilever_required_youngs_modulus"]
    inv_result = inv_fn(
        {
            "mech.load.tip_force": force,
            "mech.geom.cantilever.length": length,
            "mech.section.second_moment": second_moment,
            "mech.deflection.tip": deflection,
        }
    )
    assert inv_result.is_ok
    recovered = inv_result.danger_ok.values["mech.material.youngs_modulus"]
    assert recovered == pytest.approx(youngs_modulus, rel=1e-9)


def test_bore_von_mises_known_answer():
    """Budynas & Nisbett, Shigley's Mechanical Engineering Design,
    latest ed., Thick-Walled Cylinders section (Lame's equations), and
    the distortion-energy (von Mises) equivalent stress definition.
    pressure=30e6 Pa, inner_radius=1.0, outer_radius=2.0:
    hoop = p*(a^2+b^2)/(b^2-a^2) = 30e6*(1+4)/(4-1) = 50e6,
    radial = -p = -30e6, axial = 0,
    von_mises = sqrt(0.5*((hoop-radial)^2+(radial-axial)^2+(axial-hoop)^2))."""
    _info, fn = _solvers()["mech.bore_von_mises"]
    pressure = 30e6
    inner_radius = 1.0
    outer_radius = 2.0
    result = fn(
        {
            "mech.load.internal_pressure": pressure,
            "mech.geom.cylinder.inner_radius": inner_radius,
            "mech.geom.cylinder.outer_radius": outer_radius,
        }
    )
    assert result.is_ok

    a2 = inner_radius**2
    b2 = outer_radius**2
    hoop = pressure * (a2 + b2) / (b2 - a2)
    radial = -pressure
    axial = 0.0
    expected = math.sqrt(
        0.5 * ((hoop - radial) ** 2 + (radial - axial) ** 2 + (axial - hoop) ** 2)
    )
    assert result.danger_ok.values["mech.stress.von_mises"] == pytest.approx(
        expected, rel=1e-9
    )


def test_bore_von_mises_degenerate_ratio_rejected():
    """02-edge-cases 'Library + calibration (WO-07)': Lame ratio -> 1
    (r_o == r_i) is outside this solver's effective domain; the guard
    in mech.py must return SolveError.OutOfDomain, never raise or
    produce an inf/nan value."""
    _info, fn = _solvers()["mech.bore_von_mises"]
    result = fn(
        {
            "mech.load.internal_pressure": 30e6,
            "mech.geom.cylinder.inner_radius": 1.0,
            "mech.geom.cylinder.outer_radius": 1.0,
        }
    )
    assert result.is_err
    assert result.danger_err.kind == SolveError.OutOfDomain(violation="x").kind


def test_cantilever_length_domain_excludes_nonpositive():
    """02-edge-cases 'Library + calibration (WO-07)': 'cantilever at
    L=0 or negative: ctor/domain rejects' -- enforced by the executor's
    Domain box check, not the SolveFn itself; confirm the registered
    direction's declared Domain has a strictly positive lower bound on
    length so L<=0 is never admissible."""
    info, _fn = _solvers()["mech.cantilever_tip_deflection"]
    domain: Domain = info.domain
    length_interval = domain.box["mech.geom.cantilever.length"]
    assert length_interval.lo > 0.0
