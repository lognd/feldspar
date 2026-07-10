from __future__ import annotations

"""Leadscrew (square-thread power screw) drive sizing -- WO-24
deliverable 7's LEADSCREW half only (docs/benchmarks-memo.md sec. 15):
torque to raise/lower a load, mechanical efficiency, self-locking
margin, and collar friction torque, all square-thread power-screw
mechanics (Shigley 11e ch. 8 sec. 8-2/8-3, "The Mechanics of Power
Screws").

SCOPE (honest, narrow -- the WO-24 standing law):

- Every direction here is EXACT ALGEBRA (a closed-form statics
  result from unrolling one thread as an inclined plane, Shigley 11e
  ch. 8 sec. 8-2), the SAME calibration tier as
  `member_capacity.euler_critical_buckling_load` and
  `bolted_joints.bolt_single_load_factor_vdi2230` -- no fitted table,
  no empirical correlation, so calibration is HAND-COMPUTED exact
  arithmetic against a self-consistent worked case (docs/
  benchmarks-memo.md sec. 15), not a published numeric table (none is
  needed for an exact closed form, same precedent those two modules
  already set).
- SQUARE THREAD only -- the ACME-thread wedging correction (dividing
  every friction term by cos(alpha), Shigley 11e ch. 8) is NOT built
  here (a named cut; ACME threads are far more common in practice
  precisely because they're easier to machine, per the source's own
  note, so this is a real gap, not a trivial one).
- `leadscrew_collar_torque` (`Tc = F*fc*dc/2`) is the thrust-collar
  friction addition -- CALLER composes `leadscrew_torque_raise` +
  `leadscrew_collar_torque` for the total drive torque (this module
  does not do that sum itself, matching the "caller composes" seam
  every other WO-24 module uses).
- `leadscrew_self_locking_margin` returns `f - tan(lambda)`
  (`tan(lambda) = l/(pi*dm)`) rather than a boolean -- POSITIVE means
  self-locking (the screw will not back-drive under load without
  applied torque), matching the numeric-margin convention
  `weld_group_utilization`'s ratio and `bolted_joints`' residual
  clamp load already use (a caller reads the sign/value, this
  direction never itself raises on a non-self-locking result -- a
  non-self-locking screw is a valid, just different, design point).
- BELT drive sizing (GT2-class tooth shear/tension ratings, this
  deliverable's OTHER named half) is a SEPARATE, UNSTARTED citation
  surface -- see WO-24-library-depth.md's dispatch ledger for the
  explicit cut; no manufacturer belt-tooth rating table was
  transcribed or verified within this dispatch's research budget.
- Critical (whirling) speed of a leadscrew is NOT built here either
  -- it needs an end-support-factor table (e.g. Nook Industries/PBC
  Linear engineering data) that is its own citation surface, distinct
  from Shigley's torque/efficiency treatment; named cut, not
  attempted this dispatch."""

import math

from typani import Err, Ok

from feldspar.core import Domain, Interval
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

_SHIGLEY = "Shigley's Mechanical Engineering Design, 11th ed."

_MECHANICS_CITATION = Citation(
    kind="handbook",
    ref=(
        f'{_SHIGLEY}, ch. 8 sec. 8-2 ("The Mechanics of Power '
        'Screws"): square-thread torque to raise a load '
        "TR = (F*dm/2)*((l+pi*f*dm)/(pi*dm-f*l)), torque to lower a "
        "load TL = (F*dm/2)*((pi*f*dm-l)/(pi*dm+f*l)), mechanical "
        "efficiency e = F*l/(2*pi*TR), self-locking condition "
        "f > tan(lambda) = l/(pi*dm), and thrust-collar friction "
        "torque Tc = F*fc*dc/2 (docs/benchmarks-memo.md sec. 15)"
    ),
    note=(
        "Square thread only -- the ACME wedging correction (sec. 8-2, "
        "friction terms divided by cos(alpha)) is a named cut, not "
        "built here (WO-24 deliverable 7 scope). Exact closed-form "
        "algebra, calibrated by hand-computed arithmetic (no fitted "
        "table exists to calibrate against for an exact result), same "
        "tier as `member_capacity.euler_critical_buckling_load`."
    ),
)

# Domain box shared by every direction below: F/dm/l/f share the same
# physically-plausible ranges across a leadscrew's raise/lower/
# efficiency/self-locking forms.
_F_RANGE = Interval(1.0, 1.0e6)
_DM_RANGE = Interval(1.0e-3, 0.5)
_L_RANGE = Interval(1.0e-4, 0.1)
_F_COEFF_RANGE = Interval(0.01, 0.9)


