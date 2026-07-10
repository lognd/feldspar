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

from typani import Err, Ok

from feldspar.core import Domain, Interval
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

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


def register(registry: SolverRegistry) -> None:
    """Registers all four fatigue directions (WO-24 deliverable 4:
    baseline Se', Marin surface factor, Marin-composed Se, modified-
    Goodman factor of safety)."""
    result_a = registry.register(*fatigue_endurance_limit_baseline.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_a.danger_ok
    result_b = registry.register(*fatigue_marin_surface_factor.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_b.danger_ok
    result_c = registry.register(*fatigue_marin_endurance_limit.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_c.danger_ok
    result_d = registry.register(*fatigue_goodman_factor_of_safety.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_d.danger_ok
    _log.info("fatigue: registered %d solver directions", 4)
