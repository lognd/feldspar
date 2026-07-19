from __future__ import annotations

"""Transformation-kinetics closed forms (T-0018 slice 2): athermal
martensite fraction (Koistinen & Marburger 1959), a diffusional
transformation-onset time in the Kirkaldy/Li Avrami-Arrhenius family,
and the Grange & Kiefer (1941) linear-additive Ms-depression shift.

Licensing discipline (lithos D258/D266/D269): every direction here
evaluates a published CLOSED-FORM equation to floating-point precision
-- never a transcribed ASM handbook chart curve. Where a cited
equation's own per-element/per-system fitted constants (Kirkaldy's
regression coefficients, Grange-Kiefer's per-element depression
factors) would require transcribing a specific numeric table this
package cannot independently re-derive or verify byte-for-byte, those
constants are CALLER-SUPPLIED inputs -- the same "caller-resolved
constant" seam `mech.member_capacity`'s effective-length factor `K` and
`mech.fatigue`'s Marin `a`/`b` already use (WO-24 precedent) -- rather
than this module asserting an uncited numeric constant. Calibration
tests are hand-computed known-answer checks against each cited
equation's own closed form (the same convention `mech.fatigue`'s
Shigley-eq calibration uses); a residual honesty note is recorded in
each docstring where an independent second-source oracle point was not
locatable this dispatch (named residual, not a silent gap)."""

import math

from typani import Err, Ok

from feldspar.core import Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

_KOISTINEN_MARBURGER = (
    "Koistinen, D. P., and Marburger, R. E. (1959), 'A general equation "
    "prescribing the extent of the austenite-martensite transformation "
    "in pure iron-carbon alloys and plain carbon steels', Acta "
    "Metallurgica, 7(1), 59-60."
)
_KIRKALDY_LI = (
    "Kirkaldy, J. S., and Venugopalan, D. (1984), 'Prediction of "
    "Microstructure and Hardenability in Low Alloy Steels', in Phase "
    "Transformations in Ferrous Alloys, TMS-AIME; Li, M. V., et al. "
    "(1998), 'A computational model for the prediction of steel "
    "hardenability', Metall. Mater. Trans. B, 29(3), 661-672 -- the "
    "Kirkaldy/Li diffusional-kinetics family, whose isothermal onset "
    "times follow an Avrami-nucleation Arrhenius temperature "
    "dependence."
)
_GRANGE_KIEFER = (
    "Grange, R. A., and Kiefer, J. M. (1941), 'Transformation of "
    "Austenite on Continuous Cooling and its Relation to Transformation "
    "at Constant Temperature', Trans. ASM, 29, 85-116 -- the linear-"
    "additive martensite-start depression per wt pct alloying element."
)


# ---------------------------------------------------------------------------
# Koistinen-Marburger: f = 1 - exp(-alpha*(Ms - T)), T <= Ms
# ---------------------------------------------------------------------------

_KM_CITATIONS = (
    Citation(
        kind="paper",
        ref=_KOISTINEN_MARBURGER,
        note=(
            "alpha is CALLER-SUPPLIED (the original paper's own fitted "
            "value for plain-carbon/low-alloy steel is commonly quoted "
            "as ~0.011 per K, but this direction does not bake that "
            "constant in -- a caller citing a specific alpha for their "
            "own alloy supplies it directly). Calibration below is a "
            "hand-computed check of the closed form itself (same "
            "convention as mech.fatigue's Shigley-eq calibration); an "
            "independent second-source numeric oracle point beyond the "
            "originating paper was not located this dispatch (named "
            "residual)."
        ),
    ),
)


