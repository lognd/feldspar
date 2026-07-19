from __future__ import annotations

"""Rolling-bearing basic dynamic rating life, ISO 281:2007 (WO-24
deliverable 3, docs/benchmarks-memo.md sec. 11): the L10 basic
rating life form over rating records shaped like lithos
`std.bearings` rows (`dynamic_load_kn`/`static_load_kn`, ISO 15
boundary-dimension classes; lithos:stdlib/std.bearings/records/
deep_groove_ball.toml is the shape reference this module calibrates
its port names against, read-only).

SCOPE (honest, narrow -- the WO-24 standing law, same shape as
`bolted_joints.py`/`weld_groups.py`):

- `bearing_basic_rating_life_l10_ball` and
  `bearing_basic_rating_life_l10_roller` are ISO 281:2007 sec. 6.2
  eq. 4, `L10 = (C/P)^p` (millions of revolutions), with the load-
  life exponent `p` BAKED as a code constant per bearing kind (p=3
  for ball bearings, p=10/3 for roller bearings -- the standard's own
  fixed values, an engineering constant, not a measured quantity,
  matching how `member_capacity.py` bakes `phi_b`/`phi_c`). `C`
  (basic dynamic load rating) and `P` (equivalent dynamic bearing
  load) are CALLER-SUPPLIED -- `C` comes directly off a
  `std.bearings`-shaped record's `dynamic_load_kn` field (unit-
  converted to N by the caller); `P` is NOT derived here (ISO
  281:2007 sec. 6.1's `P = X*Fr + Y*Fa` combined-load equivalent-load
  formula needs the X/Y factor tables, which are bearing-geometry-
  specific and NOT transcribed in this module -- a named cut, not an
  omission; a pure-radial or pure-axial load with `P` set equal to
  that load is the caller's own responsibility to establish).
- `bearing_basic_rating_life_l10h` converts `L10` (millions of
  revolutions) to hours at a caller-supplied constant rotational
  speed `n` (rpm): ISO 281:2007 sec. 6.2 eq. 5,
  `L10h = L10*1e6 / (60*n)`. This direction is bearing-kind-agnostic
  (it consumes an already-computed `L10`, from either the ball or
  roller direction above).

NAMED CUT (the WO's own instruction): no ISO 281:2007 sec. 6.3
"modified rating life" `a_iso` life-modification factor (reliability
`a1`, or the full systems-approach `aISO` contamination/lubrication
factor) is applied in this v1 -- these three directions compute the
BASIC (unmodified, 90%-reliability) L10/L10h only. A future dispatch
adding `a_iso` needs its own citation trail (ISO 281:2007 annex).
Static-load safety (`C0/P0`, ISO 76) is NOT evaluated -- a separate
standard, out of this deliverable's scope."""

from typani import Err, Ok

from feldspar.core import Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

_ISO_281 = "ISO 281:2007, Rolling bearings -- Dynamic load ratings and rating life"

#: ISO 281:2007 sec. 6.2: load-life exponent, ball bearings.
_P_BALL = 3.0
#: ISO 281:2007 sec. 6.2: load-life exponent, roller bearings.
_P_ROLLER = 10.0 / 3.0

# ---------------------------------------------------------------------------
# 11.1/11.2 -- basic L10, ball / roller (p baked per bearing kind)
# ---------------------------------------------------------------------------


def _l10_citation(kind: str, p: float) -> Citation:
    return Citation(
        kind="standard",
        ref=(
            f"{_ISO_281}, sec. 6.2 eq. 4, L10 = (C/P)^p, p={p!r} "
            f"({kind} bearings) (docs/benchmarks-memo.md sec. 11)"
        ),
        note=(
            "P is CALLER-SUPPLIED (the ISO 281 sec. 6.1 X/Y combined-"
            "load equivalent-load reduction is NOT performed here -- "
            "named cut). No a_iso life-modification factor (sec. 6.3) "
            "is applied -- basic (unmodified) L10 only."
        ),
    )


def _l10(x: dict, p: float, kind: str):
    c = x["mech.bearing.dynamic_rating"]
    load = x["mech.bearing.equivalent_load"]
    if c <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(f"ISO 281 L10 ({kind}): non-positive dynamic rating C={c!r}")
            )
        )
    if load <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"ISO 281 L10 ({kind}): non-positive equivalent load P={load!r}"
                )
            )
        )
    l10 = (c / load) ** p
    return Ok({"mech.bearing.l10": l10})


