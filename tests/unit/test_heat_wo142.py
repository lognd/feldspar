from __future__ import annotations

"""WO-142 conformance tests: calibration cases for the heat-transfer
correlation growth (lithos companion WO) -- Gnielinski, Dittus-Boelter
cooling, laminar fully-developed Nu constants, Churchill-Chu natural
convection, and the NTU-effectiveness family. Every case is called
THROUGH the `SolverRegistry`/`SolveFn` protocol, same discipline as
`test_library_heat.py`."""

import math

import pytest

from feldspar.heat.closed_form import register
from feldspar.solve import SolverRegistry


# frob:ticket T-0020
def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register(registry)
    return registry


# frob:ticket T-0020
def _solvers() -> dict:
    registry = _registry()
    return {info.solver_id: (info, fn) for info, fn in registry}


# --- Dittus-Boelter cooling branch (deliverable 2) --------------------


# frob:tests python/feldspar/heat/closed_form.py::dittus_boelter_nusselt_cooling kind="unit"
# frob:ticket T-0020
def test_dittus_boelter_cooling_known_answer():
    """Nu = 0.023 * Re^0.8 * Pr^0.3 (cooling, n=0.3). Re=1e5, Pr=5.0 --
    Dittus & Boelter (1930), Univ. Calif. Publ. Eng. 2:443, reprinted
    Int. Comm. Heat Mass Transfer 12 (1985) 3-22."""
    _info, fn = _solvers()["heat.dittus_boelter_nusselt_cooling"]
    result = fn(
        {"heat.internal_flow.reynolds": 1.0e5, "heat.internal_flow.prandtl": 5.0}
    )
    assert result.is_ok
    expected = 0.023 * (1.0e5) ** 0.8 * (5.0) ** 0.3
    assert result.danger_ok.values["heat.internal_flow.nusselt"] == pytest.approx(
        expected, rel=1e-9
    )
    # Cooling exponent (0.3) must give a lower Nu than heating (0.4) at
    # the same Re/Pr > 1 (Pr^0.3 < Pr^0.4 for Pr > 1).
    _heat_info, heat_fn = _solvers()["heat.dittus_boelter_nusselt_heating"]
    heating_nu = heat_fn(
        {"heat.internal_flow.reynolds": 1.0e5, "heat.internal_flow.prandtl": 5.0}
    ).danger_ok.values["heat.internal_flow.nusselt"]
    assert expected < heating_nu


# --- Gnielinski (deliverable 1) ---------------------------------------


# frob:tests python/feldspar/heat/closed_form.py::gnielinski_nusselt kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_gnielinski_nusselt_py kind="unit"
# frob:ticket T-0020
def test_gnielinski_known_answer():
    """Nu = (f/8)(Re-1000)Pr / (1 + 12.7*(f/8)^0.5*(Pr^(2/3)-1)).
    Gnielinski, V. (1976), Int. Chem. Eng. 16(2):359-368. Re=5e4,
    Pr=0.7 (air), f=0.02096 (Petukhov first-equation smooth-tube
    friction factor at this Re, restated Incropera & DeWitt ch. 8) --
    consumes the friction factor the same way WO-139's friction model
    feeds it, the natural f-coupled pairing the WO names."""
    _info, fn = _solvers()["heat.gnielinski_nusselt"]
    reynolds = 5.0e4
    prandtl = 0.7
    friction_factor = (0.790 * math.log(reynolds) - 1.64) ** -2
    result = fn(
        {
            "heat.internal_flow.reynolds": reynolds,
            "heat.internal_flow.prandtl": prandtl,
            "heat.internal_flow.friction_factor": friction_factor,
        }
    )
    assert result.is_ok
    f8 = friction_factor / 8.0
    expected = (f8 * (reynolds - 1000.0) * prandtl) / (
        1.0 + 12.7 * f8**0.5 * (prandtl ** (2.0 / 3.0) - 1.0)
    )
    assert result.danger_ok.values[
        "heat.internal_flow.nusselt.gnielinski"
    ] == pytest.approx(expected, rel=1e-9)
    # House sanity: Gnielinski should sit within the well-known ~20%
    # band of Dittus-Boelter for the same Re/Pr, smooth pipe.
    db_fn = _solvers()["heat.dittus_boelter_nusselt_heating"][1]
    db_nu = db_fn(
        {"heat.internal_flow.reynolds": reynolds, "heat.internal_flow.prandtl": prandtl}
    ).danger_ok.values["heat.internal_flow.nusselt"]
    assert abs(expected - db_nu) / db_nu < 0.25


