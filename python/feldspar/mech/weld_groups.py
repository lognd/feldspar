from __future__ import annotations

"""Fillet-weld-group elastic line method (WO-24 deliverable 2, docs/
benchmarks-memo.md sec. 10): the classical "treat-the-weld-as-a-line"
statics for a fillet weld group under in-plane force + torque and a
separate out-of-plane bending moment, vector-summed to a single peak
line force and checked against a caller-supplied allowable.

SCOPE (honest, narrow -- the WO-24 standing law, same shape as
`bolted_joints.py`/`member_capacity.py`):

- `weld_group_inplane_shear_torsion` is Shigley 11e ch. 9 sec. 9-5/
  9-6 (also Blodgett, Design of Weldments, sec. 4.3-4.4) elastic line
  method for IN-PLANE loading: the weld throat is treated as having
  zero width, so a UNIT (per-unit-throat) area `Aw` (= total weld
  length, m) and UNIT polar second moment `Jw` (m^3) describe the
  pattern; the primary (direct) and secondary (torsional) unit line
  forces at a caller-named critical point `(x_i, y_i)` on the weld
  line are superposed. `Aw`/`Jw` are CALLER-SUPPLIED (this module
  does not derive them from a weld-line geometry catalog -- Blodgett/
  Shigley tabulate standard configurations, e.g. Table 9-1/9-2 or
  Blodgett Table 4, but transcribing that table is its own citation
  surface, not attempted here; same "caller-resolved aggregate" seam
  `bolt_group_shear_torsion` uses for `j_polar`).
- `weld_group_outofplane_bending` is the same method applied to
  OUT-OF-PLANE bending: a unit second moment of area `Iw` (m^3) and
  the caller-named distance `c` to the extreme fiber of the weld line
  give the unit bending line force. `Iw` is CALLER-SUPPLIED for the
  same reason `Jw` is above.
- `weld_group_utilization` combines a shear-plane unit line force and
  a perpendicular bending-plane unit line force by vector sum (the
  two act on mutually perpendicular faces of the weld throat, per
  Blodgett/Shigley's own treatment of the general case), converts to
  an actual stress via the 0.707*leg-size throat-area convention
  (AWS D1.1 / AISC 360-16 sec. J2.4's effective throat), and compares
  against a caller-supplied allowable stress -- returning
  `(ratio, "Valid"|"Violated")`, the SAME verdict shape as
  `feldspar.library.struct.civil_utilization_h1`. The allowable
  stress itself (e.g. AWS D1.1 table 2.3's `0.30*F_EXX` for a fillet
  weld in shear) is NOT derived here -- CALLER-SUPPLIED, so no
  electrode-classification table needs transcribing to land this
  slice (a named cut, not an omission).

None of these three directions derives weld-line unit section
properties from a named pattern (rectangular, circular, C-shaped
groups, etc.) -- that catalog is a future dispatch's own citation
surface, same shape as the `j_polar`/`sum_y_sq` cuts in
`bolted_joints.py`. Static, fillet-weld, elastic (no fatigue, no
dynamic loading) is a CALLER-ASSERTED precondition (`Domain.tags`),
never derived or checked from these ports alone."""

import math

from typani import Err, Ok

from feldspar.core import Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

# ---------------------------------------------------------------------------
# 10.1 -- elastic line, in-plane shear + torsion about centroid
# ---------------------------------------------------------------------------

_INPLANE_CITATION = Citation(
    kind="handbook",
    ref=(
        "Shigley's Mechanical Engineering Design, 11th ed., ch. 9 "
        "sec. 9-5/9-6 (fillet welds treated as a line, unit second-"
        "moment-of-area method); Blodgett, Design of Weldments, sec. "
        "4.3-4.4 (the same elastic-line torsion/shear treatment): "
        "f_direct=(Vx/Aw, Vy/Aw), f_torsion=(-T*yi/Jw, T*xi/Jw), "
        "vector sum -> unit line force (N/m) (docs/benchmarks-memo.md "
        "sec. 10.1)"
    ),
    note=(
        "Evaluated at ONE caller-named point (x_i, y_i) on the weld "
        "line -- the caller identifies the critical point; Aw "
        "(total weld length) and Jw (unit polar second moment) are "
        "CALLER-SUPPLIED, not derived from a weld-pattern catalog "
        "(no such table is transcribed in this module)."
    ),
)


