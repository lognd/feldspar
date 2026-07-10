from __future__ import annotations

"""WO-24 deliverable 4 tests: known-answer/hand-computed unit tests for
the registered `mech.fatigue` directions
(`python/feldspar/library/fatigue.py`), called THROUGH the
`SolverRegistry`/`SolveFn` protocol. Every numeric case reproduces
Shigley's Mechanical Engineering Design 11th ed. ch. 6's own worked
"Example 6-12"-style axially loaded fatigue problem (docs/
benchmarks-memo.md sec. 14): a 40 mm diameter AISI-1045 CD machined
bar, fluctuating tensile load 0..100 kN, Kf=1.85 pre-applied by the
caller."""

import math

import pytest

from feldspar.library.fatigue import register
from feldspar.solve import SolverRegistry


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    return registry


def _solvers() -> dict:
    registry = _registry()
    return {info.solver_id: (info, fn) for info, fn in registry}


# ---------------------------------------------------------------------------
# fatigue_endurance_limit_baseline: Se' = 0.5*Sut
# ---------------------------------------------------------------------------


def test_baseline_endurance_limit_matches_hand_computed():
    """Sut=630e6 Pa -> Se' = 0.5*630e6 = 315e6 Pa."""
    _info, fn = _solvers()["mech.fatigue.fatigue_endurance_limit_baseline"]
    result = fn({"mech.fatigue.baseline.sut": 630.0e6})
    assert result.is_ok
    assert result.danger_ok.values["mech.fatigue.baseline.se_prime"] == pytest.approx(
        315.0e6, rel=1e-9
    )


def test_baseline_endurance_limit_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["mech.fatigue.fatigue_endurance_limit_baseline"]
    result = fn({"mech.fatigue.baseline.sut": 0.0})
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# fatigue_marin_surface_factor: ka = a*Sut^b (Table 6-2, machined row)
# ---------------------------------------------------------------------------


