from __future__ import annotations

"""Hardenability closed forms (T-0018 slice 3): Grossmann's ideal
critical diameter multiplicative-factor law, the Jominy end-quench
distance-to-cooling-rate power-law correlation, and the Hollomon-Jaffe
(1945) tempering parameter.

Same caller-supplied-constant discipline as `materials.kinetics`
(module docstring there): each direction evaluates the cited law's
actual mathematical FORM; per-alloy/per-element fitted constants
(Grossmann's base-diameter-vs-carbon curve and multiplying-factor
tables, the Jominy correlation's fitted power-law coefficients) are
caller-supplied inputs rather than transcribed chart/table data
(licensing law, D258/D266/D269) -- the same seam `mech.member_
capacity`'s `K` and `mech.fatigue`'s Marin `a`/`b` already use."""

import math

from typani import Err, Ok

from feldspar.core import Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

_GROSSMANN = (
    "Grossmann, M. A. (1942), 'Hardenability Calculated from Chemical "
    "Composition', Trans. AIME, 150, 227-255 -- the ideal critical "
    "diameter D_I as a base-carbon diameter multiplied by per-element "
    "hardenability multiplying factors."
)
_JOMINY = (
    "Jominy, W. E., and Boegehold, A. L. (1938), 'A Hardenability Test "
    "for Carburized Steel', Trans. ASM, 26, 574-600 (ASTM A255 end-"
    "quench hardenability test) -- the empirical cooling-rate-vs-"
    "distance-from-quenched-end correlation along a standard Jominy "
    "bar, well fit by a power law in the mid-bar region."
)
_HOLLOMON_JAFFE = (
    "Hollomon, J. H., and Jaffe, L. D. (1945), 'Time-Temperature "
    "Relations in Tempering Steel', Trans. AIME, 162, 223-249 -- the "
    "tempering parameter P = T*(C + log10(t))."
)


# ---------------------------------------------------------------------------
# Grossmann: D_I = D_I_base * product(multiplying factors)
# ---------------------------------------------------------------------------

_GROSSMANN_CITATIONS = (
    Citation(
        kind="paper",
        ref=_GROSSMANN,
        note=(
            "`base_diameter` (Grossmann's own carbon-content/grain-"
            "size base curve) and `multiplying_factor` (the product of "
            "his per-element Mn/Si/Cr/Ni/Mo factors) are CALLER-"
            "SUPPLIED -- transcribing Grossmann's own chart-derived "
            "base curve is exactly the licensing risk this ticket "
            "flags (D258/D266/D269), so this direction only performs "
            "the multiplicative composition law itself. Calibration is "
            "a hand-computed check of that multiplication; an "
            "independent second-source oracle point was not located "
            "this dispatch (named residual)."
        ),
    ),
)


# frob:doc docs/modules/materials.md#materials_hardenability
@solver(
    namespace="materials.hardenability",
    inputs=(
        "materials.hardenability.grossmann.base_diameter",
        "materials.hardenability.grossmann.multiplying_factor",
    ),
    outputs=("materials.hardenability.grossmann.ideal_critical_diameter",),
    domain=Domain(
        box={
            # Base ideal critical diameter (plain-carbon base curve
            # value), m.
            "materials.hardenability.grossmann.base_diameter": Interval(1e-4, 1.0),
            # Product of per-element multiplying factors (>= 1.0:
            # alloying additions increase hardenability).
            "materials.hardenability.grossmann.multiplying_factor": Interval(1.0, 50.0),
        },
        tags={"hardenability"},
    ),
    cost=1e-9,
    accuracy=EXACT,
    citations=_GROSSMANN_CITATIONS,
    version="1",
)
def grossmann_ideal_critical_diameter(x):
    """Grossmann (1942): `D_I = base_diameter * multiplying_factor`,
    the ideal critical diameter as a base (carbon-content/grain-size)
    diameter scaled by the product of per-alloying-element
    multiplying factors (both caller-supplied -- see citation note)."""
    base_diameter = x["materials.hardenability.grossmann.base_diameter"]
    multiplying_factor = x["materials.hardenability.grossmann.multiplying_factor"]
    if base_diameter <= 0.0 or multiplying_factor <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    "Grossmann D_I: non-positive base_diameter="
                    f"{base_diameter!r} or multiplying_factor={multiplying_factor!r}"
                )
            )
        )
    return Ok(
        {
            "materials.hardenability.grossmann.ideal_critical_diameter": (
                base_diameter * multiplying_factor
            )
        }
    )


# ---------------------------------------------------------------------------
# Jominy: cooling_rate(distance) = coeff * distance^exponent
# ---------------------------------------------------------------------------

_JOMINY_CITATIONS = (
    Citation(
        kind="paper",
        ref=_JOMINY,
        note=(
            "`coeff`/`exponent` are CALLER-SUPPLIED power-law fit "
            "constants for the mid-bar Jominy cooling-rate-vs-distance "
            "correlation (the exact published fit constants vary by "
            "source and quenchant; transcribing a specific numeric fit "
            "from memory risked an uncited value, so this direction "
            "takes the fit as an input, same seam as the diffusional-"
            "onset direction in materials.kinetics). Calibration is a "
            "hand-computed power-law check; an independent second-"
            "source oracle point was not located this dispatch (named "
            "residual)."
        ),
    ),
)


