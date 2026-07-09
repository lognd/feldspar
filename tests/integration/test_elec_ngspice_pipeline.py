from __future__ import annotations

"""WO-17 `spice`-marked integration tests: real ngspice solves through
the registered `elec.ngspice.divider` / `elec.ngspice.rc_step`
directions, checked against the closed-form oracles in `library/
elec.py` (05 "Known-answer discipline": `|ngspice - closed form| <=
reported eps`), plus a twice-run digest-equality test for determinism
(04-routing "Solve cache"). ALL tests here carry the `spice` marker
and are excluded from `make test`'s default loop (`pyproject.toml`'s
`-m "not regolith and not fea and not spice"`, same AD-12e posture as
the `fea`/`ccx` precedent): they require a real `ngspice` binary (42+
recommended), not present in every dev/CI environment.

Oracle and ngspice solves each use a registry containing ONLY that
tier's direction: `elec.divider_loaded`/`elec.ngspice.divider` (and
their rc_step twins) declare the SAME input ports, so a combined
registry would let the cheaper closed form win every route and the
ngspice code path would never actually run -- separate single-tier
registries force each `solve()` call through the intended direction.

This file is written correctly per the WO-17 spec (deck/run/parse
shape, calibration cases from `lithos:docs/workflow/research/
2026-07-08-benchmarks-and-datasets.md` sec. 4) but could NOT be
executed in the sandbox this WO was implemented in (no `ngspice`
binary present, `which ngspice` empty) -- the no-ngspice honesty path
(`tests/unit/test_elec_ngspice.py`) and the mocked twice-run digest
test WERE executed and pass; only the real-binary halves below are
verified by code review, not execution, exactly the WO-08 precedent's
own documented split."""

import pytest

from feldspar.core import Interval
from feldspar.elec.solver import register as register_elec_ngspice
from feldspar.library.elec import register as register_elec_closed_form
from feldspar.plan import solve
from feldspar.solve import SolverRegistry

pytestmark = pytest.mark.spice


def _closed_form_registry() -> SolverRegistry:
    registry = SolverRegistry()
    register_elec_closed_form(registry)
    registry.freeze()
    return registry


def _ngspice_registry() -> SolverRegistry:
    registry = SolverRegistry()
    register_elec_ngspice(registry)
    registry.freeze()
    return registry


# ---------------------------------------------------------------------------
# 4.3 Resistive divider under load: ngspice .op vs. closed-form oracle.
# ---------------------------------------------------------------------------


def test_ngspice_divider_matches_closed_form_oracle():
    """`elec.ngspice.divider`'s realized value must fall within its OWN
    reported `measured_eps` of the closed-form `elec.divider_loaded`
    oracle (loaded resistive divider, benchmark memo sec. 4.3: Vin=10V,
    R1=R2=10k, RL=100k -> Vout=4.762V)."""
    known = {
        "elec.source.vin": Interval(10.0, 10.0),
        "elec.divider.r1": Interval(10e3, 10e3),
        "elec.divider.r2": Interval(10e3, 10e3),
        "elec.divider.rl": Interval(100e3, 100e3),
    }

    oracle = solve(
        _closed_form_registry(),
        known=known,
        tags={"linear", "small_signal"},
        target="elec.divider.vout",
        eps_budget=1e-15,
    ).danger_ok

    ngspice_solution = solve(
        _ngspice_registry(),
        known=known,
        tags={"linear", "small_signal"},
        target="elec.divider.vout",
        eps_budget=1e10,
    ).danger_ok

    assert abs(ngspice_solution.value.lo - oracle.value.lo) <= ngspice_solution.eps


# ---------------------------------------------------------------------------
# 4.1 RC step response: ngspice .tran (step-halved) vs. closed-form oracle.
# ---------------------------------------------------------------------------


def test_ngspice_rc_step_matches_closed_form_oracle():
    """`elec.ngspice.rc_step`'s realized value must fall within its OWN
    reported (step-halved) `measured_eps` of the closed-form `elec.
    rc_step` oracle (series RC step, benchmark memo sec. 4.1: R=1k,
    C=1uF, Vf=5V, t=1ms -> v_C=3.161V)."""
    known = {
        "elec.rc.vf": Interval(5.0, 5.0),
        "elec.rc.resistance": Interval(1000.0, 1000.0),
        "elec.rc.capacitance": Interval(1e-6, 1e-6),
        "elec.rc.time": Interval(1e-3, 1e-3),
    }

    oracle = solve(
        _closed_form_registry(),
        known=known,
        tags={"linear", "small_signal"},
        target="elec.rc.vc",
        eps_budget=1e-15,
    ).danger_ok

    ngspice_solution = solve(
        _ngspice_registry(),
        known=known,
        tags={"linear", "small_signal"},
        target="elec.rc.vc",
        eps_budget=1e10,
    ).danger_ok

    assert abs(ngspice_solution.value.lo - oracle.value.lo) <= ngspice_solution.eps


# ---------------------------------------------------------------------------
# Determinism: twice-run digest equality (04-routing "Solve cache").
# ---------------------------------------------------------------------------


def test_ngspice_divider_solve_is_deterministic_across_two_runs():
    """Two independent `solve()` calls with identical inputs against a
    freshly built registry must produce the SAME `settings_digest` --
    the twice-run determinism check the WO requires for the ngspice
    tier's `deterministic=True` claim (mirrors `test_fea_pipeline.py`'s
    `test_cantilever_fea_solve_is_deterministic_across_two_runs`)."""
    known = {
        "elec.source.vin": Interval(10.0, 10.0),
        "elec.divider.r1": Interval(10e3, 10e3),
        "elec.divider.r2": Interval(10e3, 10e3),
        "elec.divider.rl": Interval(100e3, 100e3),
    }

    first = solve(
        _ngspice_registry(),
        known=known,
        tags={"linear", "small_signal"},
        target="elec.divider.vout",
        eps_budget=1e10,
    ).danger_ok
    second = solve(
        _ngspice_registry(),
        known=known,
        tags={"linear", "small_signal"},
        target="elec.divider.vout",
        eps_budget=1e10,
    ).danger_ok

    assert first.settings_digest == second.settings_digest
    assert first.value.lo == pytest.approx(second.value.lo, rel=1e-9)
