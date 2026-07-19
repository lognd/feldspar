from __future__ import annotations

"""Binary phase-equilibria closed forms (T-0018 slice 4): the lever
rule over a two-phase tie line, and a regular-solution binary Gibbs
free-energy-of-mixing model (the honest CALPHAD-LITE tier this ticket
scopes -- full sublattice CALPHAD assessment, multi-component systems,
and non-regular excess terms are a named cut).

Eutectic/eutectoid points and tie-line compositions are RECORD INPUTS
(caller-supplied), never baked constants (the ticket's own "as record
inputs" line) -- this module never asserts a specific alloy system's
phase-diagram coordinates itself."""

import math

from typani import Err, Ok

from feldspar.core import Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["register"]

_LEVER_RULE = (
    "Gibbs, J. W. (1878 / republished), and standard phase-diagram "
    "treatment, e.g. Porter, D. A., Easterling, K. E., and Sherif, M. "
    "Y. (2009), Phase Transformations in Metals and Alloys, 3rd ed., "
    "CRC Press, ch. 1 -- the lever rule for a two-phase tie line."
)
_REGULAR_SOLUTION = (
    "Hildebrand, J. H. (1929), 'Solubility. XII. Regular Solutions', "
    "J. Am. Chem. Soc., 51(1), 66-80 -- the regular-solution model, "
    "dG_mix = R*T*(x*ln(x) + (1-x)*ln(1-x)) + Omega*x*(1-x); see also "
    "Porter, Easterling & Sherif, Phase Transformations in Metals and "
    "Alloys, 3rd ed., ch. 1 sec. 1.3 for the standard binary-alloy "
    "presentation of this form."
)

_GAS_CONSTANT_J_PER_MOL_K = 8.314462618


# ---------------------------------------------------------------------------
# Lever rule: f_alpha = (x_beta - x_overall) / (x_beta - x_alpha)
# ---------------------------------------------------------------------------

_LEVER_RULE_CITATIONS = (
    Citation(
        kind="handbook",
        ref=_LEVER_RULE,
        note=(
            "`tie_line_alpha_fraction`/`tie_line_beta_fraction` (the "
            "phase-boundary compositions at the working temperature) "
            "and `overall_fraction` are RECORD INPUTS -- the ticket's "
            "own 'eutectic/eutectoid points as record inputs' ruling -- "
            "this direction only evaluates the lever-rule arithmetic. "
            "Calibration is a hand-computed known-answer check "
            "(structural: the rule is definitional given a tie line, "
            "not a fitted empirical correlation, so no independent "
            "oracle point is applicable beyond exercising the "
            "arithmetic -- named as such, not a residual gap)."
        ),
    ),
)


# frob:doc docs/modules/materials.md#materials_phase_equilibria
@solver(
    namespace="materials.phase_equilibria",
    inputs=(
        "materials.phase_equilibria.lever.alpha_fraction",
        "materials.phase_equilibria.lever.beta_fraction",
        "materials.phase_equilibria.lever.overall_fraction",
    ),
    outputs=("materials.phase_equilibria.lever.phase_alpha_fraction",),
    domain=Domain(
        box={
            # Composition (mole or mass fraction of the solute
            # species) at the alpha-phase boundary of the tie line.
            "materials.phase_equilibria.lever.alpha_fraction": Interval(0.0, 1.0),
            # Composition at the beta-phase boundary.
            "materials.phase_equilibria.lever.beta_fraction": Interval(0.0, 1.0),
            # Overall (nominal) alloy composition -- must lie between
            # the two phase boundaries for a valid two-phase tie line.
            "materials.phase_equilibria.lever.overall_fraction": Interval(0.0, 1.0),
        },
        tags={"two_phase", "tie_line"},
    ),
    cost=1e-9,
    accuracy=EXACT,
    citations=_LEVER_RULE_CITATIONS,
    version="1",
)
def lever_rule_phase_fraction(x):
    """The lever rule: `f_alpha = (x_beta - x_overall) / (x_beta -
    x_alpha)`, the mass/mole fraction of the alpha phase on a two-phase
    tie line (`x_alpha`/`x_beta`/`x_overall` all record inputs -- see
    citation note). Refuses (as `OutOfDomain`) when `x_overall` does
    not lie between the two phase-boundary compositions (not a valid
    two-phase tie line) or when the boundaries coincide (degenerate
    tie line, division by zero)."""
    alpha_fraction = x["materials.phase_equilibria.lever.alpha_fraction"]
    beta_fraction = x["materials.phase_equilibria.lever.beta_fraction"]
    overall_fraction = x["materials.phase_equilibria.lever.overall_fraction"]
    lo = min(alpha_fraction, beta_fraction)
    hi = max(alpha_fraction, beta_fraction)
    if math.isclose(alpha_fraction, beta_fraction, abs_tol=1e-12):
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    "lever rule: degenerate tie line, alpha_fraction == "
                    f"beta_fraction == {alpha_fraction!r}"
                )
            )
        )
    if not (lo - 1e-9 <= overall_fraction <= hi + 1e-9):
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"lever rule: overall_fraction={overall_fraction!r} not "
                    f"between phase boundaries [{lo!r}, {hi!r}]"
                )
            )
        )
    phase_alpha_fraction = (beta_fraction - overall_fraction) / (
        beta_fraction - alpha_fraction
    )
    return Ok(
        {"materials.phase_equilibria.lever.phase_alpha_fraction": phase_alpha_fraction}
    )


