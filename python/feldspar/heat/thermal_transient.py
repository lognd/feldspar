from __future__ import annotations

"""Lumped-capacitance thermal TRANSIENT tier (WO-24 deliverable 6,
docs/benchmarks-memo.md sec. 12): step response, time-to-threshold,
and a periodic duty-cycle peak-temperature form, extending the WO-20
`heat.py` steady resistance-network tier with the single-node
governing ODE those steady directions never solve in time.

Governing model (Incropera & DeWitt, Fundamentals of Heat and Mass
Transfer, 7th ed., ch. 5 sec. 5.1-5.2, "lumped capacitance method"):
a single thermal node of capacitance `C_th` (J/K) losing/gaining heat
through a single resistance `R_th` (K/W) to a fixed ambient obeys

    C_th * dT/dt = P - (T - T_amb)/R_th

whose solution for constant `P` and initial condition `T(0) = T_amb`
is the exponential step response this module's `step_temperature`
direction evaluates directly (the RC-circuit analog of
`docs/benchmarks-memo.md` sec. 4.1's RC step response -- same ODE
shape, thermal instead of electrical variables, R_th*C_th playing
tau exactly as R*C does there).

COMPOSITION (not duplication) with `heat.py`: `R_th` here is the
SAME kind of quantity `heat.py`'s `heat.wall.resistance` /
`heat.network.r_series` directions already produce (a caller wires
that output into `heat.transient.r_th` through the plan graph -- this
module does not recompute conduction/convection resistances, it only
adds the time dimension on top of an already-resolved `R_th`). `C_th`
(thermal capacitance, `rho*V*c`) has NO producer anywhere in this
repo yet (a named cut below) -- it is CALLER-SUPPLIED, same seam as
`member_capacity.py`'s caller-supplied `Zx`/`Ag`/`r`.

VALIDITY -- the Biot-number honesty gate (Incropera ch. 5 sec. 5.1
eq. 5.10, the lumped-capacitance criterion): the method is valid only
when internal conduction resistance is negligible next to the
surface convection resistance,

    Bi = h*Lc/k < 0.1   (Lc = characteristic length, V/As)

This module does NOT compute `h`, `Lc`, or `k` itself (that would be
a second, separate citation surface -- convection-coefficient
correlations already live partially in `heat.py`'s Dittus-Boelter
direction for internal pipe flow, not the general external/natural
case a package-to-ambient thermal problem usually needs). Instead
every direction below takes a CALLER-ASSERTED `biot_number` port and
REJECTS (`OutOfDomain`) at or above 0.1 -- honest refusal of a
caller's claim it cannot itself verify from first principles, same
shape as `member_capacity.py`'s caller-asserted compact/braced tags,
but here enforced IN-FUNCTION (not just a domain `tags` label) because
a numeric Bi value is available to check, unlike a boolean
precondition. `biot_number_from_convection` is provided as a small
convenience direction (`Bi = h*Lc/k`, no criterion applied itself --
callers who DO have h/Lc/k can compute Bi through it and feed the
result into the transient directions' `biot_number` port; callers who
only have an already-known/measured Bi skip straight to asserting it).

NAMED CUTS (the WO's own standing law -- multi-node RC networks are
explicitly OUT):

1. Multi-node (distributed / Cauer or Foster RC-ladder) thermal
   networks are NOT built here. Every direction in this module is
   SINGLE-NODE (one `R_th`, one `C_th`, one ambient) -- a die-to-case-
   to-heatsink-to-ambient stack with materially different time
   constants at each stage needs a multi-node solve (a system of
   coupled first-order ODEs, or a resolved Foster/Cauer ladder); this
   module's forms would UNDER-predict peak temperature if applied to
   such a stack by lumping it into one falsely-fast-equilibrating
   node. A caller with a multi-node problem must either lump it
   (accepting the single-node approximation, e.g. dominant-pole
   reduction to one `R_th`+`C_th`) or wait for a future multi-node
   deliverable -- not attempted this dispatch.
2. `C_th` (thermal capacitance) has no PRODUCER direction in this
   repo (unlike `R_th`, which `heat.py` can already produce from
   conduction/convection geometry) -- CALLER-SUPPLIED, named cut,
   same shape as cut 2 in `member_capacity.py`'s docstring (a future
   `rho*V*c` direction over material density/volume/specific heat
   would close this, not attempted here).
3. Temperature-dependent properties (R_th, C_th, or the convective
   h feeding Bi varying with T) are NOT modeled -- CONSTANT
   properties is a standing lumped-capacitance precondition
   (Incropera ch. 5 sec. 5.1's own assumption set), not separately
   checked beyond the Bi gate.

Claim-kind naming rationale (for the lithos-side harness pack that
would route a thermal claim onto these directions): lithos
`python/regolith/harness/models/lumped_thermal.py` already registers
`thermo.junction_temperature` (WO-26 D105b) for the STEADY form,
`T_j = T_amb + P*R_theta`. This module's `step_temperature` direction
is the transient generalization of that SAME physics (the steady form
is this module's `t -> infinity` limit, `1 - exp(-t/tau) -> 1`) --
so a future lithos-side model pack discharging a transient junction-
temperature claim should register under a NAME THAT PARALLELS, not
collides with, `thermo.junction_temperature`: `thermo.
junction_temperature_transient` for the step/threshold forms (adds a
`time` input to the same `ambient`/`power`/`r_theta`-shaped port set)
and `thermo.junction_temperature_duty_cycle` for the periodic
duty-cycle peak form (the VRM case -- adds `t_on`/`t_off` in place of
`time`). Both stay upper-bound claims (`ClaimSense.upper_bound()`,
same sense as the steady pack -- a peak/instantaneous temperature is
still a "value must stay below a limit" quantity), and both would
need their own `NumericReducedTierModel` subclass on the lithos side
(out of this dispatch's feldspar-only scope; recorded here so the
naming is decided BEFORE that pack is written, not invented
ad hoc when it lands)."""

