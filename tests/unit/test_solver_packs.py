from __future__ import annotations

"""WO-19 tests: `feldspar.solve.packs` (discovery/composition) and
`feldspar.testing.assert_solverpack_conforms` (the M9 conformance kit).

Covers 10 sec. 3's deliverables: sorted-by-name deterministic
composition, a duplicate-id loud error naming both the pack and the
id's owner, namespace etiquette (own sub-namespace vs. squatting on a
bare standard namespace), the method-named-kind lint, pack-version
digest folding, and the conformance kit itself (registration validity,
determinism smoke, domain honesty, corner-monotonicity spot check)."""

from typani import Ok

from feldspar.core import Accuracy, Domain, Interval
from feldspar.solve import Citation, SolverRegistry, solver
from feldspar.solve.packs import (
    DuplicateSolverId,
    FakeSolverPackEntryPoint,
    MalformedSolverPack,
    MethodNamedSolverId,
    NamespaceViolation,
    PackInfo,
    load_solver_packs,
    pack_composition_digest,
)
from feldspar.testing import assert_solverpack_conforms


def _own_namespace_solver(namespace: str, solver_id_input: str, factor: float):
    """Builds a trivial `y = factor * x` closed-form direction under
    `namespace`, named to avoid cross-test id collisions."""

    @solver(
        namespace=namespace,
        inputs=(f"{namespace}.{solver_id_input}",),
        outputs=(f"{namespace}.out",),
        domain=Domain(
            box={f"{namespace}.{solver_id_input}": Interval(1.0, 10.0)},
            tags=frozenset(),
        ),
        cost=1e-6,
        accuracy={f"{namespace}.out": Accuracy(eps_abs=0.0, eps_rel=0.0)},
        citations=(Citation(kind="handbook", ref="WO-19 fixture"),),
        version="1",
    )
    def _fn(x, _in=f"{namespace}.{solver_id_input}", _factor=factor):
        return Ok({f"{namespace}.out": x[_in] * _factor})

    return _fn


# frob:tests python/feldspar/testing kind="integration"
def test_pack_composes_and_loads_deterministically() -> None:
    fn = _own_namespace_solver("mech.acme_bearings", "x", 2.0)

    def register(registry: SolverRegistry) -> None:
        _ = registry.register(*fn.solver_direction).danger_ok

    registry = SolverRegistry()
    outcome = load_solver_packs(
        registry,
        entry_points_override=[
            FakeSolverPackEntryPoint("acme_bearings", "0.1.0", register)
        ],
    )
    assert outcome.skipped == ()
    assert outcome.loaded == (PackInfo(name="acme_bearings", version="0.1.0"),)
    ids = [info.solver_id for info, _fn in registry]
    assert ids == sorted(ids)


def test_sorted_by_entry_point_name_composition() -> None:
    """Two packs load in sorted-name order regardless of list order."""
    fn_b = _own_namespace_solver("mech.bpack", "x", 1.0)
    fn_a = _own_namespace_solver("mech.apack", "x", 1.0)

    def register_b(registry: SolverRegistry) -> None:
        _ = registry.register(*fn_b.solver_direction).danger_ok

    def register_a(registry: SolverRegistry) -> None:
        _ = registry.register(*fn_a.solver_direction).danger_ok

    registry = SolverRegistry()
    outcome = load_solver_packs(
        registry,
        entry_points_override=[
            FakeSolverPackEntryPoint("bpack", "1.0", register_b),
            FakeSolverPackEntryPoint("apack", "1.0", register_a),
        ],
    )
    assert [pack.name for pack in outcome.loaded] == ["apack", "bpack"]


def test_duplicate_solver_id_across_packs_names_both() -> None:
    """Two DIFFERENT packs both upstreaming (reviewed) into the same
    bare standard namespace and colliding on the exact same solver id
    -- the genuine cross-pack duplicate-id case (a same-namespace,
    same-owner collision is instead a namespace-etiquette violation,
    covered separately)."""
    fn1 = _own_namespace_solver("mech", "x", 1.0)

    def register_one(registry: SolverRegistry) -> None:
        _ = registry.register(*fn1.solver_direction).danger_ok

    def register_two(registry: SolverRegistry) -> None:
        _ = registry.register(*fn1.solver_direction).danger_ok

    registry = SolverRegistry()
    outcome = load_solver_packs(
        registry,
        reviewed_namespaces=("mech",),
        entry_points_override=[
            FakeSolverPackEntryPoint("pack_one", "1.0", register_one),
            FakeSolverPackEntryPoint("pack_two", "1.0", register_two),
        ],
    )
    assert len(outcome.loaded) == 1
    assert outcome.loaded[0].name == "pack_one"
    assert len(outcome.skipped) == 1
    dup = outcome.skipped[0]
    assert isinstance(dup, DuplicateSolverId)
    assert dup.pack == "pack_two"
    assert dup.owned_by == "pack_one"