# frob:tests python/feldspar/heat/closed_form.py::gnielinski_nusselt kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_gnielinski_nusselt_py kind="unit"
# frob:ticket T-0020
def test_gnielinski_domain_matches_published_validity_box():
    """Gnielinski's own validity box: 3000 < Re < 5e6 (WO-142
    deliverable 1)."""
    info, _fn = _solvers()["heat.gnielinski_nusselt"]
    assert info.domain.box["heat.internal_flow.reynolds"].lo == pytest.approx(3000.0)
    assert info.domain.box["heat.internal_flow.reynolds"].hi == pytest.approx(5.0e6)


# --- Laminar fully-developed Nu constants (deliverable 3) -------------


# frob:tests python/feldspar/heat/closed_form.py::laminar_fully_developed_nusselt_const_temp kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_laminar_nusselt_py kind="unit"
# frob:tests python/feldspar/heat/closed_form.py::laminar_fully_developed_nusselt_const_flux kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_laminar_nusselt_py kind="unit"
# frob:ticket T-0020
def test_laminar_nusselt_constants_match_table_8_1():
    """Incropera & DeWitt Table 8.1 lineage: Nu=3.66 (constant T_wall),
    Nu=4.36 (constant q'')."""
    const_temp_fn = _solvers()["heat.laminar_fully_developed_nusselt_const_temp"][1]
    const_flux_fn = _solvers()["heat.laminar_fully_developed_nusselt_const_flux"][1]
    assert const_temp_fn({}).danger_ok.values[
        "heat.internal_flow.nusselt.laminar_const_temp"
    ] == pytest.approx(3.66, rel=1e-9)
    assert const_flux_fn({}).danger_ok.values[
        "heat.internal_flow.nusselt.laminar_const_flux"
    ] == pytest.approx(4.36, rel=1e-9)


# --- Churchill-Chu natural convection (deliverable 4) ------------------


# frob:tests python/feldspar/heat/closed_form.py::churchill_chu_horizontal_cylinder_nusselt kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_churchill_chu_horizontal_cylinder_nusselt_py kind="unit"
# frob:ticket T-0020
def test_churchill_chu_horizontal_cylinder_known_answer():
    """Nu^0.5 = 0.60 + 0.387*Ra^(1/6) / [1+(0.559/Pr)^(9/16)]^(8/27).
    Churchill & Chu (1975), Int. J. Heat Mass Transfer 18:1049-1053
    (primary paywalled; restated Incropera & DeWitt eq. 9.34). Ra=1e7,
    Pr=0.7 (air, horizontal cylinder)."""
    _info, fn = _solvers()["heat.churchill_chu_horizontal_cylinder_nusselt"]
    rayleigh = 1.0e7
    prandtl = 0.7
    result = fn(
        {
            "heat.natural_convection.rayleigh": rayleigh,
            "heat.natural_convection.prandtl": prandtl,
        }
    )
    assert result.is_ok
    bracket = 1.0 + (0.559 / prandtl) ** (9.0 / 16.0)
    sqrt_nu = 0.60 + 0.387 * rayleigh ** (1.0 / 6.0) / bracket ** (8.0 / 27.0)
    expected = sqrt_nu**2
    assert result.danger_ok.values[
        "heat.natural_convection.nusselt.horizontal_cylinder"
    ] == pytest.approx(expected, rel=1e-9)


