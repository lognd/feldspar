from __future__ import annotations

"""Solver registry, decorator, and digest facade over feldspar-core
(WO-03/04). Public surface (01-interfaces `feldspar.solve`) re-exported
here; `_build.py`/`_models.py` are private implementation details."""

from typani import Err, Ok, Result

from feldspar.solve.errors import RegistryError, SolveError
from feldspar.solve.payload import (
    PAYLOAD_KINDS,
    PayloadRef,
    PayloadResolver,
    payload_feature_violation,
)
from feldspar.solve.registry import SolverRegistry
from feldspar.solve.seeking import CostCurve, CostPoint
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
    "CostCurve",
    "CostPoint",
    "CoupledGroup",
    "EXACT",
    "Err",
    "Ok",
    "PAYLOAD_KINDS",
    "PayloadRef",
    "PayloadResolver",
    "Relation",
    "RegistryError",
    "Result",
    "SolveError",
    "SolveOutput",
    "SolverInfo",
    "SolverRegistry",
    "make_direction",
    "payload_feature_violation",
    "solver",
    "table_solver_1d",
    "table_solver_2d",
]
