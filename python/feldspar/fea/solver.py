from __future__ import annotations

"""FEA (discretized-tier) solver directions (WO-08): registers
`fea.static_deflection.cantilever` and `fea.static_stress.cylinder_bore`,
the discretized twins of `library/mech.py`'s closed-form cantilever and
Lame/von-Mises directions. Each direction runs a fixed two-mesh (h, h/2)
Richardson pair through gmsh -> deck -> ccx -> results, reporting a
MEASURED `SolveOutput.measured_eps` that `plan/execute.py`'s
`_make_corner_fn` (WO-06, already landed) uses in place of the declared
`accuracy=` ceiling below -- solver.py only needs to report it, never
apply the override itself (04-routing).

Mirrors `python/feldspar/library/mech.py`'s `register()` pattern exactly:
`SolverInfo`/`SolveFn` pairs are built at import time via `@solver`, and
`register(registry)` just calls `registry.register(*fn.solver_direction)`
for each, checks `.danger_ok`, and logs a count (AD-4: no global registry
access outside `register()`)."""

from typing import Optional

from pydantic import BaseModel, ConfigDict
from typani import Err, Ok

from feldspar.__about__ import __version__
from feldspar.core import Accuracy, Domain, Interval
from feldspar.fea import ccx
from feldspar.fea.deck import build_cantilever_deck, build_cylinder_deck
from feldspar.fea.geometry import CantileverGeometry, CylinderGeometry, Material
from feldspar.fea.ladder import RungCache, climb_richardson_ladder
from feldspar.fea.mesh import MeshSettings, build_cantilever_mesh, build_cylinder_mesh
from feldspar.fea.results import (
    max_displacement_magnitude,
    max_von_mises,
    parse_dat_displacements,
    parse_dat_principal_stresses,
)
from feldspar.fea.richardson import richardson_extrapolate
from feldspar.logging_setup import get_logger
from feldspar.solve import (
    Citation,
    CostCurve,
    CostPoint,
    SolveOutput,
    SolverRegistry,
    solver,
)
from feldspar.solve.digest import canonical_digest
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["SolveSettings", "ToolVersions", "register"]


# ---------------------------------------------------------------------------
# Settings models folded into each direction's fixed, registration-time
# settings_digest (see the module-level fold comment below for the
# tradeoff this encodes).
# ---------------------------------------------------------------------------


class SolveSettings(BaseModel):
    """ccx invocation flags that can change a successful answer.
    `timeout_s` is deliberately EXCLUDED (WO-08 contract): a longer/
    shorter timeout never changes a run that already succeeded, so it
    has no business being part of the settings_digest fold."""

    model_config = ConfigDict(frozen=True)

    omp_num_threads: int = 1


class ToolVersions(BaseModel):
    """Best-effort external tool version strings folded into the
    settings_digest. `gmsh_version` is a fixed "unknown" placeholder --
    gmsh has no cheap version query that doesn't require
    `gmsh.initialize()` (a real mesh-generation side effect we don't
    want to pay at *registration* time, before any solve has even been
    requested). `ccx_version` is ALSO fixed at registration time (see
    the fold-timing note below), not read from a real `CcxRun` -- real
    per-run tool version drift is NOT captured in `settings_digest` at
    v1. This is the same class of limitation as any other registered
    solver's fixed `settings_digest` (SolverInfo.settings_digest is set
    once, at registration, never re-derived per call): the registry has
    no mechanism for a dynamic, per-call digest, so a nominal/placeholder
    ToolVersions is folded here instead of the real one. Acceptable at
    v1; revisit if tool-version-sensitive answers ever matter."""

    model_config = ConfigDict(frozen=True)

    gmsh_version: str
    ccx_version: str
    feldspar_version: str


#: Nominal, registration-time-only tool versions (see `ToolVersions`
#: docstring for why these are fixed placeholders, not real probed
#: values).
_NOMINAL_TOOL_VERSIONS = ToolVersions(
    gmsh_version="unknown",
    ccx_version="unknown",
    feldspar_version=__version__,
)

_DEFAULT_SOLVE_SETTINGS = SolveSettings()

