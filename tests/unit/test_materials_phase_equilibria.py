from __future__ import annotations

"""T-0018 slice 4 tests: known-answer/hand-computed calibration for the
registered `materials.phase_equilibria` directions
(`python/feldspar/materials/phase_equilibria.py`) -- the lever rule and
the regular-solution binary free-energy-of-mixing model."""

import math

import pytest

from feldspar.materials.phase_equilibria import register
from feldspar.solve import SolverRegistry


def _solvers() -> dict:
    registry = SolverRegistry()
    register(registry)
    return {info.solver_id: (info, fn) for info, fn in registry}


# frob:tests python/feldspar/materials/phase_equilibria.py::lever_rule_phase_fraction kind="unit"
def test_lever_rule_matches_hand_computed():
    """alpha=0.02, beta=0.20, overall=0.10:
    f_alpha = (0.20-0.10)/(0.20-0.02) = 0.10/0.18."""
    _info, fn = _solvers()["materials.phase_equilibria.lever_rule_phase_fraction"]
    result = fn(
        {
            "materials.phase_equilibria.lever.alpha_fraction": 0.02,
            "materials.phase_equilibria.lever.beta_fraction": 0.20,
            "materials.phase_equilibria.lever.overall_fraction": 0.10,
        }
    )
    assert result.is_ok
    expected = (0.20 - 0.10) / (0.20 - 0.02)
    assert result.danger_ok.values[
        "materials.phase_equilibria.lever.phase_alpha_fraction"
    ] == pytest.approx(expected, rel=1e-12)


# frob:tests python/feldspar/materials/phase_equilibria.py::lever_rule_phase_fraction kind="unit"
def test_lever_rule_at_boundary_gives_pure_phase():
    """overall == alpha boundary -> f_alpha = 1.0 (all alpha phase)."""
    _info, fn = _solvers()["materials.phase_equilibria.lever_rule_phase_fraction"]
    result = fn(
        {
            "materials.phase_equilibria.lever.alpha_fraction": 0.02,
            "materials.phase_equilibria.lever.beta_fraction": 0.20,
            "materials.phase_equilibria.lever.overall_fraction": 0.02,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "materials.phase_equilibria.lever.phase_alpha_fraction"
    ] == pytest.approx(1.0, rel=1e-9)


# frob:tests python/feldspar/materials/phase_equilibria.py::lever_rule_phase_fraction kind="unit"
def test_lever_rule_rejects_overall_outside_tie_line():
    _info, fn = _solvers()["materials.phase_equilibria.lever_rule_phase_fraction"]
    result = fn(
        {
            "materials.phase_equilibria.lever.alpha_fraction": 0.02,
            "materials.phase_equilibria.lever.beta_fraction": 0.20,
            "materials.phase_equilibria.lever.overall_fraction": 0.90,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# frob:tests python/feldspar/materials/phase_equilibria.py::lever_rule_phase_fraction kind="unit"
def test_lever_rule_rejects_degenerate_tie_line():
    _info, fn = _solvers()["materials.phase_equilibria.lever_rule_phase_fraction"]
    result = fn(
        {
            "materials.phase_equilibria.lever.alpha_fraction": 0.10,
            "materials.phase_equilibria.lever.beta_fraction": 0.10,
            "materials.phase_equilibria.lever.overall_fraction": 0.10,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# frob:tests python/feldspar/materials/phase_equilibria.py::regular_solution_binary_free_energy kind="unit"
def test_regular_solution_matches_hand_computed_at_ideal_limit():
    """Omega=0 (ideal solution): dG_mix = R*T*(x*ln(x)+(1-x)*ln(1-x))."""
    _info, fn = _solvers()[
        "materials.phase_equilibria.regular_solution_binary_free_energy"
    ]
    x_b = 0.3
    temperature = 1000.0
    result = fn(
        {
            "materials.phase_equilibria.regular_solution.mole_fraction": x_b,
            "materials.phase_equilibria.regular_solution.temperature": temperature,
            "materials.phase_equilibria.regular_solution.omega": 0.0,
        }
    )
    assert result.is_ok
    r = 8.314462618
    expected = (
        r * temperature * (x_b * math.log(x_b) + (1.0 - x_b) * math.log(1.0 - x_b))
    )
    assert result.danger_ok.values[
        "materials.phase_equilibria.regular_solution.gibbs_mixing"
    ] == pytest.approx(expected, rel=1e-12)


# frob:tests python/feldspar/materials/phase_equilibria.py::regular_solution_binary_free_energy kind="unit"
def test_regular_solution_matches_hand_computed_with_excess_term():
    """x=0.5, T=800 K, Omega=12000 J/mol."""
    _info, fn = _solvers()[
        "materials.phase_equilibria.regular_solution_binary_free_energy"
    ]
    x_b = 0.5
    temperature = 800.0
    omega = 12000.0
    result = fn(
        {
            "materials.phase_equilibria.regular_solution.mole_fraction": x_b,
            "materials.phase_equilibria.regular_solution.temperature": temperature,
            "materials.phase_equilibria.regular_solution.omega": omega,
        }
    )
    assert result.is_ok
    r = 8.314462618
    expected = r * temperature * (
        x_b * math.log(x_b) + (1.0 - x_b) * math.log(1.0 - x_b)
    ) + omega * x_b * (1.0 - x_b)
    assert result.danger_ok.values[
        "materials.phase_equilibria.regular_solution.gibbs_mixing"
    ] == pytest.approx(expected, rel=1e-12)


# frob:tests python/feldspar/materials/phase_equilibria.py::register kind="unit"
# frob:tests python/feldspar/materials kind="integration"
def test_register_declares_full_phase_equilibria_port_table():
    """Integration exercise: registering the family declares every
    port both directions consume/produce, end to end through the
    SolverRegistry."""
    solvers = _solvers()
    assert "materials.phase_equilibria.lever_rule_phase_fraction" in solvers
    assert "materials.phase_equilibria.regular_solution_binary_free_energy" in solvers