# frob:doc docs/modules/materials.md#materials_hardenability
@solver(
    namespace="materials.hardenability",
    inputs=(
        "materials.hardenability.jominy.distance",
        "materials.hardenability.jominy.coeff",
        "materials.hardenability.jominy.exponent",
    ),
    outputs=("materials.hardenability.jominy.cooling_rate",),
    domain=Domain(
        box={
            # Distance from the quenched end, m (ASTM A255 bar is
            # 25.4 mm diameter x 100 mm long; distances up to ~80 mm).
            "materials.hardenability.jominy.distance": Interval(1e-3, 0.1),
            # Power-law coefficient, K/s * m^(-exponent) folded in
            # (caller-fitted, keeps this a pure power-law evaluator).
            "materials.hardenability.jominy.coeff": Interval(1e-6, 1e6),
            # Power-law exponent (negative: cooling rate falls with
            # distance from the quenched end).
            "materials.hardenability.jominy.exponent": Interval(-5.0, 0.0),
        },
        tags={"hardenability", "jominy"},
    ),
    cost=1e-9,
    accuracy=EXACT,
    citations=_JOMINY_CITATIONS,
    version="1",
)
def jominy_distance_to_cooling_rate(x):
    """`cooling_rate = coeff * distance^exponent`: the Jominy end-
    quench distance-to-cooling-rate power-law correlation (`coeff`/
    `exponent` caller-fitted -- see citation note)."""
    distance = x["materials.hardenability.jominy.distance"]
    coeff = x["materials.hardenability.jominy.coeff"]
    exponent = x["materials.hardenability.jominy.exponent"]
    if distance <= 0.0 or coeff <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"Jominy correlation: non-positive distance={distance!r} "
                    f"or coeff={coeff!r}"
                )
            )
        )
    cooling_rate = coeff * (distance**exponent)
    return Ok({"materials.hardenability.jominy.cooling_rate": cooling_rate})


# ---------------------------------------------------------------------------
# Hollomon-Jaffe: P = T*(C + log10(t))
# ---------------------------------------------------------------------------

_HOLLOMON_JAFFE_CITATIONS = (
    Citation(
        kind="paper",
        ref=_HOLLOMON_JAFFE,
        note=(
            "`constant_c` is CALLER-SUPPLIED (commonly quoted near 20 "
            "for many steels in the original paper's own fit, but "
            "varies by alloy -- this direction does not bake a "
            "default). Calibration below is a hand-computed check of "
            "the closed form itself; an independent second-source "
            "oracle point was not located this dispatch (named "
            "residual)."
        ),
    ),
)


# frob:doc docs/modules/materials.md#materials_hardenability
@solver(
    namespace="materials.hardenability",
    inputs=(
        "materials.hardenability.hollomon_jaffe.temperature",
        "materials.hardenability.hollomon_jaffe.time",
        "materials.hardenability.hollomon_jaffe.constant_c",
    ),
    outputs=("materials.hardenability.hollomon_jaffe.parameter",),
    domain=Domain(
        box={
            # Tempering temperature, K.
            "materials.hardenability.hollomon_jaffe.temperature": Interval(
                300.0, 1000.0
            ),
            # Tempering time, hours.
            "materials.hardenability.hollomon_jaffe.time": Interval(1e-3, 1e4),
            # The alloy-dependent constant C (order 10-25 for most
            # steels, wide box to cover published variants).
            "materials.hardenability.hollomon_jaffe.constant_c": Interval(5.0, 30.0),
        },
        tags={"tempering"},
    ),
    cost=1e-9,
    accuracy=EXACT,
    citations=_HOLLOMON_JAFFE_CITATIONS,
    version="1",
)
def hollomon_jaffe_tempering_parameter(x):
    """Hollomon & Jaffe (1945): `P = T*(C + log10(t))`, `T` in K, `t`
    in hours, `C` a caller-supplied alloy-dependent constant."""
    temperature = x["materials.hardenability.hollomon_jaffe.temperature"]
    time = x["materials.hardenability.hollomon_jaffe.time"]
    constant_c = x["materials.hardenability.hollomon_jaffe.constant_c"]
    if temperature <= 0.0 or time <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    "Hollomon-Jaffe: non-positive temperature="
                    f"{temperature!r} or time={time!r}"
                )
            )
        )
    parameter = temperature * (constant_c + math.log10(time))
    return Ok({"materials.hardenability.hollomon_jaffe.parameter": parameter})


_PORT_DECLS = (
    PortDecl("materials.hardenability.grossmann.base_diameter", "m"),
    PortDecl("materials.hardenability.grossmann.multiplying_factor", "1"),
    PortDecl("materials.hardenability.grossmann.ideal_critical_diameter", "m"),
    PortDecl("materials.hardenability.jominy.distance", "m"),
    PortDecl("materials.hardenability.jominy.coeff", "K/s"),
    PortDecl("materials.hardenability.jominy.exponent", "1"),
    PortDecl("materials.hardenability.jominy.cooling_rate", "K/s"),
    PortDecl("materials.hardenability.hollomon_jaffe.temperature", "K"),
    PortDecl("materials.hardenability.hollomon_jaffe.time", "h"),
    PortDecl("materials.hardenability.hollomon_jaffe.constant_c", "1"),
    PortDecl("materials.hardenability.hollomon_jaffe.parameter", "K"),
)


# frob:doc docs/modules/materials.md#materials_hardenability
def register(registry: SolverRegistry) -> None:
    """Registers every `materials.hardenability` direction (T-0018
    slice 3). Declares this family's port table first (WO111b
    convention)."""
    _ = registry.declare_ports(*_PORT_DECLS).danger_ok
    directions = [
        grossmann_ideal_critical_diameter.solver_direction,  # ty: ignore[unresolved-attribute]
        jominy_distance_to_cooling_rate.solver_direction,  # ty: ignore[unresolved-attribute]
        hollomon_jaffe_tempering_parameter.solver_direction,  # ty: ignore[unresolved-attribute]
    ]
    for direction in directions:
        result = registry.register(*direction)
        _ = result.danger_ok
    _log.info(
        "materials.hardenability: registered %d solver directions", len(directions)
    )
