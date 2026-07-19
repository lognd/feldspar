from __future__ import annotations

"""WO-13 tests (09 sec. 3): `climb_richardson_ladder`/`RungCache` --
the deterministic budget-seeking ladder climb, its per-rung caching,
and the required 02-edge-cases rows (zero budget, budget met at rung
0, ladder exhaustion, non-monotone eps ladder)."""

import pytest
from typani import Err, Ok

from feldspar.fea.ladder import RungCache, climb_richardson_ladder
from feldspar.solve.errors import SolveError

# Four synthetic "rungs" (0..3, opaque to the climber) whose raw values
# converge like a real O(h^2) mesh refinement (each halving of h quarters
# the remaining error): value(i) = 16 * (1 - 4**-(i+1)).
_VALUES = [16.0 * (1.0 - 4.0 ** -(i + 1)) for i in range(4)]
_RUNGS = (0, 1, 2, 3)
# Expected Richardson pair eps at each climb step (order=2, safety=1.5):
# 1.5, 0.375, 0.09375 (decreasing by exactly 4x each rung, matching the
# theoretical O(h^2) order).
_EPS_AT_PAIR = {1: 1.5, 2: 0.375, 3: 0.09375}


def _run_rung_factory(calls=None):
    calls = [] if calls is None else calls

    def run_rung(rung):
        calls.append(rung)
        return Ok(_VALUES[rung])

    return run_rung, calls


def test_no_budget_context_runs_exactly_the_first_pair() -> None:
    run_rung, calls = _run_rung_factory()
    result = climb_richardson_ladder(
        _RUNGS, run_rung, None, solver_id="test.solver", version="1", box={}
    )
    assert result.is_ok
    extrapolated, eps, rungs_used = result.danger_ok
    assert rungs_used == 2
    assert eps == pytest.approx(_EPS_AT_PAIR[1])
    assert extrapolated == pytest.approx(16.0)
    assert calls == [0, 1]


def test_budget_met_at_rung_zero_needs_no_extra_climb() -> None:
    """A budget looser than the FIRST pair's eps stops there -- zero
    additional rungs beyond the mandatory pair (02-edge-cases: "budget
    met at rung 0")."""
    run_rung, calls = _run_rung_factory()
    result = climb_richardson_ladder(
        _RUNGS, run_rung, 2.0, solver_id="test.solver", version="1", box={}
    )
    assert result.is_ok
    _extrapolated, eps, rungs_used = result.danger_ok
    assert rungs_used == 2
    assert eps == pytest.approx(_EPS_AT_PAIR[1])
    assert calls == [0, 1]


def test_climbs_further_when_budget_demands_it() -> None:
    run_rung, calls = _run_rung_factory()
    result = climb_richardson_ladder(
        _RUNGS, run_rung, 0.5, solver_id="test.solver", version="1", box={}
    )
    assert result.is_ok
    _extrapolated, eps, rungs_used = result.danger_ok
    assert rungs_used == 3
    assert eps == pytest.approx(_EPS_AT_PAIR[2])
    assert calls == [0, 1, 2]


# frob:tests python/feldspar/solve/errors.py::SolveError.LadderExhausted kind="unit"
def test_zero_budget_exhausts_the_ladder() -> None:
    run_rung, _calls = _run_rung_factory()
    result = climb_richardson_ladder(
        _RUNGS, run_rung, 0.0, solver_id="test.solver", version="1", box={}
    )
    assert result.is_err
    error = result.danger_err
    assert isinstance(error, SolveError)
    assert error.kind == "LadderExhausted"
    assert error.rungs_tried == len(_RUNGS)
    assert error.budget == 0.0


def test_ladder_exhaustion_carries_best_eps_achieved() -> None:
    run_rung, _calls = _run_rung_factory()
    tight_budget = 0.05  # tighter than the finest declared pair (0.09375)
    result = climb_richardson_ladder(
        _RUNGS, run_rung, tight_budget, solver_id="test.solver", version="1", box={}
    )
    assert result.is_err
    error = result.danger_err
    assert error.kind == "LadderExhausted"
    assert error.best_eps == pytest.approx(_EPS_AT_PAIR[3])
    assert error.budget == tight_budget


