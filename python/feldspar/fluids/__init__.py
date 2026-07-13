from __future__ import annotations

"""Fluid-mechanics closed-form solver directions (WO-20 Phase 2), split
by regime: `incompressible` (internal flow, pipe networks,
turbomachinery, water hammer) and `compressible` (D141 isentropic
relations, normal shocks, the Fanno function). `register` here composes
both regimes so `from feldspar.fluids import register` keeps working
exactly as before the WO-118 library/ -> per-domain-package migration
(spec 12 sec. 1; the module content and behavior are unchanged, only
the package home moved from `feldspar.library.fluids`).

`network` (WO-20 residual: the Hardy-Cross `flownet`-payload solver) is
NOT folded into `register` -- it declares payload ports (F12) and
needs a `PayloadResolver`, so it follows `feldspar.fea.payload_steps`'s
convention: a separate `register_network(registry, resolver)` the
catalog loader calls LAST, after every declaration-free module."""

from feldspar.logging_setup import get_logger
from feldspar.solve import SolverRegistry
from feldspar.solve.payload import PayloadResolver

from . import compressible, incompressible, network

_log = get_logger(__name__)

__all__ = ["register", "register_network"]


def register(registry: SolverRegistry) -> None:
    """Registers every declaration-free fluids solver direction, both
    regimes (WO-20/D141)."""
    count = incompressible.register(registry)
    count += compressible.register(registry)
    _log.info("fluids: registered %d solver directions", count)


def register_network(registry: SolverRegistry, resolver: PayloadResolver) -> None:
    """Registers the Hardy-Cross `flownet`-payload direction (WO-20
    residual). Must be called after `register()` and after every other
    declaration-free module, same F12 ordering `payload_steps`
    documents."""
    network.register(registry, resolver)
