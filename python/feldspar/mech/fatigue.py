from __future__ import annotations

"""Shaft/member fatigue tier -- stress-life mean-stress (WO-24
deliverable 4, docs/benchmarks-memo.md sec. 14): the Marin-modified
endurance limit chain and the modified-Goodman fatigue factor of
safety, both closed-form and directly calibrated against a fully
worked textbook example.

SCOPE (honest, narrow -- the WO-24 standing law, and the WO's own
"honesty over reach" flag on this specific deliverable):

- `fatigue_endurance_limit_baseline`: `Se' = 0.5*Sut` for
  `Sut <= 1400 MPa` (Shigley 11e ch. 6 eq. 6-8, the steel S'e-vs-Sut
  correlation, docs/benchmarks-memo.md sec. 14.1). STEEL ONLY -- the
  `Sut > 1400 MPa` (`Se' = 700 MPa` plateau) branch is a named cut
  (not calibrated this dispatch, no worked case exercises it).
- `fatigue_marin_surface_factor`: `ka = a*Sut^b` (Shigley 11e ch. 6
  Table 6-2, the surface-condition Marin factor). Only the numeric
  worked-example row (machined/cold-drawn, `a=4.51, b=-0.265`, `Sut`
  in MPa) is CALIBRATED here; `a`/`b` are CALLER-SUPPLIED ports (not
  a baked lookup table) precisely so this module never asserts an
  uncalibrated row of Table 6-2 -- a caller wanting the ground/hot-
  rolled/as-forged rows must supply their own `a`/`b` from the cited
  table, at their own citation risk, same "caller-resolved constant"
  seam `member_capacity.py`'s `K` (effective-length factor) uses.
- `fatigue_marin_endurance_limit`: `Se = ka*kb*kc*kd*ke*Se'` (Shigley
  11e ch. 6 eq. 6-18), composing five Marin factors. Only `ka`
  (surface) and `kc` (load type) are independently derived/calibrated
  in this module (`kc` values are CODE CONSTANTS: 1.0 bending, 0.85
  axial, 0.59 torsion, per Shigley 11e ch. 6 sec. 6-9 -- the loading
  factor is a fixed lookup, not a fitted formula, matching how
  `member_capacity.py` bakes AISC's phi_b/phi_c). `kb` (size), `kd`
  (temperature), `ke` (reliability) are CALLER-SUPPLIED numeric
  factors -- deriving them needs their own citation surfaces (size:
  Table 6-3's A_0.95-sigma geometry catalog; temperature: the quartic
  fit eq. 6-27; reliability: Table 6-5's z-score-per-percentile table)
  not attempted this dispatch (named cuts); a caller who has computed
  those factors from the cited tables elsewhere still gets the
  compose-and-multiply step here, cited and calibrated.
- `fatigue_goodman_factor_of_safety`: the modified-Goodman fatigue
  criterion (Shigley 11e ch. 6 eq. 6-46, the `r >= r_crit` "fatigue
  governs" branch only -- `Sa = r*Se*Sut/(r*Sut+Se)`,
  `Sm = Sa/r`, `nf = 1/(sigma_a/Se + sigma_m/Sut)`). The complementary
  `r < r_crit` STATIC-YIELDING branch (Shigley's own case 2, needs Sy
  and r_crit = (Sy-Se)*Sut/(Sy*(Sut-Se))) is a named cut -- a caller
  needing the yield-governs check should compose this module's `Se`
  output with `member_capacity.py`'s existing yield forms rather than
  this module re-deriving a static check it does not own. This
  direction also does NOT apply a fatigue stress-concentration factor
  Kf itself (Neuber/notch-sensitivity, Shigley ch. 6 sec. 6-10, its
  own citation surface, named cut) -- the caller pre-multiplies
  sigma_a/sigma_m by Kf before calling, matching the worked
  calibration example's own convention.

Every direction here is STEEL, HIGH-CYCLE-FATIGUE (N > 10^3, the
Goodman-line infinite-life region) ONLY, per the WO's own honesty
flag -- `Domain.tags` documents this precondition, never derives or
verifies it from an input (same convention `member_capacity.py`'s
"compact"/"braced" tags use)."""

import json
import math

from typani import Err, Ok

from feldspar.core import Domain, Interval, PortDecl, Rank
from feldspar.logging_setup import get_logger
from feldspar.solve import (
    EXACT,
    Citation,
    SolveOutput,
    SolverRegistry,
    make_direction,
    solver,
)
from feldspar.solve.digest import canonical_digest
from feldspar.solve.errors import SolveError
from feldspar.solve.payload import PayloadResolver, resolver_cache_identity

