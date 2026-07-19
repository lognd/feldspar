from __future__ import annotations

"""WO-24 deliverable 0 tests: known-answer/hand-computed unit tests for
the registered `mech.member` capacity directions
(`python/feldspar/library/member_capacity.py`), called THROUGH the
`SolverRegistry`/`SolveFn` protocol (ports, domain guards, marshalling
exercised, not just the raw formula)."""

import math

import pytest

from feldspar.library.member_capacity import register
from feldspar.solve import SolverRegistry

_PHI_B = 0.90
_PHI_C = 0.90


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    return registry


def _solvers() -> dict:
    registry = _registry()
    return {info.solver_id: (info, fn) for info, fn in registry}


def test_flexural_yield_capacity_f2_matches_hand_computed():
    """AISC 360-16 F2.1 eq. F2-1: Mn = Fy*Zx. Fy=345e6 Pa (~50 ksi),
    Zx=1.639e-3 m^3 (~100 in^3) -> Mp = 345e6 * 1.639e-3 = 565,455 N*m;
    phi_b*Mp = 0.90 * 565,455 = 508,909.5 N*m (hand-computed)."""
    _info, fn = _solvers()["mech.member.flexural_yield_capacity_f2"]
    fy = 345.0e6
    zx = 1.639e-3
    result = fn({"mech.member.flexure.fy": fy, "mech.member.flexure.zx": zx})
    assert result.is_ok
    expected = _PHI_B * fy * zx
    assert expected == pytest.approx(508909.5, rel=1e-3)
    assert result.danger_ok.values["mech.member.flexure.capacity"] == pytest.approx(
        expected, rel=1e-9
    )


