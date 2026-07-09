from __future__ import annotations

"""Incompressible fluid-mechanics closed-form solver directions (WO-20 Phase 2).

Pure marshalling over `feldspar._feldspar.fluids_*` (the single Rust
home of each formula, `crates/feldspar-library/src/fluids/`): no math
is reimplemented in Python here (NO DUPLICATION). Every direction
declares `accuracy=EXACT` following the `mech.py` precedent (A-7): each
solver evaluates its OWN declared closed-form model exactly, even where
that model (Haaland) is itself a textbook approximation of physical
reality -- the model is the contract, and these compute it to
floating-point precision.

Scope note (WO-20 close-out): this module covers the acceptance-tested
slice of the 07 `fluids` catalog -- internal flow (Poiseuille,
Colebrook/Haaland, Darcy-Weisbach, minor-K), series/parallel network
reduction, turbomachinery (pump operating point, NPSH), and Joukowsky
water hammer. Hydrostatics, external flow, open channel, flow
measurement (ISO 5167), and full multi-branch Hardy-Cross NETWORK
solving over resolved `flownet` payload bytes are EXPLICITLY CUT and
flagged in the WO-20 close-out report -- not silently dropped."""

from typani import Ok

from feldspar import _feldspar
from feldspar.core import Domain, Interval
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, Relation, SolverRegistry, solver

_log = get_logger(__name__)

__all__ = ["register"]

# ---------------------------------------------------------------------------
# Citations (07 "fluids"; 03 "every entry carries citations")
# ---------------------------------------------------------------------------

_WHITE = "White, Fluid Mechanics, 8th ed."
_CRANE = "Crane Technical Paper 410, Flow of Fluids Through Valves, Fittings, and Pipe"
_CENGEL = "Cengel & Cimbala, Fluid Mechanics: Fundamentals and Applications, latest ed."
_WYLIE = "Wylie & Streeter, Fluid Transients in Systems, ch. 1 (Joukowsky equation)"
_COLEBROOK_PAPER = "Colebrook, Turbulent Flow in Pipes, J. Inst. Civ. Eng., 1939"
_HAALAND_PAPER = (
    "Haaland, Simple and Explicit Formulas for the Friction Factor "
    "in Turbulent Pipe Flow, J. Fluids Eng., 1983"
)

# ---------------------------------------------------------------------------
# Internal flow: friction factors
# ---------------------------------------------------------------------------

_LAMINAR_CITATIONS = (
    Citation(
        kind="handbook", ref=_WHITE, note="sec. 6.4, laminar fully developed pipe flow"
    ),
)


