from __future__ import annotations

"""WO-17 closed-form `elec` directions: known-answer checks against the
worked fixtures in `lithos:docs/workflow/research/
2026-07-08-benchmarks-and-datasets.md` sec. 4 (the same numbers the
ngspice-tier spice-marked tests calibrate against), plus registration
and out-of-domain coverage."""

import pytest

from feldspar.library.elec import register as register_elec
from feldspar.solve import SolverRegistry


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register_elec(registry)
    registry.freeze()
    return registry


def test_register_elec_adds_five_directions():
    registry = _registry()
    assert len(list(registry)) == 5


# ---------------------------------------------------------------------------
# 4.1 RC step response.
# ---------------------------------------------------------------------------


# frob:tests crates/feldspar-py/src/library/elec.rs::elec_rc_step_response_py
def test_rc_step_matches_benchmark_memo():
    from feldspar import _feldspar

    vc = _feldspar.elec_rc_step_response(5.0, 1000.0, 1e-6, 1e-3)
    assert vc == pytest.approx(3.161, rel=1e-3)


# ---------------------------------------------------------------------------
# 4.2 Series RLC resonance.
# ---------------------------------------------------------------------------


# frob:tests crates/feldspar-py/src/library/elec.rs::elec_rlc_resonant_frequency_py
# frob:tests crates/feldspar-py/src/library/elec.rs::elec_rlc_quality_factor_py
def test_rlc_resonance_matches_benchmark_memo():
    from feldspar import _feldspar

    f0 = _feldspar.elec_rlc_resonant_frequency(10e-3, 100e-9)
    q = _feldspar.elec_rlc_quality_factor(10.0, 10e-3, 100e-9)
    assert f0 == pytest.approx(5033, rel=1e-2)
    assert q == pytest.approx(31.6, rel=1e-2)


# ---------------------------------------------------------------------------
# 4.3 Resistive divider under load.
# ---------------------------------------------------------------------------


# frob:tests crates/feldspar-py/src/library/elec.rs::elec_divider_loaded_vout_py
def test_divider_unloaded_and_loaded_match_benchmark_memo():
    from feldspar import _feldspar

    unloaded = _feldspar.elec_divider_loaded_vout(10.0, 10e3, 10e3, 1e15)
    loaded = _feldspar.elec_divider_loaded_vout(10.0, 10e3, 10e3, 100e3)
    assert unloaded == pytest.approx(5.000, rel=1e-6)
    assert loaded == pytest.approx(4.762, rel=1e-3)


# ---------------------------------------------------------------------------
# 4.4 BJT 4-resistor bias point.
# ---------------------------------------------------------------------------


# frob:tests crates/feldspar-py/src/library/elec.rs::elec_bjt_bias_collector_current_py
# frob:tests crates/feldspar-py/src/library/elec.rs::elec_bjt_bias_collector_voltage_py
def test_bjt_bias_matches_benchmark_memo():
    from feldspar import _feldspar

    ic = _feldspar.elec_bjt_bias_collector_current(12.0, 47e3, 10e3, 1e3, 100.0, 0.7)
    vc = _feldspar.elec_bjt_bias_collector_voltage(12.0, ic, 2.2e3)
    assert ic == pytest.approx(1.286e-3, rel=1e-3)
    assert vc == pytest.approx(9.17, rel=1e-3)


# ---------------------------------------------------------------------------
# 4.5 NMOS saturation bias.
# ---------------------------------------------------------------------------


# frob:tests crates/feldspar-py/src/library/elec.rs::elec_nmos_saturation_drain_current_py
def test_nmos_bias_matches_benchmark_memo():
    from feldspar import _feldspar

    drain_current = _feldspar.elec_nmos_saturation_drain_current(1e-3, 3.0, 1.0)
    assert drain_current == pytest.approx(2.0e-3, rel=1e-9)


# ---------------------------------------------------------------------------
# Out-of-domain guards.
# ---------------------------------------------------------------------------


def test_nmos_bias_rejects_cutoff_point():
    from feldspar.library.elec import nmos_bias

    result = nmos_bias(
        {"elec.nmos.k": 1e-3, "elec.nmos.vgs": 0.5, "elec.nmos.vth": 1.0}
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_bjt_bias_rejects_negative_collector_voltage():
    from feldspar.library.elec import bjt_bias

    # Absurdly large beta/RC drives Vc negative (saturated/invalid box).
    result = bjt_bias(
        {
            "elec.bjt.vcc": 5.0,
            "elec.bjt.r1": 1e3,
            "elec.bjt.r2": 1e3,
            "elec.bjt.re": 1.0,
            "elec.bjt.rc": 1e6,
            "elec.bjt.beta": 1000.0,
            "elec.bjt.vbe": 0.7,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_solve_end_to_end_divider():
    from feldspar.core import Interval as CoreInterval
    from feldspar.plan import solve

    registry = _registry()
    result = solve(
        registry,
        known={
            "elec.source.vin": CoreInterval(10.0, 10.0),
            "elec.divider.r1": CoreInterval(10e3, 10e3),
            "elec.divider.r2": CoreInterval(10e3, 10e3),
            "elec.divider.rl": CoreInterval(100e3, 100e3),
        },
        tags={"linear", "small_signal"},
        target="elec.divider.vout",
        eps_budget=1e10,
    )
    assert result.is_ok
    solution = result.danger_ok
    assert solution.value.lo == pytest.approx(4.762, rel=1e-3)
