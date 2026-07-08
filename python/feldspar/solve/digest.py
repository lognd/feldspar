from __future__ import annotations

"""Canonical-JSON -> blake3 digest facade (AD-5). The one digest
IMPLEMENTATION home is `feldspar.core.canonical_digest` (WO-02, backed by
the Rust core); this module is the `feldspar.solve`-side surface over
it -- `SolverInfo.settings_digest` (F1) and `SolverRegistry.digest()`
(FINV-7) both go through `settings_digest`/`canonical_digest` here so
there is exactly one call site per digest kind, not one per WO."""

from typing import Any

from feldspar.core import canonical_digest

__all__ = ["canonical_digest", "settings_digest"]


def settings_digest(settings: Any) -> str:
    """The `SolverInfo.settings_digest` a solver's decorator-level
    `settings=` closure folds into (F1); `None` (no settings) digests
    just as deterministically as a real settings model."""
    return canonical_digest(settings)
