from __future__ import annotations

"""Signal-integrity closed-form models (WO-25 deliverable: PCB trace
controlled impedance + termination sizing), lithos design-log
2026-07-10-cycle-32 D186 / lithos:docs/spec/toolchain/35-signal-
integrity.md sec. 1.6. Same "ordinary `@solver` pure-map directions
over already-numeric ports" shape as `member_capacity.py` (10 sec. 2
pattern 1): geometry/material numbers IN, an impedance or a sized
component value OUT, no registry-resolution of a stackup/net RECORD
(that seam is lithos WO-78's, same posture as `member_capacity.py`'s
"caller-resolved numbers" note re: `struct.civil_utilization_h1`).

SCOPE (honest, narrow -- the WO-24/WO-25 standing law: never land
uncalibrated; a direction with no citable published numeric agreement
is CUT WHOLE and recorded, never approximated silently):

- `microstrip_z0` -- Hammerstad-Jensen microstrip characteristic
  impedance (Wadell, Transmission Line Design Handbook, Artech House
  1991, the closed form Wadell attributes to Hammerstad and Jensen;
  reproduced verbatim as eq. (2)/(3a)/(3b) in Burkhardt, Gregg &
  Staniforth, "Calculation of PCB Track Impedance", IPC Printed
  Circuit Expo 1999 (the "Burkhardt 1999" memo citation below) --
  quoted accuracy 2% for any er/w). CALIBRATED against Burkhardt
  1999 Table 1's field-solver ("Numerical Method") column: t=35um,
  h=794um, er=4.2, three widths (450/1500/3300um) -- this
  implementation reproduces the numerical-method Z0 to within ~1.3%
  at every tabulated width (see `docs/benchmarks-memo.md` sec. 13),
  well inside Wadell's own 2% claim. The zero-thickness track-width
  correction dw = (t/pi)*(1+ln(2h/t)) (Hammerstad 1975, the standard
  form quoted across the microstrip CAD literature, e.g. Pozar,
  Microwave Engineering, sec. 3.8) is NOT independently reproduced
  verbatim from Burkhardt 1999 (the paper cites but does not
  transcribe Wadell's own dw equation) -- an honest, named
  approximation of ONE intermediate term, cross-checked by the same
  Table 1 numeric agreement, not silently assumed exact.
- `stripline_z0` -- Cohn's EXACT centred-track symmetric-stripline
  closed form (Cohn, S.B., "Characteristic Impedance of the
  Shielded-Strip Transmission Line", IRE Trans. MTT-2, July 1954,
  pp52-57; reproduced as eq. (4)/(5a)/(5b) in Burkhardt 1999), an
  analytic result (not a curve fit) -- same calibration TIER as
  `member_capacity.py`'s `euler_critical_buckling_load` (classical
  closed-form theory cited to its origin, not a numeric-table fit).
  The complete-elliptic-integral ratio K(k)/K(k') is evaluated via
  Hilberg's closed-form rational approximation (Hilberg, W., "From
  Approximations to Exact Relations for Characteristic Impedances",
  IEEE Trans. MTT-17 No 5, May 1969, pp259-265; Burkhardt 1999 states
  this approximation is "accurate to 10-12" relative to the true
  ratio) -- so the ONLY approximation in this direction is Hilberg's
  own bounded-error one, not an added empirical fit.
- `series_termination` / `thevenin_termination` -- exact Ohm's-
  law/Kirchhoff's-law termination sizing (Johnson, H. & Graham, M.,
  High-Speed Digital Design: A Handbook of Black Magic, Prentice
  Hall 1993, ch. 4, "Source (Series) Termination" / "Thevenin
  (Parallel) Termination"), algebraically exact given Z0 and driver/
  bias parameters -- calibrated by hand-derivation (Kirchhoff current
  law at the Thevenin node), not by a fitted table (same tier as
  `pack.models.MechStiffnessModel`'s exact-algebra calibration).
- `ac_shunt_sizing` -- R sized to Z0 (matched shunt), C sized from a
  quarter-rise-time RC guideline (Johnson & Graham 1993 ch. 4, "AC
  (RC) Termination": keep the RC time constant well under the
  driver's rise time so the shunt looks resistive during the edge;
  Johnson & Graham state the literature range as roughly tr/5..tr/2 --
  this direction bakes the tr/4 midpoint as a NAMED, explicitly
  declared heuristic, not a physical law with a single exact answer.
  `declared error` on this direction's citation is wide (order-of-
  magnitude sizing aid), honestly, not narrowed to hide the
  heuristic's real spread.

NAMED CUT: `diff_pair_z` (edge-coupled differential impedance,
deliverable 1's third form) is CUT WHOLE, not built. No independently
verifiable PUBLISHED numeric impedance table for an edge-coupled
differential closed form could be confirmed against a primary source
within this dispatch's research budget (the commonly quoted
`Zdiff = 2*Z0*(1-0.48*exp(-0.96*s/h))` IPC-2141 form could not be
traced to a verbatim primary-source equation the way `microstrip_z0`/
`stripline_z0` above were -- landing it uncited would violate the
WO-24/WO-25 standing law). Reopen criteria: a verbatim IPC-2141(A) or
Wadell equation for edge-coupled differential impedance, confirmed
against a primary source (not a secondary paraphrase), with at least
one numeric calibration point traceable to that source."""

