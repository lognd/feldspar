from __future__ import annotations

"""`CalibError` -- the total error union for the calibration harness
(01-interfaces ~261-275, WO-07). Same `_TaggedError` idiom as
`feldspar.solve.errors.RegistryError`/`SolveError` (one home for the
kind/fields/eq/hash/repr machinery, house rule: no duplication)."""

from feldspar.solve.errors import _TaggedError


# frob:doc docs/modules/calib.md#calib_errors
class CalibError(_TaggedError):
    """Calibration harness failures: an unknown solver id, domains that
    don't overlap enough to sample, a declared accuracy ceiling tighter
    than its backing evidence, or a calibration citation with no
    matching run record on disk."""

    # frob:doc docs/modules/calib.md#calib_errors
    @classmethod
    def UnknownSolver(cls, solver_id: str) -> "CalibError":
        return cls("UnknownSolver", solver_id=solver_id)

    # frob:doc docs/modules/calib.md#calib_errors
    @classmethod
    def DomainMismatch(cls, solver_id: str, reference_id: str) -> "CalibError":
        return cls("DomainMismatch", solver_id=solver_id, reference_id=reference_id)

    # frob:doc docs/modules/calib.md#calib_errors
    @classmethod
    def CeilingBusted(
        cls, solver_id: str, declared: float, observed: float
    ) -> "CalibError":
        return cls(
            "CeilingBusted", solver_id=solver_id, declared=declared, observed=observed
        )

    # frob:doc docs/modules/calib.md#calib_errors
    @classmethod
    def NoRecord(cls, solver_id: str) -> "CalibError":
        return cls("NoRecord", solver_id=solver_id)
