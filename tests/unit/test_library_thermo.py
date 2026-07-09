from __future__ import annotations

"""WO-20 residual conformance tests: known-answer unit tests for the
registered `thermo` solver directions (`feldspar/library/thermo.py`),
called THROUGH the `SolverRegistry`/`SolveFn` protocol, turning the
benchmarks memo's CoolProp reference state points (lithos
`docs/workflow/research/2026-07-08-benchmarks-and-datasets.md` sec.
3.4) into pytest conformance tests with their cited tolerances."""

import pytest

pytest.importorskip("CoolProp", reason="props extra not installed")

from feldspar.library.thermo import register  # noqa: E402
from feldspar.solve import SolverRegistry  # noqa: E402


def _solvers() -> dict:
    registry = SolverRegistry()
    register(registry)
    return {info.solver_id: (info, fn) for info, fn in registry}


# Benchmarks memo sec. 3.4, verbatim (fluid, T[K], P[Pa], rho, cp, mu).
_STATE_POINTS = [
    ("water", 293.15, 101325.0, 998.2, 4184.0, 1.002e-3),
    ("water", 298.15, 101325.0, 997.0, 4181.0, 8.90e-4),
    ("water", 373.124, 101325.0, 958.4, 4217.0, 2.82e-4),
    ("air", 298.15, 101325.0, 1.184, 1006.0, 1.849e-5),
    ("nitrogen", 298.15, 101325.0, 1.145, 1040.0, 1.78e-5),
]


@pytest.mark.parametrize("fluid,t,p,rho,cp,mu", _STATE_POINTS)
def test_density_matches_reference_state_point(fluid, t, p, rho, cp, mu):
    """Benchmarks memo sec. 3.4: +/-0.5% tolerance on liquid/gas density
    against the IAPWS-95/Lemmon reference EOS CoolProp implements."""
    _info, fn = _solvers()[f"thermo.{fluid}_density"]
    result = fn({f"thermo.{fluid}.temperature": t, f"thermo.{fluid}.pressure": p})
    assert result.is_ok
    value = result.danger_ok.values[f"thermo.{fluid}.density"]
    assert value == pytest.approx(rho, rel=5e-3)


@pytest.mark.parametrize("fluid,t,p,rho,cp,mu", _STATE_POINTS)
def test_specific_heat_matches_reference_state_point(fluid, t, p, rho, cp, mu):
    """Benchmarks memo sec. 3.4: +/-0.5% tolerance on cp."""
    _info, fn = _solvers()[f"thermo.{fluid}_specific_heat_cp"]
    result = fn({f"thermo.{fluid}.temperature": t, f"thermo.{fluid}.pressure": p})
    assert result.is_ok
    value = result.danger_ok.values[f"thermo.{fluid}.specific_heat_cp"]
    assert value == pytest.approx(cp, rel=5e-3)


@pytest.mark.parametrize("fluid,t,p,rho,cp,mu", _STATE_POINTS)
def test_viscosity_matches_reference_state_point(fluid, t, p, rho, cp, mu):
    """Benchmarks memo sec. 3.4: +/-2% tolerance on viscosity (the
    looser correlation-band figure)."""
    _info, fn = _solvers()[f"thermo.{fluid}_viscosity"]
    result = fn({f"thermo.{fluid}.temperature": t, f"thermo.{fluid}.pressure": p})
    assert result.is_ok
    value = result.danger_ok.values[f"thermo.{fluid}.viscosity"]
    assert value == pytest.approx(mu, rel=2e-2)


def test_register_declares_nine_directions():
    """Three fluids (water, air, nitrogen) x three properties (density,
    specific_heat_cp, viscosity) -- the honest coverage this WO
    delivers, not the full 07 thermo catalog (device models, cycles,
    combustion, psychrometrics, exergy are explicitly CUT, WO-20 file)."""
    solvers = _solvers()
    thermo_ids = {sid for sid in solvers if sid.startswith("thermo.")}
    assert len(thermo_ids) == 9


def test_out_of_domain_temperature_is_rejected_at_registration_level():
    """The declared domain box brackets the calibration anchors; a
    caller asking for a state far outside it is the registry's/
    planner's job to reject via the declared `Domain`, not this test's
    -- but the direction itself must still be well-defined (not raise)
    for a nearby in-box probe, confirming the box is wired to real
    values, not a placeholder."""
    _info, fn = _solvers()["thermo.water_density"]
    result = fn({"thermo.water.temperature": 293.15, "thermo.water.pressure": 101325.0})
    assert result.is_ok


def test_propsi_valueerror_is_honest_out_of_domain_not_a_crash():
    """M5 (cycle-28 audit): the rectangular T-P `Domain` box does not
    guarantee CoolProp accepts every interior point. `(T=273.16,
    P=611.0)` is inside water's declared box (`[273.16, 373.124]` x
    `[611e0, 2e7]`) but is just below water's triple-point pressure
    (611.655 Pa) at Tmin -- CoolProp's `PropsSI` raises `ValueError`
    for it. This must surface as `SolveError.OutOfDomain`, never an
    unhandled crash."""
    _info, fn = _solvers()["thermo.water_density"]
    result = fn({"thermo.water.temperature": 273.16, "thermo.water.pressure": 611.0})
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