# Fixed two-mesh Richardson pair (05/WO-08 contract): h is a deliberately
# coarse char_length chosen to keep both the coarse and fine run cheap in
# CI/testing while still giving gmsh's transfinite meshing at least a
# handful of elements per axis on the geometries this solver's Domain
# boxes admit; h/2 is the standard Richardson refinement step. Retained
# as the `cylinder_bore` direction's fixed pair (unchanged by WO-13:
# only `cantilever` below grows a full budget-seeking ladder).
_MESH_H = 0.02  # m
_MESH_H2 = 0.01  # m

# WO-13 (09 sec. 3): `cantilever`'s full deterministic refinement ladder
# -- the h/h2 pair above extended with two finer rungs, each halving
# char_length again (same "cheap enough for CI, still resolves gmsh's
# transfinite meshing" rationale as the original pair). Coarsest first;
# `feldspar.fea.ladder.climb_richardson_ladder` climbs in this order.
_MESH_H3 = 0.005  # m
_MESH_H4 = 0.0025  # m

# Axial length of the cylinder family's r-z rectangle: NOT a port (only
# inner_radius/outer_radius are exposed per the 05 port-naming contract),
# so a fixed nominal axial length is chosen and documented here instead.
_CYLINDER_AXIAL_LENGTH = 0.5  # m

# Nominal yield_strength for the `Material` model: not a port (only
# youngs_modulus/poisson are exposed), and unused by the linear-elastic
# ccx deck this module builds (deck.py's `*ELASTIC` block only emits E,
# nu) -- a fixed placeholder satisfies the required `Material` field
# without implying any yield-based behavior.
_NOMINAL_YIELD_STRENGTH = 2.5e8  # Pa

_DEFAULT_TIMEOUT_S = 120.0  # s -- excluded from settings_digest (see SolveSettings)


def _fold_settings_digest(
    mesh_h: MeshSettings,
    mesh_h2: MeshSettings,
    solve_settings: SolveSettings,
    tool_versions: ToolVersions,
) -> str:
    """The ONE settings_digest fold for a discretized direction: both
    mesh levels (h, h/2) + ccx invocation flags + nominal tool versions,
    via `canonical_digest` (AD-5). Exposed as a private module function
    (rather than inlined per direction) so both directions share exactly
    one fold implementation and the FINV-2 unit test can exercise it
    directly without re-deriving the fold logic."""
    return canonical_digest(
        {
            "mesh_h": mesh_h,
            "mesh_h2": mesh_h2,
            "solve_settings": solve_settings,
            "tool_versions": tool_versions,
        }
    )


def _fold_ladder_settings_digest(
    rungs: "tuple[MeshSettings, ...]",
    solve_settings: SolveSettings,
    tool_versions: ToolVersions,
) -> str:
    """WO-13 (09 sec. 3): the ladder-policy twin of `_fold_settings_digest`
    -- folds the FULL ordered rung sequence (not just an h/h2 pair) so
    the settings_digest changes if any rung's char_length changes OR if
    a rung is added/removed (the ladder policy IS part of the settings
    digest per the WO-13 deliverable). `cantilever` uses this; `cylinder
    _bore` keeps the original fixed-pair fold unchanged."""
    return canonical_digest(
        {
            "rungs": rungs,
            "solve_settings": solve_settings,
            "tool_versions": tool_versions,
        }
    )


def _probe_tools():
    """Combined tool-presence probe attached to each registered
    `SolveFn` as `.probe_tools` (cache.py's `_tools_still_consistent`
    convention, `getattr(fn, "probe_tools", None)`): gmsh importability
    first (cheap, no `gmsh.initialize()` needed), then `ccx.probe_tools`
    for the external `ccx` binary."""
    try:
        import gmsh  # noqa: F401
    except ImportError:
        _log.info("probe_tools: gmsh not importable")
        return Err(
            SolveError.ToolMissing(
                tool="gmsh",
                guidance="install the 'mesh' extra: pip install feldspar[mesh]",
            )
        )
    return ccx.probe_tools()


# ---------------------------------------------------------------------------
# Shared citations.
# ---------------------------------------------------------------------------

_ELEMENT_CITATION = Citation(
    kind="standard",
    ref="CalculiX CrunchiX (ccx) User's Manual, element library: C3D20 "
    "(20-node quadratic brick), CAX8 (8-node quadratic axisymmetric "
    "quad)",
)

_RICHARDSON_CITATION = Citation(
    kind="paper",
    ref="Roache, P.J., Verification and Validation in Computational "
    "Science and Engineering, Hermosa Publishers, 1998 (Richardson "
    "extrapolation / grid convergence)",
)

