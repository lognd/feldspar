from __future__ import annotations

"""ccx modal direction (WO-16, 07 vibration Phase 3): the discretized
competitor for `mech.vibe.first_mode_freq`, instantiating the 05
pipeline pattern (mesh-as-a-graph-step, `payload_steps.py`) over the
SAME cantilever mesh payload the WO-12 static direction consumes --
one mesh feeds both the static and modal tiers through the shared
per-payload step cache, exactly the M2 mesh step's stated purpose.

Single-mesh, declared-ceiling accuracy (no Richardson pair -- an
eigenvalue extraction has no h/h^2 convergence estimator wired here
yet; that is a natural M3 budget-seeking extension, not required by
this WO's acceptance list, which only needs escalation to happen, not
a measured eps ladder). `register(registry, resolver)` mirrors
`payload_steps.py`'s exact shape: closes over the caller's
`PayloadResolver`, no module-global registry access (AD-4)."""

from feldspar.core import Accuracy, Domain
from feldspar.fea import ccx
from feldspar.fea.deck import build_cantilever_modal_deck
from feldspar.fea.geometry import Material
from feldspar.fea.mesh import MeshData
from feldspar.fea.payload_steps import MESH_PORT
from feldspar.fea.results import first_mode_frequency, parse_dat_frequencies
from feldspar.logging_setup import get_logger
from feldspar.mech.vibe import FIRST_MODE_PORT
from feldspar.solve import Citation, Ok, SolveOutput, SolverRegistry, make_direction
from feldspar.solve.digest import canonical_digest
from feldspar.solve.payload import PayloadResolver

_log = get_logger(__name__)

__all__ = ["register"]

# FIRST_MODE_PORT (Hz) is declared once in `mech/vibe.py` -- both the
# closed-form beam direction there and this ccx direction target it
# (the planner picks whichever is cheaper/in-domain, 04). Re-exported
# via the import above so callers that only need the port name are not
# forced to also import the closed-form module's solver registrations.

_MODAL_CITATION = Citation(
    kind="standard",
    ref="CalculiX CrunchiX (ccx) User's Manual, *FREQUENCY step "
    "(Lanczos eigenvalue extraction)",
)

# Declared ceiling for the single-mesh (no Richardson) modal direction:
# same posture as payload_steps.py's static-from-mesh twin -- a
# one-mesh eigenvalue solve carries no convergence evidence of its own,
# so the ceiling is looser than a measured-eps direction's would be.
_MODAL_ACCURACY = {FIRST_MODE_PORT: Accuracy(eps_abs=0.5, eps_rel=5e-2)}

_DEFAULT_TIMEOUT_S = 600.0  # s -- fine C3D20 solves are slow on CI
# (single-threaded); timeout excluded from settings digests (WO-08 rule).


def _make_modal_direction(resolver: PayloadResolver):
    """`fea.modal.cantilever_from_mesh`: resolve the mesh payload, build
    the WO-16 modal deck, run ccx's `*FREQUENCY` step ONCE, and report
    the first (fundamental) mode's frequency in Hz."""

    def modal_fn(x):
        mesh_result = resolver.resolve(x[MESH_PORT])
        if mesh_result.is_err:
            _log.warning(
                "cantilever_from_mesh (modal): mesh payload unresolvable: %r",
                mesh_result.err,
            )
            return mesh_result
        mesh = MeshData.model_validate_json(mesh_result.danger_ok)
        material = Material(
            youngs_modulus=x["mech.material.youngs_modulus"],
            poisson=x["mech.material.poisson"],
            yield_strength=2.5e8,  # nominal; unused by the modal deck
            density=x["mech.material.density"],
        )
        deck = build_cantilever_modal_deck(mesh, material, num_modes=1)
        run_result = ccx.run_ccx(deck, _DEFAULT_TIMEOUT_S)
        if run_result.is_err:
            _log.warning(
                "cantilever_from_mesh (modal): ccx run failed: %r", run_result.err
            )
            return run_result
        parsed = parse_dat_frequencies(run_result.danger_ok.dat_text)
        if parsed.is_err:
            _log.warning(
                "cantilever_from_mesh (modal): frequency parse failed: %r", parsed.err
            )
            return parsed
        freq_hz = first_mode_frequency(parsed.danger_ok)
        _log.info("cantilever_from_mesh (modal): first mode %s Hz", freq_hz)
        return Ok(SolveOutput(values={FIRST_MODE_PORT: freq_hz}))

    info, fn = make_direction(
        solver_id="fea.modal.cantilever_from_mesh",
        namespace="fea.modal",
        inputs=(
            MESH_PORT,
            "mech.material.youngs_modulus",
            "mech.material.poisson",
            "mech.material.density",
        ),
        outputs=(FIRST_MODE_PORT,),
        # No scalar box on the mesh input (payload); the three material
        # scalars are unconstrained here since the closed-form beam
        # direction (library/vibe.py) already carries the domain box
        # for the same physical inputs -- the ccx direction's box only
        # needs to admit whatever the planner routes to it.
        domain=Domain({}, {"linear_elastic", "small_deflection"}),
        cost=5.0,
        accuracy=_MODAL_ACCURACY,
        citations=(_MODAL_CITATION,),
        version="1",
        tier="discretized",
        settings=canonical_digest({"num_modes": 1}),
        fn=modal_fn,
    )
    fn.probe_tools = ccx.probe_tools  # ty: ignore[unresolved-attribute]
    return info, fn


# frob:waive TEST005 reason="measured 20.0% branch cov on 2026-07-18; register()'s branches gate on gmsh/ccx tool presence (T-0014's documented external-tool floor), neither installed in this sandbox. Backfill T-0014."
# frob:doc docs/modules/fea.md#fea_modal
def register(registry: SolverRegistry, resolver: PayloadResolver) -> None:
    """Registers the ccx modal direction only (WO-16); the port table
    (`FIRST_MODE_PORT`, `mech.material.density`) and the mesh/geometry
    ports are declared by `mech/vibe.py`/`payload_steps.py` -- this
    module follows the same F12 accumulated-table rule those modules
    document (register/declare in a consistent order across a
    catalog)."""
    info, fn = _make_modal_direction(resolver)
    result = registry.register(info, fn)
    _ = result.danger_ok
    _log.info("fea.modal: registered 1 payload direction")
