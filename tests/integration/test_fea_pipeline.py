from __future__ import annotations

"""WO-08 `fea`-marked integration tests: real gmsh/ccx solves through the
registered `fea.static_deflection.cantilever` / `fea.static_stress.
cylinder_bore` directions, checked against the WO-07 closed-form oracles
in `library/mech.py` (05 "Known-answer discipline": `|FEA - oracle| <=
reported eps`, at more than one geometry point per family), plus a
twice-run digest-equality test for determinism (04-routing "Solve
cache"). ALL tests here carry the `fea` marker (`pytestmark`) and are
excluded from `make test`'s default loop (`pyproject.toml`'s
`-m "not regolith and not fea"`) -- they require a real `ccx` binary and
a real `gmsh` install (the `mesh` extra), neither of which is present in
every dev/CI environment (AD-12e). This file is written correctly per
spec but could not be executed in the sandbox this WO was implemented
in (no `ccx`, no `gmsh`) -- see the WO-08 closing report for exactly
which halves of the acceptance bar were verified by execution vs. by
code review only."""

import pytest

from feldspar.core import Interval
from feldspar.fea.solver import register as register_fea
from feldspar.library.mech import register as register_mech
from feldspar.plan import solve
from feldspar.solve import SolverRegistry

pytestmark = pytest.mark.fea


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register_mech(registry)
    register_fea(registry)
    registry.freeze()
    return registry


# ---------------------------------------------------------------------------
# Cantilever family: FEA deflection vs. Euler-Bernoulli closed-form oracle.
# ---------------------------------------------------------------------------

_CANTILEVER_POINTS = [
    # (length, width, height, youngs_modulus, poisson, tip_force)
    (0.50, 0.040, 0.060, 7.0e10, 0.33, 1.0e3),  # aluminum-ish
    (0.30, 0.020, 0.030, 2.0e11, 0.30, 5.0e2),  # steel-ish, smaller/stiffer
]


@pytest.mark.parametrize(
    "length,width,height,youngs_modulus,poisson,tip_force", _CANTILEVER_POINTS
)
def test_cantilever_fea_matches_closed_form_oracle(
    length, width, height, youngs_modulus, poisson, tip_force
):
    """`fea.static_deflection.cantilever`'s realized value must fall
    within its OWN reported `measured_eps` of the WO-07 closed-form
    Euler-Bernoulli oracle -- the "known-answer discipline" 05 requires
    of every registered FEA direction (the oracle IS the ground truth
    here, per 03's tier framing: closed-form is the reference, FEA is
    being validated against it, not the other way around)."""
    registry = _registry()

    second_moment = width * height**3 / 12
    oracle = solve(
        registry,
        known={
            "mech.section.width": Interval(width, width),
            "mech.section.height": Interval(height, height),
        },
        tags=set(),
        target="mech.section.second_moment",
        eps_budget=1e-15,
    ).unwrap()
    assert oracle.value.lo == pytest.approx(second_moment, rel=1e-9)

    oracle_deflection = solve(
        registry,
        known={
            "mech.load.tip_force": Interval(tip_force, tip_force),
            "mech.geom.cantilever.length": Interval(length, length),
            "mech.material.youngs_modulus": Interval(youngs_modulus, youngs_modulus),
            "mech.section.second_moment": Interval(second_moment, second_moment),
        },
        tags=set(),
        target="mech.deflection.tip",
        eps_budget=1e-15,
    ).unwrap()
    oracle_value = oracle_deflection.value.lo

    fea_solution = solve(
        registry,
        known={
            "mech.geom.cantilever.length": Interval(length, length),
            "mech.geom.cantilever.width": Interval(width, width),
            "mech.geom.cantilever.height": Interval(height, height),
            "mech.material.youngs_modulus": Interval(youngs_modulus, youngs_modulus),
            "mech.material.poisson": Interval(poisson, poisson),
            "mech.load.tip_force": Interval(tip_force, tip_force),
        },
        tags={"linear_elastic", "small_deflection"},
        target="mech.deflection.tip",
        eps_budget=1e-2,
    ).unwrap()

    fea_value = fea_solution.value.lo
    assert abs(fea_value - oracle_value) <= fea_solution.eps