# Declared nominal accuracy ceilings (per output port). This is a
# CEILING only -- `plan/execute.py`'s `_make_corner_fn` (WO-06, already
# landed) replaces it at execution time with the MEASURED Richardson eps
# every `SolveOutput` below actually reports (`measured_eps`), per
# 04-routing's "measured eps overrides declared accuracy" rule. These
# values are placeholders chosen to be loose enough not to falsely claim
# more precision than the two-mesh estimate can actually promise.
_CANTILEVER_ACCURACY = {"mech.deflection.tip": Accuracy(eps_abs=1e-4, eps_rel=1e-2)}
_CYLINDER_ACCURACY = {"mech.stress.von_mises": Accuracy(eps_abs=1e-4, eps_rel=1e-2)}


# ---------------------------------------------------------------------------
# fea.static_deflection.cantilever
# ---------------------------------------------------------------------------

_CANTILEVER_MESH_H = MeshSettings(
    family="cantilever", element_type="C3D20", char_length=_MESH_H
)
_CANTILEVER_MESH_H2 = MeshSettings(
    family="cantilever", element_type="C3D20", char_length=_MESH_H2
)
_CANTILEVER_MESH_H3 = MeshSettings(
    family="cantilever", element_type="C3D20", char_length=_MESH_H3
)
_CANTILEVER_MESH_H4 = MeshSettings(
    family="cantilever", element_type="C3D20", char_length=_MESH_H4
)

# WO-13 (09 sec. 3): the full deterministic ladder, coarsest first --
# `climb_richardson_ladder` walks this in order, Richardson-pairing each
# new rung against the previous one, stopping the first pair whose eps
# fits the caller's remaining budget.
_CANTILEVER_LADDER = (
    _CANTILEVER_MESH_H,
    _CANTILEVER_MESH_H2,
    _CANTILEVER_MESH_H3,
    _CANTILEVER_MESH_H4,
)

_CANTILEVER_SETTINGS_DIGEST = _fold_ladder_settings_digest(
    _CANTILEVER_LADDER,
    _DEFAULT_SOLVE_SETTINGS,
    _NOMINAL_TOOL_VERSIONS,
)

# WO-13 cost curve (09 sec. 3, additive schema -- the planner still
# reads only the scalar `cost=5.0` below, unchanged): nominal, relative
# nominal-order-of-magnitude declared points, one per achievable rung
# pair, in the same placeholder spirit as `_CANTILEVER_ACCURACY`'s fixed
# ceiling -- cost climbs as the required eps tightens, mirroring the
# ladder's actual (mesh_h, mesh_h2), (mesh_h2, mesh_h3), (mesh_h3,
# mesh_h4) Richardson pairs.
_CANTILEVER_COST_CURVE = CostCurve(
    points=(
        CostPoint(eps=1e-5, cost=20.0),
        CostPoint(eps=1e-4, cost=10.0),
        CostPoint(eps=1e-3, cost=5.0),
    )
)

# WO-13: per-rung result cache shared across calls in this process (09
# sec. 3 "a later request with a looser budget reuses the h solve and
# skips h/2" -- the dev-loop-pays-each-mesh-once-ever property). Module-
# level and mutable by design (mirrors `PayloadStepCache`'s own
# process-lifetime, injectable-elsewhere shape; tests construct their
# own `RungCache()` to observe hit/miss counts in isolation).
_CANTILEVER_RUNG_CACHE = RungCache()


