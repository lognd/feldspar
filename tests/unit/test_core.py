from __future__ import annotations

"""WO-02 Python-side type smoke tests: feldspar.core (01-interfaces).

Covers the WO-02 rows of docs/spec/toolchain/02-edge-cases.md at the
Python surface (the Rust-side equivalents live in
crates/feldspar-core/src/units.rs and tests/property.rs)."""

import math

import pytest

from feldspar import _feldspar, core


# frob:tests crates/feldspar-py/src/interval.rs::PyInterval._new_checked
# frob:tests crates/feldspar-py/src/errors.rs::core_error_to_py
def test_interval_new_inverted_is_err() -> None:
    r = core.Interval.new(2.0, 1.0)
    assert r.is_err
    assert r.err == core.CoreError.InvertedInterval


def test_interval_new_non_finite_is_err() -> None:
    r = core.Interval.new(0.0, math.inf)
    assert r.is_err
    assert r.err == core.CoreError.NonFiniteBound


# frob:tests crates/feldspar-py/src/interval.rs::PyInterval.py_new
# frob:tests crates/feldspar-py/src/lib.rs::_feldspar
def test_interval_direct_construction_raises_on_invalid_bounds() -> None:
    """`Interval(lo, hi)` direct construction raises (programmer-bug path)."""
    with pytest.raises(_feldspar.CoreErrorRaised):
        core.Interval(2.0, 1.0)


# frob:tests crates/feldspar-py/src/interval.rs::PyInterval._point_checked
def test_interval_degenerate_point_has_zero_width() -> None:
    p = core.Interval.point(0.0).danger_ok
    assert p.width() == 0.0


# frob:tests crates/feldspar-py/src/interval.rs::PyInterval.__richcmp__
# frob:tests crates/feldspar-py/src/interval.rs::PyInterval.__hash__
# frob:tests crates/feldspar-py/src/interval.rs::PyInterval.__repr__
def test_interval_equality_and_hash() -> None:
    a = core.Interval(1.0, 2.0)
    b = core.Interval(1.0, 2.0)
    assert a == b
    assert hash(a) == hash(b)
    assert "1" in repr(a) and "2" in repr(a)


# frob:tests crates/feldspar-py/src/accuracy.rs::PyAccuracy.py_new
# frob:tests crates/feldspar-py/src/accuracy.rs::PyAccuracy.eps_abs
# frob:tests crates/feldspar-py/src/accuracy.rs::PyAccuracy.eps_rel
def test_accuracy_worst_over_takes_larger_abs_endpoint() -> None:
    acc = core.Accuracy(0.0, 0.1)
    iv = core.Interval(-1.0, 5.0)
    assert acc.worst_over(iv) == acc.eps(5.0)


# frob:tests crates/feldspar-py/src/accuracy.rs::PyAccuracy.__repr__
# frob:tests crates/feldspar-py/src/accuracy.rs::PyAccuracy.__richcmp__
# frob:tests crates/feldspar-py/src/accuracy.rs::PyAccuracy.__hash__
def test_accuracy_equality_hash_and_repr() -> None:
    a = core.Accuracy(0.0, 0.1)
    b = core.Accuracy(0.0, 0.1)
    assert a == b
    assert hash(a) == hash(b)
    assert "0.1" in repr(a)


def test_to_si_degc_applies_offset() -> None:
    sys_ = core.UnitSystem.builtin()
    r = sys_.to_si(25.0, "degC")
    assert r.danger_ok == pytest.approx(298.15)


def test_percent_ingest_scale() -> None:
    sys_ = core.UnitSystem.builtin()
    assert sys_.to_si(1.0, "%").danger_ok == pytest.approx(0.01)


# frob:tests crates/feldspar-py/src/errors.rs::unit_error_to_py
def test_unknown_unit_is_err_never_a_guess() -> None:
    sys_ = core.UnitSystem.builtin()
    r = sys_.to_si(1.0, "furlong")
    assert r.is_err
    assert r.err == core.UnitError.UnknownUnit


