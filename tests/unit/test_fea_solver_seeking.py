from __future__ import annotations

"""WO-13 tests (09 sec. 3): `fea.static_deflection.cantilever`'s
budget-seeking wiring -- eps_seeking + the real ladder climb, WITHOUT
requiring gmsh/ccx (mocked at the `build_cantilever_mesh`/`ccx.run_ccx`/
`parse_dat_displacements`/`max_displacement_magnitude` seams, same
"never raise, real tool absence is a value" spirit as
`test_fea_solver.py`'s `ToolMissing` tests -- here we go one step
further and simulate SUCCESSFUL rungs to exercise the ladder itself).

Acceptance-bar-adjacent (WO-13): "the FEA cantilever discharges a
tight-margin claim by climbing exactly the rungs the budget demands,
deterministically twice."""

import pytest
from typani import Ok

import feldspar.fea.solver as fea_solver
from feldspar.fea.ccx import CcxRun
from feldspar.fea.ladder import RungCache
from feldspar.fea.mesh import MeshData
from feldspar.solve import SolverRegistry
from feldspar.solve._build import invoke_solve_fn

# Synthetic per-rung raw displacement values keyed by char_length,
# converging like a real O(h^2) mesh refinement (16 * (1 - 4**-(i+1))
# for rung index i, matching `test_fea_ladder.py`'s fixture).
_CHAR_LENGTHS = [0.02, 0.01, 0.005, 0.0025]
_VALUES_BY_CHAR_LENGTH = {
    cl: 16.0 * (1.0 - 4.0 ** -(i + 1)) for i, cl in enumerate(_CHAR_LENGTHS)
}

_DUMMY_MESH = MeshData(
    element_type="C3D20",
    nodes=((0.0, 0.0, 0.0),),
    elements=(),
    node_sets={"FIXED": (1,), "TIP": (1,)},
)


def _install_fakes(monkeypatch, char_length_log):
    def fake_build_mesh(geometry, settings):
        char_length_log.append(settings.char_length)
        return Ok(_DUMMY_MESH)

    def fake_run_ccx(deck, timeout_s):
        return Ok(
            CcxRun(dat_text="", frd_text=None, elapsed_s=0.0, tool_version="fake")
        )

    def fake_parse(dat_text):
        return Ok(object())

    def fake_max_disp(parsed):
        char_length = char_length_log[-1]
        return _VALUES_BY_CHAR_LENGTH[char_length]

    monkeypatch.setattr(fea_solver, "build_cantilever_mesh", fake_build_mesh)
    monkeypatch.setattr(fea_solver.ccx, "run_ccx", fake_run_ccx)
    monkeypatch.setattr(fea_solver, "parse_dat_displacements", fake_parse)
    monkeypatch.setattr(fea_solver, "max_displacement_magnitude", fake_max_disp)


_INPUTS = {
    "mech.geom.cantilever.length": 0.5,
    "mech.geom.cantilever.width": 0.04,
    "mech.geom.cantilever.height": 0.06,
    "mech.material.youngs_modulus": 7e10,
    "mech.material.poisson": 0.33,
    "mech.load.tip_force": 1000.0,
}


def _cantilever_fn():
    registry = SolverRegistry()
    fea_solver.register(registry)
    registry.freeze()
    fns = {info.solver_id: fn for info, fn in registry}
    return fns["fea.static_deflection.cantilever"]


def _fresh_cache(monkeypatch) -> RungCache:
    cache = RungCache()
    monkeypatch.setattr(fea_solver, "_CANTILEVER_RUNG_CACHE", cache)
    return cache


def test_cantilever_is_eps_seeking() -> None:
    registry = SolverRegistry()
    fea_solver.register(registry)
    registry.freeze()
    infos = {info.solver_id: info for info, _fn in registry}
    assert infos["fea.static_deflection.cantilever"].eps_seeking is True
    assert infos["fea.static_deflection.cantilever"].cost_curve is not None
    # cylinder_bore is untouched by WO-13.
    assert infos["fea.static_stress.cylinder_bore"].eps_seeking is False


# frob:tests python/feldspar/solve/_build.py::invoke_solve_fn kind="unit"
def test_no_budget_context_runs_fixed_first_pair(monkeypatch) -> None:
    log: list = []
    _install_fakes(monkeypatch, log)
    _fresh_cache(monkeypatch)
    fn = _cantilever_fn()

    result = invoke_solve_fn(fn, _INPUTS, None)
    assert result.is_ok
    assert log == [0.02, 0.01]


def test_tight_budget_climbs_more_rungs_than_loose_budget(monkeypatch) -> None:
    # Fresh cache per call: isolates each climb's OWN rung count (the
    # separate `test_looser_later_budget_reuses_coarser_rungs` test
    # covers cross-call cache reuse).
    log: list = []
    _install_fakes(monkeypatch, log)
    _fresh_cache(monkeypatch)
    fn = _cantilever_fn()
    loose = invoke_solve_fn(fn, _INPUTS, 2.0)
    assert loose.is_ok
    loose_rungs = list(log)

    log.clear()
    _fresh_cache(monkeypatch)
    tight = invoke_solve_fn(fn, _INPUTS, 0.2)
    assert tight.is_ok
    tight_rungs = list(log)

    assert len(tight_rungs) > len(loose_rungs)


def test_deterministic_twice_same_rungs_same_stop(monkeypatch) -> None:
    """WO-13 acceptance: same budget -> same rungs -> same stop, run
    twice."""
    log_1: list = []
    _install_fakes(monkeypatch, log_1)
    _fresh_cache(monkeypatch)
    fn = _cantilever_fn()
    result_1 = invoke_solve_fn(fn, _INPUTS, 0.5)
    assert result_1.is_ok
    rungs_1 = list(log_1)
    eps_1 = result_1.danger_ok.measured_eps
    value_1 = result_1.danger_ok.values["mech.deflection.tip"]

    log_2: list = []
    _install_fakes(monkeypatch, log_2)
    _fresh_cache(monkeypatch)  # fresh process-equivalent cache, second run
    fn_2 = _cantilever_fn()
    result_2 = invoke_solve_fn(fn_2, _INPUTS, 0.5)
    assert result_2.is_ok
    rungs_2 = list(log_2)
    eps_2 = result_2.danger_ok.measured_eps
    value_2 = result_2.danger_ok.values["mech.deflection.tip"]

    assert rungs_1 == rungs_2
    assert eps_1 == pytest.approx(eps_2)
    assert value_1 == pytest.approx(value_2)


def test_looser_later_budget_reuses_coarser_rungs(monkeypatch) -> None:
    """09 sec. 3's per-rung caching scenario: an h+h/2 pair followed by
    a looser request reuses h (and h/2) from the shared rung cache
    instead of re-running gmsh/ccx."""
    log: list = []
    _install_fakes(monkeypatch, log)
    cache = _fresh_cache(monkeypatch)
    fn = _cantilever_fn()

    first = invoke_solve_fn(fn, _INPUTS, 2.0)  # needs only rungs 0, 1
    assert first.is_ok
    assert log == [0.02, 0.01]
    misses_after_first = cache.misses

    second = invoke_solve_fn(fn, _INPUTS, 0.5)  # needs rungs 0, 1, 2
    assert second.is_ok
    assert log == [0.02, 0.01, 0.005]  # rungs 0/1 NOT re-run
    assert cache.hits == 2
    assert cache.misses == misses_after_first + 1
