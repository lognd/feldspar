//! PyO3 wrappers for `feldspar_library::heat` (WO-20): marshalling
//! only, no logic (AD-1 layering). Same thin pass-through contract as
//! `library::mech`.

use pyo3::prelude::*;

// frob:doc docs/modules/feldspar-py.md#py_library_heat
#[pyfunction]
#[pyo3(name = "heat_plane_wall_resistance")]
pub fn heat_plane_wall_resistance_py(thickness: f64, conductivity: f64, area: f64) -> f64 {
    feldspar_library::heat::heat_plane_wall_resistance(thickness, conductivity, area)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
#[pyfunction]
#[pyo3(name = "heat_cylindrical_wall_resistance")]
pub fn heat_cylindrical_wall_resistance_py(
    inner_radius: f64,
    outer_radius: f64,
    conductivity: f64,
    length: f64,
) -> f64 {
    feldspar_library::heat::heat_cylindrical_wall_resistance(
        inner_radius,
        outer_radius,
        conductivity,
        length,
    )
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
#[pyfunction]
#[pyo3(name = "heat_convection_resistance")]
pub fn heat_convection_resistance_py(coefficient: f64, area: f64) -> f64 {
    feldspar_library::heat::heat_convection_resistance(coefficient, area)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
#[pyfunction]
#[pyo3(name = "heat_series_resistance")]
pub fn heat_series_resistance_py(r1: f64, r2: f64) -> f64 {
    feldspar_library::heat::heat_series_resistance(r1, r2)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
#[pyfunction]
#[pyo3(name = "heat_rate_from_resistance")]
pub fn heat_rate_from_resistance_py(delta_temp: f64, resistance: f64) -> f64 {
    feldspar_library::heat::heat_rate_from_resistance(delta_temp, resistance)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
#[pyfunction]
#[pyo3(name = "heat_dittus_boelter_nusselt")]
pub fn heat_dittus_boelter_nusselt_py(reynolds: f64, prandtl: f64, heating: bool) -> f64 {
    feldspar_library::heat::heat_dittus_boelter_nusselt(reynolds, prandtl, heating)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
#[pyfunction]
#[pyo3(name = "heat_coefficient_from_nusselt")]
pub fn heat_coefficient_from_nusselt_py(
    nusselt: f64,
    fluid_conductivity: f64,
    diameter: f64,
) -> f64 {
    feldspar_library::heat::heat_coefficient_from_nusselt(nusselt, fluid_conductivity, diameter)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
// frob:ticket T-0020
#[pyfunction]
#[pyo3(name = "heat_gnielinski_nusselt")]
pub fn heat_gnielinski_nusselt_py(reynolds: f64, prandtl: f64, friction_factor: f64) -> f64 {
    feldspar_library::heat::heat_gnielinski_nusselt(reynolds, prandtl, friction_factor)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
// frob:ticket T-0020
#[pyfunction]
#[pyo3(name = "heat_laminar_nusselt")]
pub fn heat_laminar_nusselt_py(constant_wall_temp: bool) -> f64 {
    feldspar_library::heat::heat_laminar_nusselt(constant_wall_temp)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
// frob:ticket T-0020
#[pyfunction]
#[pyo3(name = "heat_churchill_chu_horizontal_cylinder_nusselt")]
pub fn heat_churchill_chu_horizontal_cylinder_nusselt_py(rayleigh: f64, prandtl: f64) -> f64 {
    feldspar_library::heat::heat_churchill_chu_horizontal_cylinder_nusselt(rayleigh, prandtl)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
// frob:ticket T-0020
#[pyfunction]
#[pyo3(name = "heat_churchill_chu_vertical_plate_nusselt")]
pub fn heat_churchill_chu_vertical_plate_nusselt_py(rayleigh: f64, prandtl: f64) -> f64 {
    feldspar_library::heat::heat_churchill_chu_vertical_plate_nusselt(rayleigh, prandtl)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
// frob:ticket T-0020
#[pyfunction]
#[pyo3(name = "heat_ntu_from_ua")]
pub fn heat_ntu_from_ua_py(ua: f64, c_min: f64) -> f64 {
    feldspar_library::heat::heat_ntu_from_ua(ua, c_min)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
// frob:ticket T-0020
#[pyfunction]
#[pyo3(name = "heat_effectiveness_parallel_flow")]
pub fn heat_effectiveness_parallel_flow_py(ntu: f64, c_r: f64) -> f64 {
    feldspar_library::heat::heat_effectiveness_parallel_flow(ntu, c_r)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
// frob:ticket T-0020
#[pyfunction]
#[pyo3(name = "heat_effectiveness_counterflow")]
pub fn heat_effectiveness_counterflow_py(ntu: f64, c_r: f64) -> f64 {
    feldspar_library::heat::heat_effectiveness_counterflow(ntu, c_r)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
// frob:ticket T-0020
#[pyfunction]
#[pyo3(name = "heat_effectiveness_shell_and_tube_one_pass")]
pub fn heat_effectiveness_shell_and_tube_one_pass_py(ntu: f64, c_r: f64) -> f64 {
    feldspar_library::heat::heat_effectiveness_shell_and_tube_one_pass(ntu, c_r)
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
// frob:ticket T-0020
#[pyfunction]
#[pyo3(name = "heat_hx_rate_from_effectiveness")]
pub fn heat_hx_rate_from_effectiveness_py(
    effectiveness: f64,
    c_min: f64,
    t_hot_in: f64,
    t_cold_in: f64,
) -> f64 {
    feldspar_library::heat::heat_hx_rate_from_effectiveness(
        effectiveness,
        c_min,
        t_hot_in,
        t_cold_in,
    )
}

// frob:doc docs/modules/feldspar-py.md#py_library_heat
// frob:ticket T-0020
#[pyfunction]
#[pyo3(name = "heat_hx_outlet_temp")]
pub fn heat_hx_outlet_temp_py(t_in: f64, rate: f64, capacity_rate: f64, cooling: bool) -> f64 {
    feldspar_library::heat::heat_hx_outlet_temp(t_in, rate, capacity_rate, cooling)
}
