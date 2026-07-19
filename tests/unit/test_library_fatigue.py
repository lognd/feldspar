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

import hashlib
import json
import math
from typing import Dict

import pytest
from typani import Err, Ok

from feldspar.library.fatigue import MINER_SPECTRUM_PORT, register
from feldspar.solve import PayloadRef, SolveError, SolverRegistry


class DictResolver:
    """In-memory orchestrator store stand-in (D96/OPEN-2 handle);
    mirrors `tests/unit/test_library_struct.py`'s fixture verbatim."""

    def __init__(self) -> None:
        self._blobs: Dict[str, bytes] = {}

    def store(self, kind: str, content: bytes, origin: str) -> PayloadRef:
        digest = hashlib.sha256(content).hexdigest()
        self._blobs[digest] = content
        return PayloadRef(kind=kind, digest=digest, origin=origin)

    def resolve(self, ref: PayloadRef):
        blob = self._blobs.get(ref.digest)
        if blob is None:
            return Err(SolveError.DanglingDigest(digest=ref.digest))
        return Ok(blob)


def _registry(resolver=None) -> SolverRegistry:
    registry = SolverRegistry()
    register(registry, resolver if resolver is not None else DictResolver())
    return registry


def _solvers(resolver=None) -> dict:
    registry = _registry(resolver)
    return {info.solver_id: (info, fn) for info, fn in registry}


# ---------------------------------------------------------------------------
# fatigue_endurance_limit_baseline: Se' = 0.5*Sut
# ---------------------------------------------------------------------------


# frob:tests python/feldspar/mech/fatigue.py::fatigue_endurance_limit_baseline kind="unit"
def test_baseline_endurance_limit_matches_hand_computed():
    """Sut=630e6 Pa -> Se' = 0.5*630e6 = 315e6 Pa."""
    _info, fn = _solvers()["mech.fatigue.fatigue_endurance_limit_baseline"]
    result = fn({"mech.fatigue.baseline.sut": 630.0e6})
    assert result.is_ok
    assert result.danger_ok.values["mech.fatigue.baseline.se_prime"] == pytest.approx(
        315.0e6, rel=1e-9
    )


# frob:tests python/feldspar/mech/fatigue.py::fatigue_marin_surface_factor kind="unit"
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


# frob:tests python/feldspar/mech/fatigue.py::fatigue_marin_endurance_limit kind="unit"
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


# ---------------------------------------------------------------------------
# fatigue_gerber_factor_of_safety: Gerber parabola (WO-111), Table 6-7
# ---------------------------------------------------------------------------


def test_gerber_factor_of_safety_matches_hand_computed():
    """Se=100e6, Sut=400e6, sigma_a=sigma_m=50e6 ->
    nf = 0.5*(8)^2*(0.5)*(-1+sqrt(1+0.25)) = 16*(sqrt(1.25)-1) = 1.888544."""
    _info, fn = _solvers()["mech.fatigue.fatigue_gerber_factor_of_safety"]
    result = fn(
        {
            "mech.fatigue.gerber.se": 100.0e6,
            "mech.fatigue.gerber.sut": 400.0e6,
            "mech.fatigue.gerber.sigma_a": 50.0e6,
            "mech.fatigue.gerber.sigma_m": 50.0e6,
        }
    )
    assert result.is_ok
    expected = 16.0 * (math.sqrt(1.25) - 1.0)
    assert result.danger_ok.values[
        "mech.fatigue.gerber.factor_of_safety"
    ] == pytest.approx(expected, rel=1e-9)


def test_gerber_less_conservative_than_goodman():
    """Published relationship: for the same stresses the Gerber parabola
    gives a factor of safety >= the modified-Goodman line (Gerber fits
    the failure data less conservatively). Independent cross-check."""
    inputs = {"se": 100.0e6, "sut": 400.0e6, "sigma_a": 50.0e6, "sigma_m": 50.0e6}
    _gi, gfn = _solvers()["mech.fatigue.fatigue_gerber_factor_of_safety"]
    _di, dfn = _solvers()["mech.fatigue.fatigue_goodman_factor_of_safety"]
    nf_gerber = gfn(
        {f"mech.fatigue.gerber.{k}": v for k, v in inputs.items()}
    ).danger_ok.values["mech.fatigue.gerber.factor_of_safety"]
    nf_goodman = dfn(
        {f"mech.fatigue.goodman.{k}": v for k, v in inputs.items()}
    ).danger_ok.values["mech.fatigue.goodman.factor_of_safety"]
    assert nf_gerber > nf_goodman