# frob:tests python/feldspar/heat/closed_form.py::churchill_chu_vertical_plate_nusselt kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_churchill_chu_vertical_plate_nusselt_py kind="unit"
# frob:ticket T-0020
def test_churchill_chu_vertical_plate_known_answer():
    """Nu^0.5 = 0.825 + 0.387*Ra^(1/6) / [1+(0.492/Pr)^(9/16)]^(8/27).
    Churchill & Chu (1975), Int. J. Heat Mass Transfer 18:1323-1329
    (primary paywalled; restated Incropera & DeWitt eq. 9.26). Ra=1e9,
    Pr=0.7 (air, vertical plate)."""
    _info, fn = _solvers()["heat.churchill_chu_vertical_plate_nusselt"]
    rayleigh = 1.0e9
    prandtl = 0.7
    result = fn(
        {
            "heat.natural_convection.rayleigh": rayleigh,
            "heat.natural_convection.prandtl": prandtl,
        }
    )
    assert result.is_ok
    bracket = 1.0 + (0.492 / prandtl) ** (9.0 / 16.0)
    sqrt_nu = 0.825 + 0.387 * rayleigh ** (1.0 / 6.0) / bracket ** (8.0 / 27.0)
    expected = sqrt_nu**2
    assert result.danger_ok.values[
        "heat.natural_convection.nusselt.vertical_plate"
    ] == pytest.approx(expected, rel=1e-9)


# --- NTU-effectiveness family (deliverable 5) --------------------------


# frob:tests python/feldspar/heat/closed_form.py::ntu_from_ua kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_ntu_from_ua_py kind="unit"
# frob:ticket T-0020
def test_ntu_from_ua_known_answer():
    """NTU = UA/C_min. Kays & London, Compact Heat Exchangers, 3rd ed.
    (1984); restated Incropera & DeWitt sec. 11.4. UA=500 W/K,
    C_min=250 W/K -> NTU=2.0."""
    fn = _solvers()["heat.ntu_from_ua"][1]
    result = fn({"heat.hx.ua": 500.0, "heat.hx.c_min": 250.0})
    assert result.is_ok
    assert result.danger_ok.values["heat.hx.ntu"] == pytest.approx(2.0, rel=1e-9)


@pytest.mark.parametrize(
    "solver_id,port",
    [
        ("heat.effectiveness_parallel_flow", "heat.hx.effectiveness.parallel_flow"),
        ("heat.effectiveness_counterflow", "heat.hx.effectiveness.counterflow"),
        (
            "heat.effectiveness_shell_and_tube_one_pass",
            "heat.hx.effectiveness.shell_and_tube_one_pass",
        ),
    ],
)
# frob:tests python/feldspar/heat/closed_form.py::effectiveness_parallel_flow kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_effectiveness_parallel_flow_py kind="unit"
# frob:tests python/feldspar/heat/closed_form.py::effectiveness_counterflow kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_effectiveness_counterflow_py kind="unit"
# frob:tests python/feldspar/heat/closed_form.py::effectiveness_shell_and_tube_one_pass kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_effectiveness_shell_and_tube_one_pass_py kind="unit"
# frob:ticket T-0020
def test_effectiveness_cr_zero_identity_holds_for_every_arrangement(solver_id, port):
    """The Cr=0 special case (one fluid changing phase, or C_max
    infinite) reduces to `eff = 1 - exp(-NTU)` for EVERY flow
    arrangement (Incropera & DeWitt Table 11.4, footnote); a case-
    independent identity that must hold across the whole family."""
    fn = _solvers()[solver_id][1]
    ntu = 1.5
    result = fn({"heat.hx.ntu": ntu, "heat.hx.c_r": 0.0})
    assert result.is_ok
    expected = 1.0 - math.exp(-ntu)
    assert result.danger_ok.values[port] == pytest.approx(expected, rel=1e-6)


