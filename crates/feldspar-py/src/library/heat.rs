//! PyO3 wrappers for `feldspar_library::heat` (WO-20): marshalling
//! only, no logic (AD-1 layering). Same thin pass-through contract as
//! `library::mech`.

use pyo3::prelude::*;

#[pyfunction]
#[pyo3(name = "heat_plane_wall_resistance")]
pub fn heat_plane_wall_resistance_py(thickness: f64, conductivity: f64, area: f64) -> f64 {
    feldspar_library::heat::heat_plane_wall_resistance(thickness, conductivity, area)
}

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

#[pyfunction]
#[pyo3(name = "heat_convection_resistance")]
pub fn heat_convection_resistance_py(coefficient: f64, area: f64) -> f64 {
    feldspar_library::heat::heat_convection_resistance(coefficient, area)
}

#[pyfunction]
#[pyo3(name = "heat_series_resistance")]
pub fn heat_series_resistance_py(r1: f64, r2: f64) -> f64 {
    feldspar_library::heat::heat_series_resistance(r1, r2)
}

#[pyfunction]
#[pyo3(name = "heat_rate_from_resistance")]
pub fn heat_rate_from_resistance_py(delta_temp: f64, resistance: f64) -> f64 {
    feldspar_library::heat::heat_rate_from_resistance(delta_temp, resistance)
}

#[pyfunction]
#[pyo3(name = "heat_dittus_boelter_nusselt")]
pub fn heat_dittus_boelter_nusselt_py(reynolds: f64, prandtl: f64, heating: bool) -> f64 {
    feldspar_library::heat::heat_dittus_boelter_nusselt(reynolds, prandtl, heating)
}

#[pyfunction]
#[pyo3(name = "heat_coefficient_from_nusselt")]
pub fn heat_coefficient_from_nusselt_py(
    nusselt: f64,
    fluid_conductivity: f64,
    diameter: f64,
) -> f64 {
    feldspar_library::heat::heat_coefficient_from_nusselt(nusselt, fluid_conductivity, diameter)
}