import math

from typani import Err, Ok

from feldspar.core import Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

_INCROPERA = "Incropera & DeWitt, Fundamentals of Heat and Mass Transfer, 7th ed."

#: Incropera ch. 5 sec. 5.1 eq. 5.10: lumped-capacitance validity
#: criterion, Bi = h*Lc/k. Bi >= this threshold is REJECTED.
_BI_MAX = 0.1


def _reject_biot(bi: float, where: str):
    """Shared Biot-number honesty gate: `OutOfDomain` at/above 0.1
    (Incropera ch. 5 sec. 5.1 eq. 5.10), the single validity predicate
    every direction in this module enforces before trusting a
    single-node lumped solve."""
    if bi >= _BI_MAX:
        return SolveError.OutOfDomain(
            violation=(
                f"{where}: Bi={bi!r} >= {_BI_MAX} -- lumped-capacitance "
                "method invalid (Incropera ch. 5 sec. 5.1 eq. 5.10 "
                "requires Bi < 0.1; internal conduction resistance is "
                "not negligible, a single-node solve would misstate "
                "the transient response)"
            )
        )
    if bi < 0.0:
        return SolveError.OutOfDomain(
            violation=f"{where}: negative Bi={bi!r} is not physical"
        )
    return None


_BIOT_BOX = Interval(0.0, _BI_MAX)

# ---------------------------------------------------------------------------
# Biot number convenience direction: Bi = h*Lc/k
# ---------------------------------------------------------------------------

_BIOT_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_INCROPERA}, ch. 5 sec. 5.1 eq. 5.10 (Bi = h*Lc/k, the "
            "lumped-capacitance validity criterion; Lc = V/As, the "
            "characteristic length)"
        ),
        note="Computes Bi only; the < 0.1 criterion is NOT applied here"
        " -- every OTHER direction in this module applies it to the Bi"
        " value a caller feeds into their `biot_number` port (which may"
        " come from this direction or be independently asserted).",
    ),
)


@solver(
    namespace="heat.transient",
    inputs=(
        "heat.transient.convection_coefficient",
        "heat.transient.characteristic_length",
        "heat.transient.conductivity",
    ),
    outputs=("heat.transient.biot_number",),
    domain=Domain(
        box={
            # Convection coefficient h, W/(m^2*K).
            "heat.transient.convection_coefficient": Interval(1e-3, 1e5),
            # Characteristic length Lc = V/As, m.
            "heat.transient.characteristic_length": Interval(1e-6, 10.0),
            # Solid conductivity k, W/(m*K).
            "heat.transient.conductivity": Interval(1e-3, 500.0),
        },
        tags=set(),
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_BIOT_CITATIONS,
    version="1",
)
def biot_number_from_convection(x):
    """Incropera ch. 5 sec. 5.1 eq. 5.10: `Bi = h*Lc/k`."""
    h = x["heat.transient.convection_coefficient"]
    lc = x["heat.transient.characteristic_length"]
    k = x["heat.transient.conductivity"]
    if h <= 0.0 or lc <= 0.0 or k <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(f"Biot: non-positive h={h!r}, Lc={lc!r}, or k={k!r}")
            )
        )
    return Ok({"heat.transient.biot_number": h * lc / k})


