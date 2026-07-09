from __future__ import annotations

"""WO-22 tests: symbolic follow-ups (11 sec. 4, R4/R5 -- DECIDED).

R4 (symbolic propagation): kernel differentiation over the canonical
`Expr` AST, and delta-method `Normal` propagation with a per-step
symbolic-vs-numeric derivative mode -- symbolic/numeric agreement,
determinism, and `CANON_VERSION` exposure.

R5 (calibration interplay): a `Relation.law()`-derived direction
inherits citations but DROPS calibration evidence; the calibration
harness re-sweeps derived directions over the mapped domain
automatically (`resweep_derived`/`resweep_all_derived`); `Accuracy(0,0)`
laws are exempt; a derived direction whose re-sweep has not run
reports its ceiling as UNCALIBRATED via `check_ceilings` (non-blocking)."""

from pathlib import Path

from feldspar import _feldspar
from feldspar.calib import check_ceilings, resweep_all_derived, resweep_derived
from feldspar.calib.store import read_record
from feldspar.core import (
    CANON_VERSION,
    Accuracy,
    Expr,
    Normal,
    delta_propagate_numeric,
    delta_propagate_symbolic,
)
from feldspar.solve import Citation, SolverRegistry
from feldspar.solve.sugar import Relation

# ---------------------------------------------------------------------------
# R4: symbolic differentiation kernel.
# ---------------------------------------------------------------------------


def _orifice_rhs() -> "Expr":
    c_d = Expr.var("C_d")
    a = Expr.var("A")
    dp = Expr.var("dp")
    rho = Expr.var("rho")
    return Expr.mul([c_d, a, Expr.sqrt(Expr.div(Expr.mul([Expr.lit(2.0), dp]), rho))])


def test_canon_version_is_exposed_and_stable() -> None:
    assert isinstance(CANON_VERSION, int)
    assert CANON_VERSION == _feldspar.CANON_VERSION
    assert CANON_VERSION >= 1


def test_differentiate_power_rule_matches_hand_derivative() -> None:
    x = Expr.var("x")
    e = Expr.pow(x, Expr.lit(3.0))
    d = e.differentiate("x")
    # d/dx[x^3] = 3*x^2 -> 3 * 4 = 12 at x=2.
    assert d.eval({"x": 2.0}) == 12.0


def test_differentiate_of_absent_variable_is_zero() -> None:
    e = Expr.mul([Expr.var("y"), Expr.lit(2.0)])
    d = e.differentiate("x")
    assert d.eval({"y": 5.0}) == 0.0


def test_differentiate_matches_numeric_central_difference_on_orifice() -> None:
    rhs = _orifice_rhs()
    point = {"C_d": 0.62, "A": 0.002, "dp": 5000.0, "rho": 1000.0}
    h = 1e-4
    for var in ("C_d", "A", "dp", "rho"):
        symbolic = rhs.differentiate(var).eval(point)
        plus = dict(point)
        minus = dict(point)
        plus[var] += h
        minus[var] -= h
        numeric = (rhs.eval(plus) - rhs.eval(minus)) / (2 * h)
        scale = max(abs(symbolic), abs(numeric), 1.0)
        assert abs(symbolic - numeric) / scale < 1e-4, (var, symbolic, numeric)


def test_differentiate_is_deterministic() -> None:
    rhs = _orifice_rhs()
    d1 = rhs.differentiate("dp")
    d2 = rhs.differentiate("dp")
    assert d1.canonical_string() == d2.canonical_string()


# ---------------------------------------------------------------------------
# R4: delta-method Normal propagation, symbolic vs numeric mode.
# ---------------------------------------------------------------------------


def _orifice_deltas() -> list:
    return [
        ("C_d", 0.62, 0.01),
        ("A", 0.002, 0.0001),
        ("dp", 5000.0, 50.0),
        ("rho", 1000.0, 2.0),
    ]


def test_delta_propagate_symbolic_and_numeric_agree() -> None:
    rhs = _orifice_rhs()
    inputs = _orifice_deltas()

    symbolic = delta_propagate_symbolic(rhs, inputs)

    def callback(pt: dict) -> float:
        return rhs.eval(pt)

    numeric = delta_propagate_numeric(callback, inputs, 1e-5)

    assert symbolic.mean == numeric.mean
    rel_diff = abs(symbolic.stddev - numeric.stddev) / symbolic.stddev
    assert rel_diff < 1e-3


def test_delta_propagate_symbolic_is_deterministic() -> None:
    rhs = _orifice_rhs()
    inputs = _orifice_deltas()
    r1 = delta_propagate_symbolic(rhs, inputs)
    r2 = delta_propagate_symbolic(rhs, inputs)
    assert r1.mean == r2.mean
    assert r1.stddev == r2.stddev


def test_normal_to_interval_is_conservative() -> None:
    n = Normal(10.0, 2.0)
    iv = n.to_interval()
    assert iv.lo < n.mean - n.stddev
    assert iv.hi > n.mean + n.stddev


# ---------------------------------------------------------------------------
# R5: derived directions inherit citations, drop calibration evidence.
# ---------------------------------------------------------------------------


