from __future__ import annotations

"""WO-11 tests: symbolic core (`feldspar_core::symbolic`), its PyO3
exposure (`Expr`/`Predicate`/`invert_for`/`invertible_targets`/
`predicate_to_box`, re-exported from `feldspar.core`), and the Python
integration surface (`Relation.law()` in `feldspar.solve.sugar`,
the four new `RegistryError` symbolic variants, `SolverInfo`
provenance fields, and the `explain()` rendering of
`algebraic_form`/`admission_predicate`).

Covers: digest-equality golden (derived vs. hand-built twin, WO-03
F-series pattern extended to WO-11), full 5-direction registration for
the orifice law, non-invertible/multi-branch/unboundable-predicate/
empty-domain declaration failures, domain-predicate-to-box derivation,
determinism, `explain()` golden for a mixed derived+hand-written route,
and a domain-fault-at-eval-time-is-a-Result-not-an-exception check."""

from typani import Ok

from feldspar import _feldspar
from feldspar.core import Accuracy, Domain, Expr, Interval, Predicate, canonical_digest
from feldspar.plan import execute, plan
from feldspar.solve import Citation, SolverRegistry, solver
from feldspar.solve._models import EXACT
from feldspar.solve.errors import RegistryError, SolveError
from feldspar.solve.sugar import Relation, make_direction


def _orifice_expr() -> tuple:
    """`Q = C_d * A * sqrt(2 * dp / rho)`, built directly from `Expr`
    primitives (not via any string parser -- WO-11 has none)."""
    c_d = Expr.var("C_d")
    a = Expr.var("A")
    dp = Expr.var("dp")
    rho = Expr.var("rho")
    q = Expr.var("Q")
    rhs = Expr.mul([c_d, a, Expr.sqrt(Expr.div(Expr.mul([Expr.lit(2.0), dp]), rho))])
    return q, rhs


def _orifice_box() -> dict:
    return {
        "C_d": (0.1, 1.0),
        "A": (1e-6, 1.0),
        "dp": (0.0, 1e6),
        "rho": (1.0, 2000.0),
        "Q": (0.0, 1e6),
    }


def _orifice_relation() -> Relation:
    return Relation(
        namespace="orifice",
        ports=("Q", "C_d", "A", "dp", "rho"),
        domain=_orifice_box(),
        cost=1e-6,
        version="1",
        citations=("handbook: test",),
    )


# ---------------------------------------------------------------------------
# 1. Digest-equality golden: derived direction vs. hand-built twin.
# ---------------------------------------------------------------------------


def test_law_derived_digest_equals_hand_built_twin() -> None:
    """Solving the orifice law for `Q` via `.law()` must digest
    byte-identically (`exclude={"solver_id"}`) to a hand-built
    `.direction()`/`make_direction()` twin with the same namespace,
    inputs, outputs, domain, cost, accuracy, citations, version, tier --
    proving the `exclude=True` provenance fields (`algebraic_form`,
    `solved_for`, `branch`, `admission_predicate`, `derivation_digest`)
    do not affect `canonical_digest`/`registry.digest()` (AD-5, FINV-7)."""
    q, rhs = _orifice_expr()
    rel = _orifice_relation()
    assert rel.law(lhs=q, rhs=rhs).is_ok

    info_derived = next(i for i, _ in rel._directions if i.solved_for == "Q")

    info_hand, _ = make_direction(
        solver_id="orifice.solve_Q_hand",
        fn=lambda x: {"Q": x["C_d"] * x["A"] * (2.0 * x["dp"] / x["rho"]) ** 0.5},
        namespace="orifice",
        inputs=("C_d", "A", "dp", "rho"),
        outputs=("Q",),
        domain=_orifice_box(),
        cost=1e-6,
        accuracy=EXACT,
        citations=("handbook: test",),
        version="1",
    )

    dump_derived = info_derived.model_dump(exclude={"solver_id"})
    dump_hand = info_hand.model_dump(exclude={"solver_id"})
    assert canonical_digest(dump_derived) == canonical_digest(dump_hand)


# ---------------------------------------------------------------------------
# 2. All 5 directions register cleanly with full provenance.
# ---------------------------------------------------------------------------


def test_law_derives_all_five_directions() -> None:
    q, rhs = _orifice_expr()
    rel = _orifice_relation()
    result = rel.law(lhs=q, rhs=rhs)
    assert result.is_ok
    assert result.danger_ok is None


def test_law_derived_directions_solve_for_every_port() -> None:
    q, rhs = _orifice_expr()
    rel = _orifice_relation()
    rel.law(lhs=q, rhs=rhs)
    solved_for = {i.solved_for for i, _ in rel._directions}
    assert solved_for == {"Q", "C_d", "A", "dp", "rho"}


def test_law_derived_directions_carry_full_provenance() -> None:
    q, rhs = _orifice_expr()
    rel = _orifice_relation()
    rel.law(lhs=q, rhs=rhs)
    assert len(rel._directions) == 5
    for info, _ in rel._directions:
        assert info.algebraic_form is not None
        assert info.solved_for is not None
        assert info.branch is not None
        assert info.derivation_digest is not None