# frob:doc docs/modules/materials.md#materials_kinetics
@solver(
    namespace="materials.kinetics",
    inputs=(
        "materials.kinetics.km.ms_temperature",
        "materials.kinetics.km.quench_temperature",
        "materials.kinetics.km.alpha",
    ),
    outputs=("materials.kinetics.km.martensite_fraction",),
    domain=Domain(
        box={
            # Martensite-start temperature, K (plausible steel Ms range).
            "materials.kinetics.km.ms_temperature": Interval(150.0, 750.0),
            # Quench (hold) temperature, K.
            "materials.kinetics.km.quench_temperature": Interval(4.0, 750.0),
            # alpha, 1/K (K-M's own fitted value is order 0.01-0.05/K
            # for steels; wide enough box to cover published variants).
            "materials.kinetics.km.alpha": Interval(1.0e-4, 0.2),
        },
        tags={"martensite", "athermal"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_KM_CITATIONS,
    version="1",
)
def koistinen_marburger_martensite_fraction(x):
    """Koistinen & Marburger (1959): `f = 1 - exp(-alpha*(Ms - T))` for
    `T <= Ms` (athermal martensite fraction below the martensite-start
    temperature); `f = 0` for `T > Ms` (no transformation above Ms,
    the equation's own defined domain boundary, not an approximation
    of it)."""
    ms = x["materials.kinetics.km.ms_temperature"]
    t = x["materials.kinetics.km.quench_temperature"]
    alpha = x["materials.kinetics.km.alpha"]
    if alpha <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=f"Koistinen-Marburger: non-positive alpha={alpha!r}"
            )
        )
    if t > ms:
        fraction = 0.0
    else:
        fraction = 1.0 - math.exp(-alpha * (ms - t))
    return Ok({"materials.kinetics.km.martensite_fraction": fraction})


# ---------------------------------------------------------------------------
# Kirkaldy/Li-family diffusional TTT onset: Avrami-Arrhenius form
# ---------------------------------------------------------------------------

_KIRKALDY_CITATIONS = (
    Citation(
        kind="paper",
        ref=_KIRKALDY_LI,
        note=(
            "This direction evaluates the family's shared Avrami-"
            "nucleation Arrhenius temperature dependence, `t_onset = "
            "t0 * exp(activation_energy / (R * T))`; the pre-exponential "
            "`t0` and `activation_energy` are CALLER-SUPPLIED (Kirkaldy/"
            "Li's own multi-element regression coefficients that fold "
            "composition and ASTM grain size into t0 are a named cut -- "
            "transcribing their exact published regression constants "
            "from memory risked an uncited/misremembered number, so "
            "this direction takes the already-fitted t0/activation_"
            "energy as inputs, same 'caller-resolved constant' seam as "
            "mech.fatigue's Marin a/b). Calibration is a hand-computed "
            "Arrhenius check; a from-scratch independent oracle "
            "reproducing Kirkaldy/Li's own regression was not attempted "
            "this dispatch (named residual)."
        ),
    ),
)

_GAS_CONSTANT_J_PER_MOL_K = 8.314462618


# frob:doc docs/modules/materials.md#materials_kinetics
@solver(
    namespace="materials.kinetics",
    inputs=(
        "materials.kinetics.diffusional.t0",
        "materials.kinetics.diffusional.activation_energy",
        "materials.kinetics.diffusional.temperature",
    ),
    outputs=("materials.kinetics.diffusional.onset_time",),
    domain=Domain(
        box={
            # Pre-exponential onset time, s.
            "materials.kinetics.diffusional.t0": Interval(1e-6, 1e6),
            # Apparent activation energy, J/mol (typical diffusional
            # steel-transformation range, ~50-400 kJ/mol).
            "materials.kinetics.diffusional.activation_energy": Interval(1.0e4, 5.0e5),
            # Isothermal hold temperature, K.
            "materials.kinetics.diffusional.temperature": Interval(300.0, 1200.0),
        },
        tags={"diffusional", "ttt_onset"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_KIRKALDY_CITATIONS,
    version="1",
)
def kirkaldy_diffusional_onset_time(x):
    """`t_onset = t0 * exp(Q / (R*T))`: the Kirkaldy/Li-family
    diffusional-transformation isothermal onset time's shared Avrami-
    nucleation Arrhenius temperature dependence (the C-curve shape of
    a TTT diagram is this equation evaluated across a temperature
    sweep). `t0`/`activation_energy` (Q) are caller-supplied
    already-fitted constants (see citation note)."""
    t0 = x["materials.kinetics.diffusional.t0"]
    activation_energy = x["materials.kinetics.diffusional.activation_energy"]
    temperature = x["materials.kinetics.diffusional.temperature"]
    if t0 <= 0.0 or temperature <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"diffusional onset: non-positive t0={t0!r} or "
                    f"temperature={temperature!r}"
                )
            )
        )
    onset_time = t0 * math.exp(
        activation_energy / (_GAS_CONSTANT_J_PER_MOL_K * temperature)
    )
    return Ok({"materials.kinetics.diffusional.onset_time": onset_time})


