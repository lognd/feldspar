from __future__ import annotations

"""Bolted-joint solver directions (WO-24 deliverable 1, docs/
benchmarks-memo.md sec. 8): a VDI 2230-class single-bolt elastic
tier (preload, load factor, working load, separation margin) and an
elastic-method bolt-GROUP distribution (in-plane shear + torsion
about the group centroid; tension from an out-of-plane moment about
the group's neutral axis, linear).

SCOPE (honest, narrow -- the WO-24 standing law, same shape as
`member_capacity.py`):

- `bolt_single_load_factor_vdi2230` is VDI 2230 Part 1:2015's
  SIMPLIFIED TWO-BODY elastic model (memo sec. 8.1): one bolt
  stiffness `c_B`, one lumped clamped-parts stiffness `c_P`,
  CONCENTRIC axial loading only. The full VDI 2230 procedure
  (embedding/settling loss, eccentric loading, multi-body stiffness
  stacks, tightening-technique scatter alpha_A, gasket creep) is NOT
  built -- this is the elastic, no-gasket-creep, concentric-load,
  friction-grip-out-of-scope tier the WO text names. `c_B`/`c_P` are
  CALLER-SUPPLIED (this module does not derive bolt/plate stiffness
  from geometry -- that is its own citation surface, not attempted
  here).
- `bolt_group_shear_torsion` is the Shigley 11e ch. 8 sec. 8-11
  elastic (superposition) method for a bolt group's shear resultant
  under a centroidal shear plus an in-plane torque about the
  centroid (memo sec. 8.2). It evaluates a SINGLE caller-named bolt
  position `(x_i, y_i)` (the caller picks the critical/farthest
  bolt; this module does not search a bolt list -- no variable-
  length port exists on this solver's port surface, the same
  "caller-resolved aggregate" seam `member_capacity.py`/
  `civil_utilization_h1` use).
- `bolt_group_tension_from_moment` is the AISC Manual Part 7 / Shigley
  ch. 8 sec. 8-12 elastic (linear, bending-stress-analogy) method for
  bolt tension under a moment about the group's neutral axis (memo
  sec. 8.3), again evaluated at a single caller-named bolt distance
  `y_i` from that axis. Prying action, gasket/washer flexibility, and
  bolt-to-bolt stiffness variation are NOT modeled -- pure linear-
  elastic distribution, the WO's own scope.

None of these three directions models friction-grip (slip-critical)
connections, gasket creep, or fatigue -- CALLER-ASSERTED preconditions
(`Domain.tags`), never derived or checked from these ports alone."""

import math

from typani import Err, Ok

from feldspar.core import Domain, Interval
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

# ---------------------------------------------------------------------------
# 8.1 -- VDI 2230 single-bolt elastic tier
# ---------------------------------------------------------------------------

_VDI_CITATION = Citation(
    kind="standard",
    ref=(
        "VDI 2230 Blatt 1:2015, Systematic calculation of highly "
        "stressed bolted joints, simplified two-body elastic model: "
        "load factor phi = c_B/(c_B+c_P); bolt working load F_S = "
        "F_V + phi*F_A; residual clamp load F_KR = F_V - (1-phi)*F_A "
        "(docs/benchmarks-memo.md sec. 8.1)"
    ),
    note=(
        "Concentric axial loading, elastic, NO gasket creep, NO "
        "embedding/settling loss, NO friction-grip (slip-critical) "
        "analysis -- the simplified two-body model only. c_B/c_P are "
        "CALLER-SUPPLIED (this direction does not derive bolt/plate "
        "stiffness from geometry)."
    ),
)


