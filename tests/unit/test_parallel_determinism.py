from __future__ import annotations

"""WO-15 (09 sec. 6, closes OPEN-9) determinism suite: serial and
parallel paths must be bit-identical at any thread count (FINV-9).
Covers `feldspar.plan.parallel.parallel_corner_sweep` against the
serial `feldspar.core.corner_sweep`, and `feldspar.calib.harness.
calibrate`'s `thread_count` knob against itself at different counts."""

import pytest
from typani import Err, Ok

from feldspar import core
from feldspar.calib.harness import calibrate
from feldspar.core import Accuracy, Domain, Interval
from feldspar.plan.parallel import parallel_corner_sweep
from feldspar.solve import EXACT, Citation, SolveOutput, SolverInfo, SolverRegistry


def _box() -> dict:
    return {
        "a": core.Interval(0.0, 1.0),
        "b": core.Interval(-2.0, 3.0),
        "c": core.Interval(-1.0, 1.0),
    }


def _fn(corner: dict) -> Ok:
    return Ok(
        {
            "y": corner["a"] + corner["b"] * corner["c"],
            "z": corner["a"] - corner["b"] + corner["c"],
        }
    )


@pytest.mark.parametrize("thread_count", [1, 2, 4, 8])
def test_parallel_corner_sweep_matches_serial_at_any_thread_count(
    thread_count: int,
) -> None:
    serial = core.corner_sweep(_box(), _fn)
    parallel = parallel_corner_sweep(_box(), _fn, thread_count=thread_count)
    assert serial.is_ok
    assert parallel.is_ok
    assert serial.danger_ok == parallel.danger_ok


# frob:tests python/feldspar/core.py::enumerate_corners kind="unit"
def test_parallel_corner_sweep_serial_fallthrough_short_circuits() -> None:
    """`thread_count<=1` must short-circuit on the FIRST corner's `Err`,
    exactly like `corner_sweep` -- never evaluating corners AFTER the
    erroring one, in enumeration order."""
    calls: list[dict] = []

    def failing_fn(corner: dict):
        calls.append(dict(corner))
        if corner["a"] == 0.0:
            return Err("boom")
        return Ok({"y": corner["a"]})

    box = {"a": core.Interval(0.0, 1.0)}
    result = parallel_corner_sweep(box, failing_fn, thread_count=1)
    assert result.is_err
    assert result.err == "boom"
    # a=0.0 sorts first (enumerate_corners); the a=1.0 corner is never
    # reached because the serial path stops at the first Err.
    assert len(calls) == 1


def test_parallel_corner_sweep_reports_first_in_order_err_at_any_thread_count() -> None:
    """The parallel path cannot short-circuit mid-flight (all corners are
    dispatched eagerly), but the reported `Err` is still the FIRST one in
    enumeration order, matching the serial outcome (02-edge-cases WO-04)."""

    def failing_fn(corner: dict):
        if corner["a"] == 1.0:
            return Err(f"boom at a={corner['a']}")
        return Ok({"y": corner["a"]})

    box = {"a": core.Interval(0.0, 1.0)}
    serial = core.corner_sweep(box, failing_fn)
    parallel = parallel_corner_sweep(box, failing_fn, thread_count=4)
    assert serial.is_err
    assert parallel.is_err
    assert serial.err == parallel.err


def test_parallel_corner_sweep_empty_box_matches_serial() -> None:
    """An empty box is one degenerate corner (empty dict), same as
    `corner_sweep`'s "all degenerate -> one corner" case."""

    def const_fn(_corner: dict) -> Ok:
        return Ok({"y": 42.0})

    result = parallel_corner_sweep({}, const_fn, thread_count=4)
    assert result.is_ok
    assert result.danger_ok["y"].lo == 42.0


def _calib_domain(lo: float, hi: float) -> Domain:
    return Domain(box={"x": Interval(lo, hi)})


def _calib_registry() -> SolverRegistry:
    """A tiny exact-vs-noisy two-solver registry (same shape as
    `test_calib.py`'s fixtures) purely to exercise `calibrate`'s
    threading knob."""
    registry = SolverRegistry()

    def exact_fn(inputs: dict):
        return Ok(SolveOutput(values={"y": 2.0 * inputs["x"]}))

    def noisy_fn(inputs: dict):
        return Ok(SolveOutput(values={"y": 2.0 * inputs["x"] + 0.001}))

    registry.register(
        SolverInfo(
            solver_id="calib_test.exact",
            namespace="test",
            version="1",
            inputs=("x",),
            outputs=("y",),
            domain=_calib_domain(0.0, 10.0),
            cost=1.0,
            accuracy={"y": EXACT},
            citations=(Citation(kind="handbook", ref="test ref"),),
            tier="closed_form",
            settings_digest="none",
        ),
        exact_fn,
    )
    registry.register(
        SolverInfo(
            solver_id="calib_test.noisy",
            namespace="test",
            version="1",
            inputs=("x",),
            outputs=("y",),
            domain=_calib_domain(0.0, 10.0),
            cost=1.0,
            accuracy={"y": Accuracy(0.01, 0.01)},
            citations=(Citation(kind="handbook", ref="test ref"),),
            tier="closed_form",
            settings_digest="none",
        ),
        noisy_fn,
    )
    registry.freeze()
    return registry


def test_calibrate_thread_count_does_not_change_the_digest() -> None:
    registry = _calib_registry()
    serial = calibrate(
        "calib_test.noisy",
        "calib_test.exact",
        registry,
        n_samples=32,
        seed=7,
        thread_count=1,
    )
    parallel = calibrate(
        "calib_test.noisy",
        "calib_test.exact",
        registry,
        n_samples=32,
        seed=7,
        thread_count=4,
    )
    assert serial.is_ok
    assert parallel.is_ok
    assert serial.danger_ok.digest == parallel.danger_ok.digest
    assert serial.danger_ok == parallel.danger_ok
