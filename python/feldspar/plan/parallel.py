from __future__ import annotations

"""`parallel_corner_sweep` -- the WO-15 (09 sec. 6) parallel-dispatch
counterpart to `feldspar.core.corner_sweep`.

Real solver corner evaluation goes through a Python `SolveFn` callback
(GIL-bound), unlike the planner's pure-Rust sum-surrogate estimate
(WO-05, `search.rs`) -- so the only place additional cores actually help
here is the PYTHON dispatch of that callback across corners, not Rust
threading inside `corner_sweep` itself (a GIL-bound callback cannot be
called from a rayon worker thread). `thread_count <= 1` is the always-
present serial fallthrough (AD-10, 09 sec. 6): it runs exactly the same
code path as `feldspar.core.corner_sweep`, just split into its
enumerate/fold halves.

Determinism (FINV-9): corners are enumerated ONCE, in `enumerate_corners`
order; results are folded via `hull_from_results` in THAT SAME order
regardless of which worker finished a given corner first (a thread
pool's `map` preserves input order in its output, independent of
completion order) -- so the assembled hull is bit-identical to the
serial path at any `thread_count`. The FIRST corner (in enumeration
order, never arrival order) to report an `Err` is authoritative, exactly
matching `corner_sweep`'s short-circuit-on-first-corner-err contract
(02-edge-cases WO-04)."""

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Mapping, TypeVar

from typani.result import Err, Ok, Result

from feldspar.core import Interval, enumerate_corners, hull_from_results
from feldspar.logging_setup import get_logger

__all__ = ["parallel_corner_sweep"]

_log = get_logger(__name__)

_E = TypeVar("_E")


def parallel_corner_sweep(
    box: Mapping[str, Interval],
    fn: Callable[[Mapping[str, float]], "Result[Mapping[str, float], _E]"],
    thread_count: int = 1,
) -> "Result[Mapping[str, Interval], _E]":
    """Evaluates `fn` at every corner of `box` (same enumeration as
    `corner_sweep`) and hulls the results, dispatching the per-corner
    `fn` calls across `thread_count` worker threads when `thread_count
    > 1` (a configuration, not a build variant -- 09 sec. 6). `fn`'s own
    `Err` value passes through unchanged, exactly like `corner_sweep`.

    `thread_count <= 1` runs fully serially (no executor spun up at
    all) -- the fallthrough that must always exist on every platform.
    """
    corners = list(enumerate_corners(box))
    if not corners:
        return Ok(hull_from_results([]))

    if thread_count <= 1:
        # Serial fallthrough: short-circuits on the first corner's `Err`,
        # exactly like `corner_sweep` (never evaluates later corners).
        results = []
        for corner in corners:
            result = fn(corner)
            if result.is_err:
                return Err(result.danger_err)
            results.append(result)
    else:
        _log.info(
            "parallel_corner_sweep: dispatching %d corner(s) across %d thread(s)",
            len(corners),
            thread_count,
        )
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            # `Executor.map` yields results in the SAME order as the
            # input iterable (`corners`), independent of which worker
            # finishes first -- this is what keeps the fold order
            # identical to the serial path (FINV-9). Unlike the serial
            # path, ALL corners are dispatched eagerly (no short-circuit
            # mid-flight is possible once work is handed to the pool);
            # the value returned is still the FIRST-in-enumeration-order
            # `Err`, identical to the serial path's outcome.
            results = list(executor.map(fn, corners))
            for result in results:
                if result.is_err:
                    return Err(result.danger_err)

    outputs = [result.danger_ok for result in results]
    return Ok(hull_from_results(outputs))
