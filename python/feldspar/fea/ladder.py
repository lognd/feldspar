from __future__ import annotations

"""`climb_richardson_ladder`/`RungCache` -- the WO-13 (09 sec. 3)
deterministic refinement ladder for a self-meshing Richardson direction
(`fea/solver.py`'s `cantilever`): given an ORDERED sequence of rungs
(coarsest first) and a way to run one rung, climbs rung-by-rung,
Richardson-pairing each new rung against the previous one, and STOPS
the first time the pair's eps fits the caller's remaining budget --
same budget, same rungs, same stop (the sec. 3 determinism contract).

Per-rung caching (`RungCache`) is what makes "an h+h/2 Richardson pair
is two cache entries; a looser later budget reuses h and skips h/2"
literally true: each rung's raw scalar result is cached independently,
keyed on the solver id/version/rung settings/scalar box, so a repeat
climb over the SAME box that only needs the coarser rungs never re-runs
the (expensive) finer ones -- and a climb that ALSO needs a finer rung
still reuses every coarser rung's cached value instead of re-running
gmsh/ccx for it."""

from typing import Callable, Dict, Optional, Sequence, Tuple, TypeVar

from typani.result import Err, Ok, Result

from feldspar.fea.richardson import (
    SAFETY_FACTOR,
    THEORETICAL_ORDER,
    richardson_extrapolate,
)
from feldspar.logging_setup import get_logger
from feldspar.solve.digest import canonical_digest
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["RungCache", "climb_richardson_ladder"]

#: A rung specification is opaque to the ladder climber (typically a
#: `feldspar.fea.mesh.MeshSettings`, but the mechanism is family-
#: agnostic); this TypeVar just lets `climb_richardson_ladder` forward
#: the caller's concrete rung type through to `run_rung` unchanged.
RungT = TypeVar("RungT")


class RungCache:
    """In-process cache from `(solver_id, version, rung_settings, box)`
    to a rung's raw scalar value. Lighter than the WO-12
    `PayloadStepCache` (04-routing "Per-payload step cache") on purpose:
    a ladder rung's OWN scalar mesh run carries no payload refs at all,
    so this is a dedicated rung-grain cache alongside it, not a
    replacement -- `hits`/`misses` are exposed as plain counters so
    tests can assert the WO-13 sec. 3 reuse scenario (a looser later
    budget hits on the coarser rungs and never re-runs the finer
    ones)."""

    def __init__(self) -> None:
        self._store: Dict[str, float] = {}
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(solver_id: str, version: str, rung_settings: object, box: object) -> str:
        return canonical_digest(
            {
                "solver_id": solver_id,
                "version": version,
                "rung_settings": rung_settings,
                "box": box,
            }
        )

    def get(self, key: str) -> Optional[float]:
        value = self._store.get(key)
        if value is None:
            self.misses += 1
            _log.debug("RungCache miss: key=%s", key)
        else:
            self.hits += 1
            _log.debug("RungCache hit: key=%s", key)
        return value

    def put(self, key: str, value: float) -> None:
        self._store[key] = value


def climb_richardson_ladder(
    rungs: Sequence[RungT],
    run_rung: Callable[[RungT], "Result[float, SolveError]"],
    eps_budget: Optional[float],
    *,
    solver_id: str,
    version: str,
    box: object,
    rung_cache: Optional[RungCache] = None,
    order: float = THEORETICAL_ORDER,
    safety_factor: float = SAFETY_FACTOR,
) -> "Result[Tuple[float, float, int], SolveError]":
    """Climbs `rungs` (coarsest first) via two-mesh Richardson pairing,
    stopping the first time a pair's eps fits `eps_budget`.

    `eps_budget=None` means "no budget context" (a bare `execute()` call
    with no caller budget, 04-routing "Execution"): the climb then runs
    EXACTLY the first two rungs -- the pre-WO-13 fixed h/h2 behavior --
    and returns whatever eps that pair reports, never seeking further
    (there is no budget to seek against).

    Requires at least 2 rungs (Richardson needs a pair; a single rung
    has no error estimate). `SolveError.LadderExhausted(best_eps,
    budget, rungs_tried)` is returned if every rung is climbed and the
    tightest pair still busts the budget -- honest indeterminate, never
    a silent downgrade.

    A non-monotone ladder (a finer rung's pair reporting a WORSE eps
    than a coarser rung's pair already did) is a solver/ladder-policy
    bug, not a value the caller can act on -- loud `RuntimeError`, per
    the house rule that only recoverable states get `Result` values.

    Returns `(extrapolated_value, eps, rungs_run)` on success."""
    if len(rungs) < 2:
        raise RuntimeError(
            f"climb_richardson_ladder: {solver_id} declares {len(rungs)} rung(s); "
            "at least 2 are required for a Richardson pair"
        )

    def _run(rung: RungT) -> "Result[float, SolveError]":
        if rung_cache is None:
            return run_rung(rung)
        key = RungCache.key(solver_id, version, rung, box)
        cached = rung_cache.get(key)
        if cached is not None:
            return Ok(cached)
        result = run_rung(rung)
        if result.is_ok:
            rung_cache.put(key, result.danger_ok)
        return result

    first = _run(rungs[0])
    if first.is_err:
        return Err(first.danger_err)
    prev_value = first.danger_ok
    prev_eps: Optional[float] = None

    for i in range(1, len(rungs)):
        current = _run(rungs[i])
        if current.is_err:
            return Err(current.danger_err)
        value = current.danger_ok

        pair = richardson_extrapolate(
            prev_value, value, order=order, safety_factor=safety_factor
        )

        if prev_eps is not None and pair.eps > prev_eps:
            raise RuntimeError(
                f"climb_richardson_ladder: {solver_id} produced a NON-MONOTONE "
                f"eps ladder (rung {i} pair eps={pair.eps!r} exceeds the "
                f"previous pair's eps={prev_eps!r}) -- the declared ladder "
                "policy is a bug, not a caller-actionable error"
            )

        _log.info(
            "climb_richardson_ladder: %s rung %d/%d eps=%s (budget=%s)",
            solver_id,
            i,
            len(rungs) - 1,
            pair.eps,
            eps_budget,
        )

        if eps_budget is None:
            # No budget context: pre-WO-13 fixed-pair behavior -- stop
            # after exactly the first pair.
            return Ok((pair.extrapolated, pair.eps, i + 1))

        if pair.eps <= eps_budget:
            _log.info(
                "climb_richardson_ladder: %s budget met at rung %d "
                "(eps=%s <= budget=%s)",
                solver_id,
                i,
                pair.eps,
                eps_budget,
            )
            return Ok((pair.extrapolated, pair.eps, i + 1))

        prev_value = value
        prev_eps = pair.eps

    _log.warning(
        "climb_richardson_ladder: %s exhausted %d rungs without meeting "
        "budget=%s (best eps=%s)",
        solver_id,
        len(rungs),
        eps_budget,
        prev_eps,
    )
    return Err(
        SolveError.LadderExhausted(
            best_eps=prev_eps if prev_eps is not None else float("inf"),
            budget=eps_budget,
            rungs_tried=len(rungs),
        )
    )