def _reject_nonpositive(**kwargs: float) -> SolveError | None:
    """Shared honesty gate (NO DUPLICATION): every leadscrew direction
    below rejects non-positive F/dm/l or an out-of-(0,1) friction
    coefficient the same way."""
    for name, value in kwargs.items():
        if value <= 0.0:
            return SolveError.OutOfDomain(
                violation=f"leadscrew: non-positive {name}={value!r}"
            )
    return None


@solver(
    namespace="mech.drive",
    inputs=(
        "mech.drive.leadscrew.force",
        "mech.drive.leadscrew.dm",
        "mech.drive.leadscrew.lead",
        "mech.drive.leadscrew.friction",
    ),
    outputs=("mech.drive.leadscrew.torque_raise",),
    domain=Domain(
        box={
            "mech.drive.leadscrew.force": _F_RANGE,
            "mech.drive.leadscrew.dm": _DM_RANGE,
            "mech.drive.leadscrew.lead": _L_RANGE,
            "mech.drive.leadscrew.friction": _F_COEFF_RANGE,
        },
        tags={"square_thread", "no_collar"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_MECHANICS_CITATION,),
    version="1",
)
def leadscrew_torque_raise(x):
    """Shigley 11e ch. 8 sec. 8-2: `TR = (F*dm/2)*((l+pi*f*dm)/
    (pi*dm-f*l))`. `pi*dm <= f*l` (a degenerate/binding geometry, not
    a physically realizable screw) is `OutOfDomain`, not a division
    fabricated through zero."""
    f = x["mech.drive.leadscrew.force"]
    dm = x["mech.drive.leadscrew.dm"]
    lead = x["mech.drive.leadscrew.lead"]
    mu = x["mech.drive.leadscrew.friction"]
    err = _reject_nonpositive(force=f, dm=dm, lead=lead, friction=mu)
    if err is not None:
        return Err(err)
    denom = math.pi * dm - mu * lead
    if denom <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"leadscrew raise: pi*dm - f*l = {denom!r} <= 0 -- "
                    "not a physically realizable screw geometry"
                )
            )
        )
    tr = (f * dm / 2.0) * ((lead + math.pi * mu * dm) / denom)
    return Ok({"mech.drive.leadscrew.torque_raise": tr})


