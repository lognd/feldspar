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
report -- not silently dropped.

WO-142 growth: widens the forced-convection branch (Gnielinski
f-coupled correlation, Dittus-Boelter cooling exponent), adds the
laminar fully-developed Nu constants, Churchill & Chu (1975) natural
convection (horizontal cylinder, vertical plate), and the NTU-
effectiveness family (parallel flow, counterflow, shell-and-tube one
shell pass) composing UA -> NTU -> effectiveness -> outlet
temperatures. Boiling/condensation and radiation networks remain CUT
(not this WO's territory); conjugate/coupled flow-and-wall problems
are a recorded wall (`docs/spec/fluorite/03-lowering.md:114-124`),
never attempted here."""

from typani import Ok

from feldspar import _feldspar
from feldspar.core import Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver

_log = get_logger(__name__)

__all__ = ["register"]

_DITTUS_BOELTER_COOLING = (
    "Dittus & Boelter (1930), Univ. Calif. Publ. Eng. 2:443, reprinted "
    "Int. Comm. Heat Mass Transfer 12 (1985) 3-22"
)
_GNIELINSKI = "Gnielinski, V. (1976), Int. Chem. Eng. 16(2):359-368"
_CHURCHILL_CHU_HORIZONTAL = (
    "Churchill, S.W. & Chu, H.H.S. (1975), Int. J. Heat Mass Transfer 18:1049-1053"
)
_CHURCHILL_CHU_VERTICAL = (
    "Churchill, S.W. & Chu, H.H.S. (1975), Int. J. Heat Mass Transfer 18:1323-1329"
)
_KAYS_LONDON = "Kays & London, Compact Heat Exchangers, 3rd ed. (1984)"

_INCROPERA = "Incropera & DeWitt, Fundamentals of Heat and Mass Transfer, 7th ed."
_DITTUS_BOELTER = (
    "Dittus & Boelter (1930), reprinted Incropera & DeWitt, 7th ed., ch. 8"
)

_RESISTANCE_CITATIONS = (
    Citation(kind="handbook", ref=_INCROPERA, note="ch. 3, 1-D steady conduction"),
)


# frob:doc docs/modules/heat.md#heat_closed_form
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


# frob:doc docs/modules/heat.md#heat_closed_form
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


# frob:doc docs/modules/heat.md#heat_closed_form
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


# frob:doc docs/modules/heat.md#heat_closed_form
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


# frob:doc docs/modules/heat.md#heat_closed_form
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


# frob:doc docs/modules/heat.md#heat_closed_form
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


# frob:doc docs/modules/heat.md#heat_closed_form
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


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=("heat.internal_flow.reynolds", "heat.internal_flow.prandtl"),
    outputs=("heat.internal_flow.nusselt",),
    domain=Domain(
        # Published validity box: Re >= 1e4, 0.6 <= Pr <= 160 (same
        # Dittus-Boelter box; cooling is the n=0.3 branch of the same
        # correlation).
        box={
            "heat.internal_flow.reynolds": Interval(1e4, 1e7),
            "heat.internal_flow.prandtl": Interval(0.6, 160.0),
        },
        tags={"forced_convection", "cooling"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(Citation(kind="paper", ref=_DITTUS_BOELTER_COOLING),),
    version="1",
)
# frob:ticket T-0020
def dittus_boelter_nusselt_cooling(x):
    reynolds = x["heat.internal_flow.reynolds"]
    prandtl = x["heat.internal_flow.prandtl"]
    return Ok(
        {
            "heat.internal_flow.nusselt": _feldspar.heat_dittus_boelter_nusselt(
                reynolds, prandtl, False
            )
        }
    )


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=(
        "heat.internal_flow.reynolds",
        "heat.internal_flow.prandtl",
        "heat.internal_flow.friction_factor",
    ),
    outputs=("heat.internal_flow.nusselt.gnielinski",),
    domain=Domain(
        # Gnielinski's own published validity box (WO-142 deliverable 1).
        box={
            "heat.internal_flow.reynolds": Interval(3000.0, 5.0e6),
            "heat.internal_flow.prandtl": Interval(0.5, 2000.0),
            "heat.internal_flow.friction_factor": Interval(1e-4, 1.0),
        },
        tags={"forced_convection", "f_coupled"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(
        Citation(kind="paper", ref=_GNIELINSKI),
        Citation(
            kind="handbook",
            ref=_INCROPERA,
            note="ch. 8, Gnielinski correlation restatement",
        ),
    ),
    version="1",
)
# frob:ticket T-0020
def gnielinski_nusselt(x):
    reynolds = x["heat.internal_flow.reynolds"]
    prandtl = x["heat.internal_flow.prandtl"]
    friction_factor = x["heat.internal_flow.friction_factor"]
    return Ok(
        {
            "heat.internal_flow.nusselt.gnielinski": _feldspar.heat_gnielinski_nusselt(
                reynolds, prandtl, friction_factor
            )
        }
    )


_LAMINAR_NUSSELT_CITATIONS = (
    Citation(
        kind="handbook", ref=_INCROPERA, note="Table 8.1, fully developed laminar flow"
    ),
)


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=(),
    outputs=("heat.internal_flow.nusselt.laminar_const_temp",),
    domain=Domain(box={}, tags={"laminar", "constant_wall_temp"}),
    cost=1e-9,
    accuracy=EXACT,
    citations=_LAMINAR_NUSSELT_CITATIONS,
    version="1",
)
# frob:ticket T-0020
def laminar_fully_developed_nusselt_const_temp(_x):
    return Ok(
        {
            "heat.internal_flow.nusselt.laminar_const_temp": _feldspar.heat_laminar_nusselt(
                True
            )
        }
    )


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=(),
    outputs=("heat.internal_flow.nusselt.laminar_const_flux",),
    domain=Domain(box={}, tags={"laminar", "constant_heat_flux"}),
    cost=1e-9,
    accuracy=EXACT,
    citations=_LAMINAR_NUSSELT_CITATIONS,
    version="1",
)
# frob:ticket T-0020
def laminar_fully_developed_nusselt_const_flux(_x):
    return Ok(
        {
            "heat.internal_flow.nusselt.laminar_const_flux": _feldspar.heat_laminar_nusselt(
                False
            )
        }
    )


_CHURCHILL_CHU_HORIZONTAL_CITATIONS = (
    Citation(kind="paper", ref=_CHURCHILL_CHU_HORIZONTAL),
    Citation(
        kind="handbook",
        ref=_INCROPERA,
        note="eq. 9.34, Churchill-Chu restatement (primary paywalled)",
    ),
)
_CHURCHILL_CHU_VERTICAL_CITATIONS = (
    Citation(kind="paper", ref=_CHURCHILL_CHU_VERTICAL),
    Citation(
        kind="handbook",
        ref=_INCROPERA,
        note="eq. 9.26, Churchill-Chu restatement (primary paywalled)",
    ),
)


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=("heat.natural_convection.rayleigh", "heat.natural_convection.prandtl"),
    outputs=("heat.natural_convection.nusselt.horizontal_cylinder",),
    domain=Domain(
        box={
            # Churchill-Chu horizontal-cylinder correlation's published
            # full-range validity: Ra <= 1e12.
            "heat.natural_convection.rayleigh": Interval(1e-2, 1e12),
            "heat.natural_convection.prandtl": Interval(1e-3, 1e4),
        },
        tags={"natural_convection", "horizontal_cylinder"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_CHURCHILL_CHU_HORIZONTAL_CITATIONS,
    version="1",
)
# frob:ticket T-0020
def churchill_chu_horizontal_cylinder_nusselt(x):
    rayleigh = x["heat.natural_convection.rayleigh"]
    prandtl = x["heat.natural_convection.prandtl"]
    return Ok(
        {
            "heat.natural_convection.nusselt.horizontal_cylinder": (
                _feldspar.heat_churchill_chu_horizontal_cylinder_nusselt(
                    rayleigh, prandtl
                )
            )
        }
    )


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=("heat.natural_convection.rayleigh", "heat.natural_convection.prandtl"),
    outputs=("heat.natural_convection.nusselt.vertical_plate",),
    domain=Domain(
        box={
            "heat.natural_convection.rayleigh": Interval(1e-2, 1e12),
            "heat.natural_convection.prandtl": Interval(1e-3, 1e4),
        },
        tags={"natural_convection", "vertical_plate"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_CHURCHILL_CHU_VERTICAL_CITATIONS,
    version="1",
)
# frob:ticket T-0020
def churchill_chu_vertical_plate_nusselt(x):
    rayleigh = x["heat.natural_convection.rayleigh"]
    prandtl = x["heat.natural_convection.prandtl"]
    return Ok(
        {
            "heat.natural_convection.nusselt.vertical_plate": (
                _feldspar.heat_churchill_chu_vertical_plate_nusselt(rayleigh, prandtl)
            )
        }
    )


_NTU_CITATIONS = (
    Citation(
        kind="handbook",
        ref=_KAYS_LONDON,
        note="Table 11.4 lineage (Incropera restatement)",
    ),
    Citation(
        kind="handbook", ref=_INCROPERA, note="sec. 11.4, effectiveness-NTU method"
    ),
)


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=("heat.hx.ua", "heat.hx.c_min"),
    outputs=("heat.hx.ntu",),
    domain=Domain(
        box={
            "heat.hx.ua": Interval(1e-6, 1e9),
            "heat.hx.c_min": Interval(1e-6, 1e9),
        },
        tags={"ntu_effectiveness"},
    ),
    cost=1e-9,
    accuracy=EXACT,
    citations=_NTU_CITATIONS,
    version="1",
)
# frob:ticket T-0020
def ntu_from_ua(x):
    ua = x["heat.hx.ua"]
    c_min = x["heat.hx.c_min"]
    return Ok({"heat.hx.ntu": _feldspar.heat_ntu_from_ua(ua, c_min)})


# frob:ticket T-0020
def _ntu_domain(tags):
    return Domain(
        box={
            "heat.hx.ntu": Interval(0.0, 100.0),
            "heat.hx.c_r": Interval(0.0, 1.0),
        },
        tags=tags,
    )


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=("heat.hx.ntu", "heat.hx.c_r"),
    outputs=("heat.hx.effectiveness.parallel_flow",),
    domain=_ntu_domain({"ntu_effectiveness", "parallel_flow"}),
    cost=1e-7,
    accuracy=EXACT,
    citations=_NTU_CITATIONS,
    version="1",
)
# frob:ticket T-0020
def effectiveness_parallel_flow(x):
    ntu = x["heat.hx.ntu"]
    c_r = x["heat.hx.c_r"]
    return Ok(
        {
            "heat.hx.effectiveness.parallel_flow": _feldspar.heat_effectiveness_parallel_flow(
                ntu, c_r
            )
        }
    )


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=("heat.hx.ntu", "heat.hx.c_r"),
    outputs=("heat.hx.effectiveness.counterflow",),
    domain=_ntu_domain({"ntu_effectiveness", "counterflow"}),
    cost=1e-7,
    accuracy=EXACT,
    citations=_NTU_CITATIONS,
    version="1",
)
# frob:ticket T-0020
def effectiveness_counterflow(x):
    ntu = x["heat.hx.ntu"]
    c_r = x["heat.hx.c_r"]
    return Ok(
        {
            "heat.hx.effectiveness.counterflow": _feldspar.heat_effectiveness_counterflow(
                ntu, c_r
            )
        }
    )


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=("heat.hx.ntu", "heat.hx.c_r"),
    outputs=("heat.hx.effectiveness.shell_and_tube_one_pass",),
    domain=_ntu_domain({"ntu_effectiveness", "shell_and_tube"}),
    cost=1e-7,
    accuracy=EXACT,
    citations=_NTU_CITATIONS,
    version="1",
)
# frob:ticket T-0020
def effectiveness_shell_and_tube_one_pass(x):
    ntu = x["heat.hx.ntu"]
    c_r = x["heat.hx.c_r"]
    return Ok(
        {
            "heat.hx.effectiveness.shell_and_tube_one_pass": (
                _feldspar.heat_effectiveness_shell_and_tube_one_pass(ntu, c_r)
            )
        }
    )


_HX_ENERGY_BALANCE_CITATIONS = (
    Citation(kind="handbook", ref=_INCROPERA, note="sec. 11.1/11.3, HX energy balance"),
)


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=(
        "heat.hx.effectiveness",
        "heat.hx.c_min",
        "heat.hx.t_hot_in",
        "heat.hx.t_cold_in",
    ),
    outputs=("heat.hx.rate",),
    domain=Domain(
        box={
            "heat.hx.effectiveness": Interval(0.0, 1.0),
            "heat.hx.c_min": Interval(1e-6, 1e9),
            "heat.hx.t_hot_in": Interval(-273.0, 1e4),
            "heat.hx.t_cold_in": Interval(-273.0, 1e4),
        },
        tags={"ntu_effectiveness"},
    ),
    cost=1e-9,
    accuracy=EXACT,
    citations=_HX_ENERGY_BALANCE_CITATIONS,
    version="1",
)
# frob:ticket T-0020
def hx_rate_from_effectiveness(x):
    effectiveness = x["heat.hx.effectiveness"]
    c_min = x["heat.hx.c_min"]
    t_hot_in = x["heat.hx.t_hot_in"]
    t_cold_in = x["heat.hx.t_cold_in"]
    return Ok(
        {
            "heat.hx.rate": _feldspar.heat_hx_rate_from_effectiveness(
                effectiveness, c_min, t_hot_in, t_cold_in
            )
        }
    )


_HX_OUTLET_DOMAIN = Domain(
    box={
        "heat.hx.t_in": Interval(-273.0, 1e4),
        "heat.hx.rate": Interval(-1e12, 1e12),
        "heat.hx.capacity_rate": Interval(1e-6, 1e9),
    },
    tags={"ntu_effectiveness"},
)


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=("heat.hx.t_in", "heat.hx.rate", "heat.hx.capacity_rate"),
    outputs=("heat.hx.t_out.hot",),
    domain=_HX_OUTLET_DOMAIN,
    cost=1e-9,
    accuracy=EXACT,
    citations=_HX_ENERGY_BALANCE_CITATIONS,
    version="1",
)
# frob:ticket T-0020
def hx_outlet_temp_hot(x):
    """Hot-stream outlet: `T_out = T_in - q/C` (the stream is cooled)."""
    t_in = x["heat.hx.t_in"]
    rate = x["heat.hx.rate"]
    capacity_rate = x["heat.hx.capacity_rate"]
    return Ok(
        {
            "heat.hx.t_out.hot": _feldspar.heat_hx_outlet_temp(
                t_in, rate, capacity_rate, True
            )
        }
    )


# frob:doc docs/modules/heat.md#heat_closed_form
@solver(
    namespace="heat",
    inputs=("heat.hx.t_in", "heat.hx.rate", "heat.hx.capacity_rate"),
    outputs=("heat.hx.t_out.cold",),
    domain=_HX_OUTLET_DOMAIN,
    cost=1e-9,
    accuracy=EXACT,
    citations=_HX_ENERGY_BALANCE_CITATIONS,
    version="1",
)
# frob:ticket T-0020
def hx_outlet_temp_cold(x):
    """Cold-stream outlet: `T_out = T_in + q/C` (the stream is heated)."""
    t_in = x["heat.hx.t_in"]
    rate = x["heat.hx.rate"]
    capacity_rate = x["heat.hx.capacity_rate"]
    return Ok(
        {
            "heat.hx.t_out.cold": _feldspar.heat_hx_outlet_temp(
                t_in, rate, capacity_rate, False
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
    PortDecl("heat.internal_flow.friction_factor", "1"),
    PortDecl("heat.internal_flow.nusselt.gnielinski", "1"),
    PortDecl("heat.internal_flow.nusselt.laminar_const_temp", "1"),
    PortDecl("heat.internal_flow.nusselt.laminar_const_flux", "1"),
    PortDecl("heat.natural_convection.rayleigh", "1"),
    PortDecl("heat.natural_convection.prandtl", "1"),
    PortDecl("heat.natural_convection.nusselt.horizontal_cylinder", "1"),
    PortDecl("heat.natural_convection.nusselt.vertical_plate", "1"),
    PortDecl("heat.hx.ua", "W/K"),
    PortDecl("heat.hx.c_min", "W/K"),
    PortDecl("heat.hx.c_r", "1"),
    PortDecl("heat.hx.ntu", "1"),
    PortDecl("heat.hx.effectiveness", "1"),
    PortDecl("heat.hx.effectiveness.parallel_flow", "1"),
    PortDecl("heat.hx.effectiveness.counterflow", "1"),
    PortDecl("heat.hx.effectiveness.shell_and_tube_one_pass", "1"),
    PortDecl("heat.hx.t_hot_in", "K"),
    PortDecl("heat.hx.t_cold_in", "K"),
    PortDecl("heat.hx.rate", "W"),
    PortDecl("heat.hx.t_in", "K"),
    PortDecl("heat.hx.capacity_rate", "W/K"),
    PortDecl("heat.hx.t_out.hot", "K"),
    PortDecl("heat.hx.t_out.cold", "K"),
)


# frob:doc docs/modules/heat.md#heat_closed_form
# frob:ticket T-0020
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
        dittus_boelter_nusselt_cooling.solver_direction,  # ty: ignore[unresolved-attribute]
        gnielinski_nusselt.solver_direction,  # ty: ignore[unresolved-attribute]
        laminar_fully_developed_nusselt_const_temp.solver_direction,  # ty: ignore[unresolved-attribute]
        laminar_fully_developed_nusselt_const_flux.solver_direction,  # ty: ignore[unresolved-attribute]
        churchill_chu_horizontal_cylinder_nusselt.solver_direction,  # ty: ignore[unresolved-attribute]
        churchill_chu_vertical_plate_nusselt.solver_direction,  # ty: ignore[unresolved-attribute]
        ntu_from_ua.solver_direction,  # ty: ignore[unresolved-attribute]
        effectiveness_parallel_flow.solver_direction,  # ty: ignore[unresolved-attribute]
        effectiveness_counterflow.solver_direction,  # ty: ignore[unresolved-attribute]
        effectiveness_shell_and_tube_one_pass.solver_direction,  # ty: ignore[unresolved-attribute]
        hx_rate_from_effectiveness.solver_direction,  # ty: ignore[unresolved-attribute]
        hx_outlet_temp_hot.solver_direction,  # ty: ignore[unresolved-attribute]
        hx_outlet_temp_cold.solver_direction,  # ty: ignore[unresolved-attribute]
    ]
    for direction in directions:
        result = registry.register(*direction)
        _ = result.danger_ok
    _log.info("heat: registered %d solver directions", len(directions))
