from __future__ import annotations

"""Structural-steel member CAPACITY forms (WO-24 deliverable 0, closing
the WO-21/23 `section_material` `ea`/`ei` cut-1 seam consumer-side per
lithos design-log 2026-07-09-cycle-31 D176): AISC 360-16 F2 compact-
section flexural yield and E3 axial yield/flexural-buckling, over
CALLER-SUPPLIED section properties (Zx, Ag, r) and material Fy.

SCOPE (honest, narrow -- the WO-24 standing law): these are the BASIC
yield-limit-state forms only.

- `flexural_yield_capacity_f2` is AISC 360-16 sec. F2.1 eq. F2-1
  (Mn = Mp = Fy*Zx) for a COMPACT, LATERALLY BRACED (Lb <= Lp) wide-
  flange member ONLY -- the lateral-torsional-buckling limit state
  (sec. F2.2, eq. F2-2/F2-3, needs Lb/Lp/Lr/Cb) is NOT built here; it
  is the recorded WO-23 cut, unchanged (compactness and bracing are
  CALLER-ASSERTED preconditions this function cannot itself verify
  from Fy/Zx alone -- no invented physics, no fabricated Lb/Lp check).
- `axial_yield_buckling_capacity_e3` is AISC 360-16 sec. E3 (flexural
  buckling of members without slender elements): eq. E3-1 (Pn =
  Fcr*Ag) with the eq. E3-2/E3-3 Fcr branches selected by the E3
  user-note KL/r <= 4.71*sqrt(E/Fy) (equivalently Fy/Fe <= 2.25)
  boundary. Torsional/flexural-torsional buckling (sec. E4) and
  slender-element reduction (sec. E7) are NOT built -- named cuts.
- `euler_critical_buckling_load` (WO-24 deliverable 8, docs/
  benchmarks-memo.md sec. 9) is the classical Euler elastic column
  buckling formula, `Pcr = pi^2*E*I/(K*L)^2` (Timoshenko, Theory of
  Elastic Stability, ch. 2; Shigley 11e ch. 4 sec. 4-14 eq. 4-42) --
  the SAME physics as `axial_yield_buckling_capacity_e3`'s `Fe`
  (`Pcr = Fe*Ag` since `I = Ag*r^2`), but as its own direction over
  caller-supplied `E, I, K, L` directly, with no yield-strength input
  and no inelastic (eq. E3-2) branch to select -- a narrower, purely
  elastic tier for callers who have `I` and not `r`/`Ag` separately
  (e.g. a non-steel or non-AISC-catalog column, or a bare elastic-
  stability check upstream of a yield check). `K` (effective-length
  factor) is CALLER-SUPPLIED, per AISC 360-16 commentary Table
  C-A-7.1 standard values (1.0 pinned-pinned, 0.5 fixed-fixed, 0.7
  fixed-pinned, 2.0 fixed-free) -- this direction does not derive `K`
  from end-condition tags, it only consumes the numeric value.

Both F2/E3 apply the standard LRFD resistance factors (phi_b = 0.90, sec.
F1; phi_c = 0.90, sec. E1) as CODE CONSTANTS, not solver inputs (an
engineering code coefficient, not a measured physical quantity --
matching how other library modules bake fixed physical constants into
a formula body rather than exposing them as ports).

Same "caller-resolved numbers" seam as `civil_utilization_h1`
(`feldspar.library.struct`): no registry-resolution channel exists in
feldspar's payload port surface for a section/material `RecordRef`'s
digest to become numeric Zx/Ag/r (WO-21 close-out cut 1, unchanged).
These are ordinary `@solver` pure-map directions (10 sec. 2 pattern
1) over already-numeric ports, registered through the pack protocol
like every `library.mech` formula."""

import math

from typani import Err, Ok

from feldspar.core import Domain, Interval
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

_AISC = "ANSI/AISC 360-16, Specification for Structural Steel Buildings"

#: LRFD resistance factor, flexure (AISC 360-16 sec. F1).
_PHI_B = 0.90
#: LRFD resistance factor, compression (AISC 360-16 sec. E1).
_PHI_C = 0.90

# ---------------------------------------------------------------------------
# F2.1 -- compact, braced flexural yield: Mn = Mp = Fy*Zx (eq. F2-1)
# ---------------------------------------------------------------------------