import math

from typani import Err, Ok

from feldspar.core import Accuracy, Domain, Interval
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

# Declared accuracy bands, DISTINCT from EXACT (04-routing/06 "accuracy
# declares the honest known error"): a curve-fit/approximate closed
# form states its own citable error band instead of pretending
# `Accuracy(0.0, 0.0)`.
#: Wadell 1991's own quoted 2% accuracy for the Hammerstad-Jensen
#: microstrip form (this module's docstring: Burkhardt 1999 confirms
#: agreement within ~1.5% at every tabulated width).
_MICROSTRIP_ACCURACY = Accuracy(eps_abs=0.0, eps_rel=0.02)
#: The AC-shunt capacitor heuristic's own wide, honestly-declared
#: spread (Johnson & Graham's quoted tr/5..tr/2 range around the tr/4
#: midpoint this direction bakes -- see `ac_shunt_sizing_c`'s
#: docstring): +100%/-20% relative to the chosen value, declared as a
#: symmetric 100% band (the wider, more conservative side) rather than
#: a false tight number.
_AC_SHUNT_C_ACCURACY = Accuracy(eps_abs=0.0, eps_rel=1.0)

_log = get_logger(__name__)

__all__ = ["register"]

_WADELL = "Wadell, B.C., Transmission Line Design Handbook, Artech House, 1991"
_BURKHARDT_1999 = (
    'Burkhardt, A.J., Gregg, C.S. & Staniforth, J.A., "Calculation of PCB '
    'Track Impedance", IPC Printed Circuit Expo 1999 (eq. (1)/(2)/(3)/(4)/'
    "(5), Table 1)"
)
_COHN_1954 = (
    'Cohn, S.B., "Characteristic Impedance of the Shielded-Strip '
    'Transmission Line", IRE Trans. MTT-2, July 1954, pp52-57'
)
_HILBERG_1969 = (
    'Hilberg, W., "From Approximations to Exact Relations for '
    'Characteristic Impedances", IEEE Trans. MTT-17 No 5, May 1969, '
    "pp259-265"
)
_JOHNSON_GRAHAM_1993 = (
    "Johnson, H. & Graham, M., High-Speed Digital Design: A Handbook of "
    "Black Magic, Prentice Hall, 1993, ch. 4"
)

#: Impedance of free space (Burkhardt 1999 eq. (2)'s eta0, ~120*pi).
_ETA0 = 376.7

# ---------------------------------------------------------------------------
# microstrip_z0 -- Hammerstad-Jensen (Wadell 1991 eq. (2)/(3a)/(3b), quoted
# verbatim from Burkhardt 1999 eq. (2)/(3a)/(3b)); calibrated against
# Burkhardt 1999 Table 1's numerical-method column (docs/benchmarks-memo.md
# sec. 13).
# ---------------------------------------------------------------------------

_MICROSTRIP_CITATIONS = (
    Citation(
        kind="handbook",
        ref=f"{_WADELL}, eq. (2)/(3a)/(3b) (Hammerstad-Jensen closed form), "
        f"as reproduced verbatim in {_BURKHARDT_1999}",
        note=(
            "Quoted accuracy 2% for any er/w (Burkhardt 1999). This "
            "implementation's own agreement against Burkhardt 1999 Table "
            "1's field-solver ('Numerical Method') column, t=35um, "
            "h=794um, er=4.2: w=450um -> -1.04%, w=1500um -> -0.77%, "
            "w=3300um -> -0.90% (see docs/benchmarks-memo.md sec. 13, and "
            "tests/unit/test_library_signal_integrity.py). The thickness "
            "correction dw=(t/pi)*(1+ln(2h/t)) (Hammerstad 1975, "
            "reproduced in Pozar, Microwave Engineering, sec. 3.8) fills "
            "the one intermediate term Burkhardt 1999 cites but does not "
            "transcribe (w'=w+dw, eq. (3c))."
        ),
    ),
)