# ---------------------------------------------------------------------------
# 3. Non-invertible variable fails loudly, naming the variable.
# ---------------------------------------------------------------------------


def test_invertible_targets_excludes_repeated_variable() -> None:
    """`y = x + x`: `x` appears twice, so it is simply absent from
    `invertible_targets` (needs exactly one occurrence)."""
    x = Expr.var("x")
    y = Expr.var("y")
    rhs = Expr.add([x, x])
    targets = _feldspar.invertible_targets(y, rhs)
    assert "x" not in targets


def test_invert_for_repeated_variable_raises_non_invertible() -> None:
    x = Expr.var("x")
    y = Expr.var("y")
    rhs = Expr.add([x, x])
    try:
        _feldspar.invert_for(y, rhs, "x")
        raise AssertionError("expected SymbolicErrorRaised")
    except _feldspar.SymbolicErrorRaised as exc:
        assert exc.args[0] == "NonInvertible"
        assert "x" in exc.args


# ---------------------------------------------------------------------------
# 4. Multi-branch declaration fails loudly, listing branches.
# ---------------------------------------------------------------------------


def _sho_expr() -> tuple:
    e = Expr.var("E")
    k = Expr.var("k")
    x = Expr.var("x")
    rhs = Expr.mul([Expr.lit(0.5), k, Expr.pow(x, Expr.lit(2.0))])
    return e, rhs


def test_law_unresolved_multi_branch_is_registry_error() -> None:
    e, rhs = _sho_expr()
    rel = Relation(
        namespace="sho",
        ports=("E", "k", "x"),
        domain={"E": (0.0, 1e6), "k": (0.0, 1e6), "x": (-1e3, 1e3)},
        cost=1e-6,
        version="1",
        citations=("handbook: t",),
    )
    result = rel.law(lhs=e, rhs=rhs)
    assert result.is_err
    err = result.danger_err
    assert err == RegistryError.MultiBranch(variable="x", branches=["+", "-"])


def test_law_declared_branch_succeeds() -> None:
    e, rhs = _sho_expr()
    rel = Relation(
        namespace="sho2",
        ports=("E", "k", "x"),
        domain={"E": (0.0, 1e6), "k": (0.0, 1e6), "x": (-1e3, 1e3)},
        cost=1e-6,
        version="1",
        citations=("handbook: t",),
    )
    result = rel.law(lhs=e, rhs=rhs, branches={"x": "+"})
    assert result.is_ok
    assert result.danger_ok is None


# ---------------------------------------------------------------------------
# 5. Domain-predicate-to-box derivation (boundable case).
# ---------------------------------------------------------------------------


def test_law_predicate_narrows_declared_box() -> None:
    re_ = Expr.var("Re")
    y = Expr.var("y")
    pred = Predicate(re_, "lt", Expr.lit(2300.0))
    rel = Relation(
        namespace="flow",
        ports=("Re", "y"),
        domain={"Re": (0.0, 100000.0), "y": (0.0, 1.0)},
        cost=1e-6,
        version="1",
        citations=("handbook: t",),
    )
    result = rel.law(lhs=y, rhs=re_, predicates=[pred])
    assert result.is_ok
    info = next(i for i, _ in rel._directions if i.solved_for == "y")
    assert info.domain.box["Re"].hi == 2300.0


# ---------------------------------------------------------------------------
# 6. Unboundable predicate without a compatible declared box.
# ---------------------------------------------------------------------------


def test_law_nonlinear_predicate_is_unboundable() -> None:
    x = Expr.var("x")
    y = Expr.var("y")
    pred = Predicate(Expr.pow(x, Expr.lit(2.0)), "lt", Expr.lit(4.0))
    rel = Relation(
        namespace="nl",
        ports=("x", "y"),
        domain={"x": (0.0, 10.0), "y": (0.0, 100.0)},
        cost=1e-6,
        version="1",
        citations=("handbook: t",),
    )
    result = rel.law(lhs=y, rhs=x, predicates=[pred])
    assert result.is_err
    assert result.danger_err == RegistryError.UnboundablePredicate(
        predicate="(pow V:x L:2.0) < L:4.0"
    )


# ---------------------------------------------------------------------------
# 7. Determinism.
# ---------------------------------------------------------------------------


def test_canonicalize_is_deterministic_across_separately_built_trees() -> None:
    """Two independently-built but structurally-equal `Expr` trees
    produce identical `canonical_string()`. NOTE: this only exercises
    same-process determinism -- cross-platform/cross-process stability
    is claimed by the Rust `format_f64`/`canonical_digest` design but
    not independently re-verified here (per this project's
    executed-and-observed-vs-written-but-unverified convention)."""
    a1 = Expr.mul([Expr.var("A"), Expr.var("B")])
    a2 = Expr.mul([Expr.var("A"), Expr.var("B")])
    assert a1.canonical_string() == a2.canonical_string()


