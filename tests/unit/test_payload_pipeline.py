from __future__ import annotations

"""WO-12 payload-pipeline tests: the acceptance cantilever shape
(geometry.parametric -> mesh -> fea, each stage a registry edge) built
from stub solvers so it runs everywhere (no gmsh/ccx; the real-tool
twin is tests/integration/test_fea_payload_steps.py, `fea`-marked).

Covers the 02-edge-cases "Payload ports (WO-12)" pipeline rows:
execution kind mismatch, missing payload, dangling digest, payload in
a digest is its hash (twice-run equality), same-mesh reuse by cache-hit
count, tier-blindness with payload edges, and the 09 sec. 4a
abstraction-edge reroute."""

import hashlib
import json
from typing import Dict, Tuple

from typani import Err, Ok

from feldspar.core import Interval, PortDecl, Rank
from feldspar.plan import PayloadStepCache, execute, plan, solve
from feldspar.plan.cache import request_digest
from feldspar.plan.execute import execute_with_attribution
from feldspar.solve import (
    EXACT,
    ClaimSenses,
    PayloadRef,
    SolveError,
    SolveOutput,
    SolverRegistry,
    payload_feature_violation,
    solver,
)

GEOM_PORT = "mech.geom.cantilever.parametric"
REALIZED_PORT = "mech.geom.cantilever.realized"
MESH_PORT = "mech.mesh.cantilever"
E_PORT = "mech.material.youngs_modulus"
F_PORT = "mech.load.tip_force"
DEFL_PORT = "mech.deflection.tip"
FREQ_PORT = "mech.freq.fundamental"

_CITATION = ("handbook: Roark's Formulas for Stress and Strain, 9e",)


class DictResolver:
    """In-memory orchestrator store stand-in (the D96/OPEN-2 handle):
    content-addressed via sha256, which is the STORE's discipline --
    feldspar never re-derives payload hashes."""

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


def _geometry_ref(resolver: DictResolver, length: float = 0.1) -> PayloadRef:
    content = json.dumps(
        {"length": length, "width": 0.02, "height": 0.005}, sort_keys=True
    ).encode()
    return resolver.store("geometry.parametric", content, "test-fixture")


def _declare_ports(registry: SolverRegistry) -> None:
    result = registry.declare_ports(
        PortDecl(GEOM_PORT, "", Rank.payload("geometry.parametric")),
        PortDecl(REALIZED_PORT, "", Rank.payload("geometry.realized")),
        PortDecl(MESH_PORT, "", Rank.payload("mesh")),
        PortDecl(E_PORT, "Pa"),
        PortDecl(F_PORT, "N"),
        PortDecl(DEFL_PORT, "m"),
        PortDecl(FREQ_PORT, "Hz"),
    )
    assert result.is_ok