# frob:doc docs/modules/mech.md#mech_bearing_life
@solver(
    namespace="mech.bearing",
    inputs=("mech.bearing.dynamic_rating", "mech.bearing.equivalent_load"),
    outputs=("mech.bearing.l10",),
    domain=Domain(
        box={
            # Basic dynamic load rating C, N (std.bearings
            # dynamic_load_kn * 1000; 608-class through large 62xx
            # series spans roughly 1 kN to a few hundred kN).
            "mech.bearing.dynamic_rating": Interval(1.0e2, 1.0e7),
            # Equivalent dynamic bearing load P, N (caller-resolved,
            # not derived here).
            "mech.bearing.equivalent_load": Interval(1.0, 1.0e7),
        },
        tags={"iso_281", "ball", "basic_rating", "no_a_iso"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_l10_citation("ball", _P_BALL),),
    version="1",
)
def bearing_basic_rating_life_l10_ball(x):
    """ISO 281:2007 sec. 6.2 eq. 4, ball bearings (p=3): `L10 =
    (C/P)^3`, millions of revolutions."""
    return _l10(x, _P_BALL, "ball")


# frob:doc docs/modules/mech.md#mech_bearing_life
@solver(
    namespace="mech.bearing",
    inputs=("mech.bearing.dynamic_rating", "mech.bearing.equivalent_load"),
    outputs=("mech.bearing.l10",),
    domain=Domain(
        box={
            "mech.bearing.dynamic_rating": Interval(1.0e2, 1.0e7),
            "mech.bearing.equivalent_load": Interval(1.0, 1.0e7),
        },
        tags={"iso_281", "roller", "basic_rating", "no_a_iso"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_l10_citation("roller", _P_ROLLER),),
    version="1",
)
def bearing_basic_rating_life_l10_roller(x):
    """ISO 281:2007 sec. 6.2 eq. 4, roller bearings (p=10/3): `L10 =
    (C/P)^(10/3)`, millions of revolutions."""
    return _l10(x, _P_ROLLER, "roller")


# ---------------------------------------------------------------------------
# 11.3 -- L10 -> L10h at a caller-supplied constant speed
# ---------------------------------------------------------------------------

_L10H_CITATION = Citation(
    kind="standard",
    ref=(
        f"{_ISO_281}, sec. 6.2 eq. 5, L10h = L10*1e6 / (60*n), n the "
        "constant rotational speed in rev/min (docs/benchmarks-memo.md "
        "sec. 11)"
    ),
    note="Constant-speed operation is a CALLER-ASSERTED precondition.",
)


# frob:doc docs/modules/mech.md#mech_bearing_life
@solver(
    namespace="mech.bearing",
    inputs=("mech.bearing.l10", "mech.bearing.speed_rpm"),
    outputs=("mech.bearing.l10h",),
    domain=Domain(
        box={
            # Basic rating life, millions of revolutions.
            "mech.bearing.l10": Interval(1.0e-6, 1.0e6),
            # Constant rotational speed, rev/min.
            "mech.bearing.speed_rpm": Interval(1.0e-3, 1.0e5),
        },
        tags={"iso_281", "constant_speed"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=(_L10H_CITATION,),
    version="1",
)
def bearing_basic_rating_life_l10h(x):
    """ISO 281:2007 sec. 6.2 eq. 5: converts `L10` (millions of
    revolutions) to `L10h` (hours) at a caller-supplied constant
    speed `n` (rpm)."""
    l10 = x["mech.bearing.l10"]
    n = x["mech.bearing.speed_rpm"]
    if l10 <= 0.0:
        return Err(
            SolveError.OutOfDomain(violation=f"ISO 281 L10h: non-positive L10={l10!r}")
        )
    if n <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"ISO 281 L10h: non-positive speed n={n!r}"
            )
        )
    l10h = l10 * 1.0e6 / (60.0 * n)
    return Ok({"mech.bearing.l10h": l10h})


#: This family's port table (WO111b composition fix; see
#: `member_capacity.py`'s `_PORT_DECLS` note). `l10` is in millions
#: of revolutions (ISO 281's own unit for the basic rating life).
_PORT_DECLS = (
    PortDecl("mech.bearing.dynamic_rating", "N"),
    PortDecl("mech.bearing.equivalent_load", "N"),
    PortDecl("mech.bearing.l10", "Mrev"),
    PortDecl("mech.bearing.l10h", "h"),
    PortDecl("mech.bearing.speed_rpm", "rev/min"),
)


# frob:doc docs/modules/mech.md#mech_bearing_life
def register(registry: SolverRegistry) -> None:
    """Registers all three bearing-life directions (WO-24 deliverable
    3: ISO 281 basic L10 for ball and roller bearings + L10 -> L10h
    at a caller-supplied constant speed). Declares this family's port
    table first (WO111b)."""
    _ = registry.declare_ports(*_PORT_DECLS).danger_ok
    ball_direction = bearing_basic_rating_life_l10_ball.solver_direction  # ty: ignore[unresolved-attribute]
    result_a = registry.register(*ball_direction)
    _ = result_a.danger_ok
    roller_direction = bearing_basic_rating_life_l10_roller.solver_direction  # ty: ignore[unresolved-attribute]
    result_b = registry.register(*roller_direction)
    _ = result_b.danger_ok
    l10h_direction = bearing_basic_rating_life_l10h.solver_direction  # ty: ignore[unresolved-attribute]
    result_c = registry.register(*l10h_direction)
    _ = result_c.danger_ok
    _log.info("bearing_life: registered %d solver directions", 3)