_log = get_logger(__name__)

__all__ = ["MINER_SPECTRUM_PORT", "register"]

#: The Miner-damage spectrum payload port (kind "spectrum", 09 sec. 4):
#: its content is `{"sigma_a": [...], "cycles": [...]}` -- parallel
#: lists, both Pa/count, one entry per declared load block (WO111b
#: deliverable 1, lithos WO-110-F6/F4). Same JSON-payload convention
#: `library/vibe.py`'s `SPECTRUM_PORT` uses (own home here, no shared
#: schema module -- the two spectra carry unrelated fields).
MINER_SPECTRUM_PORT = "mech.fatigue.miner.spectrum"

_SHIGLEY = "Shigley's Mechanical Engineering Design, 11th ed."

#: Shigley 11e ch. 6 sec. 6-9: load-type Marin factor, code constants
#: (a fixed lookup, not a fitted formula).
KC_BENDING = 1.0
KC_AXIAL = 0.85
KC_TORSION = 0.59

# ---------------------------------------------------------------------------
# eq. 6-8: Se' = 0.5*Sut (steel, Sut <= 1400 MPa branch only)
# ---------------------------------------------------------------------------

_BASELINE_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_SHIGLEY}, ch. 6 eq. 6-8 (Se' = 0.5*Sut for steel, "
            "Sut <= 1400 MPa; docs/benchmarks-memo.md sec. 14.1)"
        ),
        note=(
            "The Sut > 1400 MPa plateau branch (Se' = 700 MPa) is a "
            "named cut -- no worked case in the calibrated example "
            "exercises it (WO-24 deliverable 4, honesty over reach)."
        ),
    ),
)

_SUT_MAX_CALIBRATED_PA = 1.4e9


@solver(
    namespace="mech.fatigue",
    inputs=("mech.fatigue.baseline.sut",),
    outputs=("mech.fatigue.baseline.se_prime",),
    domain=Domain(
        box={
            # Ultimate tensile strength, Pa (structural/machine steel
            # range up to the eq. 6-8 branch boundary).
            "mech.fatigue.baseline.sut": Interval(2.0e8, _SUT_MAX_CALIBRATED_PA),
        },
        tags={"steel", "hcf"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_BASELINE_CITATIONS,
    version="1",
)
def fatigue_endurance_limit_baseline(x):
    """Shigley 11e eq. 6-8: `Se' = 0.5*Sut`, steel, `Sut <= 1400 MPa`
    only (the plateau branch above that is a named cut, not built
    here)."""
    sut = x["mech.fatigue.baseline.sut"]
    if sut <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"fatigue baseline: non-positive sut={sut!r}"
            )
        )
    return Ok({"mech.fatigue.baseline.se_prime": 0.5 * sut})


# ---------------------------------------------------------------------------
# Table 6-2: ka = a*Sut^b (surface-condition Marin factor)
# ---------------------------------------------------------------------------

_SURFACE_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_SHIGLEY}, ch. 6 Table 6-2 (surface-condition Marin "
            "factor, ka = a*Sut^b, Sut in MPa; docs/benchmarks-memo.md "
            "sec. 14.2)"
        ),
        note=(
            "`a`/`b` are CALLER-SUPPLIED (not a baked lookup table) -- "
            "only the machined/cold-drawn row (a=4.51, b=-0.265) is "
            "independently calibrated this dispatch; a caller wanting "
            "another Table 6-2 row supplies its own a/b at their own "
            "citation risk (WO-24 deliverable 4 scope)."
        ),
    ),
)


@solver(
    namespace="mech.fatigue",
    inputs=(
        "mech.fatigue.surface.sut_mpa",
        "mech.fatigue.surface.coeff_a",
        "mech.fatigue.surface.exponent_b",
    ),
    outputs=("mech.fatigue.surface.ka",),
    domain=Domain(
        box={
            # Sut in MPa -- Table 6-2's a/b constants are defined for
            # Sut expressed in MPa, not Pa (a documented unit gotcha,
            # not this module's invention).
            "mech.fatigue.surface.sut_mpa": Interval(200.0, 2000.0),
            # Table 6-2 coefficient a (MPa^(1-b)-ish units, dimension
            # folded into the fitted constant per the table's own
            # convention); wide enough to cover every published row.
            "mech.fatigue.surface.coeff_a": Interval(0.5, 300.0),
            "mech.fatigue.surface.exponent_b": Interval(-1.5, 0.0),
        },
        tags={"steel"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_SURFACE_CITATIONS,
    version="1",
)
def fatigue_marin_surface_factor(x):
    """Shigley 11e Table 6-2: `ka = a*Sut^b`, `Sut` in MPa (caller-
    supplied `a`/`b`, this direction only evaluates the power law)."""
    sut_mpa = x["mech.fatigue.surface.sut_mpa"]
    a = x["mech.fatigue.surface.coeff_a"]
    b = x["mech.fatigue.surface.exponent_b"]
    if sut_mpa <= 0.0 or a <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"Marin surface factor: non-positive sut_mpa={sut_mpa!r} "
                    f"or coeff_a={a!r}"
                )
            )
        )
    ka = a * (sut_mpa**b)
    return Ok({"mech.fatigue.surface.ka": ka})


