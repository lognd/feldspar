from __future__ import annotations

import logging


# frob:doc docs/modules/logging_setup.md#logging_setup_filter
class BelowLevelFilter(logging.Filter):
    """Pass records strictly below `below` level (used to keep stdout clean)."""

    def __init__(self, below: str) -> None:
        super().__init__()
        self._below = getattr(logging, below.upper())

    # frob:doc docs/modules/logging_setup.md#logging_setup_filter
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self._below