def _orifice_relation_with_calibration_citation() -> Relation:
    return Relation(
        namespace="orifice_r5",
        ports=("Q", "C_d", "A", "dp", "rho"),
        domain={
            "C_d": (0.1, 1.0),
            "A": (1e-6, 1.0),
            "dp": (1.0, 1e5),
            "rho": (1.0, 2000.0),
            "Q": (0.0, 1e6),
        },
        cost=1e-6,
        version="1",
        # A realistic declared model-error band, well above the
        # float-precision residual an exact-by-construction inversion
        # actually produces (~1e-10 scale here) -- an `eps_abs=0.0`
        # ceiling would bust on float noise alone, which is a separate,
        # pre-existing WO-07 concern (declaring a literal zero-error
        # ceiling for a non-EXACT tier), not something this fixture
        # should exercise.
        accuracy=Accuracy(1e-6, 0.05),
        citations=(
            Citation(kind="handbook", ref="orifice handbook"),
            Citation(kind="calibration", ref="parent-record-digest"),
        ),
    )


def test_law_drops_calibration_citation_but_keeps_others() -> None:
    q = Expr.var("Q")
    rhs = _orifice_rhs()
    rel = _orifice_relation_with_calibration_citation()
    assert rel.law(lhs=q, rhs=rhs).is_ok

    for info, _fn in rel._directions:
        kinds = {c.kind for c in info.citations}
        assert "calibration" not in kinds
        assert "handbook" in kinds


def test_law_exact_default_accuracy_needs_no_calibration_citation_anyway() -> None:
    # A-7: Accuracy(0,0) laws are exempt from calibration entirely, so
    # dropping calibration citations is a no-op in the common EXACT case.
    q = Expr.var("Q")
    rhs = _orifice_rhs()
    rel = Relation(
        namespace="orifice_exact",
        ports=("Q", "C_d", "A", "dp", "rho"),
        domain={
            "C_d": (0.1, 1.0),
            "A": (1e-6, 1.0),
            "dp": (1.0, 1e5),
            "rho": (1.0, 2000.0),
            "Q": (0.0, 1e6),
        },
        cost=1e-6,
        version="1",
        citations=(Citation(kind="handbook", ref="orifice handbook"),),
    )
    assert rel.law(lhs=q, rhs=rhs).is_ok
    for info, _fn in rel._directions:
        assert info.accuracy[info.solved_for] == Accuracy(0.0, 0.0)


# ---------------------------------------------------------------------------
# R5: automatic mapped-domain re-sweep.
# ---------------------------------------------------------------------------


def test_resweep_derived_produces_tight_residual_record() -> None:
    q = Expr.var("Q")
    rhs = _orifice_rhs()
    rel = _orifice_relation_with_calibration_citation()
    assert rel.law(lhs=q, rhs=rhs).is_ok

    info_q, fn_q = next((i, f) for i, f in rel._directions if i.solved_for == "Q")
    result = resweep_derived(info_q, fn_q, n_samples=64, seed=0)
    assert result.is_ok
    record = result.danger_ok
    assert record.solver_id == info_q.solver_id
    # The inversion is exact, so the residual is float-precision only.
    assert record.worst_abs_error < 1e-6
    assert record.digest


def test_resweep_all_derived_writes_records_for_every_non_exact_derived_direction(
    tmp_path: Path,
) -> None:
    q = Expr.var("Q")
    rhs = _orifice_rhs()
    rel = _orifice_relation_with_calibration_citation()
    assert rel.law(lhs=q, rhs=rhs).is_ok

    registry = SolverRegistry()
    assert rel.register(registry).is_ok
    registry.freeze()

    records_dir = tmp_path / "records"
    result = resweep_all_derived(registry, records_dir, n_samples=32, seed=0)
    assert result.is_ok
    records = result.danger_ok
    assert len(records) == 5  # every derived direction (Q, C_d, A, dp, rho)
    for record in records:
        stored = read_record(records_dir, record.digest)
        assert stored is not None
        assert stored.worst_abs_error == record.worst_abs_error


def test_check_ceilings_reports_uncalibrated_not_blocking_for_fresh_derived_direction() -> (
    None
):
    """A derived, non-EXACT direction with no calibration citation yet
    (R5: dropped at declaration time) must not hard-fail `check_ceilings`
    -- the harness re-sweeps it live and only fails on an ACTUAL busted
    ceiling, never merely because no record has been written to disk."""
    q = Expr.var("Q")
    rhs = _orifice_rhs()
    rel = _orifice_relation_with_calibration_citation()
    assert rel.law(lhs=q, rhs=rhs).is_ok

    registry = SolverRegistry()
    assert rel.register(registry).is_ok
    registry.freeze()

    result = check_ceilings(registry, Path("/nonexistent/records/dir"))
    assert result.is_ok


def test_check_ceilings_still_busts_a_too_tight_derived_ceiling(tmp_path: Path) -> None:
    q = Expr.var("Q")
    rhs = _orifice_rhs()
    rel = Relation(
        namespace="orifice_tight",
        ports=("Q", "C_d", "A", "dp", "rho"),
        domain={
            "C_d": (0.1, 1.0),
            "A": (1e-6, 1.0),
            "dp": (1.0, 1e5),
            "rho": (1.0, 2000.0),
            "Q": (0.0, 1e6),
        },
        cost=1e-6,
        version="1",
        # eps_rel so tight that even float-precision residual busts it.
        accuracy=Accuracy(0.0, 0.0),
        citations=(Citation(kind="handbook", ref="orifice handbook"),),
    )
    assert rel.law(lhs=q, rhs=rhs).is_ok
    # EXACT (0,0) accuracy is exempt (A-7) -- check_ceilings must pass
    # trivially since there are no non-exact ports to verify.
    registry = SolverRegistry()
    assert rel.register(registry).is_ok
    registry.freeze()
    result = check_ceilings(registry, tmp_path / "records")
    assert result.is_ok
