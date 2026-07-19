from __future__ import annotations

"""T-0018 slice 3 tests: known-answer/hand-computed calibration for the
registered `materials.hardenability` directions
(`python/feldspar/materials/hardenability.py`). Grossmann (1942)'s
multiplicative ideal-critical-diameter law, the Jominy end-quench
power-law correlation, and Hollomon & Jaffe (1945)'s tempering
parameter."""

import math

import pytest

from feldspar.materials.hardenability import register
from feldspar.solve import SolverRegistry


def _solvers() -> dict:
    registry = SolverRegistry()
    register(registry)
    return {info.solver_id: (info, fn) for info, fn in registry}


# frob:tests python/feldspar/materials/hardenability.py::grossmann_ideal_critical_diameter kind="unit"
def test_grossmann_matches_hand_computed():
    """base_diameter=0.01 m, multiplying_factor=3.5 -> D_I=0.035 m."""
    _info, fn = _solvers()["materials.hardenability.grossmann_ideal_critical_diameter"]
    result = fn(
        {
            "materials.hardenability.grossmann.base_diameter": 0.01,
            "materials.hardenability.grossmann.multiplying_factor": 3.5,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "materials.hardenability.grossmann.ideal_critical_diameter"
    ] == pytest.approx(0.035, rel=1e-12)


# frob:tests python/feldspar/materials/hardenability.py::grossmann_ideal_critical_diameter kind="unit"
def test_grossmann_nonpositive_input_is_honest_indeterminate():
    _info, fn = _solvers()["materials.hardenability.grossmann_ideal_critical_diameter"]
    result = fn(
        {
            "materials.hardenability.grossmann.base_diameter": 0.0,
            "materials.hardenability.grossmann.multiplying_factor": 3.5,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# frob:tests python/feldspar/materials/hardenability.py::jominy_distance_to_cooling_rate kind="unit"
def test_jominy_matches_hand_computed_power_law():
    """coeff=500.0, exponent=-1.5, distance=0.02 m:
    cooling_rate = 500 * 0.02^-1.5."""
    _info, fn = _solvers()["materials.hardenability.jominy_distance_to_cooling_rate"]
    result = fn(
        {
            "materials.hardenability.jominy.distance": 0.02,
            "materials.hardenability.jominy.coeff": 500.0,
            "materials.hardenability.jominy.exponent": -1.5,
        }
    )
    assert result.is_ok
    expected = 500.0 * (0.02**-1.5)
    assert result.danger_ok.values[
        "materials.hardenability.jominy.cooling_rate"
    ] == pytest.approx(expected, rel=1e-12)


# frob:tests python/feldspar/materials/hardenability.py::jominy_distance_to_cooling_rate kind="unit"
def test_jominy_nonpositive_distance_is_honest_indeterminate():
    _info, fn = _solvers()["materials.hardenability.jominy_distance_to_cooling_rate"]
    result = fn(
        {
            "materials.hardenability.jominy.distance": 0.0,
            "materials.hardenability.jominy.coeff": 500.0,
            "materials.hardenability.jominy.exponent": -1.5,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# frob:tests python/feldspar/materials/hardenability.py::hollomon_jaffe_tempering_parameter kind="unit"
def test_hollomon_jaffe_matches_hand_computed():
    """T=873 K, t=1 h, C=20 -> P = 873*(20 + log10(1)) = 873*20 = 17460."""
    _info, fn = _solvers()["materials.hardenability.hollomon_jaffe_tempering_parameter"]
    result = fn(
        {
            "materials.hardenability.hollomon_jaffe.temperature": 873.0,
            "materials.hardenability.hollomon_jaffe.time": 1.0,
            "materials.hardenability.hollomon_jaffe.constant_c": 20.0,
        }
    )
    assert result.is_ok
    expected = 873.0 * (20.0 + math.log10(1.0))
    assert result.danger_ok.values[
        "materials.hardenability.hollomon_jaffe.parameter"
    ] == pytest.approx(expected, rel=1e-12)


# frob:tests python/feldspar/materials/hardenability.py::hollomon_jaffe_tempering_parameter kind="unit"
def test_hollomon_jaffe_at_ten_hours_matches_hand_computed():
    """T=773 K, t=10 h, C=18 -> P = 773*(18 + 1) = 773*19 = 14687."""
    _info, fn = _solvers()["materials.hardenability.hollomon_jaffe_tempering_parameter"]
    result = fn(
        {
            "materials.hardenability.hollomon_jaffe.temperature": 773.0,
            "materials.hardenability.hollomon_jaffe.time": 10.0,
            "materials.hardenability.hollomon_jaffe.constant_c": 18.0,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "materials.hardenability.hollomon_jaffe.parameter"
    ] == pytest.approx(773.0 * 19.0, rel=1e-12)


# frob:tests python/feldspar/materials/hardenability.py::register kind="unit"
# frob:tests python/feldspar/materials kind="integration"
def test_register_declares_full_hardenability_port_table():
    """Integration exercise: registering the family declares every
    port the three directions consume/produce, end to end through the
    SolverRegistry."""
    solvers = _solvers()
    assert "materials.hardenability.grossmann_ideal_critical_diameter" in solvers
    assert "materials.hardenability.jominy_distance_to_cooling_rate" in solvers
    assert "materials.hardenability.hollomon_jaffe_tempering_parameter" in solvers
