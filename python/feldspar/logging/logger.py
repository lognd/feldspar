from __future__ import annotations

import logging
import logging.config
from pathlib import Path

import tomllib as toml

_CONFIG_PATH = Path(__file__).parent / "config.toml"
_initialized = False


def _init() -> None:
    """Loads config.toml and applies it via dictConfig, exactly once per process."""
    global _initialized
    if _initialized:
        return
    with _CONFIG_PATH.open("rb") as f:
        cfg = toml.load(f)
    logging.config.dictConfig(cfg)
    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """Returns a module logger, initializing the dictConfig setup on first call."""
    _init()
    return logging.getLogger(name)
