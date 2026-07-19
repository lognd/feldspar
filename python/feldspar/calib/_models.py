from __future__ import annotations

"""`CalibRecord` -- the content-addressed calibration run record
(01-interfaces ~261-275, 09 sec. 7, 03 "Citations and calibration").
Frozen pydantic model, same convention as `Citation`/`SolverInfo`
(`feldspar.solve._models`)."""

from pydantic import BaseModel, ConfigDict


# frob:doc docs/modules/calib.md#calib_models
class CalibRecord(BaseModel):
    """One calibration run's evidence: `solver_id` swept against
    `reference_id` over `n_samples` deterministic (`seed`) in-domain
    points, with the worst observed absolute/relative error. `digest`
    is `canonical_digest` of every OTHER field (AD-5, AD-9: the digest
    IS the record's content-address; a `Citation(kind="calibration",
    ref=digest)` points here)."""

    model_config = ConfigDict(frozen=True)

    solver_id: str
    reference_id: str
    n_samples: int
    seed: int
    worst_abs_error: float
    worst_rel_error: float
    digest: str
