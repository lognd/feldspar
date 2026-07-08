from __future__ import annotations

import feldspar
from feldspar.__about__ import __version__


def test_version_single_sourced() -> None:
    """feldspar.__version__ must be the same object __about__ defines (AD-11)."""
    assert feldspar.__version__ == __version__


# `feldspar.pack` itself now requires regolith installed to import (it is
# the `regolith.model_packs` entry point target, WO-09): unlike the WO-01
# no-op stub, real registration needs regolith's `Model`/`ModelSignature`
# types, so it is no longer import-safe in a bare (non-`regolith`-extra)
# environment. Its coverage lives under the `regolith` marker in
# `tests/regolith/` (06 "Boundary rules": everything OUTSIDE `pack/`
# stays regolith-free, not `pack/` itself).