def _build_registry(
    resolver: DictResolver,
    mesh_tier: str = "discretized",
    fea_tier: str = "discretized",
) -> Tuple[SolverRegistry, Dict[str, int]]:
    """The stub cantilever graph: meshgen (geometry.parametric -> mesh),
    static FEA (mesh -> deflection), and modal (mesh -> frequency, the
    'one mesh feeds multiple solves' second consumer). `counts` tracks
    raw solver invocations so mesh reuse is provable independently of
    the cache's own counters."""
    registry = SolverRegistry()
    _declare_ports(registry)
    counts = {"mesh": 0, "static": 0, "modal": 0}

    @solver(
        namespace="meshgen",
        inputs=(GEOM_PORT,),
        outputs=(MESH_PORT,),
        domain={},
        cost=5.0,
        accuracy=EXACT,
        citations=_CITATION,
        version="1",
        tier=mesh_tier,
    )
    def cantilever_mesh(x):
        counts["mesh"] += 1
        resolved = resolver.resolve(x[GEOM_PORT])
        if resolved.is_err:
            return resolved
        params = json.loads(resolved.danger_ok)
        # Deterministic stand-in for gmsh: the "mesh" is derived purely
        # from the geometry content.
        mesh_content = json.dumps(
            {"cells": int(params["length"] * 1000), "order": 2}, sort_keys=True
        ).encode()
        ref = resolver.store("mesh", mesh_content, "meshgen.cantilever_mesh")
        return Ok(SolveOutput(values={}, payloads={MESH_PORT: ref}))

    @solver(
        namespace="fea.static_deflection",
        inputs=(MESH_PORT, E_PORT, F_PORT),
        outputs=(DEFL_PORT,),
        domain={E_PORT: (1e9, 1e12), F_PORT: (1.0, 1e4)},
        cost=10.0,
        accuracy=EXACT,
        citations=_CITATION,
        version="1",
        tier=fea_tier,
    )
    def cantilever_static(x):
        counts["static"] += 1
        resolved = resolver.resolve(x[MESH_PORT])
        if resolved.is_err:
            return resolved
        mesh = json.loads(resolved.danger_ok)
        return Ok(
            SolveOutput(values={DEFL_PORT: x[F_PORT] / x[E_PORT] * mesh["cells"] * 1e3})
        )

    @solver(
        namespace="fea.modal",
        inputs=(MESH_PORT, E_PORT),
        outputs=(FREQ_PORT,),
        domain={E_PORT: (1e9, 1e12)},
        cost=10.0,
        accuracy=EXACT,
        citations=_CITATION,
        version="1",
        tier=fea_tier,
    )
    def cantilever_modal(x):
        counts["modal"] += 1
        resolved = resolver.resolve(x[MESH_PORT])
        if resolved.is_err:
            return resolved
        mesh = json.loads(resolved.danger_ok)
        return Ok(SolveOutput(values={FREQ_PORT: 100.0 + mesh["cells"]}))

    for fn in (cantilever_mesh, cantilever_static, cantilever_modal):
        assert registry.register(*fn.solver_direction).is_ok
    registry.freeze()
    return registry, counts


_KNOWN = {E_PORT: Interval(200e9, 200e9), F_PORT: Interval(100.0, 100.0)}
_BUDGET = 10.0


class TestCantileverRoute:
    def test_routes_geometry_to_mesh_to_fea(self) -> None:
        """Acceptance: geometry.parametric -> mesh -> fea, each stage a
        registry edge; digests stable across runs."""
        resolver = DictResolver()
        registry, counts = _build_registry(resolver)
        geom = _geometry_ref(resolver)

        result = plan(
            registry,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            payloads={GEOM_PORT: geom},
        )
        assert result.is_ok
        route = result.danger_ok
        assert [s.solver_id for s in route.steps] == [
            "meshgen.cantilever_mesh",
            "fea.static_deflection.cantilever_static",
        ]

        executed = execute(route, registry, _KNOWN, payloads={GEOM_PORT: geom})
        assert executed.is_ok
        solution = executed.danger_ok
        assert solution.value.lo == solution.value.hi  # point inputs
        assert counts["mesh"] == 1 and counts["static"] == 1

        # All digests stable across runs (acceptance).
        rerun = plan(
            registry,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            payloads={GEOM_PORT: geom},
        )
        assert rerun.danger_ok.digest == route.digest
        req1 = request_digest(
            _KNOWN, frozenset(), DEFL_PORT, _BUDGET, ClaimSenses.BOTH, {GEOM_PORT: geom}
        )
        req2 = request_digest(
            _KNOWN, frozenset(), DEFL_PORT, _BUDGET, ClaimSenses.BOTH, {GEOM_PORT: geom}
        )
        assert req1 == req2

    def test_planner_remains_tier_blind_with_payload_edges(self) -> None:
        """Acceptance/FINV-8: permuting tier labels on the payload edges
        changes no Route."""
        resolver = DictResolver()
        registry_a, _ = _build_registry(resolver, mesh_tier="discretized")
        registry_b, _ = _build_registry(resolver, mesh_tier="table", fea_tier="reduced")
        geom = _geometry_ref(resolver)
        route_a = plan(
            registry_a,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            payloads={GEOM_PORT: geom},
        ).danger_ok
        route_b = plan(
            registry_b,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            payloads={GEOM_PORT: geom},
        ).danger_ok
        assert route_a.digest == route_b.digest

    # frob:tests python/feldspar/plan/cache.py::request_digest kind="unit"
    def test_payload_in_digest_is_its_hash(self) -> None:
        """FINV-12: two different geometry payloads -> different request
        digests; the ref's `origin` provenance does NOT fold."""
        resolver = DictResolver()
        geom_a = _geometry_ref(resolver, length=0.1)
        geom_b = _geometry_ref(resolver, length=0.2)
        base = (_KNOWN, frozenset(), DEFL_PORT, _BUDGET, ClaimSenses.BOTH)
        assert request_digest(*base, {GEOM_PORT: geom_a}) != request_digest(
            *base, {GEOM_PORT: geom_b}
        )
        relabeled = PayloadRef(
            kind=geom_a.kind, digest=geom_a.digest, origin="different-origin"
        )
        assert request_digest(*base, {GEOM_PORT: geom_a}) == request_digest(
            *base, {GEOM_PORT: relabeled}
        )


