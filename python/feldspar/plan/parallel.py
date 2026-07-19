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
completion order) -- so the RETURNED VALUE is bit-identical to the
serial path at any `thread_count`. The FIRST corner (in enumeration
order, never arrival order) to report an `Err` is authoritative, exactly
matching `corner_sweep`'s short-circuit-on-first-corner-err contract
(02-edge-cases WO-04).

This identical-return-value guarantee does NOT extend to `fn`'s SIDE
EFFECTS (L3, cycle-29 audit): corner solves may write to
`PayloadStepCache` or shell out to ccx/gmsh, and once a corner's work
is handed to the thread pool it cannot be un-run. `thread_count > 1`
best-effort avoids dispatching corners still queued once an earlier
(in enumeration order) corner's `Err` is already known -- futures not
yet started are cancelled -- but corners already RUNNING when the
`Err` is discovered still complete their side effects. Only
`thread_count <= 1` gives the serial path's true short-circuit (zero
extra side effects)."""

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Mapping, TypeVar

from typani.result import Err, Ok, Result

from feldspar.core import Interval, enumerate_corners, hull_from_results
from feldspar.logging_setup import get_logger

__all__ = ["parallel_corner_sweep"]

_log = get_logger(__name__)

_E = TypeVar("_E")


# frob:doc docs/modules/plan.md#plan_parallel
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
            # Submit all corners up front, then block on each future IN
            # ENUMERATION ORDER (matching the serial path's fold order,
            # FINV-9) -- as soon as an `Err` is discovered, cancel every
            # later future not yet started. `Future.cancel()`
            # is a no-op once a worker has picked the task up, so this
            # is best-effort, not a true short-circuit (L3, cycle-29
            # audit): it stops corners still queued behind the failing
            # one, it cannot stop ones already mid-flight.
            futures = [executor.submit(fn, corner) for corner in corners]
            results = []
            for idx, future in enumerate(futures):
                result = future.result()
                if result.is_err:
                    for later in futures[idx + 1 :]:
                        later.cancel()
                    return Err(result.danger_err)
                results.append(result)

    outputs = [result.danger_ok for result in results]
    return Ok(hull_from_results(outputs))
