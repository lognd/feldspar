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

Both apply the standard LRFD resistance factors (phi_b = 0.90, sec.
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


def register(registry: SolverRegistry) -> None:
    """Registers both F2/E3 capacity directions (WO-24 deliverable 0)."""
    result_a = registry.register(*flexural_yield_capacity_f2.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_a.danger_ok
    result_b = registry.register(*axial_yield_buckling_capacity_e3.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_b.danger_ok
    _log.info("member_capacity: registered %d solver directions", 2)