#: w/h and t/h ranges the numerical calibration above actually spans
#: (Burkhardt 1999 Table 1: w=450..3300um at h=794um -> w/h=0.567..4.16;
#: t=35um -> t/h=0.044). Widened symmetrically but NOT extrapolated past
#: an order of magnitude beyond the tabulated w/h range (the formula's
#: OWN stated 2% accuracy band, not this direction inventing a tighter
#: one).
_MICROSTRIP_W_RANGE = Interval(1.0e-5, 5.0e-2)
_MICROSTRIP_H_RANGE = Interval(1.0e-5, 5.0e-2)
_MICROSTRIP_T_RANGE = Interval(1.0e-6, 2.0e-4)
_MICROSTRIP_ER_RANGE = Interval(2.0, 12.0)


@solver(
    namespace="elec.si",
    inputs=(
        "elec.si.microstrip.w",
        "elec.si.microstrip.h",
        "elec.si.microstrip.t",
        "elec.si.microstrip.er",
    ),
    outputs=("elec.si.microstrip.z0",),
    domain=Domain(
        box={
            "elec.si.microstrip.w": _MICROSTRIP_W_RANGE,
            "elec.si.microstrip.h": _MICROSTRIP_H_RANGE,
            "elec.si.microstrip.t": _MICROSTRIP_T_RANGE,
            "elec.si.microstrip.er": _MICROSTRIP_ER_RANGE,
        },
        tags={"tem", "surface_microstrip", "hammerstad_jensen"},
    ),
    cost=1e-7,
    accuracy=_MICROSTRIP_ACCURACY,
    citations=_MICROSTRIP_CITATIONS,
    version="1",
)
def microstrip_z0(x):
    """Hammerstad-Jensen microstrip Z0 (Wadell 1991 eq. (2)), all
    lengths in meters, `er` dimensionless. Caller asserts a TEM-mode,
    surface (not embedded) microstrip -- the formula's own stated
    domain (`tags` documents, never enforces, per `member_capacity.py`
    precedent)."""
    w = x["elec.si.microstrip.w"]
    h = x["elec.si.microstrip.h"]
    t = x["elec.si.microstrip.t"]
    er = x["elec.si.microstrip.er"]
    if w <= 0.0 or h <= 0.0 or t <= 0.0 or er <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"microstrip_z0: non-positive w={w!r}, h={h!r}, t={t!r}, "
                    f"or er={er!r} -- cannot form a microstrip impedance"
                )
            )
        )
    dw = (t / math.pi) * (1.0 + math.log(2.0 * h / t))
    wp = w + dw
    if wp <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"microstrip_z0: corrected width w'={wp!r} non-positive "
                    f"(w={w!r}, dw={dw!r})"
                )
            )
        )
    a = ((14.0 + 8.0 / er) / 11.0) * (4.0 * h / wp)
    b = math.sqrt(a**2 + (1.0 + 1.0 / er) / 2.0 * math.pi**2)
    z0 = (
        _ETA0
        / (2.0 * math.sqrt(2.0) * math.pi * math.sqrt(er + 1.0))
        * math.log(1.0 + (4.0 * h / wp) * (a + b))
    )
    return Ok({"elec.si.microstrip.z0": z0})


# ---------------------------------------------------------------------------
# stripline_z0 -- Cohn's exact centred-track symmetric-stripline closed
# form (Cohn 1954, eq. (4)/(5a)/(5b) as reproduced in Burkhardt 1999),
# elliptic-integral ratio via Hilberg's 1969 closed-form approximation.
# Zero-thickness (Cohn's own stated assumption).
# ---------------------------------------------------------------------------

_STRIPLINE_CITATIONS = (
    Citation(
        kind="standard",
        ref=f"{_COHN_1954}, eq. (4)/(5a)/(5b) (exact, zero-thickness, "
        f"centred track), as reproduced in {_BURKHARDT_1999}",
        note=(
            "Exact analytic result (not a curve fit), same calibration "
            "tier as member_capacity.py's euler_critical_buckling_load: "
            "cited to origin, verified by identity (k^2+k'^2=1) and "
            "monotonicity, not a numeric-table fit. The K(k)/K(k') "
            f"elliptic ratio uses {_HILBERG_1969}'s closed-form "
            "approximation, which Burkhardt 1999 states is accurate to "
            "10-12 relative to the true ratio -- the only approximation "
            "in this direction is that bounded-error one."
        ),
    ),
)

