from __future__ import annotations

"""Rotary drive-sizing tier -- WO-111 Class-C model growth (WO-24
deliverable 7, the motor torque/inertia reflected-load check the fleet's
motion axes declare: printer_k1 / cnc_router / arm_a6 / reaction_wheel
drive trains).

One closed-form direction, `drive_acceleration_torque`: the peak motor
torque required to accelerate a geared inertial load, reflected through a
speed-reduction ratio `N` (motor speed / load speed) and drive efficiency
`eta`:

    J_total = J_motor + J_load / N^2                 (reflected inertia)
    T_required = J_total * alpha + T_load / (N * eta)

where `alpha` is the MOTOR-side angular acceleration (rad/s^2) and
`T_load` the resisting torque at the LOAD shaft (N*m). The reflected-
inertia law `J_r = J_load/N^2` and the rigid-body acceleration torque
`tau = J*alpha` are standard rotational dynamics (Norton, Design of
Machinery, 6th ed., sec. 11.11 reflected inertia; Slocum, Precision
Machine Design, sec. 7.4 drive sizing).

SCOPE (honest, narrow): RIGID drivetrain, single reduction stage, no
backlash/compliance/windup, constant efficiency, constant `alpha` over
the move (trapezoidal-profile peak). Torque-ripple, thermal (RMS-torque)
sizing, and resonance are OUT (named cuts). `J_load`, `T_load`, `N`,
`eta`, `alpha`, `J_motor` are all caller-resolved scalars (the reflected-
inertia catalog of specific load geometries -- ballscrew, rack, belt --
stays a caller-side composition, same seam every WO-24 module uses).

Sense for pack exposure: `T_required` is a CEILING claim -- the required
motor torque must stay AT OR BELOW the motor's rated/available torque
(the obligation states the supply, this model reports the demand, the
same shape `WeldUtilizationModel`/`LeadscrewTorqueRaiseModel` use).

CALIBRATION HONESTY (WO111-F1): this is an exact evaluation of the two
cited textbook relations composed; the calibration test evaluates the
same closed form analytically (no independent worked numeric with a
verified example number transcribed) and cross-checks the two limiting
cases (`N=1` -> direct-drive `J_motor+J_load` sum; `J_load=0` ->
`J_motor*alpha + T_load/(N*eta)` alone).
"""

from typani import Err, Ok

from feldspar.core import Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

_ACCEL_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            "Norton, Design of Machinery, 6th ed., sec. 11.11 (reflected "
            "inertia J_r = J_load/N^2) + rigid-body acceleration torque "
            "tau = J*alpha; Slocum, Precision Machine Design, sec. 7.4 "
            "(drive sizing T = J_total*alpha + T_load/(N*eta)); "
            "docs/benchmarks-memo.md sec. 19"
        ),
        note=(
            "Rigid single-stage drivetrain, constant efficiency, "
            "trapezoidal-peak (constant alpha) sizing. RMS/thermal "
            "torque, backlash, and compliance are named cuts."
        ),
    ),
)


# frob:doc docs/modules/mech.md#mech_drive
@solver(
    namespace="mech.drive",
    inputs=(
        "mech.drive.accel.j_motor",
        "mech.drive.accel.j_load",
        "mech.drive.accel.gear_ratio",
        "mech.drive.accel.efficiency",
        "mech.drive.accel.alpha",
        "mech.drive.accel.t_load",
    ),
    outputs=("mech.drive.accel.torque_required",),
    domain=Domain(
        box={
            # Motor rotor inertia, kg*m^2.
            "mech.drive.accel.j_motor": Interval(1.0e-9, 1.0e2),
            # Load inertia at the load shaft, kg*m^2.
            "mech.drive.accel.j_load": Interval(0.0, 1.0e4),
            # Speed-reduction ratio N = motor_speed / load_speed (>=1
            # for a reducer; a direct drive is N=1).
            "mech.drive.accel.gear_ratio": Interval(1.0, 1.0e3),
            # Drive efficiency (0, 1].
            "mech.drive.accel.efficiency": Interval(0.1, 1.0),
            # Motor-side angular acceleration, rad/s^2.
            "mech.drive.accel.alpha": Interval(0.0, 1.0e6),
            # Resisting torque at the load shaft, N*m.
            "mech.drive.accel.t_load": Interval(0.0, 1.0e6),
        },
        tags={"rigid_drivetrain", "single_stage", "constant_efficiency"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_ACCEL_CITATIONS,
    version="1",
)
def drive_acceleration_torque(x):
    """Reflected-inertia acceleration torque:
    `T = (J_motor + J_load/N^2)*alpha + T_load/(N*eta)`, the peak motor
    torque to accelerate a geared inertial load."""
    j_motor = x["mech.drive.accel.j_motor"]
    j_load = x["mech.drive.accel.j_load"]
    n = x["mech.drive.accel.gear_ratio"]
    eta = x["mech.drive.accel.efficiency"]
    alpha = x["mech.drive.accel.alpha"]
    t_load = x["mech.drive.accel.t_load"]
    if j_motor <= 0.0 or j_load < 0.0 or n < 1.0 or not (0.0 < eta <= 1.0):
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"drive accel torque: bad j_motor={j_motor!r}, "
                    f"j_load={j_load!r}, gear_ratio={n!r}, or efficiency={eta!r}"
                )
            )
        )
    j_total = j_motor + j_load / n**2
    t_required = j_total * alpha + t_load / (n * eta)
    return Ok({"mech.drive.accel.torque_required": t_required})


#: This family's port table (WO111b composition fix; see
#: `member_capacity.py`'s `_PORT_DECLS` note).
_PORT_DECLS = (
    PortDecl("mech.drive.accel.j_motor", "kg*m^2"),
    PortDecl("mech.drive.accel.j_load", "kg*m^2"),
    PortDecl("mech.drive.accel.gear_ratio", "1"),
    PortDecl("mech.drive.accel.efficiency", "1"),
    PortDecl("mech.drive.accel.alpha", "rad/s^2"),
    PortDecl("mech.drive.accel.t_load", "N*m"),
    PortDecl("mech.drive.accel.torque_required", "N*m"),
)


# frob:doc docs/modules/mech.md#mech_drive
def register(registry: SolverRegistry) -> None:
    """Registers the reflected-inertia acceleration-torque direction
    (WO-111 drive sizing). Declares this family's port table first
    (WO111b)."""
    _ = registry.declare_ports(*_PORT_DECLS).danger_ok
    result = registry.register(*drive_acceleration_torque.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result.danger_ok
    _log.info("drive: registered %d solver direction(s)", 1)