# ---------------------------------------------------------------------------
# eq. 6-18: Se = ka*kb*kc*kd*ke*Se'
# ---------------------------------------------------------------------------

_MARIN_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_SHIGLEY}, ch. 6 eq. 6-18 (Se = ka*kb*kc*kd*ke*Se', the "
            "Marin-modified endurance limit; docs/benchmarks-memo.md "
            "sec. 14.3). Load-type kc per sec. 6-9: 1.0 bending, 0.85 "
            "axial, 0.59 torsion (code constants, KC_BENDING/KC_AXIAL/"
            "KC_TORSION module attributes)."
        ),
        note=(
            "kb (size), kd (temperature), ke (reliability) are "
            "CALLER-SUPPLIED numeric factors -- each needs its own "
            "citation surface (Table 6-3 geometry catalog, eq. 6-27 "
            "quartic fit, Table 6-5 z-score table respectively), not "
            "derived here (named cuts, WO-24 deliverable 4 scope)."
        ),
    ),
)


@solver(
    namespace="mech.fatigue",
    inputs=(
        "mech.fatigue.marin.se_prime",
        "mech.fatigue.marin.ka",
        "mech.fatigue.marin.kb",
        "mech.fatigue.marin.kc",
        "mech.fatigue.marin.kd",
        "mech.fatigue.marin.ke",
    ),
    outputs=("mech.fatigue.marin.se",),
    domain=Domain(
        box={
            "mech.fatigue.marin.se_prime": Interval(1.0e7, 7.0e8),
            "mech.fatigue.marin.ka": Interval(0.01, 1.5),
            "mech.fatigue.marin.kb": Interval(0.01, 1.5),
            "mech.fatigue.marin.kc": Interval(0.1, 1.0),
            "mech.fatigue.marin.kd": Interval(0.01, 1.5),
            "mech.fatigue.marin.ke": Interval(0.01, 1.5),
        },
        tags={"steel", "hcf"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_MARIN_CITATIONS,
    version="1",
)
def fatigue_marin_endurance_limit(x):
    """Shigley 11e eq. 6-18: `Se = ka*kb*kc*kd*ke*Se'`, plain
    composition of five already-derived Marin factors."""
    se_prime = x["mech.fatigue.marin.se_prime"]
    ka = x["mech.fatigue.marin.ka"]
    kb = x["mech.fatigue.marin.kb"]
    kc = x["mech.fatigue.marin.kc"]
    kd = x["mech.fatigue.marin.kd"]
    ke = x["mech.fatigue.marin.ke"]
    if se_prime <= 0.0 or ka <= 0.0 or kb <= 0.0 or kc <= 0.0 or kd <= 0.0 or ke <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    "Marin endurance limit: non-positive se_prime="
                    f"{se_prime!r}, ka={ka!r}, kb={kb!r}, kc={kc!r}, "
                    f"kd={kd!r}, or ke={ke!r}"
                )
            )
        )
    se = ka * kb * kc * kd * ke * se_prime
    return Ok({"mech.fatigue.marin.se": se})


# ---------------------------------------------------------------------------
# eq. 6-46 (r >= r_crit branch): modified-Goodman fatigue factor of safety
# ---------------------------------------------------------------------------

_GOODMAN_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_SHIGLEY}, ch. 6 eq. 6-46 (modified-Goodman fatigue "
            'line, the r >= r_crit "fatigue governs" branch: '
            "Sa = r*Se*Sut/(r*Sut+Se), Sm = Sa/r, "
            "nf = 1/(sigma_a/Se + sigma_m/Sut); docs/benchmarks-memo.md "
            "sec. 14.4, Example 6-12)"
        ),
        note=(
            "The complementary r < r_crit STATIC-YIELDING branch (needs "
            "Sy and r_crit) is a named cut -- compose this direction's "
            "Se with member_capacity.py's yield forms instead. Kf "
            "(fatigue stress concentration) is NOT applied here -- "
            "CALLER pre-multiplies sigma_a/sigma_m by Kf before calling "
            "(Neuber/notch-sensitivity is its own citation surface, "
            "named cut, WO-24 deliverable 4 scope)."
        ),
    ),
)