def test_law_derivation_digest_is_deterministic_across_fresh_relations() -> None:
    q1, rhs1 = _orifice_expr()
    q2, rhs2 = _orifice_expr()
    rel1 = _orifice_relation()
    rel2 = _orifice_relation()
    rel1.law(lhs=q1, rhs=rhs1)
    rel2.law(lhs=q2, rhs=rhs2)
    digests1 = {i.solved_for: i.derivation_digest for i, _ in rel1._directions}
    digests2 = {i.solved_for: i.derivation_digest for i, _ in rel2._directions}
    assert digests1 == digests2


# ---------------------------------------------------------------------------
# 8. explain() golden extension: mixed derived + hand-written route.
# ---------------------------------------------------------------------------


def test_explain_renders_algebraic_form_for_derived_step_and_placeholder_for_hand_written() -> (
    None
):
    registry = SolverRegistry()
    x = Expr.var("ex.x")
    y = Expr.var("ex.y")
    rhs = Expr.mul([Expr.lit(2.0), x])
    # Only "ex.x" is a declared box port -- the derived direction's own
    # inputs are ("ex.x",), so the domain box must not also carry
    # "ex.y" (the output itself) or corner-sweep expansion rejects it
    # for a missing input (03/04 domain-rejection semantics, not a
    # WO-11 concern -- this mirrors how a hand-written `.direction()`
    # under this same `Relation` would need to declare its domain).
    rel = Relation(
        namespace="ex",
        ports=("ex.x", "ex.y"),
        domain={"ex.x": (0.0, 10.0)},
        cost=1.0,
        version="1",
        citations=("handbook: test fixture -- a note",),
    )
    assert rel.law(lhs=y, rhs=rhs).is_ok
    # Keep only the ex.x -> ex.y direction; the reverse direction would
    # need "ex.y" as an input and isn't needed for this route.
    rel._directions = [(i, f) for i, f in rel._directions if i.solved_for == "ex.y"]
    assert rel.register(registry).is_ok

    @solver(
        namespace="ex",
        inputs=("ex.y",),
        outputs=("ex.z",),
        domain=Domain(box={"ex.y": Interval(0.0, 100.0)}, tags=frozenset()),
        cost=1.0,
        accuracy={"ex.z": Accuracy(eps_abs=0.1, eps_rel=0.0)},
        citations=(Citation(kind="handbook", ref="test fixture", note="a note"),),
        version="1",
    )
    def increment(inp):
        return Ok({"ex.z": inp["ex.y"] + 1.0})

    assert registry.register(*increment.solver_direction).is_ok
    registry.freeze()

    known = {"ex.x": Interval(1.0, 2.0)}
    route = plan(registry, known, frozenset(), "ex.z", 10.0).danger_ok
    solution = execute(route, registry, known).danger_ok

    text = solution.explain()
    assert "algebraic_form: ex.y = (neg (neg (mul L:2.0 V:ex.x)))" in text
    assert "algebraic_form: (not carried -- hand-written direction)" in text
    assert "admission_predicate: (none)" in text


# ---------------------------------------------------------------------------
# 9. predicate_to_box refuses silently-wrong hulls -- EmptyDomain.
# ---------------------------------------------------------------------------


def test_predicate_to_box_contradictory_bound_is_empty_domain() -> None:
    """`x < -5` intersected with declared box `x in [0, 10]` yields an
    empty interval. Not easily reachable via `Relation.law()`'s public
    surface (its declared-box seeding always comes from a real domain,
    and `law()`'s own callers control the predicate), so this is tested
    directly at the `_feldspar.predicate_to_box` level."""
    x = Expr.var("x")
    pred = Predicate(x, "lt", Expr.lit(-5.0))
    box = {"x": Interval(0.0, 10.0)}
    try:
        _feldspar.predicate_to_box([pred], box, set())
        raise AssertionError("expected SymbolicErrorRaised")
    except _feldspar.SymbolicErrorRaised as exc:
        assert exc.args[0] == "EmptyDomain"
        assert exc.args[1] == "x"


# ---------------------------------------------------------------------------
# 10. Eval domain fault surfaces as a recoverable SolveError.
# ---------------------------------------------------------------------------


def test_derived_solve_fn_negative_radicand_is_non_finite_error() -> None:
    """A negative radicand inside the derived `Q` direction's
    `sqrt(2*dp/rho)` must come back as `Err(SolveError.NonFinite(...))`
    -- never a raised exception -- per `sugar.py`'s `raw_fn` closure
    mapping `_feldspar.EvalErrorRaised` to a typani `Result`."""
    q, rhs = _orifice_expr()
    rel = _orifice_relation()
    rel.law(lhs=q, rhs=rhs)
    _, fn_q = next((i, f) for i, f in rel._directions if i.solved_for == "Q")
    result = fn_q({"C_d": 0.5, "A": 0.1, "dp": -100.0, "rho": 5.0})
    assert result.is_err
    assert result.danger_err == SolveError.NonFinite(port="Q")
