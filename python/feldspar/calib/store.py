from __future__ import annotations

"""Flat content-addressed store for `CalibRecord` run files (AD-9,
same shape as `feldspar.plan.cache.SolveCache`): filename IS the
record's own digest, so `write_record`/`read_record` are pure
key-value operations -- no index, no eviction. A `CalibRecord` is far
simpler than a `Solution`, so plain functions suffice (no store
class needed)."""

import json
from pathlib import Path

from feldspar.calib._models import CalibRecord
from feldspar.logging import get_logger

__all__ = ["record_path", "write_record", "read_record"]

_log = get_logger(__name__)


def record_path(records_dir: Path, digest: str) -> Path:
    """`records_dir / f"{digest}.json"` -- the one place this filename
    convention is spelled out (AD-9: filename IS the key)."""
    return records_dir / f"{digest}.json"


def write_record(records_dir: Path, record: CalibRecord) -> Path:
    """Write `record` to `records_dir / f"{record.digest}.json"`,
    sorted-key JSON (matches `SolveCache.put`'s dump style)."""
    path = record_path(records_dir, record.digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record.model_dump(), sort_keys=True))
    _log.info(
        "calib record store: digest=%s solver_id=%s", record.digest, record.solver_id
    )
    return path


def read_record(records_dir: Path, digest: str) -> "CalibRecord | None":
    """`None` if no record file exists for `digest` -- caller (`check_ceilings`)
    turns that into `CalibError.NoRecord`."""
    path = record_path(records_dir, digest)
    if not path.exists():
        _log.info("calib record miss: digest=%s (no entry)", digest)
        return None
    data = json.loads(path.read_text())
    _log.info("calib record hit: digest=%s", digest)
    return CalibRecord(**data)