@solver(
    namespace="mech.fatigue",
    inputs=(
        "mech.fatigue.goodman.se",
        "mech.fatigue.goodman.sut",
        "mech.fatigue.goodman.sigma_a",
        "mech.fatigue.goodman.sigma_m",
    ),
    outputs=(
        "mech.fatigue.goodman.sa_limit",
        "mech.fatigue.goodman.sm_limit",
        "mech.fatigue.goodman.factor_of_safety",
    ),
    domain=Domain(
        box={
            "mech.fatigue.goodman.se": Interval(1.0e7, 7.0e8),
            "mech.fatigue.goodman.sut": Interval(2.0e8, 2.0e9),
            # Kf-already-applied alternating/mean stress components, Pa.
            "mech.fatigue.goodman.sigma_a": Interval(1.0e5, 1.0e9),
            "mech.fatigue.goodman.sigma_m": Interval(1.0e5, 1.0e9),
        },
        tags={"steel", "hcf", "fatigue_governs"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_GOODMAN_CITATIONS,
    version="1",
)
def fatigue_goodman_factor_of_safety(x):
    """Shigley 11e eq. 6-46 (fatigue-governs branch): returns
    `(Sa_limit, Sm_limit, factor_of_safety)` for a caller-supplied
    (already Kf-multiplied) alternating/mean stress pair. `sigma_m<=0`
    (pure alternating) degenerates the load-line ratio `r` to
    infinity -- handled as the pure-alternating limit,
    `nf = Se/sigma_a`, `Sa_limit = Se`, `Sm_limit = 0.0`, rather than
    a spurious `OutOfDomain` (a real, physical loading case, not a
    degenerate input)."""
    se = x["mech.fatigue.goodman.se"]
    sut = x["mech.fatigue.goodman.sut"]
    sigma_a = x["mech.fatigue.goodman.sigma_a"]
    sigma_m = x["mech.fatigue.goodman.sigma_m"]
    if se <= 0.0 or sut <= 0.0 or sigma_a <= 0.0 or sigma_m < 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"Goodman: non-positive se={se!r}, sut={sut!r}, "
                    f"sigma_a={sigma_a!r}, or negative sigma_m={sigma_m!r}"
                )
            )
        )
    if sigma_m == 0.0:
        return Ok(
            {
                "mech.fatigue.goodman.sa_limit": se,
                "mech.fatigue.goodman.sm_limit": 0.0,
                "mech.fatigue.goodman.factor_of_safety": se / sigma_a,
            }
        )
    r = sigma_a / sigma_m
    sa_limit = r * se * sut / (r * sut + se)
    sm_limit = sa_limit / r
    nf = 1.0 / (sigma_a / se + sigma_m / sut)
    return Ok(
        {
            "mech.fatigue.goodman.sa_limit": sa_limit,
            "mech.fatigue.goodman.sm_limit": sm_limit,
            "mech.fatigue.goodman.factor_of_safety": nf,
        }
    )


# ---------------------------------------------------------------------------
# Table 6-7 / eq. 6-48: Gerber-parabola fatigue factor of safety
# ---------------------------------------------------------------------------

_GERBER_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_SHIGLEY}, ch. 6 Table 6-7 / eq. 6-48 (the Gerber "
            "parabolic mean-stress fatigue criterion factor of safety: "
            "nf = 0.5*(Sut/sigma_m)^2*(sigma_a/Se)*"
            "(-1 + sqrt(1 + (2*sigma_m*Se/(Sut*sigma_a))^2)); "
            "docs/benchmarks-memo.md sec. 18)"
        ),
        note=(
            "Same scope caveats as the modified-Goodman direction: STEEL, "
            "HCF, Kf pre-applied by the caller, fatigue-governs region "
            "only. Gerber is the LESS conservative parabolic fit (nf_Gerber "
            ">= nf_Goodman for the same stresses -- the calibration test "
            "asserts that published relationship as an independent check). "
            "sigma_m<=0 (pure alternating) degenerates to nf = Se/sigma_a, "
            "identical to the Goodman limit (both criteria share the "
            "sigma_m=0 endpoint)."
        ),
    ),
)


