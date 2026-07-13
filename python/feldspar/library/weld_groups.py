from __future__ import annotations

"""Compat shim (WO-118 migration, spec 12 sec. 1): the real home moved
to `feldspar.mech.weld_groups`; this module becomes a transparent alias
(via `sys.modules`, not `import *`, so every attribute -- not just
`__all__` -- stays reachable through the old path) so
`feldspar.library.weld_groups` keeps working exactly as
before (behavior-preserving, D227)."""

import sys

from feldspar.mech import weld_groups as _real  # noqa: F401

sys.modules[__name__] = _real