# ---------------------------------------------------------------------------
# Step response: T(t) = T_amb + P*R_th*(1 - exp(-t/tau)), tau = R_th*C_th
# ---------------------------------------------------------------------------

_STEP_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_INCROPERA}, ch. 5 sec. 5.2 (lumped-capacitance transient "
            "response to a step heat generation, the RC-analog "
            "solution of C_th*dT/dt = P - (T-T_amb)/R_th with T(0) = "
            "T_amb); docs/benchmarks-memo.md sec. 4.1 (the same ODE "
            "shape, electrical RC step response) and sec. 12.1 (thermal "
            "worked case)"
        ),
        note="Constant R_th, C_th, and single-node lumping are standing"
        " preconditions (Bi < 0.1, gated at runtime); a caller-asserted"
        " Biot number is REQUIRED on every call.",
    ),
)


@solver(
    namespace="heat.transient",
    inputs=(
        "heat.transient.t_amb",
        "heat.transient.power",
        "heat.transient.r_th",
        "heat.transient.c_th",
        "heat.transient.time",
        "heat.transient.biot_number",
    ),
    outputs=("heat.transient.temperature",),
    domain=Domain(
        box={
            # Ambient temperature, K.
            "heat.transient.t_amb": Interval(0.0, 600.0),
            # Constant dissipated power, W.
            "heat.transient.power": Interval(0.0, 1.0e5),
            # Lumped thermal resistance, K/W.
            "heat.transient.r_th": Interval(1e-6, 1e5),
            # Lumped thermal capacitance, J/K.
            "heat.transient.c_th": Interval(1e-9, 1e6),
            # Elapsed time since step onset, s.
            "heat.transient.time": Interval(0.0, 1.0e9),
            "heat.transient.biot_number": _BIOT_BOX,
        },
        tags={"lumped_capacitance", "single_node", "constant_properties"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_STEP_CITATIONS,
    version="1",
)
def step_temperature(x):
    """Lumped-capacitance step response: `T(t) = T_amb + P*R_th*(1 -
    exp(-t/tau))`, `tau = R_th*C_th`. `T(0) = T_amb` (power switches
    on at `t=0` and stays on)."""
    t_amb = x["heat.transient.t_amb"]
    power = x["heat.transient.power"]
    r_th = x["heat.transient.r_th"]
    c_th = x["heat.transient.c_th"]
    time = x["heat.transient.time"]
    bi = x["heat.transient.biot_number"]
    err = _reject_biot(bi, "step_temperature")
    if err is not None:
        return Err(err)
    if power < 0.0 or r_th <= 0.0 or c_th <= 0.0 or time < 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"step_temperature: invalid power={power!r}, "
                    f"r_th={r_th!r}, c_th={c_th!r}, or time={time!r}"
                )
            )
        )
    tau = r_th * c_th
    rise = power * r_th * (1.0 - math.exp(-time / tau))
    return Ok({"heat.transient.temperature": t_amb + rise})


# ---------------------------------------------------------------------------
# Time-to-threshold: invert the step response for t
# ---------------------------------------------------------------------------

_TTT_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_INCROPERA}, ch. 5 sec. 5.2, algebraic inversion of the "
            "step response for elapsed time (same ODE and worked case "
            "as `step_temperature`; docs/benchmarks-memo.md sec. 12.1)"
        ),
        note="Same Bi < 0.1 / constant-property preconditions as `step_temperature`.",
    ),
)