class TestSameMeshReuse:
    def test_one_mesh_feeds_static_and_modal(self, tmp_path) -> None:
        """Acceptance: same-mesh reuse proven by cache-hit count -- the
        modal solve's mesh step is a step-cache hit, gmsh's stand-in
        runs exactly once (modal-ready assert, 09 sec. 4)."""
        resolver = DictResolver()
        registry, counts = _build_registry(resolver)
        geom = _geometry_ref(resolver)
        step_cache = PayloadStepCache(root=tmp_path / "steps")
        payloads = {GEOM_PORT: geom}

        static_route = plan(
            registry, _KNOWN, frozenset(), DEFL_PORT, _BUDGET, payloads=payloads
        ).danger_ok
        static = execute(
            registry=registry,
            route=static_route,
            known=_KNOWN,
            payloads=payloads,
            step_cache=step_cache,
        )
        assert static.is_ok
        assert counts["mesh"] == 1
        assert step_cache.hits == 0

        modal_route = plan(
            registry, _KNOWN, frozenset(), FREQ_PORT, _BUDGET, payloads=payloads
        ).danger_ok
        modal = execute(
            registry=registry,
            route=modal_route,
            known=_KNOWN,
            payloads=payloads,
            step_cache=step_cache,
        )
        assert modal.is_ok
        # The mesh step was served from the step cache: no second run.
        assert counts["mesh"] == 1
        assert step_cache.hits == 1
        assert counts["modal"] == 1

    def test_twice_run_step_key_and_mesh_digest_equal(self, tmp_path) -> None:
        """Twice-run digest equality (WO-12 deliverable): re-executing
        the same request reproduces the same mesh payload digest."""
        resolver = DictResolver()
        registry, _ = _build_registry(resolver)
        geom = _geometry_ref(resolver)
        payloads = {GEOM_PORT: geom}
        route = plan(
            registry, _KNOWN, frozenset(), DEFL_PORT, _BUDGET, payloads=payloads
        ).danger_ok

        cache_a = PayloadStepCache(root=tmp_path / "a")
        cache_b = PayloadStepCache(root=tmp_path / "b")
        assert execute(route, registry, _KNOWN, payloads, cache_a).is_ok
        assert execute(route, registry, _KNOWN, payloads, cache_b).is_ok
        files_a = sorted(p.name for p in (tmp_path / "a").iterdir())
        files_b = sorted(p.name for p in (tmp_path / "b").iterdir())
        assert files_a == files_b  # identical step keys
        for name in files_a:
            assert (tmp_path / "a" / name).read_text() == (
                tmp_path / "b" / name
            ).read_text()  # identical entries, incl. the mesh ref digest


