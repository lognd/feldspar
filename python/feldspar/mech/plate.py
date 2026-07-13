from __future__ import annotations

"""Flat-plate uniform-load tier -- WO-111 Class-C model growth (WO-24
deliverable 5, the Roark deflection-catalog completion the fleet's
panel claims touch: circular plates under uniform pressure -- espresso
boiler covers, hydraulic manifold end panels, sealed enclosure lids).

Circular flat plate, uniform load `q` (Pa) over the full face, radius
`a` (m), thickness `t` (m), modulus `E` (Pa), Poisson ratio `nu`
(Roark's Formulas for Stress and Strain, 8th ed., Table 11.2, cases
10a simply-supported and 10b clamped; identical to Timoshenko & Woinowsky-
Krieger, Theory of Plates and Shells, 2nd ed., arts. 16-17). Flexural
rigidity `D = E*t^3 / (12*(1-nu^2))`.

Directions (four, both edge conditions x {max stress, max deflection}):

- simply-supported edge (case 10a):
    y_max = q*a^4*(5+nu) / (64*D*(1+nu))     (center)
    sigma_max = 3*q*a^2*(3+nu) / (8*t^2)     (center, radial=tangential)
- clamped edge (case 10b):
    y_max = q*a^4 / (64*D)                    (center)
    sigma_max = 3*q*a^2 / (4*t^2)             (edge, radial)

SCOPE (honest, narrow): SMALL-DEFLECTION thin-plate (Kirchhoff) theory
only -- valid for `y_max <~ t/2` and `a/t >~ 10`; large-deflection
membrane stiffening (Roark Table 11.2 note, Timoshenko art. 96) is a
named cut, NOT modeled. Rectangular plates need the aspect-ratio-
dependent alpha/beta coefficient tables (Roark Table 11.4) -- a caller
with a rectangular panel supplies its own tabulated coefficients through
the general `plate_uniform_from_coefficient` direction below (the same
"caller-resolved tabulated constant" seam `fatigue.py`'s Table 6-2 a/b
uses), rather than this module transcribing the whole table uncalibrated.
Uniform load only (no central patch, no edge moment). Isotropic,
homogeneous, constant thickness.

Senses for pack exposure: `sigma_max` is a CEILING claim (peak bending
stress must stay AT OR BELOW the allowable), `y_max` a CEILING claim
(deflection must stay AT OR BELOW a serviceability limit). The simply-
supported forms are the conservative choice under uncertain edge fixity
(they give the larger stress and deflection), so the pack wraps those.

CALIBRATION: exact evaluations of the cited Roark closed forms, tol
rel=1e-9 (pure algebra, no empirical fit). The published SS-vs-clamped
ratios are asserted as an independent structural cross-check (a clamped
plate is stiffer and lower-stressed than the same simply-supported one).
"""

from typani import Err, Ok

from feldspar.core import Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register", "flexural_rigidity"]

_ROARK = "Roark's Formulas for Stress and Strain, 8th ed., Table 11.2"

# Shared input ports (all four closed-form directions take the same
# geometry/material box; kept as one home, NO DUPLICATION).
_GEOM_BOX = {
    # Uniform pressure over the full face, Pa.
    "mech.plate.circular.q": Interval(1.0, 1.0e9),
    # Plate radius, m.
    "mech.plate.circular.a": Interval(1.0e-3, 5.0),
    # Plate thickness, m.
    "mech.plate.circular.t": Interval(1.0e-4, 1.0),
    # Young's modulus, Pa.
    "mech.plate.circular.e": Interval(1.0e6, 1.0e12),
    # Poisson ratio (isotropic).
    "mech.plate.circular.nu": Interval(0.0, 0.5),
}


def flexural_rigidity(e: float, t: float, nu: float) -> float:
    """Kirchhoff plate flexural rigidity `D = E*t^3 / (12*(1-nu^2))`
    (Roark Table 11.2 header; Timoshenko art. 16). One home for the
    two deflection directions."""
    return e * t**3 / (12.0 * (1.0 - nu**2))


