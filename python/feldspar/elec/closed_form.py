from __future__ import annotations

"""Circuits/electronics closed-form solver directions (WO-17, 07
"elec"). Pure marshalling over `feldspar._feldspar.elec_*` (the single
Rust home of each formula, `crates/feldspar-library/src/elec.rs`): no
math is reimplemented here (NO DUPLICATION, AD-3).

These five directions are exactly the closed-form twin of the five
ngspice calibration cases in `lithos:docs/workflow/research/
2026-07-08-benchmarks-and-datasets.md` sec. 4 (loaded divider, RC
step, RLC resonance, BJT bias, NMOS bias): `elec.solver` (this module)
registers the closed forms, `elec.solver` in `feldspar.elec.solver`
registers the ngspice-backed discretized twins under the SAME `elec.*`
claim kinds, and `tests/integration/test_elec_ngspice.py` checks
`|ngspice - closed form| <= reported eps` for each pair. Every
direction here declares `accuracy=EXACT` (A-7): these are the oracles
the ngspice tier calibrates against, not the other way around."""

from typani import Err, Ok

from feldspar import _feldspar
from feldspar.core import Accuracy, Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

_SEDRA_SMITH = Citation(
    kind="handbook", ref="Sedra & Smith, Microelectronic Circuits, latest ed."
)
_NILSSON_RIEDEL = Citation(
    kind="handbook", ref="Nilsson & Riedel, Electric Circuits, latest ed."
)
_RAZAVI = Citation(
    kind="handbook",
    ref="Razavi, Design of Analog CMOS Integrated Circuits, square-law model",
)

# ---------------------------------------------------------------------------
# divider_loaded -- resistive divider under load (4.3 in the benchmark memo).
# ---------------------------------------------------------------------------


