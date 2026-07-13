from __future__ import annotations

"""Shaft critical (whirl) speed tier -- WO-111 Class-C model growth
(lithos design-log 2026-07-13-cycle-35 D223, which adds shaft critical
speed to the solver pack explicitly; corpus `mech.critical_speed` waives
on the reaction_wheel / dune_buggy / cnc_router shafts).

The first critical speed of a rotating shaft equals its first bending
natural frequency (Shigley 11e ch. 7 sec. 7-6: the shaft whirls when the
rotation rate coincides with a lateral natural frequency). Two closed-
form directions, both STEEL-agnostic (pure dynamics, no material-strength
assumption), both HONEST-NARROW (single lumped mass, undamped, first mode
only):

- `shaft_critical_speed_from_stiffness`: the single-degree-of-freedom
  relation `omega_c = sqrt(k/m)`, `n_c = omega_c*60/(2*pi)` rpm, over a
  caller-supplied lateral stiffness `k` (N/m, at the mass location) and
  lumped mass `m` (kg). Shigley 11e eq. 7-22 in its `omega = sqrt(k/m)`
  form. EXACT.
- `shaft_critical_speed_rayleigh_single_mass`: Rayleigh's method for a
  single mass, `n_c = (30/pi)*sqrt(g/delta)` rpm, over a caller-supplied
  static deflection `delta` (m) under the mass's own weight (Shigley 11e
  eq. 7-23, the single-mass Rayleigh estimate). EXACT (the deflection is
  caller-resolved; this direction only evaluates the closed form).

NAMED CUTS (module scope, per the WO-24/WO-111 standing law): multi-mass
Rayleigh/Dunkerley summations (`omega = sqrt(g*sum(w*y)/sum(w*y^2))`,
Dunkerley `1/omega^2 = sum(1/omega_i^2)`) are NOT built -- a caller with
several masses composes per-mass deflections upstream and supplies the
aggregate `delta` (or `k`,`m`) to these directions, the same "caller-
resolved aggregate" seam every WO-24 module uses. Damped whirl, gyroscopic
stiffening, and higher critical speeds are OUT (first undamped mode only).

CALIBRATION HONESTY (WO111-F1): both directions are exact evaluations of
their cited textbook closed forms; the calibration tests evaluate the
same published formula analytically (no independent worked numeric with a
verified page/example number was transcribed), plus a cross-check that
the two directions agree for a case where `k = m*g/delta` (the static-
deflection and stiffness views of one mass must give one critical speed).
"""

import math

from typani import Err, Ok

from feldspar.core import Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register", "G_STANDARD"]

_SHIGLEY = "Shigley's Mechanical Engineering Design, 11th ed."

#: Standard gravity, m/s^2 (CODATA/ISO 80000-3), used by the Rayleigh
#: static-deflection direction.
G_STANDARD = 9.80665


_STIFFNESS_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_SHIGLEY}, ch. 7 sec. 7-6 eq. 7-22 (first critical speed of "
            "a single-mass shaft = its lateral natural frequency, "
            "omega_c = sqrt(k/m); n_c = omega_c*60/(2*pi) rpm; "
            "docs/benchmarks-memo.md sec. 16.1)"
        ),
        note=(
            "Single lumped mass, undamped, first mode only. Multi-mass "
            "Rayleigh/Dunkerley aggregation is a named cut -- caller "
            "supplies the effective k, m."
        ),
    ),
)


@solver(
    namespace="mech.critical_speed",
    inputs=(
        "mech.critical_speed.stiffness",
        "mech.critical_speed.mass",
    ),
    outputs=("mech.critical_speed.rpm",),
    domain=Domain(
        box={
            # Lateral stiffness at the mass location, N/m.
            "mech.critical_speed.stiffness": Interval(1.0e2, 1.0e12),
            # Lumped mass, kg.
            "mech.critical_speed.mass": Interval(1.0e-4, 1.0e5),
        },
        tags={"single_mass", "undamped", "first_mode"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_STIFFNESS_CITATIONS,
    version="1",
)
def shaft_critical_speed_from_stiffness(x):
    """Shigley 11e eq. 7-22: `n_c = (60/(2*pi))*sqrt(k/m)` rpm, the
    single-mass shaft first critical speed from lateral stiffness `k`
    (N/m) and lumped mass `m` (kg)."""
    k = x["mech.critical_speed.stiffness"]
    m = x["mech.critical_speed.mass"]
    if k <= 0.0 or m <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"critical speed: non-positive stiffness={k!r} or mass={m!r}"
            )
        )
    omega_c = math.sqrt(k / m)
    n_c = omega_c * 60.0 / (2.0 * math.pi)
    return Ok({"mech.critical_speed.rpm": n_c})


_RAYLEIGH_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_SHIGLEY}, ch. 7 sec. 7-6 eq. 7-23 (Rayleigh single-mass "
            "critical speed from static deflection, "
            "n_c = (30/pi)*sqrt(g/delta) rpm; docs/benchmarks-memo.md "
            "sec. 16.2)"
        ),
        note=(
            "`delta` is the caller-resolved static deflection under the "
            "mass's own weight; g = 9.80665 m/s^2. Single mass only."
        ),
    ),
)


@solver(
    namespace="mech.critical_speed",
    inputs=("mech.critical_speed.static_deflection",),
    outputs=("mech.critical_speed.rayleigh_rpm",),
    domain=Domain(
        box={
            # Static deflection under self-weight, m.
            "mech.critical_speed.static_deflection": Interval(1.0e-9, 1.0),
        },
        tags={"single_mass", "undamped", "first_mode"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_RAYLEIGH_CITATIONS,
    version="1",
)
def shaft_critical_speed_rayleigh_single_mass(x):
    """Shigley 11e eq. 7-23: `n_c = (30/pi)*sqrt(g/delta)` rpm, the
    single-mass Rayleigh critical speed from static deflection `delta`
    (m) under self-weight."""
    delta = x["mech.critical_speed.static_deflection"]
    if delta <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"Rayleigh critical speed: non-positive delta={delta!r}"
            )
        )
    n_c = (30.0 / math.pi) * math.sqrt(G_STANDARD / delta)
    return Ok({"mech.critical_speed.rayleigh_rpm": n_c})


#: This family's port table (WO111b composition fix; see
#: `member_capacity.py`'s `_PORT_DECLS` note).
_PORT_DECLS = (
    PortDecl("mech.critical_speed.stiffness", "N/m"),
    PortDecl("mech.critical_speed.mass", "kg"),
    PortDecl("mech.critical_speed.rpm", "rev/min"),
    PortDecl("mech.critical_speed.static_deflection", "m"),
    PortDecl("mech.critical_speed.rayleigh_rpm", "rev/min"),
)


def register(registry: SolverRegistry) -> None:
    """Registers the two shaft-critical-speed directions (WO-111:
    stiffness-based and Rayleigh single-mass). Declares this family's
    port table first (WO111b)."""
    _ = registry.declare_ports(*_PORT_DECLS).danger_ok
    stiffness_dir = shaft_critical_speed_from_stiffness.solver_direction  # ty: ignore[unresolved-attribute]
    _ = registry.register(*stiffness_dir).danger_ok
    rayleigh_dir = shaft_critical_speed_rayleigh_single_mass.solver_direction  # ty: ignore[unresolved-attribute]
    _ = registry.register(*rayleigh_dir).danger_ok
    _log.info("critical_speed: registered %d solver directions", 2)