@solver(
    namespace="mech.fatigue",
    inputs=(
        "mech.fatigue.gerber.se",
        "mech.fatigue.gerber.sut",
        "mech.fatigue.gerber.sigma_a",
        "mech.fatigue.gerber.sigma_m",
    ),
    outputs=("mech.fatigue.gerber.factor_of_safety",),
    domain=Domain(
        box={
            "mech.fatigue.gerber.se": Interval(1.0e7, 7.0e8),
            "mech.fatigue.gerber.sut": Interval(2.0e8, 2.0e9),
            "mech.fatigue.gerber.sigma_a": Interval(1.0e5, 1.0e9),
            "mech.fatigue.gerber.sigma_m": Interval(1.0e5, 1.0e9),
        },
        tags={"steel", "hcf", "fatigue_governs"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_GERBER_CITATIONS,
    version="1",
)
def fatigue_gerber_factor_of_safety(x):
    """Shigley 11e Table 6-7 / eq. 6-48: the Gerber-parabola fatigue
    factor of safety for a caller-supplied (already Kf-multiplied)
    alternating/mean stress pair. `sigma_m<=0` degenerates to the
    pure-alternating limit `nf = Se/sigma_a` (shared endpoint with the
    Goodman line)."""
    se = x["mech.fatigue.gerber.se"]
    sut = x["mech.fatigue.gerber.sut"]
    sigma_a = x["mech.fatigue.gerber.sigma_a"]
    sigma_m = x["mech.fatigue.gerber.sigma_m"]
    if se <= 0.0 or sut <= 0.0 or sigma_a <= 0.0 or sigma_m < 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"Gerber: non-positive se={se!r}, sut={sut!r}, "
                    f"sigma_a={sigma_a!r}, or negative sigma_m={sigma_m!r}"
                )
            )
        )
    if sigma_m == 0.0:
        return Ok({"mech.fatigue.gerber.factor_of_safety": se / sigma_a})
    nf = (
        0.5
        * (sut / sigma_m) ** 2
        * (sigma_a / se)
        * (-1.0 + math.sqrt(1.0 + (2.0 * sigma_m * se / (sut * sigma_a)) ** 2))
    )
    return Ok({"mech.fatigue.gerber.factor_of_safety": nf})


# ---------------------------------------------------------------------------
# eq. 6-13/6-14: log-log S-N knee-line cycles-to-failure (Basquin form)
# ---------------------------------------------------------------------------

_SN_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_SHIGLEY}, ch. 6 eqs. 6-13/6-14 (the log-log S-N knee "
            "line through (10^3 cycles, f*Sut) and (10^6 cycles, Se): "
            "log(Sf) = b*log(N) + log(a), a = (f*Sut)^2/Se, "
            "b = -(1/3)*log10(f*Sut/Se); docs/benchmarks-memo.md sec. "
            "20.1)"
        ),
        note=(
            "ANALYTIC SELF-CHECK (calibration-first law sec. 3.1, "
            "second path): no independently citable published worked-"
            "example NUMBER is used here (fabrication risk on a "
            "transcribed page/example number this dispatch could not "
            "verify) -- instead the closed-form algebra is checked "
            "against its OWN defining boundary conditions: substituting "
            "sigma_a = f*Sut must return N = 1e3 exactly, and sigma_a = "
            "Se must return N = 1e6 exactly, for ANY valid (Sut, Se, f) "
            "-- an identity of the two-point log-log line's own "
            "construction, verified symbolically and numerically in "
            "the calibration test (docs/benchmarks-memo.md sec. 20.1 "
            "carries the derivation and one concrete numeric instance). "
            "`f` (the Fig. 6-18-family fraction of Sut at N=10^3) is "
            "CALLER-SUPPLIED, same caller-resolved-constant seam `a`/`b` "
            "in `fatigue_marin_surface_factor` uses -- this module never "
            "bakes Fig. 6-18's own curve."
        ),
    ),
)

# Valid cycle range for the knee-line HCF region (Shigley's own S-N
# diagram domain -- below 10^3 is low-cycle fatigue territory this line
# does not model, above 10^6 is the flat Se-governed infinite-life
# region, not a knee-line extrapolation): named cut, honest OutOfDomain
# outside it, matching the WO-24 fatigue module's steel/HCF-only scope.
_SN_N_MIN = 1.0e3
_SN_N_MAX = 1.0e6
# Floating-point slack at the two knee-line endpoints themselves (the
# closed form's own boundary conditions land at EXACTLY 1e3/1e6
# algebraically, but `log10`/power-law evaluation accumulates a few
# ULP of float error there -- this is a numeric-noise allowance, not a
# physics relaxation of the honest [1e3, 1e6] range).
_SN_N_TOL = 1.0e-6