class TestPayloadErrorValues:
    def test_missing_payload_is_error_value(self) -> None:
        """02-edge-cases WO-12: a declared payload port with no supplied
        ref -> Err(MissingPayload), never a KeyError."""
        resolver = DictResolver()
        registry, _ = _build_registry(resolver)
        geom = _geometry_ref(resolver)
        route = plan(
            registry,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            payloads={GEOM_PORT: geom},
        ).danger_ok
        result = execute(route, registry, _KNOWN)  # payloads NOT passed
        assert result.is_err
        assert result.danger_err == SolveError.MissingPayload(port=GEOM_PORT)

    # frob:tests python/feldspar/solve/errors.py::SolveError.PayloadKindMismatch kind="unit"
    def test_kind_mismatch_at_execution(self) -> None:
        """02-edge-cases WO-12: a wrong-kind ref at a declared payload
        port -> Err(PayloadKindMismatch) naming both kinds."""
        resolver = DictResolver()
        registry, _ = _build_registry(resolver)
        geom = _geometry_ref(resolver)
        route = plan(
            registry,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            payloads={GEOM_PORT: geom},
        ).danger_ok
        wrong = resolver.store("spectrum", b"not-geometry", "test")
        result = execute(route, registry, _KNOWN, payloads={GEOM_PORT: wrong})
        assert result.is_err
        assert result.danger_err == SolveError.PayloadKindMismatch(
            port=GEOM_PORT,
            expected_kind="geometry.parametric",
            actual_kind="spectrum",
        )

    # frob:tests python/feldspar/plan/execute.py::execute_with_attribution kind="unit"
    def test_dangling_digest_surfaces_as_error_value(self) -> None:
        """02-edge-cases WO-12: a ref whose hash the store cannot
        resolve -> the solver's Err(DanglingDigest) surfaces with
        attribution, never an exception."""
        resolver = DictResolver()
        registry, _ = _build_registry(resolver)
        dangling = PayloadRef(
            kind="geometry.parametric", digest="0" * 64, origin="gone"
        )
        route = plan(
            registry,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            payloads={GEOM_PORT: dangling},
        ).danger_ok
        result = execute_with_attribution(
            route, registry, _KNOWN, payloads={GEOM_PORT: dangling}
        )
        assert result.is_err
        solver_id, err = result.danger_err
        assert solver_id == "meshgen.cantilever_mesh"
        assert err == SolveError.DanglingDigest(digest="0" * 64)

    def test_payload_output_missing_from_solveoutput(self) -> None:
        """A declared payload output absent from SolveOutput.payloads is
        MissingOutput (A-4 extended to the payload channel)."""
        registry = SolverRegistry()
        _declare_ports(registry)

        @solver(
            namespace="meshgen",
            inputs=(GEOM_PORT,),
            outputs=(MESH_PORT,),
            domain={},
            cost=1.0,
            accuracy=EXACT,
            citations=_CITATION,
            version="1",
        )
        def forgetful_mesh(x):
            return Ok(SolveOutput(values={}))  # payloads channel empty

        assert registry.register(*forgetful_mesh.solver_direction).is_ok
        registry.freeze()
        resolver = DictResolver()
        geom = _geometry_ref(resolver)
        route = plan(
            registry, {}, frozenset(), MESH_PORT, _BUDGET, payloads={GEOM_PORT: geom}
        )
        # MESH_PORT is a payload target: still plannable, and execution
        # surfaces the missing payload output as an error value.
        assert route.is_ok
        result = execute(route.danger_ok, registry, {}, payloads={GEOM_PORT: geom})
        assert result.is_err
        assert result.danger_err == SolveError.MissingOutput(port=MESH_PORT)

    def test_payload_output_varying_across_corners_rejected(self) -> None:
        """A payload output that depends on a swept scalar corner breaks
        exact-by-reference (09 sec. 4): Err(InvalidMeasurement), never a
        silently-picked corner's ref."""
        registry = SolverRegistry()
        _declare_ports(registry)
        resolver = DictResolver()

        @solver(
            namespace="meshgen",
            inputs=(F_PORT,),  # a real interval: two corners
            outputs=(MESH_PORT,),
            domain={F_PORT: (1.0, 1e4)},
            cost=1.0,
            accuracy=EXACT,
            citations=_CITATION,
            version="1",
        )
        def corner_dependent_mesh(x):
            content = json.dumps({"force": x[F_PORT]}).encode()
            ref = resolver.store("mesh", content, "corner-dependent")
            return Ok(SolveOutput(values={}, payloads={MESH_PORT: ref}))

        assert registry.register(*corner_dependent_mesh.solver_direction).is_ok
        registry.freeze()
        known = {F_PORT: Interval(10.0, 20.0)}  # non-degenerate: 2 corners
        route = plan(registry, known, frozenset(), MESH_PORT, _BUDGET)
        assert route.is_ok
        result = execute(route.danger_ok, registry, known)
        assert result.is_err
        assert result.danger_err.kind == "InvalidMeasurement"


