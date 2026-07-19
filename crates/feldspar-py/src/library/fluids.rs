//! PyO3 wrappers for `feldspar_library::fluids` (WO-20): marshalling
//! only, no logic (AD-1 layering). Same thin pass-through contract as
//! `library::mech`.

use pyo3::prelude::*;

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_reynolds_number")]
pub fn fluids_reynolds_number_py(
    density: f64,
    velocity: f64,
    diameter: f64,
    viscosity: f64,
) -> f64 {
    feldspar_library::fluids::fluids_reynolds_number(density, velocity, diameter, viscosity)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_laminar_friction_factor")]
pub fn fluids_laminar_friction_factor_py(reynolds: f64) -> f64 {
    feldspar_library::fluids::fluids_laminar_friction_factor(reynolds)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_colebrook_friction_factor")]
pub fn fluids_colebrook_friction_factor_py(reynolds: f64, relative_roughness: f64) -> f64 {
    feldspar_library::fluids::fluids_colebrook_friction_factor(reynolds, relative_roughness)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_haaland_friction_factor")]
pub fn fluids_haaland_friction_factor_py(reynolds: f64, relative_roughness: f64) -> f64 {
    feldspar_library::fluids::fluids_haaland_friction_factor(reynolds, relative_roughness)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_darcy_dp")]
pub fn fluids_darcy_dp_py(
    friction_factor: f64,
    length: f64,
    diameter: f64,
    density: f64,
    velocity: f64,
) -> f64 {
    feldspar_library::fluids::fluids_darcy_dp(friction_factor, length, diameter, density, velocity)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_minor_loss_dp")]
pub fn fluids_minor_loss_dp_py(k_factor: f64, density: f64, velocity: f64) -> f64 {
    feldspar_library::fluids::fluids_minor_loss_dp(k_factor, density, velocity)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_series_dp")]
pub fn fluids_series_dp_py(dp1: f64, dp2: f64) -> f64 {
    feldspar_library::fluids::fluids_series_dp(dp1, dp2)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_parallel_flow")]
pub fn fluids_parallel_flow_py(q1: f64, q2: f64) -> f64 {
    feldspar_library::fluids::fluids_parallel_flow(q1, q2)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_pump_operating_flow")]
pub fn fluids_pump_operating_flow_py(h0: f64, a: f64, h_static: f64, r: f64) -> f64 {
    feldspar_library::fluids::fluids_pump_operating_flow(h0, a, h_static, r)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_pump_operating_head")]
pub fn fluids_pump_operating_head_py(h_static: f64, r: f64, q_star: f64) -> f64 {
    feldspar_library::fluids::fluids_pump_operating_head(h_static, r, q_star)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_npsh_available")]
pub fn fluids_npsh_available_py(
    p_atm: f64,
    p_vapor: f64,
    density: f64,
    gravity: f64,
    static_head: f64,
    friction_head: f64,
) -> f64 {
    feldspar_library::fluids::fluids_npsh_available(
        p_atm,
        p_vapor,
        density,
        gravity,
        static_head,
        friction_head,
    )
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_joukowsky_dp")]
pub fn fluids_joukowsky_dp_py(density: f64, wave_speed: f64, delta_velocity: f64) -> f64 {
    feldspar_library::fluids::fluids_joukowsky_dp(density, wave_speed, delta_velocity)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_isentropic_stagnation_temp_ratio")]
pub fn fluids_isentropic_stagnation_temp_ratio_py(mach: f64, gamma: f64) -> f64 {
    feldspar_library::fluids::fluids_isentropic_stagnation_temp_ratio(mach, gamma)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_isentropic_stagnation_pressure_ratio")]
pub fn fluids_isentropic_stagnation_pressure_ratio_py(mach: f64, gamma: f64) -> f64 {
    feldspar_library::fluids::fluids_isentropic_stagnation_pressure_ratio(mach, gamma)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_normal_shock_mach2")]
pub fn fluids_normal_shock_mach2_py(mach1: f64, gamma: f64) -> f64 {
    feldspar_library::fluids::fluids_normal_shock_mach2(mach1, gamma)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_normal_shock_pressure_ratio")]
pub fn fluids_normal_shock_pressure_ratio_py(mach1: f64, gamma: f64) -> f64 {
    feldspar_library::fluids::fluids_normal_shock_pressure_ratio(mach1, gamma)
}

// frob:doc docs/modules/feldspar-py.md#py_library_fluids
#[pyfunction]
#[pyo3(name = "fluids_fanno_function")]
pub fn fluids_fanno_function_py(mach: f64, gamma: f64) -> f64 {
    feldspar_library::fluids::fluids_fanno_function(mach, gamma)
}