@solver(
    namespace="heat.transient",
    inputs=(
        "heat.transient.t_amb",
        "heat.transient.power",
        "heat.transient.r_th",
        "heat.transient.c_th",
        "heat.transient.t_threshold",
        "heat.transient.biot_number",
    ),
    outputs=("heat.transient.time_to_threshold",),
    domain=Domain(
        box={
            "heat.transient.t_amb": Interval(0.0, 600.0),
            "heat.transient.power": Interval(0.0, 1.0e5),
            "heat.transient.r_th": Interval(1e-6, 1e5),
            "heat.transient.c_th": Interval(1e-9, 1e6),
            # Threshold temperature, K (must exceed t_amb).
            "heat.transient.t_threshold": Interval(0.0, 900.0),
            "heat.transient.biot_number": _BIOT_BOX,
        },
        tags={"lumped_capacitance", "single_node", "constant_properties"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_TTT_CITATIONS,
    version="1",
)
def time_to_threshold(x):
    """Elapsed time for the step response to first reach
    `t_threshold`: `t = -tau*ln(1 - (T_thresh-T_amb)/(P*R_th))`.
    `OutOfDomain` (honest, not a fabricated verdict) when the
    asymptotic steady rise `P*R_th` never reaches the threshold."""
    t_amb = x["heat.transient.t_amb"]
    power = x["heat.transient.power"]
    r_th = x["heat.transient.r_th"]
    c_th = x["heat.transient.c_th"]
    t_thresh = x["heat.transient.t_threshold"]
    bi = x["heat.transient.biot_number"]
    err = _reject_biot(bi, "time_to_threshold")
    if err is not None:
        return Err(err)
    if power <= 0.0 or r_th <= 0.0 or c_th <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"time_to_threshold: non-positive power={power!r}, "
                    f"r_th={r_th!r}, or c_th={c_th!r}"
                )
            )
        )
    steady_rise = power * r_th
    needed_rise = t_thresh - t_amb
    if needed_rise <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"time_to_threshold: t_threshold={t_thresh!r} <= "
                    f"t_amb={t_amb!r} -- already at/above threshold at "
                    "t=0, no finite step time applies"
                )
            )
        )
    if needed_rise >= steady_rise:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"time_to_threshold: needed rise={needed_rise!r} K "
                    f">= asymptotic steady rise P*R_th={steady_rise!r} K"
                    " -- the threshold is never reached, no finite time"
                    " exists (honest refusal, not a fabricated time)"
                )
            )
        )
    tau = r_th * c_th
    t = -tau * math.log(1.0 - needed_rise / steady_rise)
    return Ok({"heat.transient.time_to_threshold": t})


# ---------------------------------------------------------------------------
# Duty-cycle peak temperature: periodic square-wave lumped-capacitance
# forcing, closed-form periodic-steady-state peak (end of "on" phase)
# ---------------------------------------------------------------------------

_DUTY_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_INCROPERA}, ch. 5 sec. 5.2 governing ODE, extended to "
            "periodic square-wave forcing by direct algebraic solution "
            "of the SAME first-order lumped ODE under a periodic-"
            "steady-state boundary condition (not a separate empirical "
            "correlation -- superposition of the ch. 5 step/decay "
            "solutions over one on/off cycle with `theta(0) = "
            "theta(period)`); docs/benchmarks-memo.md sec. 12.2 (worked "
            "case, derivation, and the two limiting-case checks: "
            "continuous power at duty=1, and quasi-steady average-power "
            "reduction at switching-period << tau)"
        ),
        note="Steady PERIODIC state only (many cycles elapsed) -- the"
        " first-cycle transient toward that periodic state is NOT"
        " this direction's output (it is bounded above by this"
        " direction's result, since T_peak is monotone-increasing"
        " toward the periodic limit from a T_amb start -- a"
        " conservative first-cycle caller can still use this value)."
        " Same Bi < 0.1 / constant-property / single-node preconditions"
        " as `step_temperature`.",
    ),
)