def _sn_knee_params(sut: float, se: float, f: float):
    """Shigley 11e eqs. 6-13/6-14: `(a, b)` for the log-log S-N line
    through `(1e3, f*Sut)` and `(1e6, Se)`. Returns `None` for a
    degenerate/non-physical input (non-positive `sut`/`se`/`f`, or the
    knee `f*Sut` at or below `Se` -- the line would have non-negative
    slope, not a real S-N knee)."""
    if sut <= 0.0 or se <= 0.0 or f <= 0.0:
        return None
    knee = f * sut
    if knee <= se:
        return None
    a = (knee * knee) / se
    b = -(1.0 / 3.0) * math.log10(knee / se)
    return a, b


def _sn_cycles_to_failure(sigma_a: float, a: float, b: float) -> float:
    """`N = (sigma_a/a)^(1/b)` -- the S-N line solved for cycles given
    a fully-reversed alternating stress amplitude (Kf pre-applied by
    the caller, same convention `fatigue_goodman_factor_of_safety`/
    `fatigue_gerber_factor_of_safety` use)."""
    return (sigma_a / a) ** (1.0 / b)


@solver(
    namespace="mech.fatigue",
    inputs=(
        "mech.fatigue.sn.sigma_a",
        "mech.fatigue.sn.sut",
        "mech.fatigue.sn.se",
        "mech.fatigue.sn.f",
    ),
    outputs=("mech.fatigue.sn.cycles_to_failure",),
    domain=Domain(
        box={
            "mech.fatigue.sn.sigma_a": Interval(1.0e5, 1.5e9),
            "mech.fatigue.sn.sut": Interval(2.0e8, 2.0e9),
            "mech.fatigue.sn.se": Interval(1.0e7, 7.0e8),
            # Fraction of Sut at the 10^3-cycle knee (Fig. 6-18 family,
            # caller-resolved -- typically ~0.75-0.9 for steel).
            "mech.fatigue.sn.f": Interval(0.5, 0.95),
        },
        tags={"steel", "hcf"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_SN_CITATIONS,
    version="1",
)
def fatigue_sn_cycles_to_failure(x):
    """Shigley 11e eqs. 6-13/6-14: cycles-to-failure `N` for a fully-
    reversed alternating stress `sigma_a` off the log-log S-N knee
    line. `OutOfDomain` outside the `[1e3, 1e6]` knee-line region (the
    line's own honest validity range -- named cut, no low-cycle or
    Se-plateau extrapolation)."""
    sigma_a = x["mech.fatigue.sn.sigma_a"]
    sut = x["mech.fatigue.sn.sut"]
    se = x["mech.fatigue.sn.se"]
    f = x["mech.fatigue.sn.f"]
    params = _sn_knee_params(sut, se, f)
    if params is None or sigma_a <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    "S-N cycles-to-failure: non-positive/degenerate "
                    f"sigma_a={sigma_a!r}, sut={sut!r}, se={se!r}, "
                    f"f={f!r} (need f*sut > se)"
                )
            )
        )
    a, b = params
    n = _sn_cycles_to_failure(sigma_a, a, b)
    if not (_SN_N_MIN * (1.0 - _SN_N_TOL) <= n <= _SN_N_MAX * (1.0 + _SN_N_TOL)):
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"S-N cycles-to-failure: N={n!r} outside the knee-"
                    f"line's honest [{_SN_N_MIN:g}, {_SN_N_MAX:g}] range "
                    f"for sigma_a={sigma_a!r} (low-cycle or Se-plateau "
                    "region, not this direction's scope)"
                )
            )
        )
    return Ok({"mech.fatigue.sn.cycles_to_failure": n})


# ---------------------------------------------------------------------------
# eq. 6-58: Miner's rule cumulative damage over a declared load-block
# spectrum payload
# ---------------------------------------------------------------------------