# ---------------------------------------------------------------------------
# Grange-Kiefer: Ms(alloyed) = Ms(base) - sum(k_i * wt_pct_i)
# ---------------------------------------------------------------------------

_GRANGE_KIEFER_CITATIONS = (
    Citation(
        kind="paper",
        ref=_GRANGE_KIEFER,
        note=(
            "The base Ms and per-element depression coefficients k_i "
            "are CALLER-SUPPLIED (Grange & Kiefer's own published "
            "per-element table -- Mn/Cr/Ni/Mo/Si depression rates -- "
            "is a named cut for the same transcription-risk reason as "
            "the diffusional-onset direction above); this direction "
            "evaluates the LINEAR-ADDITIVE shift law itself. Calibration "
            "is a hand-computed check of the additive form; an "
            "independent second-source oracle point was not located "
            "this dispatch (named residual)."
        ),
    ),
)


# frob:doc docs/modules/materials.md#materials_kinetics
@solver(
    namespace="materials.kinetics",
    inputs=(
        "materials.kinetics.gk.ms_base",
        "materials.kinetics.gk.depression",
    ),
    outputs=("materials.kinetics.gk.ms_shifted",),
    domain=Domain(
        box={
            "materials.kinetics.gk.ms_base": Interval(150.0, 750.0),
            # Total alloying depression, K (sum of k_i * wt_pct_i,
            # composed by the caller before calling -- always
            # non-negative, alloying additions depress Ms).
            "materials.kinetics.gk.depression": Interval(0.0, 500.0),
        },
        tags={"martensite_start_shift"},
    ),
    cost=1e-9,
    accuracy=EXACT,
    citations=_GRANGE_KIEFER_CITATIONS,
    version="1",
)
def grange_kiefer_ms_shift(x):
    """Grange & Kiefer (1941): `Ms(alloyed) = Ms(base) - depression`,
    the linear-additive alloying depression of the martensite-start
    temperature (`depression = sum(k_i * wt_pct_i)`, composed by the
    caller from Grange & Kiefer's own per-element table -- see citation
    note)."""
    ms_base = x["materials.kinetics.gk.ms_base"]
    depression = x["materials.kinetics.gk.depression"]
    return Ok({"materials.kinetics.gk.ms_shifted": ms_base - depression})


_PORT_DECLS = (
    PortDecl("materials.kinetics.km.ms_temperature", "K"),
    PortDecl("materials.kinetics.km.quench_temperature", "K"),
    PortDecl("materials.kinetics.km.alpha", "1/K"),
    PortDecl("materials.kinetics.km.martensite_fraction", "1"),
    PortDecl("materials.kinetics.diffusional.t0", "s"),
    PortDecl("materials.kinetics.diffusional.activation_energy", "J/mol"),
    PortDecl("materials.kinetics.diffusional.temperature", "K"),
    PortDecl("materials.kinetics.diffusional.onset_time", "s"),
    PortDecl("materials.kinetics.gk.ms_base", "K"),
    PortDecl("materials.kinetics.gk.depression", "K"),
    PortDecl("materials.kinetics.gk.ms_shifted", "K"),
)


# frob:doc docs/modules/materials.md#materials_kinetics
def register(registry: SolverRegistry) -> None:
    """Registers every `materials.kinetics` direction (T-0018 slice
    2). Declares this family's port table first (WO111b convention)."""
    _ = registry.declare_ports(*_PORT_DECLS).danger_ok
    directions = [
        koistinen_marburger_martensite_fraction.solver_direction,  # ty: ignore[unresolved-attribute]
        kirkaldy_diffusional_onset_time.solver_direction,  # ty: ignore[unresolved-attribute]
        grange_kiefer_ms_shift.solver_direction,  # ty: ignore[unresolved-attribute]
    ]
    for direction in directions:
        result = registry.register(*direction)
        _ = result.danger_ok
    _log.info("materials.kinetics: registered %d solver directions", len(directions))
