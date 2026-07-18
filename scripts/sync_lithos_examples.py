"""Refresh examples/lithos as a verbatim mirror of the sibling lithos
repo's examples/ tree (lithos D148, cycle 27: one corpus,
single-sourced in lithos; feldspar carries a committed mirror so the
repo stays self-contained for CI and fresh clones).

Usage: `make sync-examples` (or `python scripts/sync_lithos_examples.py
[--lithos PATH]`). Deletes the current mirror and re-copies; review
the resulting git diff like any generated artifact. Never edit files
under examples/lithos/ by hand -- fix them in lithos and re-sync.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# frob:doc docs/workflow/dev-scripts.md#sync-lithos-examples
REPO_ROOT = Path(__file__).resolve().parent.parent
# frob:doc docs/workflow/dev-scripts.md#sync-lithos-examples
MIRROR = REPO_ROOT / "examples" / "lithos"
# frob:doc docs/workflow/dev-scripts.md#sync-lithos-examples
MARKER = "# MIRROR of lithos:examples/ -- do not edit; `make sync-examples` regenerates.\n"


def sync(lithos_root: Path) -> int:
    """Copy lithos/examples into examples/lithos verbatim; returns file count."""
    # frob:doc docs/workflow/dev-scripts.md#sync-lithos-examples
    # frob:ticket T-0007
    src = lithos_root / "examples"
    if not src.is_dir():
        logger.error("lithos examples tree not found: %s", src)
        raise SystemExit(2)
    if MIRROR.exists():
        logger.info("removing stale mirror %s", MIRROR)
        shutil.rmtree(MIRROR)
    shutil.copytree(src, MIRROR)
    (MIRROR / ".mirror").write_text(MARKER, encoding="ascii", newline="\n")
    count = sum(1 for p in MIRROR.rglob("*") if p.is_file())
    logger.info("mirrored %d files from %s", count, src)
    return count


def main() -> int:
    """CLI entry point: parses --lithos and syncs the examples mirror from it."""
    # frob:doc docs/workflow/dev-scripts.md#sync-lithos-examples
    # frob:ticket T-0007
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lithos",
        type=Path,
        default=REPO_ROOT.parent / "lithos",
        help="path to the sibling lithos checkout (default: ../lithos)",
    )
    args = parser.parse_args()
    count = sync(args.lithos)
    print(f"examples/lithos: {count} files mirrored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
