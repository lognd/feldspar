from __future__ import annotations

"""ALL regolith imports live here (FINV-3/10); the `regolith.plugins`
entry point target (06 "Boundary rules", `[project.entry-points]` in
`pyproject.toml`; lithos WO-44/AD-26 folded the old
`regolith.model_packs` group into the one seam)."""

from typing import Any  # noqa: E402 -- after module docstring, ruff false-positive

from feldspar.__about__ import __version__  # noqa: E402
from feldspar.logging_setup import get_logger  # noqa: E402
from feldspar.pack.models import (  # noqa: E402
    FeaStaticDeflectionModel,
    FeaStaticStressModel,
)

_log = get_logger(__name__)

__all__ = ["MANIFEST", "register"]  # MANIFEST via module __getattr__ (PEP 562)


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


# The one discovery seam's target (lithos WO-44/AD-26): the entry point
# resolves `feldspar.pack:MANIFEST`, built lazily (PEP 562) so importing
# this module stays regolith-free (FINV-3 posture) -- regolith is by
# definition present when ITS discovery loads the attribute. The
# manifest's author-declared version folds into evidence keys (lithos
# INV-1), so bumping feldspar's version re-keys exactly this pack's
# evidence.
def __getattr__(name: str) -> Any:
    """Lazily build MANIFEST so the module imports without regolith."""
    if name == "MANIFEST":
        from regolith.plugins import PluginKind, PluginManifest

        return PluginManifest(
            id="feldspar",
            kind=PluginKind.MODEL_PACK,
            version=__version__,
            register_fn=register,
        )
    raise AttributeError(name)