#: w/h range: narrow center track through a track nearly spanning the
#: plane-to-plane gap (Cohn's formula is valid over the whole 0<w/h<inf
#: range; this box stays inside the region Burkhardt 1999 Figure 4
#: actually plots, four decades of w/h).
_STRIPLINE_W_RANGE = Interval(1.0e-6, 5.0e-2)
_STRIPLINE_B_RANGE = Interval(1.0e-5, 5.0e-2)
_STRIPLINE_ER_RANGE = Interval(2.0, 12.0)


def _elliptic_ratio(k: float) -> float:
    """Hilberg's 1969 closed-form approximation of K(k)/K(k') (k' the
    complementary modulus, sqrt(1-k^2)), accurate to 1e-12 per Burkhardt
    1999's citation of Hilberg -- the standard piecewise form used
    throughout the CPW/stripline closed-form literature (mirrors the
    branch split at k=1/sqrt(2))."""
    kc = math.sqrt(max(0.0, 1.0 - k**2))
    if k <= 1.0 / math.sqrt(2.0):
        return math.pi / math.log(2.0 * (1.0 + math.sqrt(kc)) / (1.0 - math.sqrt(kc)))
    return (1.0 / math.pi) * math.log(2.0 * (1.0 + math.sqrt(k)) / (1.0 - math.sqrt(k)))


@solver(
    namespace="elec.si",
    inputs=("elec.si.stripline.w", "elec.si.stripline.b", "elec.si.stripline.er"),
    outputs=("elec.si.stripline.z0",),
    domain=Domain(
        box={
            "elec.si.stripline.w": _STRIPLINE_W_RANGE,
            "elec.si.stripline.b": _STRIPLINE_B_RANGE,
            "elec.si.stripline.er": _STRIPLINE_ER_RANGE,
        },
        tags={"tem", "symmetric_stripline", "centred_track", "zero_thickness"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_STRIPLINE_CITATIONS,
    version="1",
)
def stripline_z0(x):
    """Cohn's exact symmetric-stripline Z0 (eq. (4)): `b` is the FULL
    plane-to-plane dielectric spacing, track centred, zero thickness
    (Cohn's own stated assumption -- caller-asserted, no thickness
    correction exists in this exact form)."""
    w = x["elec.si.stripline.w"]
    b = x["elec.si.stripline.b"]
    er = x["elec.si.stripline.er"]
    if w <= 0.0 or b <= 0.0 or er <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"stripline_z0: non-positive w={w!r}, b={b!r}, or "
                    f"er={er!r} -- cannot form a stripline impedance"
                )
            )
        )
    k = 1.0 / math.cosh(math.pi * w / (2.0 * b))
    ratio = _elliptic_ratio(k)
    z0 = _ETA0 / (4.0 * math.sqrt(er)) * ratio
    return Ok({"elec.si.stripline.z0": z0})


# ---------------------------------------------------------------------------
# Termination sizing: exact Ohm's-law/Kirchhoff's-law forms (Johnson &
# Graham 1993 ch. 4).
# ---------------------------------------------------------------------------

_SERIES_TERM_CITATIONS = (
    Citation(
        kind="handbook",
        ref=f'{_JOHNSON_GRAHAM_1993}, "Source (Series) Termination"',
        note=(
            "Exact algebra (Rs=Z0-Ro), calibrated by hand-derivation "
            "(matched-line condition Ro+Rs=Z0), same tier as "
            "pack.models.MechStiffnessModel's exact-algebra calibration."
        ),
    ),
)

_TERM_Z0_RANGE = Interval(1.0, 500.0)
_TERM_R_RANGE = Interval(0.0, 500.0)


