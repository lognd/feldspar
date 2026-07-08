from __future__ import annotations

"""Private home for `Citation`/`ClaimSenses`/`SolverInfo`/`SolveOutput`:
split out from `solver.py` solely so `_build.py` (needed by both
`solver.py`'s `@solver` and `sugar.py`'s builders) can import these
model types without `solver.py` <-> `_build.py` becoming a Python import
cycle. `solver.py` re-exports everything here; author-facing code always
imports from `feldspar.solve`, never from this module."""

import enum
from typing import Any, Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict

from feldspar.core import Accuracy


class Citation(BaseModel):
    """A method citation; `SolverRegistry.register` enforces the
    citation floor (FINV-6): empty or calibration-only is an error."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["paper", "handbook", "standard", "calibration"]
    ref: str
    note: str = ""


class ClaimSenses(enum.Enum):
    """Which one-sided claim(s) a solver/direction is conservative for
    (G4). Coerces from a case-insensitive string (`"upper"`, `"lower"`,
    `"both"`) as well as an existing member, since author-facing kwargs
    accept either (examples/solvers/06_coupled_groups.py)."""

    UPPER = "upper"
    LOWER = "lower"
    BOTH = "both"

    @classmethod
    def coerce(cls, value: "ClaimSenses | str") -> "ClaimSenses":
        if isinstance(value, ClaimSenses):
            return value
        return cls(str(value).lower())


class SolverInfo(BaseModel):
    """Frozen solver metadata (01-interfaces `SolverInfo`); the exact
    thing `SolverRegistry.digest()` folds (AD-5, FINV-7)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    solver_id: str
    namespace: str
    version: str
    inputs: Tuple[str, ...]
    outputs: Tuple[str, ...]
    domain: Any  # feldspar.core.Domain (arbitrary_types_allowed; PyO3, AD-2)
    cost: float
    accuracy: Mapping[str, Accuracy]
    citations: Tuple[Citation, ...]
    tier: Literal["table", "closed_form", "reduced", "discretized", "coupled"]
    deterministic: bool = True
    corner_monotone: bool = True
    conservative_for: ClaimSenses = ClaimSenses.BOTH
    settings_digest: str

    # RESERVED for M3 budget-seeking refinement (09 sec. 8 milestones);
    # documented, not implemented -- always None in M1. TODO(M3): give
    # these real types once budget-seeking search lands (WO-11+).
    eps_seeking: Optional[Any] = None
    cost_curve: Optional[Any] = None


class SolveOutput(BaseModel):
    """A solver's raw solve result (01-interfaces `SolveOutput`,
    DX F16). `measured_eps` replaces the declared accuracy ceiling for
    measuring solvers (FEA, Richardson); validity (non-negative, finite)
    is an EXECUTOR check (WO-06, `SolveError.InvalidMeasurement`), not
    enforced at construction here."""

    model_config = ConfigDict(frozen=True)

    values: Mapping[str, float]
    measured_eps: Optional[float] = None


#: `Accuracy(0.0, 0.0)`; the EXACT constant (01-interfaces `feldspar.solve.EXACT`).
EXACT = Accuracy(0.0, 0.0)