def test_flexural_yield_capacity_f2_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["mech.member.flexural_yield_capacity_f2"]
    result = fn({"mech.member.flexure.fy": 0.0, "mech.member.flexure.zx": 1e-3})
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_axial_capacity_e3_inelastic_branch_matches_hand_computed():
    """AISC 360-16 E3, inelastic branch (eq. E3-2): Fy=345e6 Pa,
    Ag=0.01 m^2, E=200e9 Pa, KL/r=80.

    Fe = pi^2*E/(KL/r)^2 = pi^2*200e9/6400 = 308,425,137 Pa.
    Fy/Fe = 1.1186 <= 2.25 (equivalently KL/r=80 <= 4.71*sqrt(E/Fy)
    = 113.4) -> eq. E3-2 governs.
    Fcr = 0.658^(Fy/Fe)*Fy = 0.658^1.1186 * 345e6 = 215.9e6 Pa (approx).
    Pn = Fcr*Ag = 2.159e6 N; phi_c*Pn = 0.9*2.159e6 = 1.943e6 N (approx).
    """
    _info, fn = _solvers()["mech.member.axial_yield_buckling_capacity_e3"]
    fy = 345.0e6
    ag = 0.01
    e = 200.0e9
    kl_r = 80.0

    fe = (math.pi**2) * e / (kl_r**2)
    assert 4.71 * math.sqrt(e / fy) == pytest.approx(113.4, rel=1e-2)
    assert fy / fe <= 2.25
    fcr = (0.658 ** (fy / fe)) * fy
    expected = _PHI_C * fcr * ag
    assert expected == pytest.approx(1.943e6, rel=2e-3)

    result = fn(
        {
            "mech.member.axial.fy": fy,
            "mech.member.axial.ag": ag,
            "mech.member.axial.e": e,
            "mech.member.axial.kl_over_r": kl_r,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["mech.member.axial.capacity"] == pytest.approx(
        expected, rel=1e-9
    )


def test_axial_capacity_e3_elastic_branch_matches_hand_computed():
    """AISC 360-16 E3, elastic branch (eq. E3-3): Fy=345e6 Pa,
    Ag=0.01 m^2, E=200e9 Pa, KL/r=150 (> 4.71*sqrt(E/Fy)=113.4, so
    eq. E3-3 governs).

    Fe = pi^2*200e9/150^2 = 87,730,462 Pa.
    Fcr = 0.877*Fe = 76,939,825 Pa (approx).
    Pn = Fcr*Ag = 769,398 N; phi_c*Pn = 692,458 N (approx).
    """
    _info, fn = _solvers()["mech.member.axial_yield_buckling_capacity_e3"]
    fy = 345.0e6
    ag = 0.01
    e = 200.0e9
    kl_r = 150.0

    fe = (math.pi**2) * e / (kl_r**2)
    assert kl_r > 4.71 * math.sqrt(e / fy)
    fcr = 0.877 * fe
    expected = _PHI_C * fcr * ag
    assert expected == pytest.approx(692458.0, rel=2e-3)

    result = fn(
        {
            "mech.member.axial.fy": fy,
            "mech.member.axial.ag": ag,
            "mech.member.axial.e": e,
            "mech.member.axial.kl_over_r": kl_r,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["mech.member.axial.capacity"] == pytest.approx(
        expected, rel=1e-9
    )


def test_axial_capacity_e3_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["mech.member.axial_yield_buckling_capacity_e3"]
    result = fn(
        {
            "mech.member.axial.fy": 345.0e6,
            "mech.member.axial.ag": 0.0,
            "mech.member.axial.e": 200.0e9,
            "mech.member.axial.kl_over_r": 80.0,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_euler_critical_buckling_load_matches_hand_computed():
    """Memo sec. 9: E=200e9 Pa, I=8.0e-6 m^4, K=1.0 (pinned-pinned),
    L=3.0 m -> Pcr = pi^2*E*I/(K*L)^2 ~ 1,754,600 N (exact algebra)."""
    _info, fn = _solvers()["mech.member.euler_critical_buckling_load"]
    e = 200.0e9
    i = 8.0e-6
    k = 1.0
    length = 3.0
    expected = (math.pi**2) * e * i / ((k * length) ** 2)
    assert expected == pytest.approx(1_754_600.0, rel=1e-3)

    result = fn(
        {
            "mech.member.euler.e": e,
            "mech.member.euler.i": i,
            "mech.member.euler.k": k,
            "mech.member.euler.length": length,
        }
    )
    assert result.is_ok
    assert result.danger_ok.values["mech.member.euler.pcr"] == pytest.approx(
        expected, rel=1e-9
    )


def test_euler_critical_buckling_load_consistent_with_e3_fe():
    """Pcr = Fe*Ag since I = Ag*r^2 -- cross-check the Euler direction
    against the E3 direction's Fe for the same KL/r, confirming both
    forms encode the same physics (memo sec. 9's own claim)."""
    e = 200.0e9
    ag = 0.01
    r = 0.05
    i = ag * r * r
    kl_r = 80.0
    length = kl_r * r  # K=1.0

    _info_euler, fn_euler = _solvers()["mech.member.euler_critical_buckling_load"]
    result_euler = fn_euler(
        {
            "mech.member.euler.e": e,
            "mech.member.euler.i": i,
            "mech.member.euler.k": 1.0,
            "mech.member.euler.length": length,
        }
    )
    assert result_euler.is_ok
    pcr = result_euler.danger_ok.values["mech.member.euler.pcr"]

    fe = (math.pi**2) * e / (kl_r**2)
    assert pcr == pytest.approx(fe * ag, rel=1e-6)


def test_euler_critical_buckling_load_nonpositive_is_honest_indeterminate():
    _info, fn = _solvers()["mech.member.euler_critical_buckling_load"]
    result = fn(
        {
            "mech.member.euler.e": 200.0e9,
            "mech.member.euler.i": 0.0,
            "mech.member.euler.k": 1.0,
            "mech.member.euler.length": 3.0,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# frob:tests python/feldspar/mech/member_capacity.py::axial_yield_buckling_capacity_e3 kind="unit"
def test_solver_ids_registered_under_mech_member_namespace():
    solvers = _solvers()
    assert "mech.member.flexural_yield_capacity_f2" in solvers
    assert "mech.member.euler_critical_buckling_load" in solvers
    assert "mech.member.axial_yield_buckling_capacity_e3" in solvers