@solver(
    namespace="mech.drive",
    inputs=(
        "mech.drive.leadscrew.force",
        "mech.drive.leadscrew.dm",
        "mech.drive.leadscrew.lead",
        "mech.drive.leadscrew.friction",
    ),
    outputs=("mech.drive.leadscrew.torque_lower",),
    domain=Domain(
        box={
            "mech.drive.leadscrew.force": _F_RANGE,
            "mech.drive.leadscrew.dm": _DM_RANGE,
            "mech.drive.leadscrew.lead": _L_RANGE,
            "mech.drive.leadscrew.friction": _F_COEFF_RANGE,
        },
        tags={"square_thread", "no_collar"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_MECHANICS_CITATION,),
    version="1",
)
def leadscrew_torque_lower(x):
    """Shigley 11e ch. 8 sec. 8-2: `TL = (F*dm/2)*((pi*f*dm-l)/
    (pi*dm+f*l))`. May be NEGATIVE (the screw back-drives without
    applied torque, i.e. NOT self-locking) -- a real physical outcome,
    not an error (pair with `leadscrew_self_locking_margin` to check
    self-locking directly)."""
    f = x["mech.drive.leadscrew.force"]
    dm = x["mech.drive.leadscrew.dm"]
    lead = x["mech.drive.leadscrew.lead"]
    mu = x["mech.drive.leadscrew.friction"]
    err = _reject_nonpositive(force=f, dm=dm, lead=lead, friction=mu)
    if err is not None:
        return Err(err)
    tl = (f * dm / 2.0) * ((math.pi * mu * dm - lead) / (math.pi * dm + mu * lead))
    return Ok({"mech.drive.leadscrew.torque_lower": tl})


@solver(
    namespace="mech.drive",
    inputs=(
        "mech.drive.leadscrew.force",
        "mech.drive.leadscrew.lead",
        "mech.drive.leadscrew.torque_raise",
    ),
    outputs=("mech.drive.leadscrew.efficiency",),
    domain=Domain(
        box={
            "mech.drive.leadscrew.force": _F_RANGE,
            "mech.drive.leadscrew.lead": _L_RANGE,
            # Torque, N*m -- wide enough to cover any realistic TR.
            "mech.drive.leadscrew.torque_raise": Interval(1.0e-6, 1.0e5),
        },
        tags={"square_thread"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_MECHANICS_CITATION,),
    version="1",
)
def leadscrew_efficiency(x):
    """Shigley 11e ch. 8 sec. 8-2: `e = F*l/(2*pi*TR)`, the ratio of
    frictionless torque to the actual (already-computed) raise
    torque. Takes `TR` as an input rather than recomputing it -- the
    caller chains `leadscrew_torque_raise`'s own output, same "compose
    don't duplicate" seam `fatigue_marin_endurance_limit` uses for its
    upstream factors."""
    f = x["mech.drive.leadscrew.force"]
    lead = x["mech.drive.leadscrew.lead"]
    tr = x["mech.drive.leadscrew.torque_raise"]
    err = _reject_nonpositive(force=f, lead=lead, torque_raise=tr)
    if err is not None:
        return Err(err)
    e = (f * lead) / (2.0 * math.pi * tr)
    return Ok({"mech.drive.leadscrew.efficiency": e})


@solver(
    namespace="mech.drive",
    inputs=(
        "mech.drive.leadscrew.dm",
        "mech.drive.leadscrew.lead",
        "mech.drive.leadscrew.friction",
    ),
    outputs=("mech.drive.leadscrew.self_locking_margin",),
    domain=Domain(
        box={
            "mech.drive.leadscrew.dm": _DM_RANGE,
            "mech.drive.leadscrew.lead": _L_RANGE,
            "mech.drive.leadscrew.friction": _F_COEFF_RANGE,
        },
        tags={"square_thread"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_MECHANICS_CITATION,),
    version="1",
)
def leadscrew_self_locking_margin(x):
    """Shigley 11e ch. 8 sec. 8-2: self-locking condition
    `f > tan(lambda)`, `tan(lambda) = l/(pi*dm)`. Returns the signed
    margin `f - tan(lambda)` -- POSITIVE means self-locking (does not
    itself raise on a non-self-locking result, same numeric-margin
    convention `weld_group_utilization`'s ratio uses)."""
    dm = x["mech.drive.leadscrew.dm"]
    lead = x["mech.drive.leadscrew.lead"]
    mu = x["mech.drive.leadscrew.friction"]
    err = _reject_nonpositive(dm=dm, lead=lead, friction=mu)
    if err is not None:
        return Err(err)
    tan_lambda = lead / (math.pi * dm)
    return Ok({"mech.drive.leadscrew.self_locking_margin": mu - tan_lambda})


@solver(
    namespace="mech.drive",
    inputs=(
        "mech.drive.leadscrew.force",
        "mech.drive.leadscrew.collar_friction",
        "mech.drive.leadscrew.collar_dc",
    ),
    outputs=("mech.drive.leadscrew.collar_torque",),
    domain=Domain(
        box={
            "mech.drive.leadscrew.force": _F_RANGE,
            "mech.drive.leadscrew.collar_friction": _F_COEFF_RANGE,
            # Collar mean diameter, m.
            "mech.drive.leadscrew.collar_dc": Interval(1.0e-3, 0.5),
        },
        tags={"thrust_collar"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_MECHANICS_CITATION,),
    version="1",
)
def leadscrew_collar_torque(x):
    """Shigley 11e ch. 8 sec. 8-2: `Tc = F*fc*dc/2`, the thrust-
    collar friction torque -- CALLER adds this to
    `leadscrew_torque_raise`'s output for the total drive torque (not
    summed here, same "caller composes" seam every WO-24 module
    uses)."""
    f = x["mech.drive.leadscrew.force"]
    fc = x["mech.drive.leadscrew.collar_friction"]
    dc = x["mech.drive.leadscrew.collar_dc"]
    err = _reject_nonpositive(force=f, collar_friction=fc, collar_dc=dc)
    if err is not None:
        return Err(err)
    tc = f * fc * dc / 2.0
    return Ok({"mech.drive.leadscrew.collar_torque": tc})


def register(registry: SolverRegistry) -> None:
    """Registers all five leadscrew directions (WO-24 deliverable 7,
    leadscrew half only: torque to raise/lower, efficiency, self-
    locking margin, collar friction torque)."""
    result_a = registry.register(*leadscrew_torque_raise.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_a.danger_ok
    result_b = registry.register(*leadscrew_torque_lower.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_b.danger_ok
    result_c = registry.register(*leadscrew_efficiency.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_c.danger_ok
    result_d = registry.register(*leadscrew_self_locking_margin.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_d.danger_ok
    result_e = registry.register(*leadscrew_collar_torque.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_e.danger_ok
    _log.info("leadscrew: registered %d solver directions", 5)