@solver(
    namespace="fluids",
    inputs=("fluids.pipe.reynolds",),
    outputs=("fluids.pipe.friction_factor",),
    domain=Domain(
        box={"fluids.pipe.reynolds": Interval(1.0, 2300.0)},
        tags={"incompressible", "laminar"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_LAMINAR_CITATIONS,
    version="1",
)
def laminar_friction_factor(x):
    reynolds = x["fluids.pipe.reynolds"]
    return Ok(
        {
            "fluids.pipe.friction_factor": _feldspar.fluids_laminar_friction_factor(
                reynolds
            )
        }
    )


_TURBULENT_CITATIONS = (
    Citation(kind="paper", ref=_COLEBROOK_PAPER),
    Citation(
        kind="handbook", ref=_WHITE, note="sec. 6.8, Moody chart / Colebrook equation"
    ),
)


@solver(
    namespace="fluids",
    inputs=("fluids.pipe.reynolds", "fluids.pipe.relative_roughness"),
    outputs=("fluids.pipe.friction_factor",),
    domain=Domain(
        box={
            "fluids.pipe.reynolds": Interval(4000.0, 1e8),
            "fluids.pipe.relative_roughness": Interval(0.0, 0.05),
        },
        tags={"incompressible", "turbulent"},
    ),
    cost=1e-6,
    accuracy=EXACT,
    citations=_TURBULENT_CITATIONS,
    version="1",
)
def colebrook_friction_factor(x):
    reynolds = x["fluids.pipe.reynolds"]
    rel_rough = x["fluids.pipe.relative_roughness"]
    return Ok(
        {
            "fluids.pipe.friction_factor": _feldspar.fluids_colebrook_friction_factor(
                reynolds, rel_rough
            )
        }
    )


_HAALAND_CITATIONS = (
    Citation(kind="paper", ref=_HAALAND_PAPER),
    Citation(
        kind="handbook", ref=_WHITE, note="sec. 6.8, explicit Colebrook approximation"
    ),
)


@solver(
    namespace="fluids",
    inputs=("fluids.pipe.reynolds", "fluids.pipe.relative_roughness"),
    outputs=("fluids.pipe.friction_factor.haaland",),
    domain=Domain(
        box={
            "fluids.pipe.reynolds": Interval(4000.0, 1e8),
            "fluids.pipe.relative_roughness": Interval(0.0, 0.05),
        },
        tags={"incompressible", "turbulent"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_HAALAND_CITATIONS,
    version="1",
)
def haaland_friction_factor(x):
    reynolds = x["fluids.pipe.reynolds"]
    rel_rough = x["fluids.pipe.relative_roughness"]
    f = _feldspar.fluids_haaland_friction_factor(reynolds, rel_rough)
    return Ok({"fluids.pipe.friction_factor.haaland": f})


# ---------------------------------------------------------------------------
# Darcy-Weisbach / minor-loss pressure drop, series/parallel reduction
# ---------------------------------------------------------------------------

_DARCY_CITATIONS = (
    Citation(
        kind="handbook", ref=_WHITE, note="sec. 6.6, Darcy-Weisbach pressure loss"
    ),
)


@solver(
    namespace="fluids",
    inputs=(
        "fluids.pipe.friction_factor",
        "fluids.pipe.length",
        "fluids.pipe.diameter",
        "fluids.fluid.density",
        "fluids.pipe.velocity",
    ),
    outputs=("fluids.pipe.dp",),
    domain=Domain(
        box={
            "fluids.pipe.friction_factor": Interval(1e-4, 1.0),
            "fluids.pipe.length": Interval(1e-3, 1e5),
            "fluids.pipe.diameter": Interval(1e-4, 10.0),
            "fluids.fluid.density": Interval(1e-3, 2e4),
            "fluids.pipe.velocity": Interval(0.0, 1e3),
        },
        tags={"incompressible"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_DARCY_CITATIONS,
    version="1",
)
def darcy_dp(x):
    f = x["fluids.pipe.friction_factor"]
    length = x["fluids.pipe.length"]
    diameter = x["fluids.pipe.diameter"]
    density = x["fluids.fluid.density"]
    velocity = x["fluids.pipe.velocity"]
    return Ok(
        {
            "fluids.pipe.dp": _feldspar.fluids_darcy_dp(
                f, length, diameter, density, velocity
            )
        }
    )


_MINOR_LOSS_CITATIONS = (Citation(kind="standard", ref=_CRANE),)


@solver(
    namespace="fluids",
    inputs=("fluids.fitting.k_factor", "fluids.fluid.density", "fluids.pipe.velocity"),
    outputs=("fluids.fitting.dp",),
    domain=Domain(
        box={
            "fluids.fitting.k_factor": Interval(0.0, 100.0),
            "fluids.fluid.density": Interval(1e-3, 2e4),
            "fluids.pipe.velocity": Interval(0.0, 1e3),
        },
        tags={"incompressible"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_MINOR_LOSS_CITATIONS,
    version="1",
)
def minor_loss_dp(x):
    k_factor = x["fluids.fitting.k_factor"]
    density = x["fluids.fluid.density"]
    velocity = x["fluids.pipe.velocity"]
    return Ok(
        {
            "fluids.fitting.dp": _feldspar.fluids_minor_loss_dp(
                k_factor, density, velocity
            )
        }
    )


_NETWORK_CITATIONS = (
    Citation(kind="handbook", ref=_WHITE, note="sec. 6.8, pipe networks"),
)


@solver(
    namespace="fluids",
    inputs=("fluids.network.dp1", "fluids.network.dp2"),
    outputs=("fluids.network.dp_series",),
    domain=Domain(
        box={
            "fluids.network.dp1": Interval(0.0, 1e9),
            "fluids.network.dp2": Interval(0.0, 1e9),
        },
        tags={"incompressible", "network_series"},
    ),
    cost=1e-9,
    accuracy=EXACT,
    citations=_NETWORK_CITATIONS,
    version="1",
)
def series_dp(x):
    dp1 = x["fluids.network.dp1"]
    dp2 = x["fluids.network.dp2"]
    return Ok({"fluids.network.dp_series": _feldspar.fluids_series_dp(dp1, dp2)})


@solver(
    namespace="fluids",
    inputs=("fluids.network.q1", "fluids.network.q2"),
    outputs=("fluids.network.q_parallel",),
    domain=Domain(
        box={
            "fluids.network.q1": Interval(0.0, 1e6),
            "fluids.network.q2": Interval(0.0, 1e6),
        },
        tags={"incompressible", "network_parallel"},
    ),
    cost=1e-9,
    accuracy=EXACT,
    citations=_NETWORK_CITATIONS,
    version="1",
)
def parallel_flow(x):
    q1 = x["fluids.network.q1"]
    q2 = x["fluids.network.q2"]
    return Ok({"fluids.network.q_parallel": _feldspar.fluids_parallel_flow(q1, q2)})


# ---------------------------------------------------------------------------
# Turbomachinery: pump operating point + NPSH margin
# ---------------------------------------------------------------------------

_PUMP_CITATIONS = (
    Citation(kind="handbook", ref=_WHITE, note="sec. 11.7, pump/system curve matching"),
)

pump_operating_point = Relation(
    namespace="fluids",
    ports=(
        "fluids.pump.h0",
        "fluids.pump.a_coeff",
        "fluids.system.h_static",
        "fluids.system.r_coeff",
        "fluids.pump.q_star",
        "fluids.pump.h_star",
    ),
    domain={
        "fluids.pump.h0": (0.0, 1e4),
        "fluids.pump.a_coeff": (0.0, 1e9),
        "fluids.system.h_static": (-1e4, 1e4),
        "fluids.system.r_coeff": (0.0, 1e9),
        "fluids.pump.q_star": (0.0, 1e3),
        "fluids.pump.h_star": (-1e4, 1e4),
    },
    tags=("incompressible", "turbomachinery"),
    cost=1e-7,
    accuracy=EXACT,
    citations=_PUMP_CITATIONS,
    version="1",
)


@pump_operating_point.direction(solves_for="fluids.pump.q_star")
def pump_operating_flow(x):
    h0 = x["fluids.pump.h0"]
    a_coeff = x["fluids.pump.a_coeff"]
    h_static = x["fluids.system.h_static"]
    r_coeff = x["fluids.system.r_coeff"]
    q_star = _feldspar.fluids_pump_operating_flow(h0, a_coeff, h_static, r_coeff)
    return Ok({"fluids.pump.q_star": q_star})


@pump_operating_point.direction(solves_for="fluids.pump.h_star")
def pump_operating_head(x):
    h_static = x["fluids.system.h_static"]
    r_coeff = x["fluids.system.r_coeff"]
    q_star = x["fluids.pump.q_star"]
    h_star = _feldspar.fluids_pump_operating_head(h_static, r_coeff, q_star)
    return Ok({"fluids.pump.h_star": h_star})


_NPSH_CITATIONS = (Citation(kind="handbook", ref=_CENGEL, note="NPSH available"),)


@solver(
    namespace="fluids",
    inputs=(
        "fluids.env.p_atm",
        "fluids.fluid.p_vapor",
        "fluids.fluid.density",
        "fluids.env.gravity",
        "fluids.suction.static_head",
        "fluids.suction.friction_head",
    ),
    outputs=("fluids.npsh_margin",),
    domain=Domain(
        box={
            "fluids.env.p_atm": Interval(1e4, 2e6),
            "fluids.fluid.p_vapor": Interval(0.0, 2e6),
            "fluids.fluid.density": Interval(1.0, 2e4),
            "fluids.env.gravity": Interval(1.0, 20.0),
            "fluids.suction.static_head": Interval(-100.0, 100.0),
            "fluids.suction.friction_head": Interval(0.0, 100.0),
        },
        tags={"incompressible", "turbomachinery"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_NPSH_CITATIONS,
    version="1",
)
def npsh_available(x):
    p_atm = x["fluids.env.p_atm"]
    p_vapor = x["fluids.fluid.p_vapor"]
    density = x["fluids.fluid.density"]
    gravity = x["fluids.env.gravity"]
    static_head = x["fluids.suction.static_head"]
    friction_head = x["fluids.suction.friction_head"]
    npsh = _feldspar.fluids_npsh_available(
        p_atm, p_vapor, density, gravity, static_head, friction_head
    )
    return Ok({"fluids.npsh_margin": npsh})


# ---------------------------------------------------------------------------
# Joukowsky water hammer
# ---------------------------------------------------------------------------

_JOUKOWSKY_CITATIONS = (
    Citation(kind="handbook", ref=_WYLIE),
    Citation(kind="handbook", ref=_WHITE, note="sec. 6.9, water hammer"),
)


@solver(
    namespace="fluids",
    inputs=(
        "fluids.transient.wave_speed",
        "fluids.transient.delta_velocity",
        "fluids.fluid.density",
    ),
    outputs=("fluids.transient.hammer_dp",),
    domain=Domain(
        box={
            "fluids.transient.wave_speed": Interval(1.0, 2000.0),
            "fluids.transient.delta_velocity": Interval(-100.0, 100.0),
            "fluids.fluid.density": Interval(1.0, 2e4),
        },
        tags={"incompressible", "transient"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_JOUKOWSKY_CITATIONS,
    version="1",
)
def joukowsky_dp(x):
    density = x["fluids.fluid.density"]
    wave_speed = x["fluids.transient.wave_speed"]
    delta_velocity = x["fluids.transient.delta_velocity"]
    return Ok(
        {
            "fluids.transient.hammer_dp": _feldspar.fluids_joukowsky_dp(
                density, wave_speed, delta_velocity
            )
        }
    )


def register(registry: SolverRegistry) -> int:
    """Registers every incompressible fluids Phase 2 direction (WO-20).

    Returns the count of directions registered."""
    directions = [
        laminar_friction_factor.solver_direction,  # ty: ignore[unresolved-attribute]
        colebrook_friction_factor.solver_direction,  # ty: ignore[unresolved-attribute]
        haaland_friction_factor.solver_direction,  # ty: ignore[unresolved-attribute]
        darcy_dp.solver_direction,  # ty: ignore[unresolved-attribute]
        minor_loss_dp.solver_direction,  # ty: ignore[unresolved-attribute]
        series_dp.solver_direction,  # ty: ignore[unresolved-attribute]
        parallel_flow.solver_direction,  # ty: ignore[unresolved-attribute]
        npsh_available.solver_direction,  # ty: ignore[unresolved-attribute]
        joukowsky_dp.solver_direction,  # ty: ignore[unresolved-attribute]
    ]
    count = 0
    for direction in directions:
        result = registry.register(*direction)
        _ = result.danger_ok
        count += 1
    result_pump = pump_operating_point.register(registry)
    _ = result_pump.danger_ok
    count += 2
    return count