class TestAbstractionEdge:
    """09 sec. 4a: execution-time domain checks over payload features;
    optimistic planning; deterministic reroute to the next tier."""

    def _build(self, resolver: DictResolver) -> Tuple[SolverRegistry, Dict[str, int]]:
        registry = SolverRegistry()
        _declare_ports(registry)
        counts = {"abstraction": 0, "fea": 0}

        @solver(
            namespace="abstract",
            inputs=(REALIZED_PORT, E_PORT, F_PORT),
            outputs=(DEFL_PORT,),
            domain={E_PORT: (1e9, 1e12), F_PORT: (1.0, 1e4)},
            cost=1.0,  # cheap: the planner tries it first (optimistic)
            accuracy=EXACT,
            citations=_CITATION,
            version="1",
            conservative_for="upper",
        )
        def cantilever_family(x):
            counts["abstraction"] += 1
            resolved = resolver.resolve(x[REALIZED_PORT])
            if resolved.is_err:
                return resolved
            features = json.loads(resolved.danger_ok)
            if features["hole_in_root"]:
                return Err(
                    SolveError.OutOfDomain(
                        violation=payload_feature_violation(
                            REALIZED_PORT, "hole_in_root_band"
                        )
                    )
                )
            return Ok({DEFL_PORT: x[F_PORT] / x[E_PORT]})

        @solver(
            namespace="fea.static_deflection",
            inputs=(REALIZED_PORT, E_PORT, F_PORT),
            outputs=(DEFL_PORT,),
            domain={E_PORT: (1e9, 1e12), F_PORT: (1.0, 1e4)},
            cost=100.0,  # the expensive escape tier
            accuracy=EXACT,
            citations=_CITATION,
            version="1",
            tier="discretized",
            conservative_for="upper",
        )
        def on_realized(x):
            counts["fea"] += 1
            return Ok({DEFL_PORT: 2.0 * x[F_PORT] / x[E_PORT]})

        for fn in (cantilever_family, on_realized):
            assert registry.register(*fn.solver_direction).is_ok
        registry.freeze()
        return registry, counts

    def _realized_ref(self, resolver: DictResolver, hole: bool) -> PayloadRef:
        content = json.dumps({"hole_in_root": hole}, sort_keys=True).encode()
        return resolver.store("geometry.realized", content, "cad-export")

    def test_clean_geometry_resolves_on_cheap_edge(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        resolver = DictResolver()
        registry, counts = self._build(resolver)
        clean = self._realized_ref(resolver, hole=False)
        result = solve(
            registry,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            sense="upper",
            payloads={REALIZED_PORT: clean},
        )
        assert result.is_ok
        assert counts == {"abstraction": 1, "fea": 0}
        assert result.danger_ok.attempts == ()

    def test_out_of_domain_payload_reroutes_to_fea(self, monkeypatch, tmp_path) -> None:
        """The G7 escape: the hole invades the root band, the
        abstraction edge returns OutOfDomain as a VALUE, and the
        fallback reroute lands on FEA-on-realized -- deterministically."""
        monkeypatch.chdir(tmp_path)
        resolver = DictResolver()
        registry, counts = self._build(resolver)
        holed = self._realized_ref(resolver, hole=True)

        result = solve(
            registry,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            sense="upper",
            payloads={REALIZED_PORT: holed},
        )
        assert result.is_ok
        solution = result.danger_ok
        assert counts == {"abstraction": 1, "fea": 1}
        assert len(solution.attempts) == 1
        assert solution.attempts[0].error_kind == "OutOfDomain"
        assert solution.attempts[0].failed_solver_id == "abstract.cantilever_family"
        assert solution.route.steps[-1].solver_id == "fea.static_deflection.on_realized"

        # Determinism: same payload digest -> same check result, same
        # route, same value (09 sec. 4a).
        rerun = solve(
            registry,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            sense="upper",
            payloads={REALIZED_PORT: holed},
            policy=None,
        )
        assert rerun.is_ok
        assert rerun.danger_ok.route.digest == solution.route.digest
        assert rerun.danger_ok.value == solution.value

    def test_conservative_for_honored_over_payload_edges(self) -> None:
        """A one-sided (upper) abstraction edge is absent for a lower-
        sense request (A-3/G4 unchanged by payloads)."""
        resolver = DictResolver()
        registry, _ = self._build(resolver)
        clean = self._realized_ref(resolver, hole=False)
        result = plan(
            registry,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            sense="lower",
            payloads={REALIZED_PORT: clean},
        )
        assert result.is_err  # both edges are upper-only


class TestSolveFacadeWithPayloads:
    def test_solve_end_to_end_and_solution_cache(self, monkeypatch, tmp_path) -> None:
        """solve() threads payloads through plan/execute/cache: second
        identical call is a solution-cache hit; a different geometry
        payload is NOT (the payload hash re-keys the request)."""
        monkeypatch.chdir(tmp_path)
        resolver = DictResolver()
        registry, counts = _build_registry(resolver)
        geom = _geometry_ref(resolver, length=0.1)

        r1 = solve(
            registry,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            payloads={GEOM_PORT: geom},
        )
        assert r1.is_ok and not r1.danger_ok.cache_hit
        r2 = solve(
            registry,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            payloads={GEOM_PORT: geom},
        )
        assert r2.is_ok and r2.danger_ok.cache_hit
        assert counts["static"] == 1  # served from the solution cache

        other_geom = _geometry_ref(resolver, length=0.2)
        r3 = solve(
            registry,
            _KNOWN,
            frozenset(),
            DEFL_PORT,
            _BUDGET,
            payloads={GEOM_PORT: other_geom},
        )
        assert r3.is_ok and not r3.danger_ok.cache_hit
        assert r3.danger_ok.value != r1.danger_ok.value


class TestFeaPayloadStepsRegistration:
    """The REAL fea/payload_steps.py module, up to the tool boundary:
    registration and PLANNING need neither gmsh nor ccx, so the
    acceptance route shape is pinned in the default suite; execution
    against real tools is tests/integration/test_fea_payload_steps.py
    (`fea`-marked)."""

    # frob:tests python/feldspar/mech/closed_form.py::declare_core_ports kind="unit"
    def test_registers_and_plans_the_acceptance_route(self) -> None:
        from feldspar.fea.payload_steps import (
            GEOMETRY_PORT as REAL_GEOM_PORT,
        )
        from feldspar.fea.payload_steps import (
            MESH_PORT as REAL_MESH_PORT,
        )
        from feldspar.fea.payload_steps import (
            register as register_payload_steps,
        )
        from feldspar.library.mech import declare_core_ports

        resolver = DictResolver()
        registry = SolverRegistry()
        # WO111b: payload_steps no longer declares the shared mech core
        # scalar ports its static direction references -- their one F12
        # home is library.mech's declare_core_ports (in the full catalog
        # library.mech registers first; standalone composition declares
        # the core table explicitly, per payload_steps' docstring).
        declare_core_ports(registry)
        register_payload_steps(registry, resolver)
        registry.freeze()

        table = registry.port_table()
        assert table[REAL_GEOM_PORT].rank == Rank.payload("geometry.parametric")
        assert table[REAL_MESH_PORT].rank == Rank.payload("mesh")

        geom = resolver.store("geometry.parametric", b"{}", "test")
        route = plan(
            registry,
            {
                "mech.material.youngs_modulus": Interval(7e10, 7e10),
                "mech.material.poisson": Interval(0.33, 0.33),
                "mech.load.tip_force": Interval(1e3, 1e3),
            },
            frozenset({"linear_elastic", "small_deflection"}),
            "mech.deflection.tip",
            # Generous: the M1 planner ESTIMATES eps from the sum
            # surrogate (search.rs module note), so the direction's
            # eps_rel ceiling scales with ~youngs_modulus here; the
            # post-execution re-check is what enforces a real budget.
            1e10,
            payloads={REAL_GEOM_PORT: geom},
        )
        assert route.is_ok
        assert [s.solver_id for s in route.danger_ok.steps] == [
            "fea.mesh.cantilever",
            "fea.static_deflection.cantilever_from_mesh",
        ]