# frob:tests python/feldspar/solve/packs.py::load_solver_packs kind="unit"
def test_namespace_squatting_is_rejected() -> None:
    """A pack registering under a bare standard namespace (`mech`, no
    own sub-namespace) is skipped LOUDLY -- the "no squatting" rule."""
    fn = _own_namespace_solver("mech", "squat_x", 1.0)

    def register(registry: SolverRegistry) -> None:
        _ = registry.register(*fn.solver_direction).danger_ok

    registry = SolverRegistry()
    outcome = load_solver_packs(
        registry,
        entry_points_override=[FakeSolverPackEntryPoint("squatter", "1.0", register)],
    )
    assert outcome.loaded == ()
    assert len(outcome.skipped) == 1
    assert isinstance(outcome.skipped[0], NamespaceViolation)


def test_reviewed_namespace_opts_in_to_bare_standard_namespace() -> None:
    """`reviewed_namespaces` explicitly opts a bare standard namespace
    in (10 sec. 3's "upstreaming ... through review")."""
    fn = _own_namespace_solver("mech", "reviewed_x", 1.0)

    def register(registry: SolverRegistry) -> None:
        _ = registry.register(*fn.solver_direction).danger_ok

    registry = SolverRegistry()
    outcome = load_solver_packs(
        registry,
        reviewed_namespaces=("mech",),
        entry_points_override=[
            FakeSolverPackEntryPoint("reviewed_pack", "1.0", register)
        ],
    )
    assert outcome.skipped == ()
    assert outcome.loaded == (PackInfo(name="reviewed_pack", version="1.0"),)


def test_own_sub_namespace_under_a_non_standard_namespace_is_fine() -> None:
    """A pack's OWN bare namespace (equal to its own name, no dotted
    standard prefix) is always its own turf -- no etiquette violation."""
    fn = _own_namespace_solver("acme_thermo", "x", 1.0)

    def register(registry: SolverRegistry) -> None:
        _ = registry.register(*fn.solver_direction).danger_ok

    registry = SolverRegistry()
    outcome = load_solver_packs(
        registry,
        entry_points_override=[
            FakeSolverPackEntryPoint("acme_thermo", "1.0", register)
        ],
    )
    assert outcome.skipped == ()


def test_method_named_solver_id_is_rejected() -> None:
    """A namespace naming a method/tool (`fea`) rather than what is
    claimed is the D94 lint, one level down."""
    fn = _own_namespace_solver("mech.fea_pack", "x", 1.0)

    def register(registry: SolverRegistry) -> None:
        _ = registry.register(*fn.solver_direction).danger_ok

    registry = SolverRegistry()
    outcome = load_solver_packs(
        registry,
        entry_points_override=[FakeSolverPackEntryPoint("fea_pack", "1.0", register)],
    )
    assert outcome.loaded == ()
    assert len(outcome.skipped) == 1
    assert isinstance(outcome.skipped[0], MethodNamedSolverId)


def test_malformed_entry_point_target_is_skipped_loudly() -> None:
    class _NotCallableEntryPoint:
        name = "bad_pack"

        def load(self) -> object:
            return object()

        dist = None

    registry = SolverRegistry()
    outcome = load_solver_packs(
        registry, entry_points_override=[_NotCallableEntryPoint()]
    )
    assert outcome.loaded == ()
    assert len(outcome.skipped) == 1
    assert isinstance(outcome.skipped[0], MalformedSolverPack)


def test_pack_composition_digest_changes_on_version_bump() -> None:
    fn = _own_namespace_solver("mech.digest_pack", "x", 1.0)

    def register(registry: SolverRegistry) -> None:
        _ = registry.register(*fn.solver_direction).danger_ok

    registry_v1 = SolverRegistry()
    outcome_v1 = load_solver_packs(
        registry_v1,
        entry_points_override=[
            FakeSolverPackEntryPoint("digest_pack", "0.1.0", register)
        ],
    )
    registry_v2 = SolverRegistry()
    outcome_v2 = load_solver_packs(
        registry_v2,
        entry_points_override=[
            FakeSolverPackEntryPoint("digest_pack", "0.2.0", register)
        ],
    )
    base_digest = registry_v1.digest()
    assert base_digest == registry_v2.digest(), (
        "SolverInfo fields are unchanged by the version bump alone"
    )
    digest_v1 = pack_composition_digest(base_digest, outcome_v1)
    digest_v2 = pack_composition_digest(base_digest, outcome_v2)
    assert digest_v1 != digest_v2, "pack version must be a digest input"


def test_assert_solverpack_conforms_passes_for_a_clean_pack() -> None:
    fn = _own_namespace_solver("mech.conforming_pack", "x", 3.0)

    def register(registry: SolverRegistry) -> None:
        _ = registry.register(*fn.solver_direction).danger_ok

    assert_solverpack_conforms(register, name="conforming_pack", version="0.1.0")


def test_assert_solverpack_conforms_names_the_composition_failure() -> None:
    """A squatting pack fails the KIT's own composition assertion,
    constructively naming the violated rule (10 sec. 3: "kit failures
    are constructive")."""
    fn = _own_namespace_solver("mech", "squat_x", 1.0)

    def register(registry: SolverRegistry) -> None:
        _ = registry.register(*fn.solver_direction).danger_ok

    try:
        assert_solverpack_conforms(register, name="bad_pack", version="0.1.0")
    except AssertionError as exc:
        assert "bad_pack" in str(exc)
    else:
        raise AssertionError("expected the kit to reject a squatting pack")