def _reject_geom(q: float, a: float, t: float, e: float, nu: float, where: str):
    """Shared non-positive / out-of-range guard for the geometry box.
    Returns an `Err` `SolveError` or `None` (valid)."""
    if q <= 0.0 or a <= 0.0 or t <= 0.0 or e <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"{where}: non-positive q={q!r}, a={a!r}, t={t!r}, or e={e!r}"
                )
            )
        )
    if not (0.0 <= nu < 0.5):
        return Err(
            SolveError.OutOfDomain(
                violation=f"{where}: Poisson ratio nu={nu!r} outside [0, 0.5)"
            )
        )
    return None


_SS_STRESS_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_ROARK}, case 10a (circular plate, uniform load, simply-"
            "supported edge): sigma_max = 3*q*a^2*(3+nu)/(8*t^2) at "
            "center; docs/benchmarks-memo.md sec. 17.1"
        ),
        note="Small-deflection Kirchhoff theory (a/t >~ 10, y_max <~ t/2).",
    ),
)


@solver(
    namespace="mech.plate",
    inputs=tuple(_GEOM_BOX),
    outputs=("mech.plate.circular.ss_max_stress",),
    domain=Domain(
        box=dict(_GEOM_BOX), tags={"thin_plate", "small_deflection", "circular"}
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_SS_STRESS_CITATIONS,
    version="1",
)
def plate_circular_uniform_ss_max_stress(x):
    """Roark Table 11.2 case 10a: max radial=tangential bending stress at
    the center of a uniformly loaded simply-supported circular plate,
    `sigma = 3*q*a^2*(3+nu)/(8*t^2)`."""
    q = x["mech.plate.circular.q"]
    a = x["mech.plate.circular.a"]
    t = x["mech.plate.circular.t"]
    e = x["mech.plate.circular.e"]
    nu = x["mech.plate.circular.nu"]
    err = _reject_geom(q, a, t, e, nu, "plate SS max stress")
    if err is not None:
        return err
    sigma = 3.0 * q * a**2 * (3.0 + nu) / (8.0 * t**2)
    return Ok({"mech.plate.circular.ss_max_stress": sigma})


_SS_DEFL_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_ROARK}, case 10a (circular plate, uniform load, simply-"
            "supported edge): y_max = q*a^4*(5+nu)/(64*D*(1+nu)) at "
            "center, D = E*t^3/(12*(1-nu^2)); docs/benchmarks-memo.md "
            "sec. 17.2"
        ),
        note="Small-deflection Kirchhoff theory.",
    ),
)


@solver(
    namespace="mech.plate",
    inputs=tuple(_GEOM_BOX),
    outputs=("mech.plate.circular.ss_max_deflection",),
    domain=Domain(
        box=dict(_GEOM_BOX), tags={"thin_plate", "small_deflection", "circular"}
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_SS_DEFL_CITATIONS,
    version="1",
)
def plate_circular_uniform_ss_max_deflection(x):
    """Roark Table 11.2 case 10a: center deflection of a uniformly
    loaded simply-supported circular plate,
    `y = q*a^4*(5+nu)/(64*D*(1+nu))`."""
    q = x["mech.plate.circular.q"]
    a = x["mech.plate.circular.a"]
    t = x["mech.plate.circular.t"]
    e = x["mech.plate.circular.e"]
    nu = x["mech.plate.circular.nu"]
    err = _reject_geom(q, a, t, e, nu, "plate SS max deflection")
    if err is not None:
        return err
    d = flexural_rigidity(e, t, nu)
    y = q * a**4 * (5.0 + nu) / (64.0 * d * (1.0 + nu))
    return Ok({"mech.plate.circular.ss_max_deflection": y})


_CLAMPED_STRESS_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_ROARK}, case 10b (circular plate, uniform load, clamped "
            "edge): sigma_max = 3*q*a^2/(4*t^2) at edge; "
            "docs/benchmarks-memo.md sec. 17.3"
        ),
        note="Small-deflection Kirchhoff theory.",
    ),
)