# frob:doc docs/modules/elec.md#elec_closed_form
@solver(
    namespace="elec",
    inputs=(
        "elec.source.vin",
        "elec.divider.r1",
        "elec.divider.r2",
        "elec.divider.rl",
    ),
    outputs=("elec.divider.vout",),
    domain=Domain(
        box={
            "elec.source.vin": Interval(1e-3, 1e4),
            "elec.divider.r1": Interval(1.0, 1e9),
            "elec.divider.r2": Interval(1.0, 1e9),
            "elec.divider.rl": Interval(1.0, 1e12),
        },
        tags={"linear", "small_signal"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_SEDRA_SMITH,),
    version="1",
)
# frob:waive TEST005 reason="measured 25.0% branch cov on 2026-07-18; straight-line body (extract, one Rust FFI call, return Ok) has no real conditional -- coverage.py branch-pair artifact on trivial bodies. Genuinely exercised via test_solve_end_to_end_divider (tests/unit/test_library_elec.py, full registry->solve path). Backfill T-0014."
def divider_loaded(x):
    vin = x["elec.source.vin"]
    r1 = x["elec.divider.r1"]
    r2 = x["elec.divider.r2"]
    rl = x["elec.divider.rl"]
    vout = _feldspar.elec_divider_loaded_vout(vin, r1, r2, rl)
    return Ok({"elec.divider.vout": vout})


# ---------------------------------------------------------------------------
# rc_step -- series RC step response (4.1 in the benchmark memo).
# ---------------------------------------------------------------------------


# frob:doc docs/modules/elec.md#elec_closed_form
@solver(
    namespace="elec",
    inputs=(
        "elec.rc.vf",
        "elec.rc.resistance",
        "elec.rc.capacitance",
        "elec.rc.time",
    ),
    outputs=("elec.rc.vc",),
    domain=Domain(
        box={
            "elec.rc.vf": Interval(1e-3, 1e4),
            "elec.rc.resistance": Interval(1e-3, 1e12),
            "elec.rc.capacitance": Interval(1e-15, 1.0),
            "elec.rc.time": Interval(0.0, 1e6),
        },
        tags={"linear", "small_signal"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_NILSSON_RIEDEL,),
    version="1",
)
# frob:waive TEST005 reason="measured 25.0% branch cov on 2026-07-18; straight-line body, same coverage.py branch-pair artifact as divider_loaded above. Genuinely exercised via test_rc_step_matches_benchmark_memo (tests/unit/test_library_elec.py). Backfill T-0014."
def rc_step(x):
    vf = x["elec.rc.vf"]
    r = x["elec.rc.resistance"]
    c = x["elec.rc.capacitance"]
    t = x["elec.rc.time"]
    vc = _feldspar.elec_rc_step_response(vf, r, c, t)
    return Ok({"elec.rc.vc": vc})


# ---------------------------------------------------------------------------
# rlc_resonance -- series RLC resonant frequency + Q (4.2 in the memo).
# ---------------------------------------------------------------------------


# frob:doc docs/modules/elec.md#elec_closed_form
@solver(
    namespace="elec",
    inputs=(
        "elec.rlc.resistance",
        "elec.rlc.inductance",
        "elec.rlc.capacitance",
    ),
    outputs=("elec.rlc.f0", "elec.rlc.q"),
    domain=Domain(
        box={
            "elec.rlc.resistance": Interval(1e-3, 1e9),
            "elec.rlc.inductance": Interval(1e-12, 1e3),
            "elec.rlc.capacitance": Interval(1e-15, 1.0),
        },
        tags={"linear", "small_signal"},
    ),
    cost=1e-7,
    accuracy={
        "elec.rlc.f0": Accuracy(eps_abs=0.0, eps_rel=0.0),
        "elec.rlc.q": Accuracy(eps_abs=0.0, eps_rel=0.0),
    },
    citations=(_NILSSON_RIEDEL,),
    version="1",
)
# frob:waive TEST005 reason="measured 25.0% branch cov on 2026-07-18; straight-line body, same coverage.py branch-pair artifact as divider_loaded above. Genuinely exercised via test_rlc_resonance_matches_benchmark_memo (tests/unit/test_library_elec.py). Backfill T-0014."
def rlc_resonance(x):
    r = x["elec.rlc.resistance"]
    inductance = x["elec.rlc.inductance"]
    capacitance = x["elec.rlc.capacitance"]
    f0 = _feldspar.elec_rlc_resonant_frequency(inductance, capacitance)
    q = _feldspar.elec_rlc_quality_factor(r, inductance, capacitance)
    return Ok({"elec.rlc.f0": f0, "elec.rlc.q": q})


# ---------------------------------------------------------------------------
# bjt_bias -- 4-resistor BJT bias point (4.4 in the memo). A cross-port
# constraint (r1+r2 must stay finite/positive, already guaranteed by the
# domain box) needs no runtime OutOfDomain check beyond the box itself.
# ---------------------------------------------------------------------------


# frob:doc docs/modules/elec.md#elec_closed_form
@solver(
    namespace="elec",
    inputs=(
        "elec.bjt.vcc",
        "elec.bjt.r1",
        "elec.bjt.r2",
        "elec.bjt.re",
        "elec.bjt.rc",
        "elec.bjt.beta",
        "elec.bjt.vbe",
    ),
    outputs=("elec.bjt.ic", "elec.bjt.vc"),
    domain=Domain(
        box={
            "elec.bjt.vcc": Interval(0.5, 100.0),
            "elec.bjt.r1": Interval(1.0, 1e9),
            "elec.bjt.r2": Interval(1.0, 1e9),
            "elec.bjt.re": Interval(1.0, 1e7),
            "elec.bjt.rc": Interval(1.0, 1e7),
            "elec.bjt.beta": Interval(1.0, 1000.0),
            "elec.bjt.vbe": Interval(0.3, 1.0),
        },
        tags={"linear", "small_signal"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_SEDRA_SMITH,),
    version="1",
)
def bjt_bias(x):
    vcc = x["elec.bjt.vcc"]
    r1 = x["elec.bjt.r1"]
    r2 = x["elec.bjt.r2"]
    re = x["elec.bjt.re"]
    rc = x["elec.bjt.rc"]
    beta = x["elec.bjt.beta"]
    vbe = x["elec.bjt.vbe"]
    ic = _feldspar.elec_bjt_bias_collector_current(vcc, r1, r2, re, beta, vbe)
    vc = _feldspar.elec_bjt_bias_collector_voltage(vcc, ic, rc)
    if vc < 0.0:
        _log.info(
            "elec.bjt_bias: rejecting saturated/invalid bias point "
            "vcc=%s ic=%s rc=%s -> vc=%s",
            vcc,
            ic,
            rc,
            vc,
        )
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"computed collector voltage {vc} < 0 (bias point is "
                    "saturated/invalid for this box -- outside this "
                    "solver's linear-active assumption)"
                )
            )
        )
    return Ok({"elec.bjt.ic": ic, "elec.bjt.vc": vc})