# ---------------------------------------------------------------------------
# Regular solution: dG_mix = R*T*(x*ln(x)+(1-x)*ln(1-x)) + Omega*x*(1-x)
# ---------------------------------------------------------------------------

_REGULAR_SOLUTION_CITATIONS = (
    Citation(
        kind="paper",
        ref=_REGULAR_SOLUTION,
        note=(
            "`omega` (the regular-solution interaction parameter, "
            "J/mol) is CALLER-SUPPLIED -- per-alloy-system Omega values "
            "come from a CALPHAD assessment or experimental fit this "
            "package does not itself perform (the ticket's own "
            "'CALPHAD-lite' honesty scope; full sublattice CALPHAD "
            "assessment is a named cut). Calibration is a hand-"
            "computed check of the closed form (the ideal-mixing limit "
            "Omega=0 reduces to the exact ideal-solution entropy term, "
            "a structural identity, not a fitted empirical value)."
        ),
    ),
)


# frob:doc docs/modules/materials.md#materials_phase_equilibria
@solver(
    namespace="materials.phase_equilibria",
    inputs=(
        "materials.phase_equilibria.regular_solution.mole_fraction",
        "materials.phase_equilibria.regular_solution.temperature",
        "materials.phase_equilibria.regular_solution.omega",
    ),
    outputs=("materials.phase_equilibria.regular_solution.gibbs_mixing",),
    domain=Domain(
        box={
            # Mole fraction of component B, dimensionless (0,1)
            # exclusive -- the ln(x) terms diverge at the pure-
            # component limits.
            "materials.phase_equilibria.regular_solution.mole_fraction": Interval(
                1e-6, 1.0 - 1e-6
            ),
            "materials.phase_equilibria.regular_solution.temperature": Interval(
                1.0, 3500.0
            ),
            # Regular-solution interaction parameter, J/mol (typical
            # metallic-system range).
            "materials.phase_equilibria.regular_solution.omega": Interval(
                -5.0e4, 5.0e4
            ),
        },
        tags={"regular_solution", "calphad_lite"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_REGULAR_SOLUTION_CITATIONS,
    version="1",
)
def regular_solution_binary_free_energy(x):
    """The regular-solution binary Gibbs free-energy-of-mixing model:
    `dG_mix = R*T*(x*ln(x) + (1-x)*ln(1-x)) + Omega*x*(1-x)` (`Omega`
    caller-supplied -- see citation note)."""
    mole_fraction = x["materials.phase_equilibria.regular_solution.mole_fraction"]
    temperature = x["materials.phase_equilibria.regular_solution.temperature"]
    omega = x["materials.phase_equilibria.regular_solution.omega"]
    if temperature <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"regular solution: non-positive temperature={temperature!r}"
                )
            )
        )
    ideal_term = (
        _GAS_CONSTANT_J_PER_MOL_K
        * temperature
        * (
            mole_fraction * math.log(mole_fraction)
            + (1.0 - mole_fraction) * math.log(1.0 - mole_fraction)
        )
    )
    excess_term = omega * mole_fraction * (1.0 - mole_fraction)
    return Ok(
        {
            "materials.phase_equilibria.regular_solution.gibbs_mixing": (
                ideal_term + excess_term
            )
        }
    )


_PORT_DECLS = (
    PortDecl("materials.phase_equilibria.lever.alpha_fraction", "1"),
    PortDecl("materials.phase_equilibria.lever.beta_fraction", "1"),
    PortDecl("materials.phase_equilibria.lever.overall_fraction", "1"),
    PortDecl("materials.phase_equilibria.lever.phase_alpha_fraction", "1"),
    PortDecl("materials.phase_equilibria.regular_solution.mole_fraction", "1"),
    PortDecl("materials.phase_equilibria.regular_solution.temperature", "K"),
    PortDecl("materials.phase_equilibria.regular_solution.omega", "J/mol"),
    PortDecl("materials.phase_equilibria.regular_solution.gibbs_mixing", "J/mol"),
)


# frob:doc docs/modules/materials.md#materials_phase_equilibria
def register(registry: SolverRegistry) -> None:
    """Registers every `materials.phase_equilibria` direction (T-0018
    slice 4). Declares this family's port table first (WO111b
    convention)."""
    _ = registry.declare_ports(*_PORT_DECLS).danger_ok
    directions = [
        lever_rule_phase_fraction.solver_direction,  # ty: ignore[unresolved-attribute]
        regular_solution_binary_free_energy.solver_direction,  # ty: ignore[unresolved-attribute]
    ]
    for direction in directions:
        result = registry.register(*direction)
        _ = result.danger_ok
    _log.info(
        "materials.phase_equilibria: registered %d solver directions",
        len(directions),
    )