_MINER_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            f"{_SHIGLEY}, ch. 6 sec. 6-16 eq. 6-58 (Miner's rule, the "
            "linear damage hypothesis: D = sum(n_i/N_i), failure at "
            "D >= 1); docs/benchmarks-memo.md sec. 20.2"
        ),
        note=(
            "ANALYTIC SELF-CHECK (calibration-first law sec. 3.1, "
            "second path, same reasoning as `fatigue_sn_cycles_to_"
            "failure`): the linear sum's own defining boundary "
            "condition -- a single block whose declared cycle count "
            "equals its own S-N life (n = N_f) must return D = 1.0 "
            "exactly -- is checked directly (docs/benchmarks-memo.md "
            "sec. 20.2). Each block's N_i comes from THIS module's own "
            "already-derived S-N line (`_sn_knee_params`/"
            "`_sn_cycles_to_failure`, NO DUPLICATION); a block whose "
            "sigma_a is at or below Se is treated as infinite life "
            "(contributes zero damage), the standard Miner's-rule "
            "convention for stresses below the endurance limit -- "
            "Shigley sec. 6-16's own stated convention, not this "
            "module's invention."
        ),
    ),
)


def _make_miner_damage_direction(resolver: PayloadResolver):
    """`mech.fatigue.miner_damage`: resolves the declared load-block
    spectrum payload (`{"sigma_a": [...], "cycles": [...]}`, parallel
    Pa/count lists) and accumulates Miner's-rule damage across blocks
    using this module's own S-N line for each block's life."""

    def miner_fn(x):
        spectrum_result = resolver.resolve(x[MINER_SPECTRUM_PORT])
        if spectrum_result.is_err:
            _log.warning(
                "miner_damage: spectrum payload unresolvable: %r",
                spectrum_result.err,
            )
            return spectrum_result
        spectrum = json.loads(spectrum_result.danger_ok)
        sigma_a_blocks = spectrum["sigma_a"]
        cycles_blocks = spectrum["cycles"]
        if len(sigma_a_blocks) != len(cycles_blocks) or not sigma_a_blocks:
            return Err(
                SolveError.OutOfDomain(
                    violation=(
                        "miner_damage: spectrum blocks mismatched length "
                        f"({len(sigma_a_blocks)} sigma_a vs "
                        f"{len(cycles_blocks)} cycles) or empty"
                    )
                )
            )
        sut = x["mech.fatigue.miner.sut"]
        se = x["mech.fatigue.miner.se"]
        f = x["mech.fatigue.miner.f"]
        params = _sn_knee_params(sut, se, f)
        if params is None:
            return Err(
                SolveError.OutOfDomain(
                    violation=(
                        "miner_damage: degenerate S-N params for "
                        f"sut={sut!r}, se={se!r}, f={f!r}"
                    )
                )
            )
        a, b = params
        damage = 0.0
        for sigma_a, n_applied in zip(sigma_a_blocks, cycles_blocks, strict=True):
            if sigma_a < 0.0 or n_applied < 0.0:
                return Err(
                    SolveError.OutOfDomain(
                        violation=(
                            "miner_damage: negative block sigma_a="
                            f"{sigma_a!r} or cycles={n_applied!r}"
                        )
                    )
                )
            if sigma_a <= se:
                # At or below the endurance limit: infinite life,
                # Miner's-rule convention (Shigley sec. 6-16) -- zero
                # damage contribution, not an S-N evaluation (which
                # would divide by an undefined/negative-slope region).
                continue
            n_life = _sn_cycles_to_failure(sigma_a, a, b)
            damage += n_applied / n_life
        _log.info(
            "miner_damage: accumulated D=%s over %d block(s)",
            damage,
            len(sigma_a_blocks),
        )
        return Ok(SolveOutput(values={"mech.fatigue.miner.damage": damage}))

    info, fn = make_direction(
        solver_id="mech.fatigue.miner_damage",
        namespace="mech.fatigue",
        inputs=(
            "mech.fatigue.miner.sut",
            "mech.fatigue.miner.se",
            "mech.fatigue.miner.f",
            MINER_SPECTRUM_PORT,
        ),
        outputs=("mech.fatigue.miner.damage",),
        domain=Domain(
            box={
                "mech.fatigue.miner.sut": Interval(2.0e8, 2.0e9),
                "mech.fatigue.miner.se": Interval(1.0e7, 7.0e8),
                "mech.fatigue.miner.f": Interval(0.5, 0.95),
            },
            tags={"steel", "hcf"},
        ),
        cost=1e-6,
        accuracy=EXACT,
        citations=_MINER_CITATIONS,
        version="1",
        tier="closed_form",
        # Bug fix (cycle-35 WO-118 integration): fold the resolver's own
        # kind into the settings digest so a no-resolver honest-Err run
        # and a working-resolver Ok run never collide on the same
        # SolveCache key (see `resolver_cache_identity`'s docstring).
        settings=canonical_digest({"resolver": resolver_cache_identity(resolver)}),
        fn=miner_fn,
    )
    return info, fn


