from __future__ import annotations

"""ALL regolith imports live here (FINV-3/10); the `regolith.model_packs`
entry point target (06 "Boundary rules", `[project.entry-points]` in
`pyproject.toml`)."""

from typing import Any  # noqa: E402 -- after module docstring, ruff false-positive

from feldspar.logging_setup import get_logger  # noqa: E402
from feldspar.pack.models import (  # noqa: E402
    FeaStaticDeflectionModel,
    FeaStaticStressModel,
)

_log = get_logger(__name__)

__all__ = ["register"]


def register(registry: Any) -> None:
    """Registers feldspar's two reduced-tier FEA models on `registry`
    (a regolith `ModelRegistry`) and nothing else (06 "register(registry)
    ... registers the models below and nothing else").

    Import-cheap and probe-free (FINV-3/10): constructing `Model`
    instances and calling `registry.register()` only adds Python-side
    metadata -- no gmsh/ccx tool discovery happens until a matched
    model's `estimate()` actually runs a route (`pack.models._FeaModel.
    estimate` builds the engine `SolverRegistry` lazily, per call)."""
    registry.register(FeaStaticStressModel())
    registry.register(FeaStaticDeflectionModel())
    _log.info("feldspar.pack: registered 2 regolith model(s)")