# frob:tests python/feldspar/heat/closed_form.py::effectiveness_counterflow kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_effectiveness_counterflow_py kind="unit"
# frob:ticket T-0020
def test_effectiveness_counterflow_beats_parallel_flow_at_equal_ntu_cr():
    """Counterflow always outperforms parallel flow at equal NTU/Cr
    (Incropera & DeWitt sec. 11.4, standard result)."""
    ntu, c_r = 2.0, 0.5
    counter = _solvers()["heat.effectiveness_counterflow"][1](
        {"heat.hx.ntu": ntu, "heat.hx.c_r": c_r}
    ).danger_ok.values["heat.hx.effectiveness.counterflow"]
    parallel = _solvers()["heat.effectiveness_parallel_flow"][1](
        {"heat.hx.ntu": ntu, "heat.hx.c_r": c_r}
    ).danger_ok.values["heat.hx.effectiveness.parallel_flow"]
    assert counter > parallel


# frob:tests python/feldspar/heat/closed_form.py::hx_rate_from_effectiveness kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_hx_rate_from_effectiveness_py kind="unit"
# frob:tests python/feldspar/heat/closed_form.py::hx_outlet_temp_hot kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_hx_outlet_temp_py kind="unit"
# frob:tests python/feldspar/heat/closed_form.py::hx_outlet_temp_cold kind="unit"
# frob:tests crates/feldspar-py/src/library/heat.rs::heat_hx_outlet_temp_py kind="unit"
# frob:ticket T-0020
def test_hx_rate_and_outlet_temps_energy_balance():
    """Composes UA -> NTU -> effectiveness -> outlet temperatures
    (WO-142 deliverable 5): C_min=1000 W/K, C_hot=2000 W/K, eff=0.6,
    T_hot_in=80C, T_cold_in=20C -- q=eff*Cmin*dT, then each stream's
    outlet from its own energy balance (Incropera & DeWitt sec. 11.1/
    11.3)."""
    solvers = _solvers()
    c_min = 1000.0
    c_hot = 2000.0
    c_cold = c_min
    effectiveness = 0.6
    t_hot_in = 80.0
    t_cold_in = 20.0

    rate_result = solvers["heat.hx_rate_from_effectiveness"][1](
        {
            "heat.hx.effectiveness": effectiveness,
            "heat.hx.c_min": c_min,
            "heat.hx.t_hot_in": t_hot_in,
            "heat.hx.t_cold_in": t_cold_in,
        }
    )
    assert rate_result.is_ok
    rate = rate_result.danger_ok.values["heat.hx.rate"]
    assert rate == pytest.approx(
        effectiveness * c_min * (t_hot_in - t_cold_in), rel=1e-9
    )

    hot_out = solvers["heat.hx_outlet_temp_hot"][1](
        {"heat.hx.t_in": t_hot_in, "heat.hx.rate": rate, "heat.hx.capacity_rate": c_hot}
    ).danger_ok.values["heat.hx.t_out.hot"]
    cold_out = solvers["heat.hx_outlet_temp_cold"][1](
        {
            "heat.hx.t_in": t_cold_in,
            "heat.hx.rate": rate,
            "heat.hx.capacity_rate": c_cold,
        }
    ).danger_ok.values["heat.hx.t_out.cold"]

    assert hot_out == pytest.approx(t_hot_in - rate / c_hot, rel=1e-9)
    assert cold_out == pytest.approx(t_cold_in + rate / c_cold, rel=1e-9)
    assert hot_out < t_hot_in
    assert cold_out > t_cold_in
    # Overall energy balance: heat lost by hot stream equals heat gained
    # by cold stream (both computed from the same q).
    assert c_hot * (t_hot_in - hot_out) == pytest.approx(
        c_cold * (cold_out - t_cold_in), rel=1e-9
    )
