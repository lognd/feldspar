from __future__ import annotations

"""WO-16 `fea`-marked integration test: the modal tier's acceptance
scenario -- "a mech.first_mode-shaped claim discharges at closed-form
tier on a clean beam and escalates to ccx modal when the margin
demands." Combines three catalogs in one registry (`fea.payload_steps`
for geometry -> mesh, `library.vibe` for the closed-form beam/SDOF
competitors, `fea.modal` for the ccx eigenvalue direction), mirroring
`tests/integration/test_fea_payload_steps.py`'s `DictResolver` fixture
and structure.

Like every other `fea`-marked suite in this repo (WO-08/09/10/12's own
note, `tests/integration/test_fea_payload_steps.py`'s docstring), this
file is written per spec but was NOT executed in the WO-16 sandbox (no
ccx, and no gmsh wheel for this platform) -- the everywhere-runnable
closed-form-only twin is `tests/unit/test_library_vibe.py`, which
exercises the beam/SDOF/GRMS/mask directions end to end without any
external tool."""

import hashlib
from typing import Dict

import pytest
from typani import Err, Ok

from feldspar.core import Interval, PortDecl
from feldspar.fea.geometry import CantileverGeometry
from feldspar.fea.modal import register as register_modal
from feldspar.fea.payload_steps import GEOMETRY_PORT
from feldspar.fea.payload_steps import register as register_payload_steps
from feldspar.library.vibe import FIRST_MODE_PORT
from feldspar.library.vibe import register as register_vibe
from feldspar.plan import PayloadStepCache, execute, plan
from feldspar.solve import PayloadRef, SolveError, SolverRegistry

pytestmark = pytest.mark.fea


class DictResolver:
    """In-memory orchestrator store stand-in (D96/OPEN-2 handle);
    identical to `tests/integration/test_fea_payload_steps.py`'s."""

    def __init__(self) -> None:
        self._blobs: Dict[str, bytes] = {}

    def store(self, kind: str, content: bytes, origin: str) -> PayloadRef:
        digest = hashlib.sha256(content).hexdigest()
        self._blobs[digest] = content
        return PayloadRef(kind=kind, digest=digest, origin=origin)

    def resolve(self, ref: PayloadRef):
        blob = self._blobs.get(ref.digest)
        if blob is None:
            return Err(SolveError.DanglingDigest(digest=ref.digest))
        return Ok(blob)


def _setup() -> tuple[SolverRegistry, DictResolver, PayloadRef]:
    resolver = DictResolver()
    registry = SolverRegistry()
    # Order matters (F12 accumulated-table rule, `vibe.register`'s
    # docstring): payload_steps declares GEOMETRY_PORT/MESH_PORT/
    # material.youngs_modulus/poisson first; the two ports vibe's beam
    # direction needs that neither module declares (length,
    # second_moment) are declared here, once, by the composing catalog
    # -- exactly the composition responsibility both modules' docstrings
    # describe.
    register_payload_steps(registry, resolver)
    assert registry.declare_ports(
        PortDecl("mech.geom.cantilever.length", "m"),
        PortDecl("mech.section.second_moment", "m^4"),
    ).is_ok
    register_vibe(registry, resolver)
    register_modal(registry, resolver)
    registry.freeze()
    geometry = CantileverGeometry(length=0.5, width=0.04, height=0.06)
    geom_ref = resolver.store(
        "geometry.parametric", geometry.model_dump_json().encode(), "test-fixture"
    )
    return registry, resolver, geom_ref


_BEAM_KNOWN = {
    "mech.geom.cantilever.length": Interval(0.5, 0.5),
    "mech.section.second_moment": Interval(0.04 * 0.06**3 / 12, 0.04 * 0.06**3 / 12),
    "mech.material.youngs_modulus": Interval(2.0e11, 2.0e11),
    "mech.material.density": Interval(7850.0, 7850.0),
    "mech.section.area": Interval(0.04 * 0.06, 0.04 * 0.06),
}
_BUDGET = 1e13


def test_first_mode_discharges_at_closed_form_tier_on_a_clean_beam() -> None:
    """Acceptance: a mech.first_mode-shaped claim discharges at
    closed-form tier on a clean beam -- the planner picks the cheap
    beam direction (cost 1e-7) over the ccx modal direction (cost 5.0)
    when both are in-domain, per FINV-8 cost-ordered tier-blind
    selection."""
    registry, _resolver, _geom_ref = _setup()
    route = plan(
        registry, _BEAM_KNOWN, frozenset({"linear_elastic"}), FIRST_MODE_PORT, _BUDGET
    ).danger_ok
    assert [s.solver_id for s in route.steps] == ["mech.beam_cantilever_first_mode"]

    result = execute(route, registry, _BEAM_KNOWN, {})
    assert result.is_ok
    # Steel cantilever, L=0.5 m box section 0.04x0.06 m: expect a
    # physically sane first-mode frequency (tens to low hundreds of Hz).
    assert 1.0 < result.danger_ok.value.midpoint() < 1000.0


def test_first_mode_escalates_to_ccx_modal_when_beam_domain_does_not_admit(
    tmp_path,
) -> None:
    """Acceptance: escalates to ccx modal when the margin demands --
    here, a density outside the closed-form beam direction's declared
    domain box forces the planner onto the ccx modal route instead
    (mesh -> modal), through the same geometry payload the static
    direction already consumes."""
    registry, _resolver, geom_ref = _setup()
    out_of_domain_known = dict(_BEAM_KNOWN)
    # Beam direction's box caps density at 3e4 kg/m^3 (vibe.py); push
    # past it so only the ccx modal direction admits this request.
    out_of_domain_known["mech.material.density"] = Interval(5e4, 5e4)
    payloads = {GEOMETRY_PORT: geom_ref}
    known = {
        "mech.material.youngs_modulus": out_of_domain_known[
            "mech.material.youngs_modulus"
        ],
        "mech.material.density": out_of_domain_known["mech.material.density"],
        "mech.material.poisson": Interval(0.3, 0.3),
    }

    route = plan(
        registry,
        known,
        frozenset({"linear_elastic", "small_deflection"}),
        FIRST_MODE_PORT,
        _BUDGET,
        payloads=payloads,
    ).danger_ok
    assert [s.solver_id for s in route.steps] == [
        "fea.mesh.cantilever",
        "fea.modal.cantilever_from_mesh",
    ]

    step_cache = PayloadStepCache(root=tmp_path / "steps")
    result = execute(route, registry, known, payloads, step_cache)
    assert result.is_ok
    assert result.danger_ok.value.midpoint() > 0.0