def test_rpm_to_si_matches_g19() -> None:
    sys_ = core.UnitSystem.builtin()
    assert sys_.to_si(6000.0, "rpm").danger_ok == pytest.approx(628.3185307, rel=1e-6)


def test_isp_seconds_view_round_trips() -> None:
    sys_ = core.UnitSystem.builtin()
    stored = sys_.to_si(285.0, "s(Isp)").danger_ok
    assert stored == pytest.approx(285.0 * 9.80665)
    assert sys_.from_si(stored, "s(Isp)").danger_ok == pytest.approx(285.0)


# frob:tests python/feldspar/core.py::canonical_digest kind="unit"
# frob:tests crates/feldspar-py/src/digest.rs::canonical_digest
def test_digest_stable_across_map_insertion_orders() -> None:
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    assert core.canonical_digest(a) == core.canonical_digest(b)


# frob:tests crates/feldspar-py/src/interval.rs::PyInterval.lo
# frob:tests crates/feldspar-py/src/interval.rs::PyInterval.hi
def test_digest_of_nested_pyo3_frozen_instances() -> None:
    """canonical_digest must not choke on core frozen classes nested
    inside plain dict/set containers (WO-03's SolverInfo digest depends
    on exactly this -- CoreError/UnitError digest ambiguity flagged in
    the WO-02 report, resolved here)."""
    d1 = {
        "box": {"x": core.Interval.new(0.0, 1.0).danger_ok},
        "tags": frozenset({"a", "b"}),
    }
    d2 = {
        "tags": frozenset({"b", "a"}),
        "box": {"x": core.Interval.new(0.0, 1.0).danger_ok},
    }
    assert core.canonical_digest(d1) == core.canonical_digest(d2)


# frob:tests crates/feldspar-py/src/dimension.rs::PyDimension.py_new
# frob:tests crates/feldspar-py/src/dimension.rs::PyDimension.exponents
def test_digest_of_domain_shaped_payload_is_order_independent() -> None:
    domain = core.Domain(
        {
            "mech.load.tip_force": core.Interval(0.0, 100.0),
            "mech.material.poisson": core.Interval(0.0, 0.5),
        },
        {"linear_elastic", "small_deflection"},
    )
    port = core.PortDecl("mech.load.tip_force", "N", core.Rank.vector(3))
    accuracy = core.Accuracy(0.01, 0.02)
    dim = core.Dimension((1, 0, 0, 0, 0, 0, 0))

    payload_a = {"domain": domain, "accuracy": accuracy, "port": port, "dim": dim}
    payload_b = {"port": port, "dim": dim, "accuracy": accuracy, "domain": domain}
    assert core.canonical_digest(payload_a) == core.canonical_digest(payload_b)


# frob:tests crates/feldspar-py/src/units.rs::PyUnitSystem.builtin
def test_registering_port_table_sample_and_mpa_to_pa() -> None:
    """Acceptance: 'registering the 02 port-table sample and converting a
    MPa ingest to Pa works; a dimension mismatch is an Err value.'"""
    port = core.PortDecl("mech.material.youngs_modulus", "Pa", core.Rank.scalar())
    assert port.unit == "Pa"

    sys_ = core.UnitSystem.builtin()
    pa_value = sys_.to_si(200.0, "MPa").danger_ok
    assert pa_value == pytest.approx(200e6)
    assert sys_.compatible("MPa", "Pa")
    assert not sys_.compatible("Pa", "m")


# frob:tests crates/feldspar-py/src/errors.rs::domain_violation_to_py
def test_domain_admits_out_of_box_and_missing_tag() -> None:
    domain = core.Domain(
        {"mech.load.tip_force": core.Interval(0.0, 100.0)}, {"linear_elastic"}
    )
    ok = domain.admits(
        {"mech.load.tip_force": core.Interval(10.0, 20.0)}, {"linear_elastic"}
    )
    assert ok.is_ok

    out_of_box = domain.admits(
        {"mech.load.tip_force": core.Interval(10.0, 200.0)}, {"linear_elastic"}
    )
    assert out_of_box.is_err
    assert out_of_box.err.kind == "OutOfBox"

    missing_tag = domain.admits(
        {"mech.load.tip_force": core.Interval(10.0, 20.0)}, set()
    )
    assert missing_tag.is_err
    assert missing_tag.err.kind == "MissingTag"


