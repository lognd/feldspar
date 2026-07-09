from __future__ import annotations

"""WO-07: generates the demonstration `CalibRecord` committed under
`tests/calib/records/`.

NORMATIVE note (docs/spec/03-solvers.md "Citations and
calibration", audit A-7): a solver declaring `accuracy=EXACT` needs
method citations like any solver but NO calibration citation -- there
is nothing to measure. All four `mech` Phase 1 solver directions
(`python/feldspar/library/mech.py`) declare `accuracy=EXACT`, so
strictly none of them require a calibration record, and
`feldspar.calib.check_ceilings` skips every EXACT-ceiling port
entirely (it only ever inspects `non_exact_ports`).

This script -- and the record it writes -- exists purely to
DEMONSTRATE the calibration harness end-to-end against a real
registered solver ahead of WO-08 landing a discretized (FEA) tier,
which is the first solver that will actually need a calibration
citation (09-model-integration sec. 7: "Upward: discretized tiers
calibrate closed-form ... ceilings"). Until then there is no second
independent tier to calibrate against, so this calibrates
`mech.bore_von_mises` against ITSELF as a trivial self-consistency
demonstration -- `worst_abs_error`/`worst_rel_error` should come out
at (or extremely near) 0.0, proving the harness's sampling, shared-
domain intersection, and digest/record-write plumbing all work against
a real registered `SolveFn`, not a synthetic test double.

Re-run this script (`uv run python tests/calib/generate_records.py`)
whenever `mech.bore_von_mises` changes; `tests/calib/test_mech_calibration.py`
re-derives the same record deterministically (same seed) and asserts
it matches what's committed on disk, so a stale committed record fails
CI rather than silently drifting.
"""

from pathlib import Path

from feldspar.calib import calibrate
from feldspar.calib.store import write_record
from feldspar.library.mech import register
from feldspar.logging_setup import get_logger
from feldspar.solve import SolverRegistry

_log = get_logger(__name__)

RECORDS_DIR = Path(__file__).resolve().parent / "records"

#: solver_id calibrated against itself; the seed/sample count fixed here
#: are also used by the byte-for-byte regression test.
SOLVER_ID = "mech.bore_von_mises"
REFERENCE_ID = "mech.bore_von_mises"
N_SAMPLES = 256
SEED = 0


def build_registry() -> SolverRegistry:
    """The same mech registration used at runtime, frozen so this
    matches how `check_ceilings` will see the registry."""
    registry = SolverRegistry()
    register(registry)
    registry.freeze()
    return registry


def main() -> None:
    """Calibrates `SOLVER_ID` against `REFERENCE_ID` and writes the
    resulting `CalibRecord` to `tests/calib/records/`."""
    registry = build_registry()
    result = calibrate(
        SOLVER_ID, REFERENCE_ID, registry, n_samples=N_SAMPLES, seed=SEED
    )
    if result.is_err:
        _log.error("generate_records: calibration failed: %r", result.danger_err)
        raise SystemExit(f"calibration failed: {result.danger_err!r}")
    record = result.danger_ok
    path = write_record(RECORDS_DIR, record)
    print(f"wrote {path} (digest={record.digest})")


if __name__ == "__main__":
    main()
