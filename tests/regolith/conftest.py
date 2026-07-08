from __future__ import annotations

"""Makes regolith's reusable pack-protocol conformance suite importable.

`../lithos/tests/packs/conformance.py` (`assert_pack_conforms`,
`registry_with_pack`) is the CONTRACT feldspar's pack proves itself
against from the outside (06 "Conformance"). It ships in regolith's
``tests/`` tree, not its installed distribution, so this session adds
``../lithos`` to `sys.path` (mirroring how regolith's OWN test suite
imports `tests.packs...` as a top-level package) -- every test under
this directory is `regolith`-marked and skipped by default
(`pyproject.toml`'s `-m "not regolith and not fea"`), so this path
insertion only ever happens when a caller explicitly opts into the
`regolith` marker."""

import sys
from pathlib import Path

_LITHOS_ROOT = Path(__file__).resolve().parents[2].parent / "lithos"

if _LITHOS_ROOT.is_dir() and str(_LITHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(_LITHOS_ROOT))
