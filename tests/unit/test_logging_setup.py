from __future__ import annotations

"""Direct unit tests for `feldspar.logging_setup`'s pure-python pieces
(get_logger, BelowLevelFilter) -- the pyo3-log bridge itself is covered
separately by test_smoke_logging.py (requires the native extension)."""

import logging

from feldspar.logging_setup.filter import BelowLevelFilter
from feldspar.logging_setup.logger import get_logger


# frob:tests python/feldspar/logging_setup/logger.py::get_logger kind="unit"
def test_get_logger_returns_named_stdlib_logger_and_is_idempotent() -> None:
    """`get_logger` hands back an ordinary `logging.Logger` named after
    the caller's module, and repeated calls do not re-run dictConfig
    (module-level `_initialized` guard) or raise."""
    first = get_logger("feldspar.test_logging_setup.probe")
    second = get_logger("feldspar.test_logging_setup.probe")
    assert isinstance(first, logging.Logger)
    assert first.name == "feldspar.test_logging_setup.probe"
    assert first is second  # stdlib logger registry returns the same instance


# frob:tests python/feldspar/logging_setup/filter.py::BelowLevelFilter.filter kind="unit"
def test_below_level_filter_passes_only_strictly_lower_levels() -> None:
    """`BelowLevelFilter("WARNING")` must pass DEBUG/INFO records and
    reject WARNING/ERROR records -- keeps stdout clean of anything at
    or above the configured ceiling."""
    filt = BelowLevelFilter("WARNING")
    info_record = logging.LogRecord(
        name="x", level=logging.INFO, pathname="", lineno=0, msg="ok", args=(), exc_info=None
    )
    warning_record = logging.LogRecord(
        name="x", level=logging.WARNING, pathname="", lineno=0, msg="no", args=(), exc_info=None
    )
    assert filt.filter(info_record) is True
    assert filt.filter(warning_record) is False