def test_marin_surface_factor_matches_hand_computed():
    """Machined/cold-drawn row: a=4.51, b=-0.265, Sut=630 MPa ->
    ka = 4.51*630^-0.265 = 0.8177 (hand-computed via math.log/exp,
    matches the class-notes worked value of 0.817 to 3 sig figs)."""
    _info, fn = _solvers()["mech.fatigue.fatigue_marin_surface_factor"]
    a = 4.51
    b = -0.265
    sut_mpa = 630.0
    expected = a * math.exp(b * math.log(sut_mpa))
    assert expected == pytest.approx(0.8177, rel=1e-3)
    result = fn(
        {
            "mech.fatigue.surface.sut_mpa": sut_mpa,
            "mech.fatigue.surface.coeff_a": a,
            "mech.fatigue.surface.exponent_b": b,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["mech.fatigue.surface.ka"] == pytest.approx(
        expected, rel=1e-9
    )
    assert result.danger_ok.values["mech.fatigue.surface.ka"] == pytest.approx(
        0.817, rel=2e-3
    )


def test_marin_surface_factor_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["mech.fatigue.fatigue_marin_surface_factor"]
    result = fn(
        {
            "mech.fatigue.surface.sut_mpa": 0.0,
            "mech.fatigue.surface.coeff_a": 4.51,
            "mech.fatigue.surface.exponent_b": -0.265,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# fatigue_marin_endurance_limit: Se = ka*kb*kc*kd*ke*Se'
# ---------------------------------------------------------------------------


def test_marin_endurance_limit_matches_hand_computed():
    """ka=0.817, kb=1 (axial), kc=0.85 (axial), kd=ke=1, Se'=315 MPa ->
    Se = 0.817*1*0.85*1*1*315 = 218.75 MPa (class-notes worked value:
    218.8 MPa)."""
    _info, fn = _solvers()["mech.fatigue.fatigue_marin_endurance_limit"]
    result = fn(
        {
            "mech.fatigue.marin.se_prime": 315.0e6,
            "mech.fatigue.marin.ka": 0.817,
            "mech.fatigue.marin.kb": 1.0,
            "mech.fatigue.marin.kc": 0.85,
            "mech.fatigue.marin.kd": 1.0,
            "mech.fatigue.marin.ke": 1.0,
        }
    )
    assert result.is_ok
    se = result.danger_ok.values["mech.fatigue.marin.se"]
    assert se == pytest.approx(0.817 * 0.85 * 315.0e6, rel=1e-9)
    assert se == pytest.approx(218.8e6, rel=2e-3)


def test_marin_endurance_limit_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["mech.fatigue.fatigue_marin_endurance_limit"]
    result = fn(
        {
            "mech.fatigue.marin.se_prime": 0.0,
            "mech.fatigue.marin.ka": 0.817,
            "mech.fatigue.marin.kb": 1.0,
            "mech.fatigue.marin.kc": 0.85,
            "mech.fatigue.marin.kd": 1.0,
            "mech.fatigue.marin.ke": 1.0,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# fatigue_goodman_factor_of_safety: eq. 6-46 fatigue-governs branch
# ---------------------------------------------------------------------------


def test_goodman_factor_of_safety_matches_hand_computed():
    """Example 6-12: Se=218.8 MPa, Sut=630 MPa, sigma_a=sigma_m=73.6
    MPa (Kf=1.85 already applied to sigma_ao=sigma_mo=39.8 MPa) ->
    r=1, Sa_limit=Sm_limit=r*Se*Sut/(r*Sut+Se)=1*218.8*630/(630+218.8)
    =162.4 MPa; nf=Sa_limit/sigma_a=162.4/73.6=2.207 (class-notes
    worked value: 2.21)."""
    _info, fn = _solvers()["mech.fatigue.fatigue_goodman_factor_of_safety"]
    se = 218.8e6
    sut = 630.0e6
    sigma_a = 73.6e6
    sigma_m = 73.6e6
    result = fn(
        {
            "mech.fatigue.goodman.se": se,
            "mech.fatigue.goodman.sut": sut,
            "mech.fatigue.goodman.sigma_a": sigma_a,
            "mech.fatigue.goodman.sigma_m": sigma_m,
        }
    )
    assert result.is_ok
    values = result.danger_ok.values
    r = sigma_a / sigma_m
    expected_sa = r * se * sut / (r * sut + se)
    assert expected_sa == pytest.approx(162.4e6, rel=2e-3)
    assert values["mech.fatigue.goodman.sa_limit"] == pytest.approx(
        expected_sa, rel=1e-9
    )
    assert values["mech.fatigue.goodman.sm_limit"] == pytest.approx(
        expected_sa, rel=1e-9
    )
    nf = values["mech.fatigue.goodman.factor_of_safety"]
    assert nf == pytest.approx(2.207, rel=1e-3)
    assert nf == pytest.approx(2.21, rel=2e-3)


def test_goodman_factor_of_safety_pure_alternating_degenerates_cleanly():
    """sigma_m=0 (pure alternating): the load-line ratio r is
    infinite, so the direction returns the pure-alternating limit
    (Sa_limit=Se, Sm_limit=0, nf=Se/sigma_a) instead of dividing by
    zero -- a real physical loading case, not a domain violation."""
    _info, fn = _solvers()["mech.fatigue.fatigue_goodman_factor_of_safety"]
    se = 218.8e6
    sigma_a = 100.0e6
    result = fn(
        {
            "mech.fatigue.goodman.se": se,
            "mech.fatigue.goodman.sut": 630.0e6,
            "mech.fatigue.goodman.sigma_a": sigma_a,
            "mech.fatigue.goodman.sigma_m": 0.0,
        }
    )
    assert result.is_ok
    values = result.danger_ok.values
    assert values["mech.fatigue.goodman.sa_limit"] == pytest.approx(se, rel=1e-9)
    assert values["mech.fatigue.goodman.sm_limit"] == 0.0
    assert values["mech.fatigue.goodman.factor_of_safety"] == pytest.approx(
        se / sigma_a, rel=1e-9
    )


def test_goodman_factor_of_safety_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["mech.fatigue.fatigue_goodman_factor_of_safety"]
    result = fn(
        {
            "mech.fatigue.goodman.se": 0.0,
            "mech.fatigue.goodman.sut": 630.0e6,
            "mech.fatigue.goodman.sigma_a": 73.6e6,
            "mech.fatigue.goodman.sigma_m": 73.6e6,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_goodman_factor_of_safety_negative_mean_stress_is_honest_indeterminate():
    _info, fn = _solvers()["mech.fatigue.fatigue_goodman_factor_of_safety"]
    result = fn(
        {
            "mech.fatigue.goodman.se": 218.8e6,
            "mech.fatigue.goodman.sut": 630.0e6,
            "mech.fatigue.goodman.sigma_a": 73.6e6,
            "mech.fatigue.goodman.sigma_m": -1.0e6,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