def register(registry: SolverRegistry, resolver: PayloadResolver) -> None:
    """Registers all seven fatigue directions (WO-24 deliverable 4:
    baseline Se', Marin surface factor, Marin-composed Se, modified-
    Goodman factor of safety; WO-111: Gerber-parabola factor of
    safety; WO111b/lithos WO-110-F6/F4: S-N cycles-to-failure and
    Miner's-rule cumulative damage over a declared load-block
    spectrum). The Miner direction is payload-consuming (F12
    accumulated-table rule: this module now declares its own spectrum
    port, so it must run BEFORE any later `register()` call in the
    same catalog that would otherwise see `MINER_SPECTRUM_PORT`
    undeclared -- no other module names this port, so ordering
    relative to `fea/payload_steps.py`/`library/vibe.py` is otherwise
    unconstrained, same disjoint-namespace reasoning those modules'
    own docstrings use)."""
    ports_result = registry.declare_ports(
        # F12 accumulated-table rule: declaring ANY port here arms the
        # registry's port-table guard for every direction registered
        # into the SAME registry (including this module's pre-existing
        # baseline/Marin/Goodman/Gerber directions, previously
        # declaration-free) -- so this call now names every port this
        # module's directions reference, not just the new ones.
        PortDecl("mech.fatigue.baseline.sut", "Pa"),
        PortDecl("mech.fatigue.baseline.se_prime", "Pa"),
        PortDecl("mech.fatigue.surface.sut_mpa", "MPa"),
        PortDecl("mech.fatigue.surface.coeff_a", "1"),
        PortDecl("mech.fatigue.surface.exponent_b", "1"),
        PortDecl("mech.fatigue.surface.ka", "1"),
        PortDecl("mech.fatigue.marin.se_prime", "Pa"),
        PortDecl("mech.fatigue.marin.ka", "1"),
        PortDecl("mech.fatigue.marin.kb", "1"),
        PortDecl("mech.fatigue.marin.kc", "1"),
        PortDecl("mech.fatigue.marin.kd", "1"),
        PortDecl("mech.fatigue.marin.ke", "1"),
        PortDecl("mech.fatigue.marin.se", "Pa"),
        PortDecl("mech.fatigue.goodman.se", "Pa"),
        PortDecl("mech.fatigue.goodman.sut", "Pa"),
        PortDecl("mech.fatigue.goodman.sigma_a", "Pa"),
        PortDecl("mech.fatigue.goodman.sigma_m", "Pa"),
        PortDecl("mech.fatigue.goodman.sa_limit", "Pa"),
        PortDecl("mech.fatigue.goodman.sm_limit", "Pa"),
        PortDecl("mech.fatigue.goodman.factor_of_safety", "1"),
        PortDecl("mech.fatigue.gerber.se", "Pa"),
        PortDecl("mech.fatigue.gerber.sut", "Pa"),
        PortDecl("mech.fatigue.gerber.sigma_a", "Pa"),
        PortDecl("mech.fatigue.gerber.sigma_m", "Pa"),
        PortDecl("mech.fatigue.gerber.factor_of_safety", "1"),
        PortDecl("mech.fatigue.sn.sigma_a", "Pa"),
        PortDecl("mech.fatigue.sn.sut", "Pa"),
        PortDecl("mech.fatigue.sn.se", "Pa"),
        PortDecl("mech.fatigue.sn.f", "1"),
        PortDecl("mech.fatigue.sn.cycles_to_failure", "1"),
        PortDecl("mech.fatigue.miner.sut", "Pa"),
        PortDecl("mech.fatigue.miner.se", "Pa"),
        PortDecl("mech.fatigue.miner.f", "1"),
        PortDecl("mech.fatigue.miner.damage", "1"),
        PortDecl(MINER_SPECTRUM_PORT, "", Rank.payload("spectrum")),
    )
    _ = ports_result.danger_ok
    result_a = registry.register(*fatigue_endurance_limit_baseline.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_a.danger_ok
    result_b = registry.register(*fatigue_marin_surface_factor.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_b.danger_ok
    result_c = registry.register(*fatigue_marin_endurance_limit.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_c.danger_ok
    result_d = registry.register(*fatigue_goodman_factor_of_safety.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_d.danger_ok
    result_e = registry.register(*fatigue_gerber_factor_of_safety.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_e.danger_ok
    result_f = registry.register(*fatigue_sn_cycles_to_failure.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_f.danger_ok
    info, fn = _make_miner_damage_direction(resolver)
    result_g = registry.register(info, fn)
    _ = result_g.danger_ok
    _log.info("fatigue: registered %d solver directions", 7)
