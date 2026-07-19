from __future__ import annotations

"""WO-04 Python-side tests: corner_sweep/inflate/total_error
(01-interfaces WO-04 section; FINV-4). Covers the WO-04 acceptance
criterion (a 3-input box hits 8 corners deduplicated and sorted; a
2-step toy route's inflate/total_error matches hand arithmetic) and the
02-edge-cases WO-04 rows exercisable from Python."""

import pytest
from typani import Err, Ok

from feldspar import core


# frob:tests crates/feldspar-py/src/propagation.rs::corner_sweep_py
def test_three_input_box_hits_eight_deduplicated_sorted_corners() -> None:
    calls: list[dict[str, float]] = []

    def fn(corner: dict) -> Ok:
        calls.append(dict(corner))
        return Ok({"y": corner["a"] + corner["b"] + corner["c"]})

    box = {
        "a": core.Interval(0.0, 1.0),
        "b": core.Interval(-1.0, 1.0),
        "c": core.Interval(10.0, 20.0),
    }
    result = core.corner_sweep(box, fn)

    assert result.is_ok
    assert len(calls) == 8
    # sorted (deterministic order): each corner is a strictly
    # non-decreasing lexicographic tuple relative to the previous one.
    tuples = [(c["a"], c["b"], c["c"]) for c in calls]
    assert tuples == sorted(tuples)
    # dedup: no duplicate corners
    assert len(set(tuples)) == 8


def test_degenerate_port_reduces_corner_count() -> None:
    """02-edge-cases WO-04: 3 interval inputs, 1 degenerate -> 4 corners."""
    calls = []

    def fn(corner: dict) -> Ok:
        calls.append(corner)
        return Ok({"y": 0.0})

    box = {
        "a": core.Interval(0.0, 1.0),
        "b": core.Interval(0.0, 1.0),
        "c": core.Interval(5.0, 5.0),
    }
    core.corner_sweep(box, fn)
    assert len(calls) == 4


def test_solver_err_at_one_corner_fails_whole_sweep() -> None:
    def fn(corner: dict):
        if corner["a"] == 1.0:
            return Err("boom at a=1.0")
        return Ok({"y": corner["a"]})

    box = {"a": core.Interval(0.0, 1.0)}
    result = core.corner_sweep(box, fn)
    assert result.is_err
    assert result.err == "boom at a=1.0"


# frob:tests crates/feldspar-py/src/propagation.rs::total_error_py
def test_accumulation_with_eps_zero_point_inputs_is_zero_exactly() -> None:
    box = {"x": core.Interval(3.0, 3.0)}
    result = core.corner_sweep(box, lambda c: Ok({"y": c["x"] * 2.0}))
    hull = result.danger_ok["y"]
    assert core.total_error(hull, 0.0) == 0.0


# frob:tests crates/feldspar-py/src/propagation.rs::inflate_py
def test_inflate_then_domain_check_uses_inflated_interval() -> None:
    """02-edge-cases WO-04: subset rule applies to the INFLATED interval."""
    point = core.Interval(5.0, 5.0)
    inflated = core.inflate(point, 0.5)
    domain = core.Domain({"x": core.Interval(4.0, 6.0)}, set())

    # The raw point is a subset of the domain box too (trivially), but
    # the INFLATED interval is what a real consuming step checks against
    # -- demonstrate it still passes here, and fails once inflated past
    # the box edge.
    assert domain.admits({"x": inflated}, set()).is_ok

    too_wide = core.inflate(point, 2.0)  # [3.0, 7.0], outside [4.0, 6.0]
    result = domain.admits({"x": too_wide}, set())
    assert result.is_err
    assert result.err.kind == "OutOfBox"


def test_gain_counterexample_matches_hand_arithmetic() -> None:
    """Acceptance: a 2-step toy route (gain != 1 second step) matches
    hand arithmetic; the audit A-1 gain-counterexample (02-edge-cases
    WO-04): target error tracks ~k*e via inflation, NOT ~e."""
    e = 0.1
    k = 1000.0
    step1_point = core.Interval(5.0, 5.0)  # step 1's exact output

    inflated = core.inflate(step1_point, e)
    assert inflated.lo == pytest.approx(5.0 - e)
    assert inflated.hi == pytest.approx(5.0 + e)

    box = {"x": inflated}
    result = core.corner_sweep(box, lambda c: Ok({"y": k * c["x"]}))
    hull = result.danger_ok["y"]

    target_error = core.total_error(hull, 0.0)
    assert target_error == pytest.approx(k * e)
    # Nowhere near the unsound eps-summation answer (~e = 0.1):
    assert abs(target_error - e) > 1.0


def test_non_monotone_flag_does_not_change_sweep_behavior() -> None:
    """02-edge-cases WO-04: non-monotone flag set -> sweep still runs;
    eps widening is the solver's declared duty, not corner_sweep's job
    (doc-tested here: corner_sweep has no monotonicity parameter at
    all -- it always just evaluates corners)."""
    box = {"x": core.Interval(-2.0, 2.0)}
    # x^2 is non-monotone over [-2, 2]; corner sweep only samples
    # endpoints (-2, 2) and hulls to [4, 4], MISSING the interior
    # minimum at x=0 -- exactly why non-monotone solvers must widen
    # their own declared eps (this function does not, and cannot,
    # detect or correct for that from here).
    result = core.corner_sweep(box, lambda c: Ok({"y": c["x"] ** 2}))
    hull = result.danger_ok["y"]
    assert (hull.lo, hull.hi) == (4.0, 4.0)
