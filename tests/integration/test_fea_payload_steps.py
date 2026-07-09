from __future__ import annotations

"""WO-12 `fea`-marked integration tests: the REAL gmsh/ccx payload
pipeline through `fea/payload_steps.py` -- a cantilever solve routed
`geometry.parametric -> mesh -> fea` with each stage a registry edge,
same-mesh reuse proven by the step cache's hit count (gmsh runs once
across two executions), and twice-run digest stability.

ALL tests here carry the `fea` marker and are excluded from
`make test`'s default loop (AD-12e: they need a real `ccx` binary and a
real `gmsh` install). Like the WO-08/09/10 fea-marked suites, this file
is written per spec but was NOT executed in the WO-12 sandbox (no ccx,
and no gmsh wheel for this platform) -- the everywhere-runnable stub
twin is tests/unit/test_payload_pipeline.py, which exercises the same
executor/cache/planner machinery end to end."""

import hashlib
from typing import Dict

import pytest
from typani import Err, Ok

from feldspar.core import Interval
from feldspar.fea.geometry import CantileverGeometry
from feldspar.fea.payload_steps import GEOMETRY_PORT
from feldspar.fea.payload_steps import register as register_payload_steps
from feldspar.plan import PayloadStepCache, execute, plan
from feldspar.solve import PayloadRef, SolveError, SolverRegistry

pytestmark = pytest.mark.fea


class DictResolver:
    """In-memory orchestrator store stand-in (D96/OPEN-2 handle)."""

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
    register_payload_steps(registry, resolver)
    registry.freeze()
    geometry = CantileverGeometry(length=0.5, width=0.04, height=0.06)
    geom_ref = resolver.store(
        "geometry.parametric", geometry.model_dump_json().encode(), "test-fixture"
    )
    return registry, resolver, geom_ref


_KNOWN = {
    "mech.material.youngs_modulus": Interval(7.0e10, 7.0e10),
    "mech.material.poisson": Interval(0.33, 0.33),
    "mech.load.tip_force": Interval(1.0e3, 1.0e3),
}
_TAGS = frozenset({"linear_elastic", "small_deflection"})
# Generous: the M1 planner estimates eps via the sum surrogate
# (search.rs module note), so the static direction's eps_rel ceiling
# scales with ~youngs_modulus at PLANNING time; execution's realized
# eps is what a real budget would be checked against.
_BUDGET = 1e10


def test_cantilever_routes_geometry_mesh_fea(tmp_path) -> None:
    """Acceptance: geometry.parametric -> mesh -> fea, each stage a
    registry edge, against the real tools."""
    registry, _resolver, geom_ref = _setup()
    payloads = {GEOMETRY_PORT: geom_ref}

    route = plan(
        registry, _KNOWN, _TAGS, "mech.deflection.tip", _BUDGET, payloads=payloads
    ).danger_ok
    assert [s.solver_id for s in route.steps] == [
        "fea.mesh.cantilever",
        "fea.static_deflection.cantilever_from_mesh",
    ]

    step_cache = PayloadStepCache(root=tmp_path / "steps")
    result = execute(route, registry, _KNOWN, payloads, step_cache)
    assert result.is_ok
    solution = result.danger_ok
    # Euler-Bernoulli oracle for this geometry: F L^3 / (3 E I) ~= 0.66 mm;
    # a coarse single-mesh solve must still land the right decade.
    assert 1e-4 < solution.value.midpoint() < 3e-3


def test_same_mesh_reused_across_executions(tmp_path) -> None:
    """Acceptance: same-mesh reuse by cache-hit count -- the second
    execution's mesh step is a step-cache hit (gmsh runs once ever for
    this geometry payload), even though the load scalars changed."""
    registry, _resolver, geom_ref = _setup()
    payloads = {GEOMETRY_PORT: geom_ref}
    step_cache = PayloadStepCache(root=tmp_path / "steps")

    route = plan(
        registry, _KNOWN, _TAGS, "mech.deflection.tip", _BUDGET, payloads=payloads
    ).danger_ok
    assert execute(route, registry, _KNOWN, payloads, step_cache).is_ok
    assert step_cache.hits == 0

    other_known = dict(_KNOWN)
    other_known["mech.load.tip_force"] = Interval(2.0e3, 2.0e3)
    route2 = plan(
        registry, other_known, _TAGS, "mech.deflection.tip", _BUDGET, payloads=payloads
    ).danger_ok
    assert execute(route2, registry, other_known, payloads, step_cache).is_ok
    # The mesh step's key depends only on the geometry payload digest
    # (its scalar box is empty), so the changed load cannot re-mesh.
    assert step_cache.hits == 1


def test_twice_run_digests_stable(tmp_path) -> None:
    """Acceptance: all digests stable across runs -- route digest, mesh
    payload digest (via identical step-cache entries), and solution
    value."""
    registry, _resolver, geom_ref = _setup()
    payloads = {GEOMETRY_PORT: geom_ref}

    route_a = plan(
        registry, _KNOWN, _TAGS, "mech.deflection.tip", _BUDGET, payloads=payloads
    ).danger_ok
    route_b = plan(
        registry, _KNOWN, _TAGS, "mech.deflection.tip", _BUDGET, payloads=payloads
    ).danger_ok
    assert route_a.digest == route_b.digest

    cache_a = PayloadStepCache(root=tmp_path / "a")
    cache_b = PayloadStepCache(root=tmp_path / "b")
    sol_a = execute(route_a, registry, _KNOWN, payloads, cache_a).danger_ok
    sol_b = execute(route_b, registry, _KNOWN, payloads, cache_b).danger_ok
    assert sol_a.value == sol_b.value
    files_a = sorted(p.name for p in (tmp_path / "a").iterdir())
    files_b = sorted(p.name for p in (tmp_path / "b").iterdir())
    assert files_a == files_b
    for name in files_a:
        assert (tmp_path / "a" / name).read_text() == (
            tmp_path / "b" / name
        ).read_text()
