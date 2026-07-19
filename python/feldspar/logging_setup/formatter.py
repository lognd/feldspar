from __future__ import annotations

import logging


# frob:doc docs/modules/logging_setup.md#logging_setup_formatter
class MalmbergFormatter(logging.Formatter):
    """Plain formatter; WARNING+ prefixes level name, DEBUG/INFO emit message only."""

    def __init__(self, show_level: bool = False) -> None:
        super().__init__()
        self._show_level = show_level

    # frob:doc docs/modules/logging_setup.md#logging_setup_formatter
    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        if self._show_level or record.levelno >= logging.WARNING:
            return f"{record.levelname}: {msg}"
        return msg