@solver(
    namespace="mech.joint",
    inputs=(
        "mech.joint.bolt.cb",
        "mech.joint.bolt.cp",
        "mech.joint.bolt.fv",
        "mech.joint.bolt.fa",
    ),
    outputs=(
        "mech.joint.bolt.load_factor",
        "mech.joint.bolt.working_load",
        "mech.joint.bolt.residual_clamp_load",
    ),
    domain=Domain(
        box={
            # Bolt axial stiffness, N/m (small M3 bolt through a large
            # grade-8 stud, order-of-magnitude band).
            "mech.joint.bolt.cb": Interval(1.0e5, 1.0e10),
            # Clamped-parts (lumped) axial stiffness, N/m.
            "mech.joint.bolt.cp": Interval(1.0e5, 1.0e10),
            # Preload, N (must be non-negative -- a bolt is tightened,
            # never pre-loaded in compression by this model).
            "mech.joint.bolt.fv": Interval(0.0, 1.0e7),
            # External concentric axial load, N (tension positive;
            # compression -- negative -- only increases clamp force,
            # so the lower bound is generous but finite).
            "mech.joint.bolt.fa": Interval(-1.0e7, 1.0e7),
        },
        tags={
            "elastic",
            "no_gasket_creep",
            "concentric_load",
            "friction_grip_out_of_scope",
        },
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_VDI_CITATION,),
    version="1",
)
def bolt_single_load_factor_vdi2230(x):
    """VDI 2230 two-body elastic tier: `phi`, bolt working load `F_S
    = F_V + phi*F_A`, and residual clamp load `F_KR = F_V -
    (1-phi)*F_A` (`F_KR <= 0` means the joint has separated -- the
    caller reads this port to check the separation margin, this
    direction never itself raises on separation since a separated
    joint is a valid, just unfavorable, physical outcome, not a
    domain violation)."""
    cb = x["mech.joint.bolt.cb"]
    cp = x["mech.joint.bolt.cp"]
    fv = x["mech.joint.bolt.fv"]
    fa = x["mech.joint.bolt.fa"]
    if cb <= 0.0 or cp <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"VDI 2230: non-positive stiffness cb={cb!r} or "
                    f"cp={cp!r} -- cannot form a load factor"
                )
            )
        )
    if fv < 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"VDI 2230: negative preload fv={fv!r} -- a bolt is "
                    "tightened, not pre-compressed"
                )
            )
        )
    phi = cb / (cb + cp)
    f_s = fv + phi * fa
    f_kr = fv - (1.0 - phi) * fa
    return Ok(
        {
            "mech.joint.bolt.load_factor": phi,
            "mech.joint.bolt.working_load": f_s,
            "mech.joint.bolt.residual_clamp_load": f_kr,
        }
    )


# ---------------------------------------------------------------------------
# 8.2 -- elastic bolt-group, in-plane shear + torsion about centroid
# ---------------------------------------------------------------------------

_SHEAR_GROUP_CITATION = Citation(
    kind="handbook",
    ref=(
        "Shigley's Mechanical Engineering Design, 11th ed., ch. 8 "
        "sec. 8-11 (Shear Joints Under Eccentric Loading), the "
        "elastic (superposition) method: F_direct=(Vx/n,Vy/n), "
        "F_torsion=(-T*yi/J, T*xi/J), J=sum(ri^2) "
        "(docs/benchmarks-memo.md sec. 8.2)"
    ),
    note=(
        "Evaluated at ONE caller-named bolt position (x_i, y_i) -- "
        "the caller identifies the critical bolt; this direction does "
        "not search a variable-length bolt list (no such port shape "
        "exists on this solver's surface)."
    ),
)