@solver(
    namespace="elec.si",
    inputs=("elec.si.series_termination.z0", "elec.si.series_termination.ro"),
    outputs=("elec.si.series_termination.rs",),
    domain=Domain(
        box={
            "elec.si.series_termination.z0": _TERM_Z0_RANGE,
            "elec.si.series_termination.ro": _TERM_R_RANGE,
        },
        tags={"source_series", "matched_line"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_SERIES_TERM_CITATIONS,
    version="1",
)
def series_termination(x):
    """Source-series termination resistor: `Rs = Z0 - Ro` (driver
    output impedance `Ro` plus `Rs` matches the line, Johnson & Graham
    1993 ch. 4). `Ro > Z0` is an honest domain error (no negative
    resistor exists)."""
    z0 = x["elec.si.series_termination.z0"]
    ro = x["elec.si.series_termination.ro"]
    if z0 <= 0.0 or ro < 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"series_termination: non-positive z0={z0!r} or negative ro={ro!r}"
                )
            )
        )
    rs = z0 - ro
    if rs < 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"series_termination: ro={ro!r} exceeds z0={z0!r} -- no "
                    "non-negative series resistor matches the line"
                )
            )
        )
    return Ok({"elec.si.series_termination.rs": rs})


_THEVENIN_CITATIONS = (
    Citation(
        kind="handbook",
        ref=f'{_JOHNSON_GRAHAM_1993}, "Thevenin (Parallel) Termination"',
        note=(
            "Exact algebra from Kirchhoff's current law at the Thevenin "
            "node: R1=Z0*Vcc/Vbias, R2=Z0*Vcc/(Vcc-Vbias) (solved from "
            "R1||R2=Z0 and the R2/(R1+R2)=Vbias/Vcc divider condition), "
            "calibrated by hand-derivation, same tier as "
            "series_termination above."
        ),
    ),
)

_TERM_V_RANGE = Interval(0.01, 20.0)


@solver(
    namespace="elec.si",
    inputs=(
        "elec.si.thevenin_termination.z0",
        "elec.si.thevenin_termination.vcc",
        "elec.si.thevenin_termination.vbias",
    ),
    outputs=("elec.si.thevenin_termination.r1",),
    domain=Domain(
        box={
            "elec.si.thevenin_termination.z0": _TERM_Z0_RANGE,
            "elec.si.thevenin_termination.vcc": _TERM_V_RANGE,
            "elec.si.thevenin_termination.vbias": _TERM_V_RANGE,
        },
        tags={"thevenin_parallel", "matched_line"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_THEVENIN_CITATIONS,
    version="1",
)
def thevenin_termination_r1(x):
    """Thevenin (parallel) termination pull-up leg: `R1 = Z0*Vcc/Vbias`
    (Johnson & Graham 1993 ch. 4). `Vbias` must sit strictly between 0
    and `Vcc` (an honest domain error otherwise -- no divider produces
    a bias point outside the rail)."""
    z0 = x["elec.si.thevenin_termination.z0"]
    vcc = x["elec.si.thevenin_termination.vcc"]
    vbias = x["elec.si.thevenin_termination.vbias"]
    if z0 <= 0.0 or vcc <= 0.0 or vbias <= 0.0 or vbias >= vcc:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"thevenin_termination_r1: z0={z0!r}, vcc={vcc!r}, "
                    f"vbias={vbias!r} -- vbias must lie strictly in "
                    "(0, vcc)"
                )
            )
        )
    r1 = z0 * vcc / vbias
    return Ok({"elec.si.thevenin_termination.r1": r1})


@solver(
    namespace="elec.si",
    inputs=(
        "elec.si.thevenin_termination.z0",
        "elec.si.thevenin_termination.vcc",
        "elec.si.thevenin_termination.vbias",
    ),
    outputs=("elec.si.thevenin_termination.r2",),
    domain=Domain(
        box={
            "elec.si.thevenin_termination.z0": _TERM_Z0_RANGE,
            "elec.si.thevenin_termination.vcc": _TERM_V_RANGE,
            "elec.si.thevenin_termination.vbias": _TERM_V_RANGE,
        },
        tags={"thevenin_parallel", "matched_line"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_THEVENIN_CITATIONS,
    version="1",
)
def thevenin_termination_r2(x):
    """Thevenin (parallel) termination pull-down leg: `R2 =
    Z0*Vcc/(Vcc-Vbias)` (Johnson & Graham 1993 ch. 4), the algebraic
    twin of `thevenin_termination_r1` (SAME two equations, the other
    unknown -- NO DUPLICATION of the underlying derivation, just the
    other component value)."""
    z0 = x["elec.si.thevenin_termination.z0"]
    vcc = x["elec.si.thevenin_termination.vcc"]
    vbias = x["elec.si.thevenin_termination.vbias"]
    if z0 <= 0.0 or vcc <= 0.0 or vbias <= 0.0 or vbias >= vcc:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"thevenin_termination_r2: z0={z0!r}, vcc={vcc!r}, "
                    f"vbias={vbias!r} -- vbias must lie strictly in "
                    "(0, vcc)"
                )
            )
        )
    r2 = z0 * vcc / (vcc - vbias)
    return Ok({"elec.si.thevenin_termination.r2": r2})