_F2_CITATIONS = (
    Citation(
        kind="standard",
        ref=(
            f"{_AISC}, sec. F2.1, eq. F2-1 (Mn = Mp = Fy*Zx, the yielding "
            "limit state for a compact-section, laterally braced "
            "doubly-symmetric I-shaped member bent about its major axis)"
        ),
        note=(
            "Lateral-torsional buckling (sec. F2.2, eq. F2-2/F2-3) is NOT "
            "evaluated here -- compact + Lb<=Lp (braced) are CALLER-"
            "ASSERTED preconditions, not derived from Fy/Zx alone "
            "(WO-24 deliverable 0 scope; WO-23 close-out cut, unchanged)."
        ),
    ),
)


@solver(
    namespace="mech.member",
    inputs=("mech.member.flexure.fy", "mech.member.flexure.zx"),
    outputs=("mech.member.flexure.capacity",),
    domain=Domain(
        box={
            # Structural steel yield strength, ASTM A36..A992 range
            # (36..70 ksi ~ 248..483 MPa), Pa.
            "mech.member.flexure.fy": Interval(2.0e8, 5.0e8),
            # Plastic section modulus, m^3 (covers small angles through
            # large wide-flange shapes).
            "mech.member.flexure.zx": Interval(1.0e-7, 1.0e-1),
        },
        tags={"compact", "braced", "steel"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_F2_CITATIONS,
    version="1",
)
def flexural_yield_capacity_f2(x):
    """AISC 360-16 F2.1 eq. F2-1: `phi_b*Mn = phi_b*Fy*Zx`. Caller
    asserts the member is compact and laterally braced (`tags`
    documents, never enforces, this precondition -- no Lb/Lp input
    exists on this port set to check it against)."""
    fy = x["mech.member.flexure.fy"]
    zx = x["mech.member.flexure.zx"]
    if fy <= 0.0 or zx <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"F2.1: non-positive fy={fy!r} or zx={zx!r} -- cannot "
                    "form a flexural yield capacity"
                )
            )
        )
    mp = fy * zx
    return Ok({"mech.member.flexure.capacity": _PHI_B * mp})


# ---------------------------------------------------------------------------
# E3 -- axial yield/flexural buckling: Pn = Fcr*Ag (eq. E3-1..E3-3)
# ---------------------------------------------------------------------------

_E3_CITATIONS = (
    Citation(
        kind="standard",
        ref=(
            f"{_AISC}, sec. E3, eq. E3-1 (Pn = Fcr*Ag), eq. E3-2 "
            "(inelastic buckling, Fcr = 0.658^(Fy/Fe)*Fy, when "
            "KL/r <= 4.71*sqrt(E/Fy) equivalently Fy/Fe <= 2.25), eq. "
            "E3-3 (elastic buckling, Fcr = 0.877*Fe, otherwise), and "
            "eq. E3-4 (Fe = pi^2*E/(KL/r)^2)"
        ),
        note=(
            "Torsional/flexural-torsional buckling (sec. E4) and "
            "slender-element reduction (sec. E7) are NOT evaluated -- "
            "member without slender elements is a CALLER-ASSERTED "
            "precondition (WO-24 deliverable 0 scope)."
        ),
    ),
)

#: AISC 360-16 sec. E2 User Note: KL/r preferably <= 200 for members
#: designed on the basis of compression.
_KL_R_MAX = 200.0


@solver(
    namespace="mech.member",
    inputs=(
        "mech.member.axial.fy",
        "mech.member.axial.ag",
        "mech.member.axial.e",
        "mech.member.axial.kl_over_r",
    ),
    outputs=("mech.member.axial.capacity",),
    domain=Domain(
        box={
            "mech.member.axial.fy": Interval(2.0e8, 5.0e8),
            # Gross cross-sectional area, m^2.
            "mech.member.axial.ag": Interval(1.0e-5, 1.0),
            # Steel Young's modulus, tightly banded around 200 GPa
            # (AISC 360-16 sec. B4, E=29,000 ksi).
            "mech.member.axial.e": Interval(1.9e11, 2.1e11),
            # AISC 360-16 sec. E2 User Note upper bound.
            "mech.member.axial.kl_over_r": Interval(1.0, _KL_R_MAX),
        },
        tags={"steel", "no_slender_elements"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_E3_CITATIONS,
    version="1",
)
def axial_yield_buckling_capacity_e3(x):
    """AISC 360-16 sec. E3: `phi_c*Pn` for a doubly-symmetric member
    without slender elements, KL/r-governed flexural buckling only."""
    fy = x["mech.member.axial.fy"]
    ag = x["mech.member.axial.ag"]
    e = x["mech.member.axial.e"]
    kl_r = x["mech.member.axial.kl_over_r"]
    if fy <= 0.0 or ag <= 0.0 or e <= 0.0 or kl_r <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"E3: non-positive fy={fy!r}, ag={ag!r}, e={e!r}, or "
                    f"kl_over_r={kl_r!r} -- cannot form an axial capacity"
                )
            )
        )
    fe = (math.pi**2) * e / (kl_r**2)  # eq. E3-4
    if kl_r <= 4.71 * math.sqrt(e / fy):
        fcr = (0.658 ** (fy / fe)) * fy  # eq. E3-2
    else:
        fcr = 0.877 * fe  # eq. E3-3
    pn = fcr * ag  # eq. E3-1
    return Ok({"mech.member.axial.capacity": _PHI_C * pn})


