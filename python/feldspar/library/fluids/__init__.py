from __future__ import annotations

"""Fluid-mechanics closed-form solver directions (WO-20 Phase 2), split
by regime: `incompressible` (internal flow, pipe networks,
turbomachinery, water hammer) and `compressible` (D141 isentropic
relations, normal shocks, the Fanno function). `register` here composes
both regimes so `from feldspar.library.fluids import register` keeps
working exactly as before the split."""

from feldspar.logging_setup import get_logger
from feldspar.solve import SolverRegistry

from . import compressible, incompressible

_log = get_logger(__name__)

__all__ = ["register"]


def register(registry: SolverRegistry) -> None:
    """Registers every fluids solver direction, both regimes (WO-20/D141)."""
    count = incompressible.register(registry)
    count += compressible.register(registry)
    _log.info("fluids: registered %d solver directions", count)