def test_gerber_pure_alternating_matches_goodman_endpoint():
    """sigma_m=0 -> both criteria share the endpoint nf = Se/sigma_a."""
    _info, fn = _solvers()["mech.fatigue.fatigue_gerber_factor_of_safety"]
    result = fn(
        {
            "mech.fatigue.gerber.se": 100.0e6,
            "mech.fatigue.gerber.sut": 400.0e6,
            "mech.fatigue.gerber.sigma_a": 50.0e6,
            "mech.fatigue.gerber.sigma_m": 0.0,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "mech.fatigue.gerber.factor_of_safety"
    ] == pytest.approx(2.0, rel=1e-9)


def test_gerber_negative_mean_stress_is_honest_indeterminate():
    _info, fn = _solvers()["mech.fatigue.fatigue_gerber_factor_of_safety"]
    result = fn(
        {
            "mech.fatigue.gerber.se": 100.0e6,
            "mech.fatigue.gerber.sut": 400.0e6,
            "mech.fatigue.gerber.sigma_a": 50.0e6,
            "mech.fatigue.gerber.sigma_m": -1.0e6,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# fatigue_sn_cycles_to_failure: eqs. 6-13/6-14 log-log S-N knee line
# (WO111b, lithos WO-110-F6/F4) -- ANALYTIC SELF-CHECK calibration
# (docs/benchmarks-memo.md sec. 20.1): the knee line's own two defining
# boundary conditions, checked as an exact algebraic identity, not a
# transcribed textbook number.
# ---------------------------------------------------------------------------

_SN_SUT = 700.0e6
_SN_SE = 350.0e6
_SN_F = 0.9
_SN_KNEE = _SN_F * _SN_SUT  # 630 MPa


def test_sn_cycles_to_failure_at_knee_is_1000_by_construction():
    """sigma_a = f*Sut (the knee point) -> N = 1e3 EXACTLY, for any
    valid (Sut, Se, f) -- the log-log line's own defining condition
    (docs/benchmarks-memo.md sec. 20.1 derivation)."""
    _info, fn = _solvers()["mech.fatigue.fatigue_sn_cycles_to_failure"]
    result = fn(
        {
            "mech.fatigue.sn.sigma_a": _SN_KNEE,
            "mech.fatigue.sn.sut": _SN_SUT,
            "mech.fatigue.sn.se": _SN_SE,
            "mech.fatigue.sn.f": _SN_F,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "mech.fatigue.sn.cycles_to_failure"
    ] == pytest.approx(1.0e3, rel=1e-9)


def test_sn_cycles_to_failure_at_se_is_1e6_by_construction():
    """sigma_a = Se -> N = 1e6 EXACTLY, the line's other defining
    point."""
    _info, fn = _solvers()["mech.fatigue.fatigue_sn_cycles_to_failure"]
    result = fn(
        {
            "mech.fatigue.sn.sigma_a": _SN_SE,
            "mech.fatigue.sn.sut": _SN_SUT,
            "mech.fatigue.sn.se": _SN_SE,
            "mech.fatigue.sn.f": _SN_F,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "mech.fatigue.sn.cycles_to_failure"
    ] == pytest.approx(1.0e6, rel=1e-6)


def test_sn_cycles_to_failure_midpoint_matches_hand_computed():
    """A concrete third point, hand-computed from the SAME closed form
    (not an independent source -- an internal-consistency check that
    the registered direction reproduces its own documented algebra)."""
    _info, fn = _solvers()["mech.fatigue.fatigue_sn_cycles_to_failure"]
    sigma_a = (_SN_KNEE + _SN_SE) / 2.0
    a = (_SN_KNEE**2) / _SN_SE
    b = -(1.0 / 3.0) * math.log10(_SN_KNEE / _SN_SE)
    expected = (sigma_a / a) ** (1.0 / b)
    assert expected == pytest.approx(19172.6, rel=1e-3)
    result = fn(
        {
            "mech.fatigue.sn.sigma_a": sigma_a,
            "mech.fatigue.sn.sut": _SN_SUT,
            "mech.fatigue.sn.se": _SN_SE,
            "mech.fatigue.sn.f": _SN_F,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values[
        "mech.fatigue.sn.cycles_to_failure"
    ] == pytest.approx(expected, rel=1e-9)


# frob:tests python/feldspar/mech/fatigue.py::fatigue_sn_cycles_to_failure kind="unit"
def test_sn_cycles_to_failure_outside_knee_range_is_honest_indeterminate():
    """A stress far above the knee drives N below 1e3 -- outside the
    line's honest validity range (named cut)."""
    _info, fn = _solvers()["mech.fatigue.fatigue_sn_cycles_to_failure"]
    result = fn(
        {
            "mech.fatigue.sn.sigma_a": _SN_SUT,  # well above the knee
            "mech.fatigue.sn.sut": _SN_SUT,
            "mech.fatigue.sn.se": _SN_SE,
            "mech.fatigue.sn.f": _SN_F,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_sn_cycles_to_failure_degenerate_knee_is_honest_indeterminate():
    """f*Sut <= Se: not a real knee line (non-positive slope)."""
    _info, fn = _solvers()["mech.fatigue.fatigue_sn_cycles_to_failure"]
    result = fn(
        {
            "mech.fatigue.sn.sigma_a": 400.0e6,
            "mech.fatigue.sn.sut": _SN_SUT,
            "mech.fatigue.sn.se": _SN_KNEE,  # se == f*sut, degenerate
            "mech.fatigue.sn.f": _SN_F,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# mech.fatigue.miner_damage: eq. 6-58 Miner's rule over a declared
# load-block spectrum payload (WO111b, lithos WO-110-F6/F4)
# ---------------------------------------------------------------------------


def _store_spectrum(resolver: DictResolver, sigma_a: list, cycles: list) -> PayloadRef:
    content = json.dumps({"sigma_a": sigma_a, "cycles": cycles}).encode()
    return resolver.store("spectrum", content, "test_library_fatigue")


def test_miner_damage_single_block_at_life_is_1_by_construction():
    """ANALYTIC SELF-CHECK (docs/benchmarks-memo.md sec. 20.2): a single
    block whose applied cycle count equals its OWN S-N life (n = N_f)
    must give D = 1.0 exactly -- Miner's rule's own defining boundary,
    not a transcribed textbook number."""
    resolver = DictResolver()
    registry = _registry(resolver)
    solvers = {info.solver_id: (info, fn) for info, fn in registry}
    _info, fn = solvers["mech.fatigue.miner_damage"]
    a = (_SN_KNEE**2) / _SN_SE
    b = -(1.0 / 3.0) * math.log10(_SN_KNEE / _SN_SE)
    sigma_a = (_SN_KNEE + _SN_SE) / 2.0
    n_life = (sigma_a / a) ** (1.0 / b)
    ref = _store_spectrum(resolver, [sigma_a], [n_life])
    result = fn(
        {
            "mech.fatigue.miner.sut": _SN_SUT,
            "mech.fatigue.miner.se": _SN_SE,
            "mech.fatigue.miner.f": _SN_F,
            MINER_SPECTRUM_PORT: ref,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["mech.fatigue.miner.damage"] == pytest.approx(
        1.0, rel=1e-9
    )


def test_miner_damage_accumulates_across_blocks():
    """Two blocks each at half their own life sum to D = 1.0 (linear
    superposition -- eq. 6-58's own defining property)."""
    resolver = DictResolver()
    registry = _registry(resolver)
    solvers = {info.solver_id: (info, fn) for info, fn in registry}
    _info, fn = solvers["mech.fatigue.miner_damage"]
    a = (_SN_KNEE**2) / _SN_SE
    b = -(1.0 / 3.0) * math.log10(_SN_KNEE / _SN_SE)
    sigma_a1, sigma_a2 = _SN_KNEE, (_SN_KNEE + _SN_SE) / 2.0
    n_life1 = (sigma_a1 / a) ** (1.0 / b)
    n_life2 = (sigma_a2 / a) ** (1.0 / b)
    ref = _store_spectrum(
        resolver, [sigma_a1, sigma_a2], [n_life1 / 2.0, n_life2 / 2.0]
    )
    result = fn(
        {
            "mech.fatigue.miner.sut": _SN_SUT,
            "mech.fatigue.miner.se": _SN_SE,
            "mech.fatigue.miner.f": _SN_F,
            MINER_SPECTRUM_PORT: ref,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["mech.fatigue.miner.damage"] == pytest.approx(
        1.0, rel=1e-9
    )


def test_miner_damage_below_endurance_limit_contributes_zero():
    """A block at or below Se is infinite life -- zero damage
    contribution (Shigley sec. 6-16's stated convention)."""
    resolver = DictResolver()
    registry = _registry(resolver)
    solvers = {info.solver_id: (info, fn) for info, fn in registry}
    _info, fn = solvers["mech.fatigue.miner_damage"]
    ref = _store_spectrum(resolver, [_SN_SE * 0.5], [1.0e9])
    result = fn(
        {
            "mech.fatigue.miner.sut": _SN_SUT,
            "mech.fatigue.miner.se": _SN_SE,
            "mech.fatigue.miner.f": _SN_F,
            MINER_SPECTRUM_PORT: ref,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["mech.fatigue.miner.damage"] == 0.0


def test_miner_damage_mismatched_block_lengths_is_honest_indeterminate():
    resolver = DictResolver()
    registry = _registry(resolver)
    solvers = {info.solver_id: (info, fn) for info, fn in registry}
    _info, fn = solvers["mech.fatigue.miner_damage"]
    ref = _store_spectrum(resolver, [_SN_KNEE, _SN_SE], [1.0e3])
    result = fn(
        {
            "mech.fatigue.miner.sut": _SN_SUT,
            "mech.fatigue.miner.se": _SN_SE,
            "mech.fatigue.miner.f": _SN_F,
            MINER_SPECTRUM_PORT: ref,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