# frob:doc docs/modules/mech.md#mech_weld_groups
@solver(
    namespace="mech.weld",
    inputs=(
        "mech.weld.group.vx",
        "mech.weld.group.vy",
        "mech.weld.group.torque",
        "mech.weld.group.aw",
        "mech.weld.group.jw",
        "mech.weld.group.xi",
        "mech.weld.group.yi",
    ),
    outputs=("mech.weld.group.inplane_line_force",),
    domain=Domain(
        box={
            "mech.weld.group.vx": Interval(-1.0e7, 1.0e7),
            "mech.weld.group.vy": Interval(-1.0e7, 1.0e7),
            # In-plane torque about the weld-group centroid, N*m.
            "mech.weld.group.torque": Interval(-1.0e6, 1.0e6),
            # Total weld line length (unit area), m.
            "mech.weld.group.aw": Interval(1.0e-3, 10.0),
            # Unit polar second moment of the weld line, m^3.
            "mech.weld.group.jw": Interval(1.0e-9, 10.0),
            "mech.weld.group.xi": Interval(-10.0, 10.0),
            "mech.weld.group.yi": Interval(-10.0, 10.0),
        },
        tags={"elastic", "fillet", "static", "planar"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_INPLANE_CITATION,),
    version="1",
)
def weld_group_inplane_shear_torsion(x):
    """Shigley ch. 9 sec. 9-5/9-6 elastic-line method: the resultant
    UNIT line force (N/m, before dividing by throat area) on the
    caller-named weld-line point `(x_i, y_i)` under centroidal shear
    `(Vx, Vy)` and centroidal torque `T`."""
    vx = x["mech.weld.group.vx"]
    vy = x["mech.weld.group.vy"]
    torque = x["mech.weld.group.torque"]
    aw = x["mech.weld.group.aw"]
    jw = x["mech.weld.group.jw"]
    xi = x["mech.weld.group.xi"]
    yi = x["mech.weld.group.yi"]
    if aw <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"weld group: non-positive weld length aw={aw!r}"
            )
        )
    if jw <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"weld group: non-positive unit polar moment jw={jw!r}"
            )
        )
    fx = vx / aw - torque * yi / jw
    fy = vy / aw + torque * xi / jw
    resultant = math.hypot(fx, fy)
    return Ok({"mech.weld.group.inplane_line_force": resultant})


# ---------------------------------------------------------------------------
# 10.2 -- elastic line, out-of-plane bending
# ---------------------------------------------------------------------------

_BENDING_CITATION = Citation(
    kind="handbook",
    ref=(
        "Shigley's Mechanical Engineering Design, 11th ed., ch. 9 "
        "sec. 9-5 (fillet weld groups loaded in bending, unit second "
        "moment of area Iw treated exactly like a bending-stress "
        "section modulus): f_bending = M*c/Iw, unit line force (N/m) "
        "(docs/benchmarks-memo.md sec. 10.2)"
    ),
    note=(
        "Evaluated at ONE caller-named extreme-fiber distance `c`; "
        "Iw (unit second moment of the weld line about the bending "
        "neutral axis) is CALLER-SUPPLIED, not derived from a "
        "weld-pattern catalog."
    ),
)


# frob:doc docs/modules/mech.md#mech_weld_groups
@solver(
    namespace="mech.weld",
    inputs=(
        "mech.weld.group.moment",
        "mech.weld.group.iw",
        "mech.weld.group.c",
    ),
    outputs=("mech.weld.group.bending_line_force",),
    domain=Domain(
        box={
            # Out-of-plane bending moment on the weld group, N*m.
            "mech.weld.group.moment": Interval(-1.0e6, 1.0e6),
            # Unit second moment of area of the weld line, m^3.
            "mech.weld.group.iw": Interval(1.0e-9, 10.0),
            # Extreme-fiber distance from the bending neutral axis, m.
            "mech.weld.group.c": Interval(-10.0, 10.0),
        },
        tags={"elastic", "fillet", "static"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_BENDING_CITATION,),
    version="1",
)
def weld_group_outofplane_bending(x):
    """Shigley ch. 9 sec. 9-5: out-of-plane bending UNIT line force
    `f = M*c/Iw` at the caller-named extreme-fiber distance `c`."""
    moment = x["mech.weld.group.moment"]
    iw = x["mech.weld.group.iw"]
    c = x["mech.weld.group.c"]
    if iw <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"weld group: non-positive unit second moment iw={iw!r}"
            )
        )
    f_bending = moment * c / iw
    return Ok({"mech.weld.group.bending_line_force": f_bending})


# ---------------------------------------------------------------------------
# 10.3 -- vector-summed peak line force vs allowable
# ---------------------------------------------------------------------------

_UTILIZATION_CITATION = Citation(
    kind="standard",
    ref=(
        "AWS D1.1/D1.1M Structural Welding Code -- Steel, and AISC "
        "360-16 sec. J2.4 (effective throat of a fillet weld = "
        "0.707*leg size h): actual stress = f_peak / (0.707*h), where "
        "f_peak is the vector sum of the in-plane (shear-plane) and "
        "out-of-plane (bending-plane) UNIT line forces, since they act "
        "on mutually perpendicular components of the weld throat "
        "(docs/benchmarks-memo.md sec. 10.3)"
    ),
    note=(
        "The allowable stress itself (e.g. AWS D1.1 table 2.3's "
        "0.30*F_EXX for fillet-weld shear) is CALLER-SUPPLIED -- no "
        "electrode-classification table is transcribed here (a named "
        "cut, not an omission)."
    ),
)


