from __future__ import annotations

"""Mesh-as-a-graph-step (WO-12, 09 sec. 4): the WO-08 mesh stage
graduated into a registry edge, plus the static-FEA direction that
consumes the resulting mesh payload.

Two directions:

- `fea.mesh.cantilever`: `geometry.parametric -> mesh` (gmsh). The one
  mesh it produces feeds EVERY downstream consumer (static today, modal
  in M6) through the per-step payload cache, so mesh settings stop
  being private to one solver and the dev loop pays each mesh once
  ever.
- `fea.static_deflection.cantilever_from_mesh`: `mesh + material/load
  scalars -> deflection` (ccx). Single-mesh, declared-ceiling accuracy:
  the WO-08 self-meshing Richardson twin remains registered for
  measured-eps solves; the refinement ladder over mesh payloads is M3
  budget-seeking (09 sec. 3), not this direction's business.

`register(registry, resolver)` takes the orchestrator-provided
`PayloadResolver` (D96/OPEN-2: feldspar never does store IO) and closes
each `SolveFn` over it -- the resolver is per-catalog wiring, never a
module global (AD-4 spirit). It also DECLARES this module's port table
(payload semantics require declared kinds: registration and execution
kind checks both read the declared `Rank.payload(kind)`, exactly as
unit checks read declared units). NOTE (F12 accumulated-table rule):
once these declarations land, any LATER `register()` into the same
registry is checked against the table -- a catalog combining this
module with the declaration-free WO-07/WO-08 modules must call their
`register()` FIRST or declare their ports; the port-table unification
is WO-14 boundary work."""

from feldspar.core import Accuracy, Domain, Interval, PortDecl, Rank
from feldspar.fea import ccx
from feldspar.fea.deck import build_cantilever_deck
from feldspar.fea.geometry import CantileverGeometry, Material
from feldspar.fea.mesh import MeshData, MeshSettings, build_cantilever_mesh
from feldspar.fea.results import max_displacement_magnitude, parse_dat_displacements
from feldspar.logging_setup import get_logger
from feldspar.solve import (
    EXACT,
    Citation,
    Err,
    Ok,
    SolveError,
    SolveOutput,
    SolverRegistry,
    make_direction,
)
from feldspar.solve.digest import canonical_digest
from feldspar.solve.payload import PayloadResolver, resolver_cache_identity

_log = get_logger(__name__)

__all__ = [
    "GEOMETRY_PORT",
    "MESH_PORT",
    "register",
]

#: The cantilever family's parametric-geometry payload port (kind
#: `geometry.parametric`, 09 sec. 4): its content is the frozen
#: `CantileverGeometry` family params as JSON.
# frob:doc docs/modules/fea.md#fea_payload_steps
GEOMETRY_PORT = "mech.geom.cantilever.parametric"

#: The cantilever mesh payload port (kind `mesh`): its content is the
#: gmsh-free `MeshData` arrays as JSON.
# frob:doc docs/modules/fea.md#fea_payload_steps
MESH_PORT = "mech.mesh.cantilever"

# The one fixed mesh level for the M2 graph step (the WO-08 pair's h;
# ladder rungs over payloads are M3 budget-seeking, 09 sec. 3).
_MESH_SETTINGS = MeshSettings(
    family="cantilever", element_type="C3D20", char_length=0.02
)

_DEFAULT_TIMEOUT_S = 600.0  # s -- fine C3D20 solves are slow on CI
# (single-threaded); timeout excluded from settings digests (WO-08 rule).

_GMSH_CITATION = Citation(
    kind="paper",
    ref="Geuzaine, C. and Remacle, J.-F., Gmsh: a three-dimensional "
    "finite element mesh generator, IJNME 79(11), 2009 (transfinite "
    "structured meshing)",
)

_ELEMENT_CITATION = Citation(
    kind="standard",
    ref="CalculiX CrunchiX (ccx) User's Manual, element library: C3D20 "
    "(20-node quadratic brick)",
)

