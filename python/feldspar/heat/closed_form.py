from __future__ import annotations

"""Heat-transfer closed-form solver directions (WO-20 Phase 2).

Pure marshalling over `feldspar._feldspar.heat_*`
(`crates/feldspar-library/src/heat.rs`); same `accuracy=EXACT`
convention as `mech.py`/`fluids.py` (A-7): each direction evaluates its
own declared model exactly.

Scope note (WO-20 close-out): this module covers 1-D conduction/
convection resistance networks and the Dittus-Boelter forced-convection
correlation with its published Re/Pr validity box. The rest of the 07
`heat` catalog (transient lumped/Heisler, natural convection, boiling/
condensation, radiation networks, LMTD/effectiveness-NTU heat
exchangers) is EXPLICITLY CUT and flagged in the WO-20 close-out
report -- not silently dropped."""

from typani import Ok

from feldspar import _feldspar
from feldspar.core import Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver

_log = get_logger(__name__)

__all__ = ["register"]

_INCROPERA = "Incropera & DeWitt, Fundamentals of Heat and Mass Transfer, 7th ed."
_DITTUS_BOELTER = (
    "Dittus & Boelter (1930), reprinted Incropera & DeWitt, 7th ed., ch. 8"
)

_RESISTANCE_CITATIONS = (
    Citation(kind="handbook", ref=_INCROPERA, note="ch. 3, 1-D steady conduction"),
)


