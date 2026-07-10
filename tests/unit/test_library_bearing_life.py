from __future__ import annotations

"""WO-24 deliverable 3 tests: known-answer/hand-computed unit tests
for the registered `mech.bearing.*` ISO 281 basic rating-life
directions (`python/feldspar/library/bearing_life.py`,
docs/benchmarks-memo.md sec. 11), called THROUGH the
`SolverRegistry`/`SolveFn` protocol. Rating-record shape (`C`, `C0`)
mirrors lithos:stdlib/std.bearings/records/deep_groove_ball.toml
(`dynamic_load_kn`/`static_load_kn`, read-only reference)."""

import pytest

from feldspar.library.bearing_life import register
from feldspar.solve import SolverRegistry


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    return registry


def _solvers() -> dict:
    registry = _registry()
    return {info.solver_id: (info, fn) for info, fn in registry}


# ---------------------------------------------------------------------------
# 11.1 -- basic L10, ball bearing (p=3)
# ---------------------------------------------------------------------------


def test_l10_ball_matches_hand_computed():
    """Memo sec. 11.1: 6205-class record, C=14,000 N (14.0 kN per
    lithos std.bearings), P=2,000 N -> L10=(14000/2000)^3=343.0
    million revolutions (exact algebra)."""
    _info, fn = _solvers()["mech.bearing.bearing_basic_rating_life_l10_ball"]
    result = fn(
        {
            "mech.bearing.dynamic_rating": 14_000.0,
            "mech.bearing.equivalent_load": 2_000.0,
        }
    )
    assert result.is_ok
    got = result.danger_ok.values["mech.bearing.l10"]
    assert got == pytest.approx(343.0, rel=1e-9)


def test_l10_ball_nonpositive_rating_is_honest_indeterminate():
    _info, fn = _solvers()["mech.bearing.bearing_basic_rating_life_l10_ball"]
    result = fn(
        {
            "mech.bearing.dynamic_rating": 0.0,
            "mech.bearing.equivalent_load": 2_000.0,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_l10_ball_nonpositive_load_is_honest_indeterminate():
    _info, fn = _solvers()["mech.bearing.bearing_basic_rating_life_l10_ball"]
    result = fn(
        {
            "mech.bearing.dynamic_rating": 14_000.0,
            "mech.bearing.equivalent_load": 0.0,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# 11.2 -- basic L10, roller bearing (p=10/3)
# ---------------------------------------------------------------------------


def test_l10_roller_matches_hand_computed():
    """Memo sec. 11.2: C=50,000 N, P=10,000 N ->
    L10=(50000/10000)^(10/3)=5^(10/3)=213.747... million revolutions
    (exact algebra, tol rel=1e-6)."""
    _info, fn = _solvers()["mech.bearing.bearing_basic_rating_life_l10_roller"]
    expected = (50_000.0 / 10_000.0) ** (10.0 / 3.0)
    result = fn(
        {
            "mech.bearing.dynamic_rating": 50_000.0,
            "mech.bearing.equivalent_load": 10_000.0,
        }
    )
    assert result.is_ok
    got = result.danger_ok.values["mech.bearing.l10"]
    assert got == pytest.approx(expected, rel=1e-9)
    assert got == pytest.approx(213.7470, rel=1e-4)


def test_l10_roller_nonpositive_rating_is_honest_indeterminate():
    _info, fn = _solvers()["mech.bearing.bearing_basic_rating_life_l10_roller"]
    result = fn(
        {
            "mech.bearing.dynamic_rating": -1.0,
            "mech.bearing.equivalent_load": 10_000.0,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# ---------------------------------------------------------------------------
# 11.3 -- L10 -> L10h at constant speed
# ---------------------------------------------------------------------------


def test_l10h_matches_hand_computed():
    """Memo sec. 11.3: L10=343.0 million rev, n=1,800 rpm ->
    L10h = 343.0e6 / (60*1800) = 3,175.9 hours (exact algebra)."""
    _info, fn = _solvers()["mech.bearing.bearing_basic_rating_life_l10h"]
    l10 = 343.0
    n = 1_800.0
    expected = l10 * 1.0e6 / (60.0 * n)
    result = fn(
        {
            "mech.bearing.l10": l10,
            "mech.bearing.speed_rpm": n,
        }
    )
    assert result.is_ok
    got = result.danger_ok.values["mech.bearing.l10h"]
    assert got == pytest.approx(expected, rel=1e-9)
    assert got == pytest.approx(3_175.93, rel=1e-4)


def test_l10h_nonpositive_l10_is_honest_indeterminate():
    _info, fn = _solvers()["mech.bearing.bearing_basic_rating_life_l10h"]
    result = fn({"mech.bearing.l10": 0.0, "mech.bearing.speed_rpm": 1_800.0})
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_l10h_nonpositive_speed_is_honest_indeterminate():
    _info, fn = _solvers()["mech.bearing.bearing_basic_rating_life_l10h"]
    result = fn({"mech.bearing.l10": 343.0, "mech.bearing.speed_rpm": 0.0})
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_l10_then_l10h_composed_matches_hand_computed():
    """Chains the ball-L10 direction into the L10h direction (same
    caller-composition pattern the module's own docstring describes)
    -- C=14000 N, P=2000 N, n=1800 rpm -> L10=343.0, L10h=3175.93 h."""
    solvers = _solvers()
    _info_a, fn_a = solvers["mech.bearing.bearing_basic_rating_life_l10_ball"]
    _info_b, fn_b = solvers["mech.bearing.bearing_basic_rating_life_l10h"]
    l10_result = fn_a(
        {
            "mech.bearing.dynamic_rating": 14_000.0,
            "mech.bearing.equivalent_load": 2_000.0,
        }
    )
    assert l10_result.is_ok
    l10 = l10_result.danger_ok.values["mech.bearing.l10"]
    l10h_result = fn_b({"mech.bearing.l10": l10, "mech.bearing.speed_rpm": 1_800.0})
    assert l10h_result.is_ok
    got = l10h_result.danger_ok.values["mech.bearing.l10h"]
    assert got == pytest.approx(3_175.93, rel=1e-4)