# Declared ceiling for the single-mesh (no Richardson) static direction:
# deliberately LOOSER than the WO-08 measured twin's ceiling, since a
# one-mesh solve carries no convergence evidence of its own.
_STATIC_ACCURACY = {"mech.deflection.tip": Accuracy(eps_abs=1e-4, eps_rel=2e-2)}


def _settings_digest_with_resolver(resolver: PayloadResolver) -> str:
    """The shared `_MESH_SETTINGS` digest, PLUS the resolver's own kind
    (bug fix, cycle-35 WO-118 integration): both payload directions in
    this module close over `resolver` and must never collide in
    `SolveCache` between a no-resolver honest-Err run and a working-
    resolver Ok run over the identical mesh settings (see
    `resolver_cache_identity`'s docstring). ONE home for both
    directions' settings digest, not two copies (house rule)."""
    return canonical_digest(
        {"mesh": _MESH_SETTINGS, "resolver": resolver_cache_identity(resolver)}
    )


def _probe_gmsh():
    """Presence probe for the mesh direction (gmsh only -- ccx is the
    consuming direction's tool, probed separately)."""
    try:
        import gmsh  # noqa: F401
    except (ImportError, OSError):
        # OSError: gmsh installed but a native dependency failed to load.
        _log.info("probe: gmsh unavailable")
        return Err(
            SolveError.ToolMissing(
                tool="gmsh",
                guidance="install the 'mesh' extra: pip install feldspar[mesh]",
            )
        )
    return Ok(None)


def _make_mesh_direction(resolver: PayloadResolver):
    """`fea.mesh.cantilever`: resolve the parametric-geometry payload,
    run the WO-08 structured mesher at the fixed M2 level, and store the
    resulting `MeshData` back through the resolver as the mesh payload.
    Accuracy is EXACT: a payload is exact by reference (09 sec. 4); any
    discretization error is charged where the mesh is CONSUMED."""

    def mesh_fn(x):
        geometry_result = resolver.resolve(x[GEOMETRY_PORT])
        if geometry_result.is_err:
            _log.warning(
                "fea.mesh.cantilever: geometry payload unresolvable: %r",
                geometry_result.err,
            )
            return geometry_result
        geometry = CantileverGeometry.model_validate_json(geometry_result.danger_ok)
        mesh_result = build_cantilever_mesh(geometry, _MESH_SETTINGS)
        if mesh_result.is_err:
            _log.warning("fea.mesh.cantilever: mesh build failed: %r", mesh_result.err)
            return mesh_result
        mesh = mesh_result.danger_ok
        ref = resolver.store(
            "mesh", mesh.model_dump_json().encode(), "fea.mesh.cantilever"
        )
        _log.info(
            "fea.mesh.cantilever: meshed %d nodes / %d elements -> payload %s",
            len(mesh.nodes),
            len(mesh.elements),
            ref.digest,
        )
        return Ok(SolveOutput(values={}, payloads={MESH_PORT: ref}))

    info, fn = make_direction(
        solver_id="fea.mesh.cantilever",
        namespace="fea.mesh",
        inputs=(GEOMETRY_PORT,),
        outputs=(MESH_PORT,),
        # No scalar box: the geometry enters as a payload, and payload-
        # feature domains are execution-time checks (09 sec. 4a).
        domain=Domain({}, {"linear_elastic", "small_deflection"}),
        cost=2.0,
        accuracy=EXACT,
        citations=(_GMSH_CITATION,),
        version="1",
        tier="discretized",
        settings=_settings_digest_with_resolver(resolver),
        fn=mesh_fn,
    )
    fn.probe_tools = _probe_gmsh  # ty: ignore[unresolved-attribute]
    return info, fn


