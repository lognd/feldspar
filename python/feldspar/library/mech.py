from __future__ import annotations

"""Mechanical-engineering closed-form solver directions (WO-07 Phase 1).

Pure marshalling over `feldspar._feldspar.mech_*` (the single Rust home
of each formula, `crates/feldspar-library/src/mech.rs`): no math is
reimplemented in Python here (NO DUPLICATION). Every direction declares
`accuracy=EXACT` -- these closed-form solvers evaluate the declared
model exactly (A-7); they are the oracles the WO-08 FEA tier will be
calibrated against, not the other way around, so they need no
calibration citation (FINV-6 is satisfied by the handbook citations
alone)."""

from typani import Err, Ok

from feldspar import _feldspar
from feldspar.core import Accuracy, Domain, Interval
from feldspar.logging import get_logger
from feldspar.solve import EXACT, Citation, Relation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

# ---------------------------------------------------------------------------
# rect_second_moment -- the real registered twin of examples/solvers/00's
# DX sketch; same ports, domain, and citation, verbatim.
# ---------------------------------------------------------------------------


@solver(
    namespace="mech",
    inputs=("mech.section.width", "mech.section.height"),
    outputs=("mech.section.second_moment",),
    domain=Domain(
        box={
            "mech.section.width": Interval(1e-4, 1.0),
            "mech.section.height": Interval(1e-4, 1.0),
        },
        tags=set(),
    ),
    cost=1e-7,
    accuracy={"mech.section.second_moment": Accuracy(eps_abs=0.0, eps_rel=0.0)},
    citations=(
        Citation(kind="handbook", ref="Gere, Mechanics of Materials 9e, App. E"),
    ),
    version="1",
)
def rect_second_moment(x):
    b, h = x["mech.section.width"], x["mech.section.height"]
    return Ok({"mech.section.second_moment": _feldspar.mech_rect_second_moment(b, h)})


# ---------------------------------------------------------------------------
# cantilever_tip_deflection -- two directions (deflection <-> required E),
# the WO-07 multi-direction example, built with Relation (F7).
# ---------------------------------------------------------------------------

_CANTILEVER_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            "Gere, Mechanics of Materials, 9th ed., Table (cantilever, "
            "concentrated load at free end)"
        ),
        note=(
            "see also Young & Budynas, Roark's Formulas for Stress and "
            "Strain, 8th ed., Table 8.1 (secondary handbook citation)"
        ),
    ),
)

cantilever = Relation(
    namespace="mech",
    ports=(
        "mech.load.tip_force",
        "mech.geom.cantilever.length",
        "mech.material.youngs_modulus",
        "mech.section.second_moment",
        "mech.deflection.tip",
    ),
    domain={
        "mech.load.tip_force": (1.0, 1e6),
        "mech.geom.cantilever.length": (1e-3, 10.0),
        "mech.material.youngs_modulus": (1e6, 1e13),
        "mech.section.second_moment": (1e-12, 1.0),
        "mech.deflection.tip": (1e-9, 1.0),
    },
    tags=("linear_elastic", "small_deflection"),
    cost=1e-7,
    accuracy=EXACT,
    citations=_CANTILEVER_CITATIONS,
    version="1",
)


@cantilever.direction(solves_for="mech.deflection.tip")
def cantilever_tip_deflection(x):
    force = x["mech.load.tip_force"]
    length = x["mech.geom.cantilever.length"]
    youngs_modulus = x["mech.material.youngs_modulus"]
    second_moment = x["mech.section.second_moment"]
    deflection = _feldspar.mech_cantilever_tip_deflection(
        force, length, youngs_modulus, second_moment
    )
    return Ok({"mech.deflection.tip": deflection})


@cantilever.direction(solves_for="mech.material.youngs_modulus")
def cantilever_required_youngs_modulus(x):
    force = x["mech.load.tip_force"]
    length = x["mech.geom.cantilever.length"]
    second_moment = x["mech.section.second_moment"]
    deflection = x["mech.deflection.tip"]
    youngs_modulus = _feldspar.mech_cantilever_required_youngs_modulus(
        force, length, second_moment, deflection
    )
    return Ok({"mech.material.youngs_modulus": youngs_modulus})


# ---------------------------------------------------------------------------
# bore_von_mises -- Lame thick-wall stresses + von Mises composite.
# Cross-port constraint (outer_radius > inner_radius) can't live in a
# per-port Domain box, so it's enforced at call time with a SolveError
# (SolveError.OutOfDomain) rather than silently dividing near zero.
# ---------------------------------------------------------------------------

_LAME_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            "Budynas & Nisbett, Shigley's Mechanical Engineering Design, "
            "latest ed., Thick-Walled Cylinders section (Lame's equations)"
        ),
    ),
    Citation(
        kind="handbook",
        ref=(
            "Budynas & Nisbett, Shigley's Mechanical Engineering Design, "
            "latest ed., distortion-energy (von Mises) equivalent stress "
            "definition"
        ),
    ),
)

_LAME_RATIO_MIN_GAP = 1e-6  # m -- minimum (outer - inner) radius gap


@solver(
    namespace="mech",
    inputs=(
        "mech.load.internal_pressure",
        "mech.geom.cylinder.inner_radius",
        "mech.geom.cylinder.outer_radius",
    ),
    outputs=("mech.stress.von_mises",),
    domain=Domain(
        box={
            "mech.load.internal_pressure": Interval(1.0, 1e9),
            "mech.geom.cylinder.inner_radius": Interval(1e-3, 5.0),
            "mech.geom.cylinder.outer_radius": Interval(1e-3, 5.0),
        },
        tags={"linear_elastic"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_LAME_CITATIONS,
    version="1",
)
def bore_von_mises(x):
    pressure = x["mech.load.internal_pressure"]
    inner_radius = x["mech.geom.cylinder.inner_radius"]
    outer_radius = x["mech.geom.cylinder.outer_radius"]
    if outer_radius - inner_radius < _LAME_RATIO_MIN_GAP:
        _log.info(
            "mech.bore_von_mises: rejecting degenerate cylinder "
            "inner_radius=%s outer_radius=%s (gap below %s m)",
            inner_radius,
            outer_radius,
            _LAME_RATIO_MIN_GAP,
        )
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"mech.geom.cylinder.outer_radius ({outer_radius}) must "
                    f"exceed mech.geom.cylinder.inner_radius ({inner_radius}) "
                    f"by at least {_LAME_RATIO_MIN_GAP} m (Lame ratio -> 1 "
                    "is outside this solver's effective domain)"
                )
            )
        )
    stress = _feldspar.mech_bore_von_mises(pressure, inner_radius, outer_radius)
    return Ok({"mech.stress.von_mises": stress})


def register(registry: SolverRegistry) -> None:
    """Registers every mech Phase 1 direction (WO-07)."""
    result_a = registry.register(*rect_second_moment.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_a.danger_ok
    result_b = cantilever.register(registry)
    _ = result_b.danger_ok
    result_c = registry.register(*bore_von_mises.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_c.danger_ok
    _log.info("mech: registered %d solver directions", 3)