# ---------------------------------------------------------------------------
# nmos_bias -- level-1 NMOS saturation bias (4.5 in the memo).
# ---------------------------------------------------------------------------


# frob:doc docs/modules/elec.md#elec_closed_form
@solver(
    namespace="elec",
    inputs=("elec.nmos.k", "elec.nmos.vgs", "elec.nmos.vth"),
    outputs=("elec.nmos.id",),
    domain=Domain(
        box={
            "elec.nmos.k": Interval(1e-6, 10.0),
            "elec.nmos.vgs": Interval(-10.0, 10.0),
            "elec.nmos.vth": Interval(-5.0, 5.0),
        },
        tags={"linear", "small_signal"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_RAZAVI,),
    version="1",
)
def nmos_bias(x):
    k = x["elec.nmos.k"]
    vgs = x["elec.nmos.vgs"]
    vth = x["elec.nmos.vth"]
    if vgs <= vth:
        _log.info("elec.nmos_bias: rejecting cutoff point vgs=%s vth=%s", vgs, vth)
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"vgs ({vgs}) <= vth ({vth}): device is in cutoff, not "
                    "the saturation region this formula assumes"
                )
            )
        )
    drain_current = _feldspar.elec_nmos_saturation_drain_current(k, vgs, vth)
    return Ok({"elec.nmos.id": drain_current})


#: This family's port table (WO111b composition fix; see
#: `member_capacity.py`'s `_PORT_DECLS` note). `elec.rlc.q` is the
#: dimensionless quality factor; `elec.nmos.k` is the saturation
#: transconductance parameter (A/V^2).
_PORT_DECLS = (
    PortDecl("elec.source.vin", "V"),
    PortDecl("elec.divider.r1", "Ohm"),
    PortDecl("elec.divider.r2", "Ohm"),
    PortDecl("elec.divider.rl", "Ohm"),
    PortDecl("elec.divider.vout", "V"),
    PortDecl("elec.rc.vf", "V"),
    PortDecl("elec.rc.resistance", "Ohm"),
    PortDecl("elec.rc.capacitance", "F"),
    PortDecl("elec.rc.time", "s"),
    PortDecl("elec.rc.vc", "V"),
    PortDecl("elec.rlc.resistance", "Ohm"),
    PortDecl("elec.rlc.inductance", "H"),
    PortDecl("elec.rlc.capacitance", "F"),
    PortDecl("elec.rlc.f0", "Hz"),
    PortDecl("elec.rlc.q", "1"),
    PortDecl("elec.bjt.vcc", "V"),
    PortDecl("elec.bjt.r1", "Ohm"),
    PortDecl("elec.bjt.r2", "Ohm"),
    PortDecl("elec.bjt.re", "Ohm"),
    PortDecl("elec.bjt.rc", "Ohm"),
    PortDecl("elec.bjt.beta", "1"),
    PortDecl("elec.bjt.vbe", "V"),
    PortDecl("elec.bjt.ic", "A"),
    PortDecl("elec.bjt.vc", "V"),
    PortDecl("elec.nmos.k", "A/V^2"),
    PortDecl("elec.nmos.vgs", "V"),
    PortDecl("elec.nmos.vth", "V"),
    PortDecl("elec.nmos.id", "A"),
)


# frob:doc docs/modules/elec.md#elec_closed_form
def register(registry: SolverRegistry) -> None:
    """Registers every elec closed-form direction (WO-17). Declares
    this family's port table first (WO111b)."""
    _ = registry.declare_ports(*_PORT_DECLS).danger_ok
    result_a = registry.register(*divider_loaded.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_a.danger_ok
    result_b = registry.register(*rc_step.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_b.danger_ok
    result_c = registry.register(*rlc_resonance.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_c.danger_ok
    result_d = registry.register(*bjt_bias.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_d.danger_ok
    result_e = registry.register(*nmos_bias.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_e.danger_ok
    _log.info("elec: registered %d solver directions", 5)