@solver(
    namespace="mech.joint",
    inputs=(
        "mech.joint.group.n",
        "mech.joint.group.vx",
        "mech.joint.group.vy",
        "mech.joint.group.torque",
        "mech.joint.group.j_polar",
        "mech.joint.group.xi",
        "mech.joint.group.yi",
    ),
    outputs=("mech.joint.group.shear_resultant",),
    domain=Domain(
        box={
            # Bolt count, dimensionless (integral, but ports are
            # float -- callers pass e.g. 4.0).
            "mech.joint.group.n": Interval(2.0, 200.0),
            "mech.joint.group.vx": Interval(-1.0e7, 1.0e7),
            "mech.joint.group.vy": Interval(-1.0e7, 1.0e7),
            # In-plane torque about the group centroid, N*m.
            "mech.joint.group.torque": Interval(-1.0e6, 1.0e6),
            # Polar "moment" of the bolt pattern, sum(r_i^2), m^2.
            "mech.joint.group.j_polar": Interval(1.0e-6, 10.0),
            "mech.joint.group.xi": Interval(-10.0, 10.0),
            "mech.joint.group.yi": Interval(-10.0, 10.0),
        },
        tags={"elastic", "planar", "rigid_plate_assumption"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_SHEAR_GROUP_CITATION,),
    version="1",
)
def bolt_group_shear_torsion(x):
    """Shigley ch. 8 sec. 8-11 elastic bolt-group shear method: the
    resultant shear magnitude on the caller-named bolt `(x_i, y_i)`
    under centroidal shear `(Vx, Vy)` and centroidal torque `T`."""
    n = x["mech.joint.group.n"]
    vx = x["mech.joint.group.vx"]
    vy = x["mech.joint.group.vy"]
    torque = x["mech.joint.group.torque"]
    j_polar = x["mech.joint.group.j_polar"]
    xi = x["mech.joint.group.xi"]
    yi = x["mech.joint.group.yi"]
    if n < 1.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"bolt group: non-positive bolt count n={n!r}"
            )
        )
    if j_polar <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"bolt group: non-positive polar moment j_polar={j_polar!r}"
            )
        )
    fx = vx / n - torque * yi / j_polar
    fy = vy / n + torque * xi / j_polar
    resultant = math.hypot(fx, fy)
    return Ok({"mech.joint.group.shear_resultant": resultant})


# ---------------------------------------------------------------------------
# 8.3 -- elastic bolt-group, tension from moment about the neutral axis
# ---------------------------------------------------------------------------

_TENSION_GROUP_CITATION = Citation(
    kind="handbook",
    ref=(
        "AISC Manual of Steel Construction, Part 7 (elastic/vector "
        "analysis method for eccentrically loaded fastener groups) "
        "and Shigley's Mechanical Engineering Design, 11th ed., ch. 8 "
        "sec. 8-12 (bolted joints loaded in bending): F_ti = "
        "M*yi/sum(yj^2), linear tension distribution analogous to "
        "bending stress (docs/benchmarks-memo.md sec. 8.3)"
    ),
    note=(
        "Evaluated at ONE caller-named bolt distance y_i from the "
        "neutral axis, with the caller-supplied group second moment "
        "sum(yj^2); no prying action, gasket/washer flexibility, or "
        "bolt-stiffness variation is modeled."
    ),
)


@solver(
    namespace="mech.joint",
    inputs=(
        "mech.joint.group.moment",
        "mech.joint.group.sum_y_sq",
        "mech.joint.group.y_critical",
    ),
    outputs=("mech.joint.group.tension_critical",),
    domain=Domain(
        box={
            # Moment about the group's neutral axis, N*m.
            "mech.joint.group.moment": Interval(-1.0e6, 1.0e6),
            # sum(y_j^2) over the bolt pattern, m^2.
            "mech.joint.group.sum_y_sq": Interval(1.0e-6, 10.0),
            "mech.joint.group.y_critical": Interval(-10.0, 10.0),
        },
        tags={"elastic", "linear_distribution", "no_prying_action"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_TENSION_GROUP_CITATION,),
    version="1",
)
def bolt_group_tension_from_moment(x):
    """AISC Manual Part 7 / Shigley ch. 8 sec. 8-12: bolt tension at
    the caller-named critical distance `y_critical` from the group's
    neutral axis under moment `M`, `F_t = M*y_critical/sum_y_sq`."""
    moment = x["mech.joint.group.moment"]
    sum_y_sq = x["mech.joint.group.sum_y_sq"]
    y_critical = x["mech.joint.group.y_critical"]
    if sum_y_sq <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"bolt group: non-positive sum_y_sq={sum_y_sq!r}"
            )
        )
    f_t = moment * y_critical / sum_y_sq
    return Ok({"mech.joint.group.tension_critical": f_t})


def register(registry: SolverRegistry) -> None:
    """Registers all three bolted-joint directions (WO-24
    deliverable 1: single-bolt VDI 2230 tier + elastic bolt-group
    shear/torsion + elastic bolt-group tension-from-moment)."""
    result_a = registry.register(*bolt_single_load_factor_vdi2230.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_a.danger_ok
    result_b = registry.register(*bolt_group_shear_torsion.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_b.danger_ok
    result_c = registry.register(*bolt_group_tension_from_moment.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_c.danger_ok
    _log.info("bolted_joints: registered %d solver directions", 3)
