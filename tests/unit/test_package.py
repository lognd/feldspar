from __future__ import annotations

import feldspar
from feldspar.__about__ import __version__
from feldspar.pack import register


def test_version_single_sourced() -> None:
    """feldspar.__version__ must be the same object __about__ defines (AD-11)."""
    assert feldspar.__version__ == __version__


def test_pack_register_is_noop_stub() -> None:
    """The regolith.model_packs entry point target is import-safe without regolith (FINV-3)."""
    assert register(None) is None