# frob:doc docs/modules/mech.md#mech_weld_groups
@solver(
    namespace="mech.weld",
    inputs=(
        "mech.weld.group.inplane_line_force",
        "mech.weld.group.bending_line_force",
        "mech.weld.group.leg_size",
        "mech.weld.group.allowable_stress",
    ),
    outputs=(
        "mech.weld.group.peak_stress",
        "mech.weld.group.utilization_ratio",
    ),
    domain=Domain(
        box={
            # Unit line forces, N/m (may be zero if only one loading
            # mode applies -- the caller feeds 0.0 for the unused
            # channel, not an invalid value).
            "mech.weld.group.inplane_line_force": Interval(0.0, 1.0e8),
            "mech.weld.group.bending_line_force": Interval(0.0, 1.0e8),
            # Fillet weld leg size, m (typical 3-25 mm range).
            "mech.weld.group.leg_size": Interval(1.0e-3, 0.05),
            # Caller-supplied allowable weld shear stress, Pa (e.g.
            # 0.30*F_EXX for E70 electrode ~ 0.30*482e6 ~ 145e6 Pa).
            "mech.weld.group.allowable_stress": Interval(1.0e6, 5.0e8),
        },
        tags={"elastic", "fillet", "static"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_UTILIZATION_CITATION,),
    version="1",
)
def weld_group_utilization(x):
    """AWS D1.1 / AISC 360-16 sec. J2.4 effective-throat convention:
    vector-sums the in-plane and out-of-plane UNIT line forces,
    divides by the 0.707*leg-size effective throat area, and compares
    to the caller-supplied allowable stress. Returns
    `(peak_stress, utilization_ratio)`; `ratio <= 1.0` means the weld
    passes (the caller reads the ratio, this direction never itself
    raises on a failing weld -- an over-utilized weld is a valid,
    just unfavorable, physical outcome, not a domain violation, same
    convention `civil_utilization_h1` uses)."""
    f_inplane = x["mech.weld.group.inplane_line_force"]
    f_bending = x["mech.weld.group.bending_line_force"]
    leg_size = x["mech.weld.group.leg_size"]
    allowable = x["mech.weld.group.allowable_stress"]
    if leg_size <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"weld group: non-positive leg size={leg_size!r}"
            )
        )
    if allowable <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"weld group: non-positive allowable stress={allowable!r}"
            )
        )
    f_peak = math.hypot(f_inplane, f_bending)
    throat = 0.707 * leg_size
    stress = f_peak / throat
    ratio = stress / allowable
    return Ok(
        {
            "mech.weld.group.peak_stress": stress,
            "mech.weld.group.utilization_ratio": ratio,
        }
    )


#: This family's port table (WO111b composition fix; see
#: `member_capacity.py`'s `_PORT_DECLS` note).
_PORT_DECLS = (
    PortDecl("mech.weld.group.vx", "N"),
    PortDecl("mech.weld.group.vy", "N"),
    PortDecl("mech.weld.group.torque", "N*m"),
    PortDecl("mech.weld.group.aw", "m"),
    PortDecl("mech.weld.group.jw", "m^3"),
    PortDecl("mech.weld.group.xi", "m"),
    PortDecl("mech.weld.group.yi", "m"),
    PortDecl("mech.weld.group.inplane_line_force", "N/m"),
    PortDecl("mech.weld.group.moment", "N*m"),
    PortDecl("mech.weld.group.iw", "m^3"),
    PortDecl("mech.weld.group.c", "m"),
    PortDecl("mech.weld.group.bending_line_force", "N/m"),
    PortDecl("mech.weld.group.leg_size", "m"),
    PortDecl("mech.weld.group.allowable_stress", "Pa"),
    PortDecl("mech.weld.group.peak_stress", "Pa"),
    PortDecl("mech.weld.group.utilization_ratio", "1"),
)


# frob:doc docs/modules/mech.md#mech_weld_groups
def register(registry: SolverRegistry) -> None:
    """Registers all three weld-group directions (WO-24 deliverable
    2: in-plane shear/torsion + out-of-plane bending + the combined
    vector-summed peak-line-force-vs-allowable utilization check).
    Declares this family's port table first (WO111b)."""
    _ = registry.declare_ports(*_PORT_DECLS).danger_ok
    result_a = registry.register(*weld_group_inplane_shear_torsion.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_a.danger_ok
    result_b = registry.register(*weld_group_outofplane_bending.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_b.danger_ok
    result_c = registry.register(*weld_group_utilization.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_c.danger_ok
    _log.info("weld_groups: registered %d solver directions", 3)