@solver(
    namespace="heat.transient",
    inputs=(
        "heat.transient.t_amb",
        "heat.transient.power",
        "heat.transient.r_th",
        "heat.transient.c_th",
        "heat.transient.t_on",
        "heat.transient.t_off",
        "heat.transient.biot_number",
    ),
    outputs=("heat.transient.duty_peak_temperature",),
    domain=Domain(
        box={
            "heat.transient.t_amb": Interval(0.0, 600.0),
            # Power dissipated during the ON phase, W (not the
            # duty-averaged power -- the pulse amplitude).
            "heat.transient.power": Interval(0.0, 1.0e5),
            "heat.transient.r_th": Interval(1e-6, 1e5),
            "heat.transient.c_th": Interval(1e-9, 1e6),
            # ON-phase duration, s.
            "heat.transient.t_on": Interval(0.0, 1.0e6),
            # OFF-phase duration, s.
            "heat.transient.t_off": Interval(0.0, 1.0e6),
            "heat.transient.biot_number": _BIOT_BOX,
        },
        tags={
            "lumped_capacitance",
            "single_node",
            "constant_properties",
            "periodic_steady_state",
        },
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_DUTY_CITATIONS,
    version="1",
)
def duty_cycle_peak_temperature(x):
    """Periodic-steady-state peak temperature (end of the ON phase)
    for a square-wave power pulse train: `T_peak = T_amb + P*R_th*
    (1-a)/(1-a*b)`, `a = exp(-t_on/tau)`, `b = exp(-t_off/tau)`, `tau
    = R_th*C_th`. Derivation: with `theta = T - T_amb`, one ON phase
    maps `theta_0 -> theta_0*a + P*R_th*(1-a)`, one OFF phase maps
    `theta_1 -> theta_1*b`; the periodic-steady-state fixed point
    (`theta` at the START of an ON phase reproduces itself after a
    full cycle) is `theta_0 = P*R_th*(1-a)*b/(1-a*b)`, and the PEAK
    (end of ON) is `theta_1 = theta_0*a + P*R_th*(1-a)`, which
    algebraically reduces to `P*R_th*(1-a)/(1-a*b)` (the fraction
    used here directly)."""
    t_amb = x["heat.transient.t_amb"]
    power = x["heat.transient.power"]
    r_th = x["heat.transient.r_th"]
    c_th = x["heat.transient.c_th"]
    t_on = x["heat.transient.t_on"]
    t_off = x["heat.transient.t_off"]
    bi = x["heat.transient.biot_number"]
    err = _reject_biot(bi, "duty_cycle_peak_temperature")
    if err is not None:
        return Err(err)
    if power < 0.0 or r_th <= 0.0 or c_th <= 0.0 or t_on < 0.0 or t_off < 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"duty_cycle_peak_temperature: invalid power={power!r}, "
                    f"r_th={r_th!r}, c_th={c_th!r}, t_on={t_on!r}, or "
                    f"t_off={t_off!r}"
                )
            )
        )
    if t_on == 0.0 and t_off == 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    "duty_cycle_peak_temperature: t_on and t_off both "
                    "zero -- no period defined"
                )
            )
        )
    tau = r_th * c_th
    a = math.exp(-t_on / tau)
    b = math.exp(-t_off / tau)
    denom = 1.0 - a * b
    if denom <= 0.0:
        # Only reachable in the degenerate a=b=1 limit (t_on=t_off=0),
        # already rejected above; kept as an explicit honest guard
        # rather than a silent division.
        return Err(
            SolveError.OutOfDomain(
                violation="duty_cycle_peak_temperature: degenerate cycle (1-a*b <= 0)"
            )
        )
    rise = power * r_th * (1.0 - a) / denom
    return Ok({"heat.transient.duty_peak_temperature": t_amb + rise})


#: This family's port table (WO111b composition fix; see
#: `member_capacity.py`'s `_PORT_DECLS` note).
_PORT_DECLS = (
    PortDecl("heat.transient.convection_coefficient", "W/(m^2*K)"),
    PortDecl("heat.transient.characteristic_length", "m"),
    PortDecl("heat.transient.conductivity", "W/(m*K)"),
    PortDecl("heat.transient.biot_number", "1"),
    PortDecl("heat.transient.t_amb", "K"),
    PortDecl("heat.transient.power", "W"),
    PortDecl("heat.transient.r_th", "K/W"),
    PortDecl("heat.transient.c_th", "J/K"),
    PortDecl("heat.transient.time", "s"),
    PortDecl("heat.transient.temperature", "K"),
    PortDecl("heat.transient.t_threshold", "K"),
    PortDecl("heat.transient.time_to_threshold", "s"),
    PortDecl("heat.transient.t_on", "s"),
    PortDecl("heat.transient.t_off", "s"),
    PortDecl("heat.transient.duty_peak_temperature", "K"),
)


def register(registry: SolverRegistry) -> None:
    """Registers all four thermal-transient directions (WO-24
    deliverable 6: Biot-number convenience form, step response,
    time-to-threshold, and periodic duty-cycle peak temperature).
    Declares this family's port table first (WO111b)."""
    _ = registry.declare_ports(*_PORT_DECLS).danger_ok
    directions = [
        biot_number_from_convection.solver_direction,  # ty: ignore[unresolved-attribute]
        step_temperature.solver_direction,  # ty: ignore[unresolved-attribute]
        time_to_threshold.solver_direction,  # ty: ignore[unresolved-attribute]
        duty_cycle_peak_temperature.solver_direction,  # ty: ignore[unresolved-attribute]
    ]
    for direction in directions:
        result = registry.register(*direction)
        _ = result.danger_ok
    _log.info("thermal_transient: registered %d solver directions", len(directions))
