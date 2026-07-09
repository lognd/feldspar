from __future__ import annotations

"""Compressible fluid-mechanics closed-form solver directions (D141).

Pure marshalling over `feldspar._feldspar.fluids_*` (the single Rust
home of each formula, `crates/feldspar-library/src/fluids/compressible.rs`):
no math is reimplemented in Python here (NO DUPLICATION). Every
direction declares `accuracy=EXACT` (A-7): each solver evaluates its
OWN declared closed-form model exactly, even where that model (the
Fanno function) is itself a textbook approximation of physical reality
-- the model is the contract, and these compute it to floating-point
precision.

Registered under the SAME `fluids` namespace/claim ports the
incompressible entries use (dp/friction_factor family), distinguished
by `Domain.tags` ("compressible" vs "incompressible") so the planner's
regime screening routes a beyond-regime gas case here (proven both
ways in tests/unit/test_library_fluids.py).

Scope note (WO-20 close-out): this module covers isentropic relations,
normal shocks, and the Fanno function (per-segment building block for
gas-subnet Fanno-line network delivery). Oblique shocks/CD-nozzle
operation and full multi-branch Fanno NETWORK solving over resolved
`flownet` payload bytes are EXPLICITLY CUT and flagged in the WO-20
close-out report -- not silently dropped."""

from typani import Ok

from feldspar import _feldspar
from feldspar.core import Domain, Interval
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, solver

_log = get_logger(__name__)

__all__ = ["register"]

_ANDERSON = "Anderson, Modern Compressible Flow, 3rd ed."

_COMPRESSIBLE_CITATIONS = (Citation(kind="handbook", ref=_ANDERSON, note="ch. 3"),)


@solver(
    namespace="fluids",
    inputs=("fluids.compressible.mach", "fluids.gas.gamma"),
    outputs=("fluids.compressible.stagnation_temp_ratio",),
    domain=Domain(
        box={
            "fluids.compressible.mach": Interval(0.0, 5.0),
            "fluids.gas.gamma": Interval(1.1, 1.8),
        },
        tags={"compressible"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_COMPRESSIBLE_CITATIONS,
    version="1",
)
def isentropic_stagnation_temp_ratio(x):
    mach = x["fluids.compressible.mach"]
    gamma = x["fluids.gas.gamma"]
    return Ok(
        {
            "fluids.compressible.stagnation_temp_ratio": (
                _feldspar.fluids_isentropic_stagnation_temp_ratio(mach, gamma)
            )
        }
    )


@solver(
    namespace="fluids",
    inputs=("fluids.compressible.mach", "fluids.gas.gamma"),
    outputs=("fluids.compressible.stagnation_pressure_ratio",),
    domain=Domain(
        box={
            "fluids.compressible.mach": Interval(0.0, 5.0),
            "fluids.gas.gamma": Interval(1.1, 1.8),
        },
        tags={"compressible"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_COMPRESSIBLE_CITATIONS,
    version="1",
)
def isentropic_stagnation_pressure_ratio(x):
    mach = x["fluids.compressible.mach"]
    gamma = x["fluids.gas.gamma"]
    return Ok(
        {
            "fluids.compressible.stagnation_pressure_ratio": (
                _feldspar.fluids_isentropic_stagnation_pressure_ratio(mach, gamma)
            )
        }
    )


@solver(
    namespace="fluids",
    inputs=("fluids.compressible.mach_upstream", "fluids.gas.gamma"),
    outputs=("fluids.compressible.mach_downstream",),
    domain=Domain(
        box={
            "fluids.compressible.mach_upstream": Interval(1.0, 5.0),
            "fluids.gas.gamma": Interval(1.1, 1.8),
        },
        tags={"compressible", "normal_shock"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_COMPRESSIBLE_CITATIONS,
    version="1",
)
def normal_shock_mach2(x):
    mach1 = x["fluids.compressible.mach_upstream"]
    gamma = x["fluids.gas.gamma"]
    return Ok(
        {
            "fluids.compressible.mach_downstream": _feldspar.fluids_normal_shock_mach2(
                mach1, gamma
            )
        }
    )


@solver(
    namespace="fluids",
    inputs=("fluids.compressible.mach_upstream", "fluids.gas.gamma"),
    outputs=("fluids.compressible.shock_pressure_ratio",),
    domain=Domain(
        box={
            "fluids.compressible.mach_upstream": Interval(1.0, 5.0),
            "fluids.gas.gamma": Interval(1.1, 1.8),
        },
        tags={"compressible", "normal_shock"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_COMPRESSIBLE_CITATIONS,
    version="1",
)
def normal_shock_pressure_ratio(x):
    mach1 = x["fluids.compressible.mach_upstream"]
    gamma = x["fluids.gas.gamma"]
    return Ok(
        {
            "fluids.compressible.shock_pressure_ratio": (
                _feldspar.fluids_normal_shock_pressure_ratio(mach1, gamma)
            )
        }
    )


_FANNO_CITATIONS = (
    Citation(kind="handbook", ref=_ANDERSON, note="ch. 3, Fanno flow"),
    Citation(
        kind="handbook",
        ref=(
            "Shapiro, The Dynamics and Thermodynamics of Compressible "
            "Fluid Flow, vol. 1, ch. 6"
        ),
    ),
)


@solver(
    namespace="fluids",
    inputs=("fluids.compressible.mach", "fluids.gas.gamma"),
    outputs=("fluids.compressible.fanno_function",),
    domain=Domain(
        box={
            "fluids.compressible.mach": Interval(1e-3, 5.0),
            "fluids.gas.gamma": Interval(1.1, 1.8),
        },
        tags={"compressible", "fanno"},
    ),
    cost=1e-7,
    accuracy=EXACT,
    citations=_FANNO_CITATIONS,
    version="1",
)
def fanno_function(x):
    mach = x["fluids.compressible.mach"]
    gamma = x["fluids.gas.gamma"]
    return Ok(
        {
            "fluids.compressible.fanno_function": _feldspar.fluids_fanno_function(
                mach, gamma
            )
        }
    )


def register(registry: SolverRegistry) -> int:
    """Registers every compressible fluids direction (D141); returns the count."""
    directions = [
        isentropic_stagnation_temp_ratio.solver_direction,  # ty: ignore[unresolved-attribute]
        isentropic_stagnation_pressure_ratio.solver_direction,  # ty: ignore[unresolved-attribute]
        normal_shock_mach2.solver_direction,  # ty: ignore[unresolved-attribute]
        normal_shock_pressure_ratio.solver_direction,  # ty: ignore[unresolved-attribute]
        fanno_function.solver_direction,  # ty: ignore[unresolved-attribute]
    ]
    count = 0
    for direction in directions:
        result = registry.register(*direction)
        _ = result.danger_ok
        count += 1
    return count