# ---------------------------------------------------------------------------
# Cylinder family: FEA bore von Mises stress vs. Lame closed-form oracle.
# ---------------------------------------------------------------------------

_CYLINDER_POINTS = [
    # (inner_radius, outer_radius, youngs_modulus, poisson, pressure)
    (1.0, 2.0, 2.0e11, 0.30, 30.0e6),
    (0.5, 1.5, 7.0e10, 0.33, 10.0e6),
]


@pytest.mark.parametrize(
    "inner_radius,outer_radius,youngs_modulus,poisson,pressure", _CYLINDER_POINTS
)
def test_cylinder_fea_matches_closed_form_oracle(
    inner_radius, outer_radius, youngs_modulus, poisson, pressure
):
    """`fea.static_stress.cylinder_bore`'s realized value must fall
    within its OWN reported `measured_eps` of the WO-07 Lame/von-Mises
    closed-form oracle (`mech.bore_von_mises`, same ports by
    construction, 05 port-naming contract)."""
    registry = _registry()

    oracle_solution = solve(
        registry,
        known={
            "mech.load.internal_pressure": Interval(pressure, pressure),
            "mech.geom.cylinder.inner_radius": Interval(inner_radius, inner_radius),
            "mech.geom.cylinder.outer_radius": Interval(outer_radius, outer_radius),
        },
        tags={"linear_elastic"},
        target="mech.stress.von_mises",
        eps_budget=1e-15,
    ).unwrap()
    oracle_value = oracle_solution.value.lo

    fea_solution = solve(
        registry,
        known={
            "mech.load.internal_pressure": Interval(pressure, pressure),
            "mech.geom.cylinder.inner_radius": Interval(inner_radius, inner_radius),
            "mech.geom.cylinder.outer_radius": Interval(outer_radius, outer_radius),
            "mech.material.youngs_modulus": Interval(youngs_modulus, youngs_modulus),
            "mech.material.poisson": Interval(poisson, poisson),
        },
        tags={"linear_elastic"},
        target="mech.stress.von_mises",
        eps_budget=1e6,
    ).unwrap()
    fea_value = fea_solution.value.lo

    assert abs(fea_value - oracle_value) <= fea_solution.eps


# ---------------------------------------------------------------------------
# Determinism: twice-run digest equality (04-routing "Solve cache").
# ---------------------------------------------------------------------------


def test_cantilever_fea_solve_is_deterministic_across_two_runs():
    """Two independent `solve()` calls with identical inputs against a
    freshly built registry must produce the SAME `settings_digest` (the
    digest is a pure function of registered solver settings, not of
    execution history) -- the twice-run determinism check the WO
    requires for the FEA tier's `deterministic=True` claim."""
    known = {
        "mech.geom.cantilever.length": Interval(0.50, 0.50),
        "mech.geom.cantilever.width": Interval(0.040, 0.040),
        "mech.geom.cantilever.height": Interval(0.060, 0.060),
        "mech.material.youngs_modulus": Interval(7.0e10, 7.0e10),
        "mech.material.poisson": Interval(0.33, 0.33),
        "mech.load.tip_force": Interval(1.0e3, 1.0e3),
    }

    first = solve(
        _registry(),
        known=known,
        tags={"linear_elastic", "small_deflection"},
        target="mech.deflection.tip",
        eps_budget=1e-2,
    ).unwrap()
    second = solve(
        _registry(),
        known=known,
        tags={"linear_elastic", "small_deflection"},
        target="mech.deflection.tip",
        eps_budget=1e-2,
    ).unwrap()

    assert first.settings_digest == second.settings_digest
    assert first.value.lo == pytest.approx(second.value.lo, rel=1e-9)