@solver(
    namespace="fea.static_deflection",
    inputs=(
        "mech.geom.cantilever.length",
        "mech.geom.cantilever.width",
        "mech.geom.cantilever.height",
        "mech.material.youngs_modulus",
        "mech.material.poisson",
        "mech.load.tip_force",
    ),
    outputs=("mech.deflection.tip",),
    domain=Domain(
        box={
            "mech.geom.cantilever.length": Interval(1e-3, 10.0),
            "mech.geom.cantilever.width": Interval(1e-4, 1.0),
            "mech.geom.cantilever.height": Interval(1e-4, 1.0),
            "mech.material.youngs_modulus": Interval(1e6, 1e13),
            "mech.material.poisson": Interval(0.0, 0.5),
            "mech.load.tip_force": Interval(1.0, 1e6),
        },
        tags={"linear_elastic", "small_deflection"},
    ),
    cost=5.0,
    accuracy=_CANTILEVER_ACCURACY,
    citations=(_ELEMENT_CITATION, _RICHARDSON_CITATION),
    version="1",
    tier="discretized",
    settings=_CANTILEVER_SETTINGS_DIGEST,
    deterministic=True,
    eps_seeking=True,
    cost_curve=_CANTILEVER_COST_CURVE,
)
def cantilever(x, eps_budget: Optional[float] = None):
    geometry = CantileverGeometry(
        length=x["mech.geom.cantilever.length"],
        width=x["mech.geom.cantilever.width"],
        height=x["mech.geom.cantilever.height"],
    )
    material = Material(
        youngs_modulus=x["mech.material.youngs_modulus"],
        poisson=x["mech.material.poisson"],
        yield_strength=_NOMINAL_YIELD_STRENGTH,
    )
    tip_force = x["mech.load.tip_force"]

    def _run_rung(settings: MeshSettings):
        mesh_result = build_cantilever_mesh(geometry, settings)
        if mesh_result.is_err:
            _log.warning(
                "cantilever: mesh build failed at char_length=%s: %r",
                settings.char_length,
                mesh_result.err,
            )
            return Err(mesh_result.danger_err)
        mesh = mesh_result.danger_ok
        _log.info(
            "cantilever: mesh built at char_length=%s (%d nodes, %d elements)",
            settings.char_length,
            len(mesh.nodes),
            len(mesh.elements),
        )

        deck = build_cantilever_deck(mesh, material, tip_force)
        run_result = ccx.run_ccx(deck, _DEFAULT_TIMEOUT_S)
        if run_result.is_err:
            _log.warning(
                "cantilever: ccx run failed at char_length=%s: %r",
                settings.char_length,
                run_result.err,
            )
            return Err(run_result.danger_err)
        run = run_result.danger_ok
        _log.info(
            "cantilever: ccx run completed at char_length=%s in %.3fs",
            settings.char_length,
            run.elapsed_s,
        )

        parsed = parse_dat_displacements(run.dat_text)
        if parsed.is_err:
            _log.warning(
                "cantilever: displacement parse failed at char_length=%s: %r",
                settings.char_length,
                parsed.err,
            )
            return Err(parsed.danger_err)
        value = max_displacement_magnitude(parsed.danger_ok)
        _log.info(
            "cantilever: max_displacement_magnitude at char_length=%s -> %s",
            settings.char_length,
            value,
        )
        return Ok(value)

    climb = climb_richardson_ladder(
        _CANTILEVER_LADDER,
        _run_rung,
        eps_budget,
        solver_id="fea.static_deflection.cantilever",
        version="1",
        box={k: x[k] for k in sorted(x)},
        rung_cache=_CANTILEVER_RUNG_CACHE,
    )
    if climb.is_err:
        return Err(climb.danger_err)
    extrapolated, eps, rungs_used = climb.danger_ok
    _log.info(
        "cantilever: ladder climb extrapolated=%s eps=%s rungs_used=%d budget=%s",
        extrapolated,
        eps,
        rungs_used,
        eps_budget,
    )
    return Ok(
        SolveOutput(
            values={"mech.deflection.tip": extrapolated},
            measured_eps=eps,
        )
    )


# ---------------------------------------------------------------------------
# fea.static_stress.cylinder_bore
# ---------------------------------------------------------------------------

_CYLINDER_MESH_H = MeshSettings(
    family="cylinder", element_type="CAX8", char_length=_MESH_H
)
_CYLINDER_MESH_H2 = MeshSettings(
    family="cylinder", element_type="CAX8", char_length=_MESH_H2
)

_CYLINDER_SETTINGS_DIGEST = _fold_settings_digest(
    _CYLINDER_MESH_H,
    _CYLINDER_MESH_H2,
    _DEFAULT_SOLVE_SETTINGS,
    _NOMINAL_TOOL_VERSIONS,
)


