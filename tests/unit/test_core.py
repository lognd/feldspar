from __future__ import annotations

"""WO-02 Python-side type smoke tests: feldspar.core (01-interfaces).

Covers the WO-02 rows of docs/implementation/02-edge-cases.md at the
Python surface (the Rust-side equivalents live in
crates/feldspar-core/src/units.rs and tests/property.rs)."""

import math

import pytest

from feldspar import _feldspar, core


def test_interval_new_inverted_is_err() -> None:
    r = core.Interval.new(2.0, 1.0)
    assert r.is_err
    assert r.err == core.CoreError.InvertedInterval


def test_interval_new_non_finite_is_err() -> None:
    r = core.Interval.new(0.0, math.inf)
    assert r.is_err
    assert r.err == core.CoreError.NonFiniteBound


def test_interval_direct_construction_raises_on_invalid_bounds() -> None:
    """`Interval(lo, hi)` direct construction raises (programmer-bug path)."""
    with pytest.raises(_feldspar.CoreErrorRaised):
        core.Interval(2.0, 1.0)


def test_interval_degenerate_point_has_zero_width() -> None:
    p = core.Interval.point(0.0).danger_ok
    assert p.width() == 0.0


def test_interval_equality_and_hash() -> None:
    a = core.Interval(1.0, 2.0)
    b = core.Interval(1.0, 2.0)
    assert a == b
    assert hash(a) == hash(b)


def test_accuracy_worst_over_takes_larger_abs_endpoint() -> None:
    acc = core.Accuracy(0.0, 0.1)
    iv = core.Interval(-1.0, 5.0)
    assert acc.worst_over(iv) == acc.eps(5.0)


def test_to_si_degc_applies_offset() -> None:
    sys_ = core.UnitSystem.builtin()
    r = sys_.to_si(25.0, "degC")
    assert r.danger_ok == pytest.approx(298.15)


def test_percent_ingest_scale() -> None:
    sys_ = core.UnitSystem.builtin()
    assert sys_.to_si(1.0, "%").danger_ok == pytest.approx(0.01)


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


def test_digest_stable_across_map_insertion_orders() -> None:
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    assert core.canonical_digest(a) == core.canonical_digest(b)


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

    missing_tag = domain.admits({"mech.load.tip_force": core.Interval(10.0, 20.0)}, set())
    assert missing_tag.is_err
    assert missing_tag.err.kind == "MissingTag"


def test_rank_variants() -> None:
    assert core.Rank.scalar().kind == "scalar"
    assert core.Rank.vector(3).n == 3
    tensor = core.Rank.tensor(2, 2)
    assert (tensor.n, tensor.m) == (2, 2)


def test_format_f64_round_trips() -> None:
    x = 0.1 + 0.2
    assert float(core.format_f64(x)) == x
