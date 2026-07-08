from __future__ import annotations

"""WO-08 tests: two-mesh Richardson extrapolation (`python/feldspar/fea/richardson.py`).

Exercises the normal extrapolation path, the conservative fallback
trigger (correction magnitude exceeding the raw coarse-fine delta), and
the eps/order_used invariants that must hold in both paths."""

import math

import pytest

from feldspar.fea.richardson import richardson_extrapolate


def test_converging_pair_extrapolates_closer_to_true_value():
    """value_h=1.030, value_h2=1.010, converged value ~1.000 (theoretical
    order p=2.0): the h/2 delta should shrink by ~4x from the h delta,
    consistent with a converging pair, so the extrapolated result should
    land closer to 1.000 than value_h2 alone, with no fallback."""
    value_h = 1.030
    value_h2 = 1.010
    converged = 1.000
    result = richardson_extrapolate(value_h, value_h2, order=2.0)

    assert result.fallback_used is False
    assert abs(result.extrapolated - converged) < abs(value_h2 - converged)
    assert result.eps > 0.0
    assert result.order_used == 2.0


def test_low_order_triggers_conservative_fallback():
    """With order=2.0, the correction is always exactly 1/3 of the raw
    delta (2**2 - 1 = 3), so it can never exceed the raw delta and the
    fallback can never trigger at the theoretical element order. To
    construct a concrete adversarial case we drop `order` toward 1.0:
    at order=1.0, 2**order - 1 = 1.0, so correction == raw_delta exactly
    (not >); pushing order below 1.0 (order=0.5) gives
    2**0.5 - 1 ~= 0.4142, so |correction| = raw_delta / 0.4142 ~= 2.41 *
    raw_delta, which strictly exceeds raw_delta and must trigger the
    fallback. This models an "implausible order for the element" case
    within the meaning of the contract."""
    value_h = 1.030
    value_h2 = 1.010
    raw_delta = abs(value_h2 - value_h)

    result = richardson_extrapolate(value_h, value_h2, order=0.5)

    assert result.fallback_used is True
    assert result.extrapolated == value_h2
    assert result.eps == pytest.approx(raw_delta)
    assert result.order_used == 0.5


def test_eps_is_always_nonnegative_and_finite():
    """Across both the normal and fallback paths, eps must be a
    non-negative finite number -- it feeds directly into BudgetExceeded
    comparisons downstream and must never be NaN/inf/negative."""
    normal = richardson_extrapolate(1.030, 1.010, order=2.0)
    fallback = richardson_extrapolate(1.030, 1.010, order=0.5)

    for result in (normal, fallback):
        assert result.eps >= 0.0
        assert math.isfinite(result.eps)


def test_order_used_is_always_reported():
    """order_used must reflect the fixed theoretical order passed in,
    even when the fallback path fires and discards the extrapolation
    correction itself."""
    normal = richardson_extrapolate(1.030, 1.010, order=2.0)
    fallback = richardson_extrapolate(1.030, 1.010, order=0.5)

    assert normal.order_used == 2.0
    assert fallback.order_used == 0.5