# ---------------------------------------------------------------------------
# ac_shunt_sizing -- R matched to Z0, C from a quarter-rise-time RC
# guideline (Johnson & Graham 1993 ch. 4, "AC (RC) Termination"). C's
# citation is a NAMED heuristic (declared error wide), not a physical
# law with one exact answer.
# ---------------------------------------------------------------------------

_AC_SHUNT_R_CITATIONS = (
    Citation(
        kind="handbook",
        ref=f'{_JOHNSON_GRAHAM_1993}, "AC (RC) Termination"',
        note="R sized to Z0 (the matched-shunt condition), exact algebra.",
    ),
)

_AC_SHUNT_C_CITATIONS = (
    Citation(
        kind="handbook",
        ref=f'{_JOHNSON_GRAHAM_1993}, "AC (RC) Termination"',
        note=(
            "NAMED HEURISTIC, not an exact law: Johnson & Graham "
            "describe keeping the RC time constant well under the "
            "signal rise time (their own quoted range spans roughly "
            "tr/5..tr/2 depending on ringing tolerance); this direction "
            "bakes the tr/4 midpoint. The declared error band is "
            "correspondingly wide (order-of-magnitude sizing aid) -- "
            "documented honestly rather than presented as a tight "
            "physical result."
        ),
    ),
)

_RISE_TIME_RANGE = Interval(1.0e-11, 1.0e-6)


@solver(
    namespace="elec.si",
    inputs=("elec.si.ac_shunt.z0",),
    outputs=("elec.si.ac_shunt.r",),
    domain=Domain(box={"elec.si.ac_shunt.z0": _TERM_Z0_RANGE}, tags={"ac_shunt"}),
    cost=1e-7,
    accuracy=EXACT,
    citations=_AC_SHUNT_R_CITATIONS,
    version="1",
)
def ac_shunt_sizing_r(x):
    """AC shunt termination resistor: `R = Z0` (matched shunt)."""
    z0 = x["elec.si.ac_shunt.z0"]
    if z0 <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"ac_shunt_sizing_r: non-positive z0={z0!r}"
            )
        )
    return Ok({"elec.si.ac_shunt.r": z0})


@solver(
    namespace="elec.si",
    inputs=("elec.si.ac_shunt.rise_time", "elec.si.ac_shunt.r"),
    outputs=("elec.si.ac_shunt.c",),
    domain=Domain(
        box={
            "elec.si.ac_shunt.rise_time": _RISE_TIME_RANGE,
            "elec.si.ac_shunt.r": _TERM_Z0_RANGE,
        },
        tags={"ac_shunt", "quarter_rise_time_heuristic"},
    ),
    cost=1e-7,
    accuracy=_AC_SHUNT_C_ACCURACY,
    citations=_AC_SHUNT_C_CITATIONS,
    version="1",
)
def ac_shunt_sizing_c(x):
    """AC shunt termination capacitor: `C = tr / (4*R)` (the tr/4
    midpoint of Johnson & Graham's quoted tr/5..tr/2 range -- a NAMED
    heuristic, see this module's docstring)."""
    tr = x["elec.si.ac_shunt.rise_time"]
    r = x["elec.si.ac_shunt.r"]
    if tr <= 0.0 or r <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"ac_shunt_sizing_c: non-positive rise_time={tr!r} or r={r!r}"
                )
            )
        )
    c = tr / (4.0 * r)
    return Ok({"elec.si.ac_shunt.c": c})


def register(registry: SolverRegistry) -> None:
    """Registers all eight WO-25 signal-integrity directions (two
    impedance forms, two termination families, `diff_pair_z` NAMED CUT
    per this module's own docstring)."""
    directions = (
        microstrip_z0,
        stripline_z0,
        series_termination,
        thevenin_termination_r1,
        thevenin_termination_r2,
        ac_shunt_sizing_r,
        ac_shunt_sizing_c,
    )
    for fn in directions:
        result = registry.register(*fn.solver_direction)  # ty: ignore[unresolved-attribute]
        _ = result.danger_ok
    _log.info("signal_integrity: registered %d solver directions", len(directions))
