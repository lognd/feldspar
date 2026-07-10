from __future__ import annotations

"""ALL regolith imports live here (FINV-3/10); the `regolith.plugins`
entry point target (06 "Boundary rules", `[project.entry-points]` in
`pyproject.toml`; lithos WO-44/AD-26 folded the old
`regolith.model_packs` group into the one seam)."""

from typing import Any  # noqa: E402 -- after module docstring, ruff false-positive

from regolith.harness.signature import ClaimSense  # noqa: E402

from feldspar.__about__ import __version__  # noqa: E402
from feldspar.logging_setup import get_logger  # noqa: E402
from feldspar.pack.models import (  # noqa: E402
    DEFAULT_RAIL_HI_CLAIM_KIND,
    DEFAULT_RAIL_LO_CLAIM_KIND,
    BearingRatingLifeModel,
    BoltLoadFactorModel,
    ElecRailModel,
    EulerBucklingLoadModel,
    FeaStaticDeflectionFromGeometryModel,
    FeaStaticDeflectionModel,
    FeaStaticStressModel,
    MechStiffnessModel,
    MemberAxialCapacityModel,
    MemberFlexuralCapacityModel,
    WeldUtilizationModel,
)

_log = get_logger(__name__)

__all__ = ["MANIFEST", "register"]  # MANIFEST via module __getattr__ (PEP 562)


def register(registry: Any) -> None:
    """Registers feldspar's twelve regolith models on `registry` (a
    regolith `ModelRegistry`) and nothing else (06 "register(registry)
    ... registers the models below and nothing else").

    Cycle-33 pack-exposure wave: `MemberFlexuralCapacityModel`/
    `MemberAxialCapacityModel`/`EulerBucklingLoadModel`/
    `BoltLoadFactorModel`/`WeldUtilizationModel`/`BearingRatingLifeModel`
    wrap WO-24 library-depth directions (`member_capacity.py`/
    `bolted_joints.py`/`weld_groups.py`/`bearing_life.py`) that landed
    complete and calibrated in `_engine_registry()` but had no regolith
    `Model` wrapper before this wave -- see `pack.models`'s own
    "cycle-33 pack-exposure wave" section comment for which directions
    stayed unexposed (named residuals) and why.

    Import-cheap and probe-free (FINV-3/10): constructing `Model`
    instances and calling `registry.register()` only adds Python-side
    metadata -- no gmsh/ccx tool discovery happens until a matched
    model's `estimate()` actually runs a route (`pack.models._FeaModel.
    estimate` builds the engine `SolverRegistry` lazily, per call).
    `FeaStaticDeflectionFromGeometryModel` (WO-14, 06 "Planned (09 M4)")
    is the D96 payload-channel model: it only matches a request that
    carries the geometry payload ref, and honestly indeterminates on
    match today (see `pack.payload_bridge`'s escalated resolver-
    threading residual) -- registering it is safe and probe-free by the
    same rule. `MechStiffnessModel`/`ElecRailModel` (two instances, one
    per rail half) are the closed-form models a freshly scaffolded
    regolith project's `mech.stiffness`/`elec.rail` claims need to have
    ANYTHING to discharge against -- without them no scaffolded project
    can ship (the project's north star: declarative file in, working
    artifact out)."""
    registry.register(FeaStaticStressModel())
    registry.register(FeaStaticDeflectionModel())
    registry.register(FeaStaticDeflectionFromGeometryModel())
    registry.register(MechStiffnessModel())
    registry.register(
        ElecRailModel(
            claim_kind=DEFAULT_RAIL_LO_CLAIM_KIND, sense=ClaimSense.lower_bound()
        )
    )
    registry.register(
        ElecRailModel(
            claim_kind=DEFAULT_RAIL_HI_CLAIM_KIND, sense=ClaimSense.upper_bound()
        )
    )
    registry.register(MemberFlexuralCapacityModel())
    registry.register(MemberAxialCapacityModel())
    registry.register(EulerBucklingLoadModel())
    registry.register(BoltLoadFactorModel())
    registry.register(WeldUtilizationModel())
    registry.register(BearingRatingLifeModel())
    _log.info("feldspar.pack: registered 12 regolith model(s)")


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
