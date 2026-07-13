from __future__ import annotations

"""Compat shim (WO-118 migration, spec 12 sec. 1): the real fluids
domain package moved to `feldspar.fluids`; this package re-exports it
unchanged (behavior-preserving, D227) so `feldspar.library.fluids`
keeps importing exactly as before. (Not a whole-package `sys.modules`
alias like the flat-module shims in this directory: that would swap
this package's own `__path__` too, breaking the sibling
`feldspar.library.fluids.network` shim's own submodule import.)"""

from feldspar.fluids import register, register_network  # noqa: F401
