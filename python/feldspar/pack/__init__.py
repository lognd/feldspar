from __future__ import annotations

"""ALL regolith imports live here (FINV-10); the regolith.model_packs entry point."""

from typing import Any  # noqa: E402 -- after module docstring, ruff false-positive


def register(registry: Any) -> None:
    """Registers feldspar's regolith Model contract entries; no-op stub until WO-09."""
    # TODO(WO-09): register mech.static_stress / mech.static_deflection models
    # (docs/feldspar/06-regolith-pack.md) against `registry`.
    return None
