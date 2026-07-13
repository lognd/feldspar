from __future__ import annotations

"""Compat shim (WO-118 migration, spec 12 sec. 1): the real module
moved to `feldspar.fluids.network`; this module becomes a transparent
alias (via `sys.modules`) so `feldspar.library.fluids.network` keeps
working exactly as before."""

import sys

from feldspar.fluids import network as _real  # noqa: F401

sys.modules[__name__] = _real
