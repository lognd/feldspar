from __future__ import annotations

"""Compat shim (WO-118 migration, spec 12 sec. 1): the real home moved
to `feldspar.elec.closed_form`; this module becomes a transparent alias
(via `sys.modules`, not `import *`, so every attribute -- not just
`__all__` -- stays reachable through the old path) so
`feldspar.library.elec` keeps working exactly as
before (behavior-preserving, D227)."""

import sys

from feldspar.elec import closed_form as _real  # noqa: F401

sys.modules[__name__] = _real