# frob:tests crates/feldspar-py/src/rank.rs::PyRank.vector
# frob:tests crates/feldspar-py/src/rank.rs::PyRank.tensor
def test_rank_variants() -> None:
    assert core.Rank.scalar().kind == "scalar"
    assert core.Rank.vector(3).n == 3
    tensor = core.Rank.tensor(2, 2)
    assert (tensor.n, tensor.m) == (2, 2)


# frob:tests crates/feldspar-py/src/rank.rs::PyRank.complex
# frob:tests crates/feldspar-py/src/rank.rs::PyRank.__repr__
# frob:tests crates/feldspar-py/src/rank.rs::PyRank.__richcmp__
# frob:tests crates/feldspar-py/src/rank.rs::PyRank.__hash__
def test_rank_complex_equality_hash_and_repr() -> None:
    a = core.Rank.complex()
    b = core.Rank.complex()
    assert a == b
    assert hash(a) == hash(b)
    assert repr(a) == "Rank.complex()"
    assert repr(core.Rank.vector(3)) == "Rank.vector(3)"


# frob:tests crates/feldspar-py/src/rank.rs::PyPortDecl.py_new
# frob:tests crates/feldspar-py/src/rank.rs::PyPortDecl.__repr__
# frob:tests crates/feldspar-py/src/rank.rs::PyPortDecl.__richcmp__
# frob:tests crates/feldspar-py/src/rank.rs::PyPortDecl.__hash__
def test_port_decl_equality_hash_and_repr() -> None:
    a = core.PortDecl("mech.load.tip_force", "N", core.Rank.vector(3))
    b = core.PortDecl("mech.load.tip_force", "N", core.Rank.vector(3))
    assert a == b
    assert hash(a) == hash(b)
    assert "mech.load.tip_force" in repr(a)


def test_format_f64_round_trips() -> None:
    x = 0.1 + 0.2
    assert float(core.format_f64(x)) == x


# frob:tests crates/feldspar-py/src/dimension.rs::PyDimension.__repr__
# frob:tests crates/feldspar-py/src/dimension.rs::PyDimension.__richcmp__
# frob:tests crates/feldspar-py/src/dimension.rs::PyDimension.__hash__
def test_dimension_equality_hash_and_repr() -> None:
    a = core.Dimension((1, 0, 0, 0, 0, 0, 0))
    b = core.Dimension((1, 0, 0, 0, 0, 0, 0))
    assert a == b
    assert hash(a) == hash(b)
    assert "1" in repr(a)


# frob:tests crates/feldspar-py/src/domain.rs::PyDomain.py_new
# frob:tests crates/feldspar-py/src/domain.rs::PyDomain.get_box
# frob:tests crates/feldspar-py/src/domain.rs::PyDomain._admits_checked
# frob:tests crates/feldspar-py/src/domain.rs::PyDomain.__repr__
def test_domain_get_box_and_repr() -> None:
    domain = core.Domain(
        {"mech.load.tip_force": core.Interval(0.0, 100.0)}, {"linear_elastic"}
    )
    box = domain.box
    assert box["mech.load.tip_force"].lo == 0.0
    assert "linear_elastic" in repr(domain)


# frob:tests crates/feldspar-py/src/units.rs::PyUnitSystem._dimension_of_checked
# frob:tests crates/feldspar-py/src/units.rs::PyUnitSystem._to_si_checked
# frob:tests crates/feldspar-py/src/units.rs::PyUnitSystem._from_si_checked
def test_unit_system_dimension_of_and_checked_conversions() -> None:
    sys_ = core.UnitSystem.builtin()
    dim = sys_.dimension_of("Pa").danger_ok
    assert isinstance(dim, core.Dimension)
    assert sys_.to_si(1.0, "Pa").danger_ok == pytest.approx(1.0)
    assert sys_.from_si(1.0, "Pa").danger_ok == pytest.approx(1.0)
