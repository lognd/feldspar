from __future__ import annotations

"""T-0018 slice 2 tests: known-answer/hand-computed calibration for the
registered `materials.kinetics` directions
(`python/feldspar/materials/kinetics.py`), called THROUGH the
`SolverRegistry`/`SolveFn` protocol (same convention as
`tests/unit/test_library_fatigue.py`). Each test reproduces the cited
equation's own closed form by hand -- Koistinen & Marburger (1959) for
martensite fraction, the Kirkaldy/Li Avrami-Arrhenius onset-time form,
and Grange & Kiefer (1941)'s linear-additive Ms-depression shift."""

import math

import pytest

from feldspar.materials.kinetics import register
from feldspar.solve import SolverRegistry


def _solvers() -> dict:
    registry = SolverRegistry()
    register(registry)
    return {info.solver_id: (info, fn) for info, fn in registry}


# ---------------------------------------------------------------------------
# koistinen_marburger_martensite_fraction
# ---------------------------------------------------------------------------


# frob:tests python/feldspar/materials/kinetics.py::koistinen_marburger_martensite_fraction kind="unit"
def test_koistinen_marburger_matches_hand_computed():
    """Ms=493 K (220 C), quench to 293 K (20 C), alpha=0.011/K (the
    K-M 1959 paper's own commonly quoted plain-carbon-steel value):
    f = 1 - exp(-0.011*(493-293)) = 1 - exp(-2.2)."""
    solvers = _solvers()
    _info, fn = solvers["materials.kinetics.koistinen_marburger_martensite_fraction"]
    result = fn(
        {
            "materials.kinetics.km.ms_temperature": 493.0,
            "materials.kinetics.km.quench_temperature": 293.0,
            "materials.kinetics.km.alpha": 0.011,
        }
    )
    assert result.is_ok
    expected = 1.0 - math.exp(-0.011 * 200.0)
    assert result.danger_ok.values[
        "materials.kinetics.km.martensite_fraction"
    ] == pytest.approx(expected, rel=1e-12)


# frob:tests python/feldspar/materials/kinetics.py::koistinen_marburger_martensite_fraction kind="unit"
def test_koistinen_marburger_above_ms_is_zero():
    solvers = _solvers()
    _info, fn = solvers["materials.kinetics.koistinen_marburger_martensite_fraction"]
    result = fn(
        {
            "materials.kinetics.km.ms_temperature": 400.0,
            "materials.kinetics.km.quench_temperature": 450.0,
            "materials.kinetics.km.alpha": 0.011,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["materials.kinetics.km.martensite_fraction"] == 0.0


# frob:tests python/feldspar/materials/kinetics.py::koistinen_marburger_martensite_fraction kind="unit"
def test_koistinen_marburger_nonpositive_alpha_is_honest_indeterminate():
    solvers = _solvers()
    _info, fn = solvers["materials.kinetics.koistinen_marburger_martensite_fraction"]
    result = fn(
        {
            "materials.kinetics.km.ms_temperature": 400.0,
            "materials.kinetics.km.quench_temperature": 300.0,
            "materials.kinetics.km.alpha": 0.0,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# kirkaldy_diffusional_onset_time
# ---------------------------------------------------------------------------


# frob:tests python/feldspar/materials/kinetics.py::kirkaldy_diffusional_onset_time kind="unit"
def test_kirkaldy_onset_time_matches_hand_computed_arrhenius():
    """t0=1e-3 s, Q=150 kJ/mol, T=873 K:
    t_onset = 1e-3 * exp(150000/(8.314462618*873))."""
    solvers = _solvers()
    _info, fn = solvers["materials.kinetics.kirkaldy_diffusional_onset_time"]
    result = fn(
        {
            "materials.kinetics.diffusional.t0": 1e-3,
            "materials.kinetics.diffusional.activation_energy": 150000.0,
            "materials.kinetics.diffusional.temperature": 873.0,
        }
    )
    assert result.is_ok
    expected = 1e-3 * math.exp(150000.0 / (8.314462618 * 873.0))
    assert result.danger_ok.values[
        "materials.kinetics.diffusional.onset_time"
    ] == pytest.approx(expected, rel=1e-12)


# frob:tests python/feldspar/materials/kinetics.py::kirkaldy_diffusional_onset_time kind="unit"
def test_kirkaldy_onset_time_nonpositive_t0_is_honest_indeterminate():
    solvers = _solvers()
    _info, fn = solvers["materials.kinetics.kirkaldy_diffusional_onset_time"]
    result = fn(
        {
            "materials.kinetics.diffusional.t0": 0.0,
            "materials.kinetics.diffusional.activation_energy": 150000.0,
            "materials.kinetics.diffusional.temperature": 873.0,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# grange_kiefer_ms_shift
# ---------------------------------------------------------------------------


# frob:tests python/feldspar/materials/kinetics.py::grange_kiefer_ms_shift kind="unit"
def test_grange_kiefer_matches_hand_computed():
    """Ms_base=550 K, depression=80 K -> Ms_shifted=470 K."""
    solvers = _solvers()
    _info, fn = solvers["materials.kinetics.grange_kiefer_ms_shift"]
    result = fn(
        {
            "materials.kinetics.gk.ms_base": 550.0,
            "materials.kinetics.gk.depression": 80.0,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["materials.kinetics.gk.ms_shifted"] == pytest.approx(
        470.0, rel=1e-12
    )


# frob:tests python/feldspar/materials/kinetics.py::register kind="unit"
# frob:tests python/feldspar/materials kind="integration"
def test_register_declares_full_kinetics_port_table():
    """Integration exercise: registering the family declares every
    port the three directions consume/produce, end to end through the
    SolverRegistry."""
    solvers = _solvers()
    assert "materials.kinetics.koistinen_marburger_martensite_fraction" in solvers
    assert "materials.kinetics.kirkaldy_diffusional_onset_time" in solvers
    assert "materials.kinetics.grange_kiefer_ms_shift" in solvers