# ---------------------------------------------------------------------------
# Euler elastic column buckling: Pcr = pi^2*E*I/(K*L)^2 (WO-24 deliverable 8)
# ---------------------------------------------------------------------------

_EULER_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            "Timoshenko, Theory of Elastic Stability, 2nd ed., ch. 2 "
            "(the classical pin-ended elastic column, Pcr = "
            "pi^2*E*I/L^2, generalized to Pcr = pi^2*E*I/(K*L)^2 via "
            "the effective-length factor K); also Shigley's Mechanical "
            "Engineering Design, 11th ed., ch. 4 sec. 4-14 eq. 4-42 "
            "(docs/benchmarks-memo.md sec. 9)"
        ),
        note=(
            "Standard K values (AISC 360-16 commentary Table C-A-7.1): "
            "1.0 pinned-pinned, 0.5 fixed-fixed, 0.7 fixed-pinned, 2.0 "
            "fixed-free -- CALLER-SUPPLIED, not derived from end-"
            "condition tags. Same physics as "
            "`axial_yield_buckling_capacity_e3`'s Fe (Pcr = Fe*Ag since "
            "I = Ag*r^2); this direction takes E/I/K/L directly with "
            "no yield-strength input and no inelastic branch (WO-24 "
            "deliverable 8, honest completion of the WO-21/23/24 "
            "column-buckling residual: E4 torsional/flexural-torsional "
            "buckling and E7 slender-element reduction remain NOT "
            "built, named cuts)."
        ),
    ),
)


@solver(
    namespace="mech.member",
    inputs=(
        "mech.member.euler.e",
        "mech.member.euler.i",
        "mech.member.euler.k",
        "mech.member.euler.length",
    ),
    outputs=("mech.member.euler.pcr",),
    domain=Domain(
        box={
            # Young's modulus, Pa (wide band -- not steel-specific,
            # unlike the E3 direction above).
            "mech.member.euler.e": Interval(1.0e9, 5.0e11),
            # Second moment of area about the buckling axis, m^4.
            "mech.member.euler.i": Interval(1.0e-10, 1.0),
            # Effective-length factor, dimensionless (AISC Table
            # C-A-7.1 standard range 0.5..2.0, widened slightly for
            # caller-computed intermediate K values).
            "mech.member.euler.k": Interval(0.3, 2.5),
            # Unbraced length, m.
            "mech.member.euler.length": Interval(1.0e-3, 100.0),
        },
        tags={"elastic", "prismatic", "no_slender_elements"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_EULER_CITATIONS,
    version="1",
)
def euler_critical_buckling_load(x):
    """Classical Euler elastic buckling: `Pcr = pi^2*E*I/(K*L)^2`,
    no yield-strength check (pairs with
    `axial_yield_buckling_capacity_e3` for the inelastic/yield
    side)."""
    e = x["mech.member.euler.e"]
    i = x["mech.member.euler.i"]
    k = x["mech.member.euler.k"]
    length = x["mech.member.euler.length"]
    if e <= 0.0 or i <= 0.0 or k <= 0.0 or length <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"Euler: non-positive e={e!r}, i={i!r}, k={k!r}, or "
                    f"length={length!r} -- cannot form a critical buckling load"
                )
            )
        )
    pcr = (math.pi**2) * e * i / ((k * length) ** 2)
    return Ok({"mech.member.euler.pcr": pcr})


def register(registry: SolverRegistry) -> None:
    """Registers all three member-capacity directions (WO-24
    deliverables 0 + 8: F2 flexural yield, E3 axial yield/buckling,
    Euler elastic column buckling)."""
    result_a = registry.register(*flexural_yield_capacity_f2.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_a.danger_ok
    result_b = registry.register(*axial_yield_buckling_capacity_e3.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_b.danger_ok
    result_c = registry.register(*euler_critical_buckling_load.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_c.danger_ok
    _log.info("member_capacity: registered %d solver directions", 3)