@solver(
    namespace="fea.static_stress",
    inputs=(
        "mech.load.internal_pressure",
        "mech.geom.cylinder.inner_radius",
        "mech.geom.cylinder.outer_radius",
        "mech.material.youngs_modulus",
        "mech.material.poisson",
    ),
    outputs=("mech.stress.von_mises",),
    domain=Domain(
        box={
            "mech.load.internal_pressure": Interval(1.0, 1e9),
            "mech.geom.cylinder.inner_radius": Interval(1e-3, 5.0),
            "mech.geom.cylinder.outer_radius": Interval(1e-3, 5.0),
            "mech.material.youngs_modulus": Interval(1e6, 1e13),
            "mech.material.poisson": Interval(0.0, 0.5),
        },
        tags={"linear_elastic"},
    ),
    cost=5.0,
    accuracy=_CYLINDER_ACCURACY,
    citations=(_ELEMENT_CITATION, _RICHARDSON_CITATION),
    version="1",
    tier="discretized",
    settings=_CYLINDER_SETTINGS_DIGEST,
    deterministic=True,
)
def cylinder_bore(x):
    geometry = CylinderGeometry(
        inner_radius=x["mech.geom.cylinder.inner_radius"],
        outer_radius=x["mech.geom.cylinder.outer_radius"],
        length=_CYLINDER_AXIAL_LENGTH,
    )
    material = Material(
        youngs_modulus=x["mech.material.youngs_modulus"],
        poisson=x["mech.material.poisson"],
        yield_strength=_NOMINAL_YIELD_STRENGTH,
    )
    pressure = x["mech.load.internal_pressure"]

    values = []
    for settings in (_CYLINDER_MESH_H, _CYLINDER_MESH_H2):
        mesh_result = build_cylinder_mesh(geometry, settings)
        if mesh_result.is_err:
            _log.warning(
                "cylinder_bore: mesh build failed at char_length=%s: %r",
                settings.char_length,
                mesh_result.err,
            )
            return Err(mesh_result.danger_err)
        mesh = mesh_result.danger_ok
        _log.info(
            "cylinder_bore: mesh built at char_length=%s (%d nodes, %d elements)",
            settings.char_length,
            len(mesh.nodes),
            len(mesh.elements),
        )

        deck = build_cylinder_deck(mesh, material, pressure)
        run_result = ccx.run_ccx(deck, _DEFAULT_TIMEOUT_S)
        if run_result.is_err:
            _log.warning(
                "cylinder_bore: ccx run failed at char_length=%s: %r",
                settings.char_length,
                run_result.err,
            )
            return Err(run_result.danger_err)
        run = run_result.danger_ok
        _log.info(
            "cylinder_bore: ccx run completed at char_length=%s in %.3fs",
            settings.char_length,
            run.elapsed_s,
        )

        parsed = parse_dat_principal_stresses(run.dat_text)
        if parsed.is_err:
            _log.warning(
                "cylinder_bore: stress parse failed at char_length=%s: %r",
                settings.char_length,
                parsed.err,
            )
            return Err(parsed.danger_err)
        value = max_von_mises(parsed.danger_ok)
        _log.info(
            "cylinder_bore: max_von_mises at char_length=%s -> %s",
            settings.char_length,
            value,
        )
        values.append(value)

    result = richardson_extrapolate(values[0], values[1])
    _log.info(
        "cylinder_bore: richardson extrapolated=%s eps=%s fallback_used=%s",
        result.extrapolated,
        result.eps,
        result.fallback_used,
    )
    return Ok(
        SolveOutput(
            values={"mech.stress.von_mises": result.extrapolated},
            measured_eps=result.eps,
        )
    )


# Attach the combined gmsh+ccx presence probe (cache.py's `probe_tools`
# convention) onto each registered `SolveFn` -- the object actually
# stored in `fn.solver_direction[1]` (the `_build.wrap_solve_fn`-wrapped
# callable), not the raw decorated function, since that wrapped object is
# what `registry.register(*fn.solver_direction)` puts in the registry and
# what `plan/cache.py`'s `_tools_still_consistent` looks up by solver_id.
cantilever.solver_direction[1].probe_tools = _probe_tools  # ty: ignore[unresolved-attribute]
cylinder_bore.solver_direction[1].probe_tools = _probe_tools  # ty: ignore[unresolved-attribute]


def register(registry: SolverRegistry) -> None:
    """Registers both FEA (discretized-tier) directions (WO-08)."""
    result_a = registry.register(*cantilever.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_a.danger_ok
    result_b = registry.register(*cylinder_bore.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_b.danger_ok
    _log.info("fea: registered %d solver directions", 2)