def test_deterministic_twice() -> None:
    """Same budget -> same rungs -> same stop (09 sec. 3's determinism
    contract), run twice."""
    run_rung_1, calls_1 = _run_rung_factory()
    run_rung_2, calls_2 = _run_rung_factory()
    result_1 = climb_richardson_ladder(
        _RUNGS, run_rung_1, 0.2, solver_id="test.solver", version="1", box={"x": 1.0}
    )
    result_2 = climb_richardson_ladder(
        _RUNGS, run_rung_2, 0.2, solver_id="test.solver", version="1", box={"x": 1.0}
    )
    assert result_1.is_ok and result_2.is_ok
    assert result_1.danger_ok == result_2.danger_ok
    assert calls_1 == calls_2


# frob:tests python/feldspar/fea/ladder.py::climb_richardson_ladder kind="unit"
def test_requires_at_least_two_rungs() -> None:
    run_rung, _calls = _run_rung_factory()
    with pytest.raises(RuntimeError):
        climb_richardson_ladder(
            (0,), run_rung, None, solver_id="test.solver", version="1", box={}
        )


def test_non_monotone_ladder_raises_loudly() -> None:
    """A ladder whose eps gets WORSE at a finer rung is a solver/policy
    bug -- loud `RuntimeError`, never a `Result` value (02-edge-cases:
    "non-monotone eps ladder (a bug -> loud error)")."""
    # rung 0->1 pair converges tightly, rung 1->2 pair "un-converges"
    # (larger delta) -- a broken ladder policy.
    values = [10.0, 10.01, 10.5]

    def run_rung(rung):
        return Ok(values[rung])

    with pytest.raises(RuntimeError):
        climb_richardson_ladder(
            (0, 1, 2), run_rung, 1e-6, solver_id="test.solver", version="1", box={}
        )


def test_run_rung_error_propagates() -> None:
    def run_rung(rung):
        if rung == 1:
            return Err(SolveError.ToolMissing(tool="gmsh", guidance="install it"))
        return Ok(1.0)

    result = climb_richardson_ladder(
        _RUNGS, run_rung, 0.2, solver_id="test.solver", version="1", box={}
    )
    assert result.is_err
    assert result.danger_err.kind == "ToolMissing"


# ---------------------------------------------------------------------------
# RungCache: per-rung reuse (09 sec. 3 "an h+h/2 pair is two cache
# entries; a looser later budget reuses h and skips h/2").
# ---------------------------------------------------------------------------


def test_rung_cache_reuses_coarser_rungs_across_climbs() -> None:
    cache = RungCache()
    calls: list = []
    run_rung, _ = _run_rung_factory(calls)

    # First climb: a loose budget only needs rungs 0 and 1.
    first = climb_richardson_ladder(
        _RUNGS,
        run_rung,
        2.0,
        solver_id="test.solver",
        version="1",
        box={"x": 1.0},
        rung_cache=cache,
    )
    assert first.is_ok
    assert calls == [0, 1]
    assert cache.hits == 0
    assert cache.misses == 2

    # Second climb, SAME box: a tighter budget needs rung 2 as well --
    # rungs 0 and 1 must be served from cache, never re-run.
    second = climb_richardson_ladder(
        _RUNGS,
        run_rung,
        0.5,
        solver_id="test.solver",
        version="1",
        box={"x": 1.0},
        rung_cache=cache,
    )
    assert second.is_ok
    assert calls == [0, 1, 2]  # only rung 2 is a NEW call
    assert cache.hits == 2  # rungs 0 and 1 served from cache
    assert cache.misses == 3  # 2 from the first climb + 1 new (rung 2)


def test_rung_cache_keys_differ_by_box() -> None:
    cache = RungCache()
    calls: list = []
    run_rung, _ = _run_rung_factory(calls)

    climb_richardson_ladder(
        _RUNGS,
        run_rung,
        None,
        solver_id="test.solver",
        version="1",
        box={"x": 1.0},
        rung_cache=cache,
    )
    climb_richardson_ladder(
        _RUNGS,
        run_rung,
        None,
        solver_id="test.solver",
        version="1",
        box={"x": 2.0},  # different scalar box -> different cache key
        rung_cache=cache,
    )
    assert calls == [0, 1, 0, 1]
    assert cache.hits == 0
    assert cache.misses == 4
