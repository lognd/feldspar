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

import importlib.util
import sys
from pathlib import Path

import pytest

_LITHOS_ROOT = Path(__file__).resolve().parents[2].parent / "lithos"

if _LITHOS_ROOT.is_dir() and str(_LITHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(_LITHOS_ROOT))

# Marker deselection (`-m "not regolith"`) is applied AFTER collection, so
# without this guard pytest still IMPORTS every module in this directory and
# dies at collection with `ModuleNotFoundError: regolith` on the jobs that run
# regolith-free. When regolith is not importable, skip collecting this tree
# entirely -- these tests are meaningful only with regolith installed.
if importlib.util.find_spec("regolith") is None:
    collect_ignore_glob = ["*"]


@pytest.fixture(autouse=True)
def _isolate_feldspar_cache(monkeypatch, tmp_path):
    """Every test under this directory drives `Model.estimate()`
    (directly, or through `regolith.harness`), which -- unless a
    caller injects its own `SolveCache`/`PayloadStepCache` -- defaults
    to `.feldspar/cache` RELATIVE to the process cwd
    (`feldspar.plan.cache._DEFAULT_CACHE_DIR`). Without chdir-ing away
    from the real checkout, run order across sessions leaks a stale
    on-disk entry from one test's resolver-threaded run into a LATER
    test's no-resolver run of the same request -- exactly the
    integration bug this fixes (a no-resolver honest-`Err` masked by a
    resolver-run's cached `Ok`). `tests/unit/test_payload_pipeline.py`
    already isolates individual tests this way
    (`monkeypatch.chdir(tmp_path)`); this applies the same fix once,
    autouse, for the whole directory instead of relying on every test
    author to remember it."""
    monkeypatch.chdir(tmp_path)
