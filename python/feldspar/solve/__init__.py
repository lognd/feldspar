from __future__ import annotations

"""Solver registry, decorator, and digest facade over feldspar-core
(WO-03/04). Public surface (01-interfaces `feldspar.solve`) re-exported
here; `_build.py`/`_models.py` are private implementation details."""

from typani import Err, Ok, Result

from feldspar.solve.errors import RegistryError, SolveError
from feldspar.solve.registry import SolverRegistry
from feldspar.solve.solver import (
    EXACT,
    Citation,
    ClaimSenses,
    SolveOutput,
    SolverInfo,
    solver,
)
from feldspar.solve.sugar import (
    Correlation,
    CoupledGroup,
    Relation,
    make_direction,
    table_solver_1d,
    table_solver_2d,
)

__all__ = [
    "Citation",
    "ClaimSenses",
    "Correlation",
    "CoupledGroup",
    "EXACT",
    "Err",
    "Ok",
    "Relation",
    "RegistryError",
    "Result",
    "SolveError",
    "SolveOutput",
    "SolverInfo",
    "SolverRegistry",
    "make_direction",
    "solver",
    "table_solver_1d",
    "table_solver_2d",
]
