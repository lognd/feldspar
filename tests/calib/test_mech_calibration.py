from __future__ import annotations

"""WO-07 tests: (1) the committed self-calibration demonstration record
(`tests/calib/records/`, see `tests/calib/generate_records.py` for the
full rationale -- EXACT-ceiling mech solvers are calibration-exempt per
docs/spec/03-solvers.md/A-7; this record only demonstrates the
harness end-to-end ahead of WO-08) reproduces byte-for-byte from the
same deterministic seed, and (2) `check_ceilings` passes against the
fully populated, frozen mech registry -- wiring the ceiling-vs-record
check into `make check`'s `test` target (no `regolith`/`fea` marker on
either test here)."""

from pathlib import Path

from feldspar.calib import calibrate, check_ceilings
from feldspar.calib.store import read_record
from feldspar.library.mech import register
from feldspar.solve import SolverRegistry

RECORDS_DIR = Path(__file__).resolve().parent / "records"

# Must match tests/calib/generate_records.py's SOLVER_ID/REFERENCE_ID/
# N_SAMPLES/SEED exactly -- duplicated here (rather than imported) since
# `tests/` is not an importable package in this repo (no `__init__.py`,
# per pyproject.toml's `testpaths`); kept in one place conceptually by
# this comment pointing back at the generator script.
SOLVER_ID = "mech.bore_von_mises"
REFERENCE_ID = "mech.bore_von_mises"
N_SAMPLES = 256
SEED = 0


def _frozen_mech_registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    registry.freeze()
    return registry


def test_committed_self_calibration_record_reproduces_deterministically():
    """Re-running `calibrate()` with the exact same solver_id/reference_id/
    n_samples/seed used by `tests/calib/generate_records.py` must yield a
    record whose fields (and therefore whose digest, AD-9) match the
    committed JSON file byte-for-byte -- this is what keeps the committed
    record honest instead of silently drifting from the solver it
    describes."""
    registry = _frozen_mech_registry()
    result = calibrate(
        SOLVER_ID, REFERENCE_ID, registry, n_samples=N_SAMPLES, seed=SEED
    )
    assert result.is_ok
    fresh_record = result.danger_ok

    committed_record = read_record(RECORDS_DIR, fresh_record.digest)
    assert committed_record is not None, (
        "no committed record for the freshly-derived digest -- "
        "re-run tests/calib/generate_records.py"
    )
    assert committed_record == fresh_record
    # The self-calibration demonstration's whole point: a solver
    # compared against itself has zero observed error.
    assert fresh_record.worst_abs_error == 0.0
    assert fresh_record.worst_rel_error == 0.0


# frob:tests python/feldspar/calib kind="integration"
# frob:tests python/feldspar/mech kind="integration"
def test_check_ceilings_passes_for_frozen_mech_registry():
    """`check_ceilings` must succeed against the fully registered, frozen
    mech registry: all four Phase 1 directions declare `accuracy=EXACT`
    (A-7, calibration-exempt), so `non_exact_ports` is empty for every
    one of them and the ceiling-vs-record check has nothing to verify --
    but it must still run cleanly (`Ok`), which is what wires this check
    into `make check`'s `test` target (this test carries no `regolith`/
    `fea` marker)."""
    registry = _frozen_mech_registry()
    result = check_ceilings(registry, records_dir=RECORDS_DIR)
    assert result.is_ok
