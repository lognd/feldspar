from __future__ import annotations

"""Private home for `Citation`/`ClaimSenses`/`SolverInfo`/`SolveOutput`:
split out from `solver.py` solely so `_build.py` (needed by both
`solver.py`'s `@solver` and `sugar.py`'s builders) can import these
model types without `solver.py` <-> `_build.py` becoming a Python import
cycle. `solver.py` re-exports everything here; author-facing code always
imports from `feldspar.solve`, never from this module."""

import enum
from typing import Any, Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from feldspar.core import Accuracy
from feldspar.solve.payload import PayloadRef


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

    # Symbolic-derivation provenance (WO-11, `Relation.law`): carried
    # for `explain()`/`to_dict()` rendering only -- `exclude=True` so
    # `model_dump()` (and therefore `canonical_digest`/`registry.digest()`,
    # AD-5/FINV-7) drops them entirely. A symbolically-derived direction
    # must digest byte-identically to a hand-built twin that never sets
    # these (02-edge-cases WO-03 row extended to WO-11's symbolic path).
    algebraic_form: Optional[str] = Field(default=None, exclude=True)
    solved_for: Optional[str] = Field(default=None, exclude=True)
    branch: Optional[str] = Field(default=None, exclude=True)
    admission_predicate: Optional[str] = Field(default=None, exclude=True)
    derivation_digest: Optional[str] = Field(default=None, exclude=True)

    # R5 re-sweep provenance (11 sec. 4, WO-22): the declared law's two
    # sides, carried ONLY so `feldspar.calib.harness.resweep_derived`
    # can verify the derived direction's closed form against the
    # ORIGINAL equation over its (possibly nonlinearly mapped) domain --
    # never used for dispatch or `explain()` rendering, and `exclude=True`
    # for the same digest-equality reason as the provenance fields above.
    law_lhs: Optional[Any] = Field(default=None, exclude=True)
    law_rhs: Optional[Any] = Field(default=None, exclude=True)


class SolveOutput(BaseModel):
    """A solver's raw solve result (01-interfaces `SolveOutput`,
    DX F16). `measured_eps` replaces the declared accuracy ceiling for
    measuring solvers (FEA, Richardson); validity (non-negative, finite)
    is an EXECUTOR check (WO-06, `SolveError.InvalidMeasurement`), not
    enforced at construction here. `payloads` (WO-12, 09 sec. 4) carries
    any payload-rank output ports' `PayloadRef` values -- exact by
    reference, so unlike `values` they are never corner-swept or hulled
    (the executor requires them corner-INVARIANT instead)."""

    model_config = ConfigDict(frozen=True)

    values: Mapping[str, float]
    measured_eps: Optional[float] = None
    payloads: Mapping[str, PayloadRef] = {}


#: `Accuracy(0.0, 0.0)`; the EXACT constant (01-interfaces `feldspar.solve.EXACT`).
EXACT = Accuracy(0.0, 0.0)