def _make_static_from_mesh_direction(resolver: PayloadResolver):
    """`fea.static_deflection.cantilever_from_mesh`: resolve the mesh
    payload, build the WO-08 deck, run ccx ONCE, and report the declared
    ceiling (no measured eps -- single mesh, no Richardson pair)."""

    def static_fn(x):
        mesh_result = resolver.resolve(x[MESH_PORT])
        if mesh_result.is_err:
            _log.warning(
                "cantilever_from_mesh: mesh payload unresolvable: %r",
                mesh_result.err,
            )
            return mesh_result
        mesh = MeshData.model_validate_json(mesh_result.danger_ok)
        material = Material(
            youngs_modulus=x["mech.material.youngs_modulus"],
            poisson=x["mech.material.poisson"],
            yield_strength=2.5e8,  # nominal; unused by the elastic deck (WO-08 note)
        )
        deck = build_cantilever_deck(mesh, material, x["mech.load.tip_force"])
        run_result = ccx.run_ccx(deck, _DEFAULT_TIMEOUT_S)
        if run_result.is_err:
            _log.warning("cantilever_from_mesh: ccx run failed: %r", run_result.err)
            return run_result
        parsed = parse_dat_displacements(run_result.danger_ok.dat_text)
        if parsed.is_err:
            _log.warning(
                "cantilever_from_mesh: displacement parse failed: %r", parsed.err
            )
            return parsed
        value = max_displacement_magnitude(parsed.danger_ok)
        _log.info("cantilever_from_mesh: max displacement %s", value)
        return Ok(SolveOutput(values={"mech.deflection.tip": value}))

    info, fn = make_direction(
        solver_id="fea.static_deflection.cantilever_from_mesh",
        namespace="fea.static_deflection",
        inputs=(
            MESH_PORT,
            "mech.material.youngs_modulus",
            "mech.material.poisson",
            "mech.load.tip_force",
        ),
        outputs=("mech.deflection.tip",),
        domain=Domain(
            box={
                "mech.material.youngs_modulus": Interval(1e6, 1e13),
                "mech.material.poisson": Interval(0.0, 0.5),
                "mech.load.tip_force": Interval(1.0, 1e6),
            },
            tags={"linear_elastic", "small_deflection"},
        ),
        cost=4.0,
        accuracy=_STATIC_ACCURACY,
        citations=(_ELEMENT_CITATION,),
        version="1",
        tier="discretized",
        settings=_settings_digest_with_resolver(resolver),
        fn=static_fn,
    )
    fn.probe_tools = ccx.probe_tools  # ty: ignore[unresolved-attribute]
    return info, fn


# frob:doc docs/modules/fea.md#fea_payload_steps
def register(registry: SolverRegistry, resolver: PayloadResolver) -> None:
    """Declares this module's OWN port table (the two payload ports --
    payload ports NEED declared kinds; see the module docstring's F12
    ordering note) and registers both payload directions, closed over
    the caller's resolver.

    WO111b composition fix: the shared mech core scalar ports this
    module's directions reference (`mech.material.youngs_modulus`,
    `mech.material.poisson`, `mech.load.tip_force`,
    `mech.deflection.tip`) are NO LONGER declared here -- their one
    F12 home is `feldspar.library.mech.declare_core_ports` (called by
    `library.mech.register`, which registers before this module in
    the one full catalog, `feldspar.catalog.build_engine_catalog`). A
    caller composing this module WITHOUT `library.mech` must call
    `declare_core_ports(registry)` itself before this `register()`
    (this module's own unit tests do so)."""
    ports_result = registry.declare_ports(
        PortDecl(GEOMETRY_PORT, "", Rank.payload("geometry.parametric")),
        PortDecl(MESH_PORT, "", Rank.payload("mesh")),
    )
    _ = ports_result.danger_ok
    for info, fn in (
        _make_mesh_direction(resolver),
        _make_static_from_mesh_direction(resolver),
    ):
        result = registry.register(info, fn)
        _ = result.danger_ok
    _log.info("fea.payload_steps: registered 2 payload directions")