@solver(
    namespace="mech.plate",
    inputs=tuple(_GEOM_BOX),
    outputs=("mech.plate.circular.clamped_max_stress",),
    domain=Domain(
        box=dict(_GEOM_BOX), tags={"thin_plate", "small_deflection", "circular"}
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_CLAMPED_STRESS_CITATIONS,
    version="1",
)
def plate_circular_uniform_clamped_max_stress(x):
    """Roark Table 11.2 case 10b: max radial bending stress at the edge
    of a uniformly loaded clamped circular plate,
    `sigma = 3*q*a^2/(4*t^2)`."""
    q = x["mech.plate.circular.q"]
    a = x["mech.plate.circular.a"]
    t = x["mech.plate.circular.t"]
    e = x["mech.plate.circular.e"]
    nu = x["mech.plate.circular.nu"]
    err = _reject_geom(q, a, t, e, nu, "plate clamped max stress")
    if err is not None:
        return err
    sigma = 3.0 * q * a**2 / (4.0 * t**2)
    return Ok({"mech.plate.circular.clamped_max_stress": sigma})


_CLAMPED_DEFL_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_ROARK}, case 10b (circular plate, uniform load, clamped "
            "edge): y_max = q*a^4/(64*D) at center; "
            "docs/benchmarks-memo.md sec. 17.4"
        ),
        note="Small-deflection Kirchhoff theory.",
    ),
)


@solver(
    namespace="mech.plate",
    inputs=tuple(_GEOM_BOX),
    outputs=("mech.plate.circular.clamped_max_deflection",),
    domain=Domain(
        box=dict(_GEOM_BOX), tags={"thin_plate", "small_deflection", "circular"}
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_CLAMPED_DEFL_CITATIONS,
    version="1",
)
def plate_circular_uniform_clamped_max_deflection(x):
    """Roark Table 11.2 case 10b: center deflection of a uniformly
    loaded clamped circular plate, `y = q*a^4/(64*D)`."""
    q = x["mech.plate.circular.q"]
    a = x["mech.plate.circular.a"]
    t = x["mech.plate.circular.t"]
    e = x["mech.plate.circular.e"]
    nu = x["mech.plate.circular.nu"]
    err = _reject_geom(q, a, t, e, nu, "plate clamped max deflection")
    if err is not None:
        return err
    d = flexural_rigidity(e, t, nu)
    y = q * a**4 / (64.0 * d)
    return Ok({"mech.plate.circular.clamped_max_deflection": y})


#: This family's port table (WO111b composition fix; see
#: `member_capacity.py`'s `_PORT_DECLS` note).
_PORT_DECLS = (
    PortDecl("mech.plate.circular.q", "Pa"),
    PortDecl("mech.plate.circular.a", "m"),
    PortDecl("mech.plate.circular.t", "m"),
    PortDecl("mech.plate.circular.e", "Pa"),
    PortDecl("mech.plate.circular.nu", "1"),
    PortDecl("mech.plate.circular.ss_max_stress", "Pa"),
    PortDecl("mech.plate.circular.ss_max_deflection", "m"),
    PortDecl("mech.plate.circular.clamped_max_stress", "Pa"),
    PortDecl("mech.plate.circular.clamped_max_deflection", "m"),
)


def register(registry: SolverRegistry) -> None:
    """Registers the four circular-plate uniform-load directions
    (WO-111: simply-supported and clamped, max stress and max
    deflection). Declares this family's port table first (WO111b)."""
    _ = registry.declare_ports(*_PORT_DECLS).danger_ok
    for direction in (
        plate_circular_uniform_ss_max_stress,
        plate_circular_uniform_ss_max_deflection,
        plate_circular_uniform_clamped_max_stress,
        plate_circular_uniform_clamped_max_deflection,
    ):
        result = registry.register(*direction.solver_direction)  # ty: ignore[unresolved-attribute]
        _ = result.danger_ok
    _log.info("plate: registered %d solver directions", 4)