@solver(
    namespace="heat",
    inputs=("heat.wall.thickness", "heat.wall.conductivity", "heat.wall.area"),
    outputs=("heat.wall.resistance",),
    domain=Domain(
        box={
            "heat.wall.thickness": Interval(1e-4, 10.0),
            "heat.wall.conductivity": Interval(1e-3, 500.0),
            "heat.wall.area": Interval(1e-4, 1e4),
        },
        tags=set(),
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_RESISTANCE_CITATIONS,
    version="1",
)
def plane_wall_resistance(x):
    thickness = x["heat.wall.thickness"]
    conductivity = x["heat.wall.conductivity"]
    area = x["heat.wall.area"]
    return Ok(
        {
            "heat.wall.resistance": _feldspar.heat_plane_wall_resistance(
                thickness, conductivity, area
            )
        }
    )


@solver(
    namespace="heat",
    inputs=(
        "heat.cylinder.inner_radius",
        "heat.cylinder.outer_radius",
        "heat.cylinder.conductivity",
        "heat.cylinder.length",
    ),
    outputs=("heat.cylinder.resistance",),
    domain=Domain(
        box={
            "heat.cylinder.inner_radius": Interval(1e-4, 10.0),
            "heat.cylinder.outer_radius": Interval(1e-4, 10.0),
            "heat.cylinder.conductivity": Interval(1e-3, 500.0),
            "heat.cylinder.length": Interval(1e-4, 1e3),
        },
        tags=set(),
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_RESISTANCE_CITATIONS,
    version="1",
)
def cylindrical_wall_resistance(x):
    inner_radius = x["heat.cylinder.inner_radius"]
    outer_radius = x["heat.cylinder.outer_radius"]
    conductivity = x["heat.cylinder.conductivity"]
    length = x["heat.cylinder.length"]
    return Ok(
        {
            "heat.cylinder.resistance": _feldspar.heat_cylindrical_wall_resistance(
                inner_radius, outer_radius, conductivity, length
            )
        }
    )


@solver(
    namespace="heat",
    inputs=("heat.convection.coefficient", "heat.convection.area"),
    outputs=("heat.convection.resistance",),
    domain=Domain(
        box={
            "heat.convection.coefficient": Interval(1e-3, 1e5),
            "heat.convection.area": Interval(1e-4, 1e4),
        },
        tags=set(),
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_RESISTANCE_CITATIONS,
    version="1",
)
def convection_resistance(x):
    coefficient = x["heat.convection.coefficient"]
    area = x["heat.convection.area"]
    return Ok(
        {
            "heat.convection.resistance": _feldspar.heat_convection_resistance(
                coefficient, area
            )
        }
    )


@solver(
    namespace="heat",
    inputs=("heat.network.r1", "heat.network.r2"),
    outputs=("heat.network.r_series",),
    domain=Domain(
        box={
            "heat.network.r1": Interval(0.0, 1e9),
            "heat.network.r2": Interval(0.0, 1e9),
        },
        tags={"network_series"},
    ),
    cost=1e-9,
    accuracy=EXACT,
    citations=_RESISTANCE_CITATIONS,
    version="1",
)
def series_resistance(x):
    r1 = x["heat.network.r1"]
    r2 = x["heat.network.r2"]
    return Ok({"heat.network.r_series": _feldspar.heat_series_resistance(r1, r2)})


@solver(
    namespace="heat",
    inputs=("heat.network.delta_temp", "heat.network.resistance"),
    outputs=("heat.network.rate",),
    domain=Domain(
        box={
            "heat.network.delta_temp": Interval(-1e4, 1e4),
            "heat.network.resistance": Interval(1e-9, 1e9),
        },
        tags=set(),
    ),
    cost=1e-9,
    accuracy=EXACT,
    citations=_RESISTANCE_CITATIONS,
    version="1",
)
def rate_from_resistance(x):
    delta_temp = x["heat.network.delta_temp"]
    resistance = x["heat.network.resistance"]
    return Ok(
        {
            "heat.network.rate": _feldspar.heat_rate_from_resistance(
                delta_temp, resistance
            )
        }
    )


_DITTUS_BOELTER_CITATIONS = (Citation(kind="paper", ref=_DITTUS_BOELTER),)


@solver(
    namespace="heat",
    inputs=("heat.internal_flow.reynolds", "heat.internal_flow.prandtl"),
    outputs=("heat.internal_flow.nusselt",),
    domain=Domain(
        # Published validity box (07 "each with its published Re/Pr
        # validity box as its Domain"): Re >= 1e4, 0.6 <= Pr <= 160.
        box={
            "heat.internal_flow.reynolds": Interval(1e4, 1e7),
            "heat.internal_flow.prandtl": Interval(0.6, 160.0),
        },
        tags={"forced_convection", "heating"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_DITTUS_BOELTER_CITATIONS,
    version="1",
)
def dittus_boelter_nusselt_heating(x):
    reynolds = x["heat.internal_flow.reynolds"]
    prandtl = x["heat.internal_flow.prandtl"]
    return Ok(
        {
            "heat.internal_flow.nusselt": _feldspar.heat_dittus_boelter_nusselt(
                reynolds, prandtl, True
            )
        }
    )


@solver(
    namespace="heat",
    inputs=("heat.convection.nusselt", "heat.fluid.conductivity", "heat.pipe.diameter"),
    outputs=("heat.convection.coefficient",),
    domain=Domain(
        box={
            "heat.convection.nusselt": Interval(1e-3, 1e5),
            "heat.fluid.conductivity": Interval(1e-4, 500.0),
            "heat.pipe.diameter": Interval(1e-4, 10.0),
        },
        tags=set(),
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(
        Citation(
            kind="handbook", ref=_INCROPERA, note="ch. 8, Nusselt-number definition"
        ),
    ),
    version="1",
)
def coefficient_from_nusselt(x):
    nusselt = x["heat.convection.nusselt"]
    conductivity = x["heat.fluid.conductivity"]
    diameter = x["heat.pipe.diameter"]
    return Ok(
        {
            "heat.convection.coefficient": _feldspar.heat_coefficient_from_nusselt(
                nusselt, conductivity, diameter
            )
        }
    )


#: This family's port table (WO111b composition fix; see
#: `member_capacity.py`'s `_PORT_DECLS` note).
_PORT_DECLS = (
    PortDecl("heat.wall.thickness", "m"),
    PortDecl("heat.wall.conductivity", "W/(m*K)"),
    PortDecl("heat.wall.area", "m^2"),
    PortDecl("heat.wall.resistance", "K/W"),
    PortDecl("heat.cylinder.inner_radius", "m"),
    PortDecl("heat.cylinder.outer_radius", "m"),
    PortDecl("heat.cylinder.conductivity", "W/(m*K)"),
    PortDecl("heat.cylinder.length", "m"),
    PortDecl("heat.cylinder.resistance", "K/W"),
    PortDecl("heat.convection.coefficient", "W/(m^2*K)"),
    PortDecl("heat.convection.area", "m^2"),
    PortDecl("heat.convection.resistance", "K/W"),
    PortDecl("heat.convection.nusselt", "1"),
    PortDecl("heat.network.r1", "K/W"),
    PortDecl("heat.network.r2", "K/W"),
    PortDecl("heat.network.r_series", "K/W"),
    PortDecl("heat.network.resistance", "K/W"),
    PortDecl("heat.network.delta_temp", "K"),
    PortDecl("heat.network.rate", "W"),
    PortDecl("heat.internal_flow.reynolds", "1"),
    PortDecl("heat.internal_flow.prandtl", "1"),
    PortDecl("heat.internal_flow.nusselt", "1"),
    PortDecl("heat.fluid.conductivity", "W/(m*K)"),
    PortDecl("heat.pipe.diameter", "m"),
)


def register(registry: SolverRegistry) -> None:
    """Registers every heat Phase 2 direction (WO-20). Declares this
    family's port table first (WO111b)."""
    _ = registry.declare_ports(*_PORT_DECLS).danger_ok
    directions = [
        plane_wall_resistance.solver_direction,  # ty: ignore[unresolved-attribute]
        cylindrical_wall_resistance.solver_direction,  # ty: ignore[unresolved-attribute]
        convection_resistance.solver_direction,  # ty: ignore[unresolved-attribute]
        series_resistance.solver_direction,  # ty: ignore[unresolved-attribute]
        rate_from_resistance.solver_direction,  # ty: ignore[unresolved-attribute]
        dittus_boelter_nusselt_heating.solver_direction,  # ty: ignore[unresolved-attribute]
        coefficient_from_nusselt.solver_direction,  # ty: ignore[unresolved-attribute]
    ]
    for direction in directions:
        result = registry.register(*direction)
        _ = result.danger_ok
    _log.info("heat: registered %d solver directions", len(directions))
