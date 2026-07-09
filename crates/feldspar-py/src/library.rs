//! PyO3 wrappers for `feldspar_library::mech` (WO-07): marshalling only,
//! no logic (AD-1 layering) -- each `#[pyfunction]` here is a thin,
//! zero-logic pass-through to the single Rust home of the formula in
//! `feldspar-library`. Python-visible names carry a `mech_` prefix to
//! keep the flat `_feldspar` namespace collision-free with future
//! namespaces (thermo, fluids, ...).

use pyo3::prelude::*;

/// See `feldspar_library::mech::rect_second_moment` for the formula and
/// citation (Gere, *Mechanics of Materials*, 9th ed., App. E).
#[pyfunction]
#[pyo3(name = "mech_rect_second_moment")]
pub fn mech_rect_second_moment_py(width: f64, height: f64) -> f64 {
    feldspar_library::mech::rect_second_moment(width, height)
}

/// See `feldspar_library::mech::cantilever_tip_deflection` for the
/// formula and citation (Gere, *Mechanics of Materials*, 9th ed.).
#[pyfunction]
#[pyo3(name = "mech_cantilever_tip_deflection")]
pub fn mech_cantilever_tip_deflection_py(
    force: f64,
    length: f64,
    youngs_modulus: f64,
    second_moment: f64,
) -> f64 {
    feldspar_library::mech::cantilever_tip_deflection(force, length, youngs_modulus, second_moment)
}

/// See `feldspar_library::mech::cantilever_required_youngs_modulus` for
/// the formula and citation (same law as the tip-deflection formula,
/// solved for `E`).
#[pyfunction]
#[pyo3(name = "mech_cantilever_required_youngs_modulus")]
pub fn mech_cantilever_required_youngs_modulus_py(
    force: f64,
    length: f64,
    second_moment: f64,
    deflection: f64,
) -> f64 {
    feldspar_library::mech::cantilever_required_youngs_modulus(
        force,
        length,
        second_moment,
        deflection,
    )
}

/// See `feldspar_library::mech::lame_hoop_stress_bore` for the formula
/// and citation (Budynas & Nisbett, *Shigley's Mechanical Engineering
/// Design*, "Thick-Walled Cylinders").
#[pyfunction]
#[pyo3(name = "mech_lame_hoop_stress_bore")]
pub fn mech_lame_hoop_stress_bore_py(pressure: f64, inner_radius: f64, outer_radius: f64) -> f64 {
    feldspar_library::mech::lame_hoop_stress_bore(pressure, inner_radius, outer_radius)
}

/// See `feldspar_library::mech::lame_radial_stress_bore` for the
/// formula and citation (Budynas & Nisbett, *Shigley's Mechanical
/// Engineering Design*, "Thick-Walled Cylinders").
#[pyfunction]
#[pyo3(name = "mech_lame_radial_stress_bore")]
pub fn mech_lame_radial_stress_bore_py(pressure: f64, inner_radius: f64, outer_radius: f64) -> f64 {
    feldspar_library::mech::lame_radial_stress_bore(pressure, inner_radius, outer_radius)
}

/// See `feldspar_library::mech::von_mises_principal` for the formula
/// and citation (Budynas & Nisbett, *Shigley's Mechanical Engineering
/// Design*, distortion-energy equivalent stress).
#[pyfunction]
#[pyo3(name = "mech_von_mises_principal")]
pub fn mech_von_mises_principal_py(sigma1: f64, sigma2: f64, sigma3: f64) -> f64 {
    feldspar_library::mech::von_mises_principal(sigma1, sigma2, sigma3)
}

/// See `feldspar_library::mech::bore_von_mises` for the formula and
/// citation (Budynas & Nisbett, *Shigley's Mechanical Engineering
/// Design*, "Thick-Walled Cylinders" and distortion-energy equivalent
/// stress).
#[pyfunction]
#[pyo3(name = "mech_bore_von_mises")]
pub fn mech_bore_von_mises_py(pressure: f64, inner_radius: f64, outer_radius: f64) -> f64 {
    feldspar_library::mech::bore_von_mises(pressure, inner_radius, outer_radius)
}

// ---------------------------------------------------------------------------
// fluids (WO-20)
// ---------------------------------------------------------------------------

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

#[pyfunction]
#[pyo3(name = "fluids_laminar_friction_factor")]
pub fn fluids_laminar_friction_factor_py(reynolds: f64) -> f64 {
    feldspar_library::fluids::fluids_laminar_friction_factor(reynolds)
}

#[pyfunction]
#[pyo3(name = "fluids_colebrook_friction_factor")]
pub fn fluids_colebrook_friction_factor_py(reynolds: f64, relative_roughness: f64) -> f64 {
    feldspar_library::fluids::fluids_colebrook_friction_factor(reynolds, relative_roughness)
}

#[pyfunction]
#[pyo3(name = "fluids_haaland_friction_factor")]
pub fn fluids_haaland_friction_factor_py(reynolds: f64, relative_roughness: f64) -> f64 {
    feldspar_library::fluids::fluids_haaland_friction_factor(reynolds, relative_roughness)
}

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

#[pyfunction]
#[pyo3(name = "fluids_minor_loss_dp")]
pub fn fluids_minor_loss_dp_py(k_factor: f64, density: f64, velocity: f64) -> f64 {
    feldspar_library::fluids::fluids_minor_loss_dp(k_factor, density, velocity)
}

#[pyfunction]
#[pyo3(name = "fluids_series_dp")]
pub fn fluids_series_dp_py(dp1: f64, dp2: f64) -> f64 {
    feldspar_library::fluids::fluids_series_dp(dp1, dp2)
}

#[pyfunction]
#[pyo3(name = "fluids_parallel_flow")]
pub fn fluids_parallel_flow_py(q1: f64, q2: f64) -> f64 {
    feldspar_library::fluids::fluids_parallel_flow(q1, q2)
}

#[pyfunction]
#[pyo3(name = "fluids_pump_operating_flow")]
pub fn fluids_pump_operating_flow_py(h0: f64, a: f64, h_static: f64, r: f64) -> f64 {
    feldspar_library::fluids::fluids_pump_operating_flow(h0, a, h_static, r)
}

#[pyfunction]
#[pyo3(name = "fluids_pump_operating_head")]
pub fn fluids_pump_operating_head_py(h_static: f64, r: f64, q_star: f64) -> f64 {
    feldspar_library::fluids::fluids_pump_operating_head(h_static, r, q_star)
}

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

#[pyfunction]
#[pyo3(name = "fluids_joukowsky_dp")]
pub fn fluids_joukowsky_dp_py(density: f64, wave_speed: f64, delta_velocity: f64) -> f64 {
    feldspar_library::fluids::fluids_joukowsky_dp(density, wave_speed, delta_velocity)
}

#[pyfunction]
#[pyo3(name = "fluids_isentropic_stagnation_temp_ratio")]
pub fn fluids_isentropic_stagnation_temp_ratio_py(mach: f64, gamma: f64) -> f64 {
    feldspar_library::fluids::fluids_isentropic_stagnation_temp_ratio(mach, gamma)
}

#[pyfunction]
#[pyo3(name = "fluids_isentropic_stagnation_pressure_ratio")]
pub fn fluids_isentropic_stagnation_pressure_ratio_py(mach: f64, gamma: f64) -> f64 {
    feldspar_library::fluids::fluids_isentropic_stagnation_pressure_ratio(mach, gamma)
}

#[pyfunction]
#[pyo3(name = "fluids_normal_shock_mach2")]
pub fn fluids_normal_shock_mach2_py(mach1: f64, gamma: f64) -> f64 {
    feldspar_library::fluids::fluids_normal_shock_mach2(mach1, gamma)
}

#[pyfunction]
#[pyo3(name = "fluids_normal_shock_pressure_ratio")]
pub fn fluids_normal_shock_pressure_ratio_py(mach1: f64, gamma: f64) -> f64 {
    feldspar_library::fluids::fluids_normal_shock_pressure_ratio(mach1, gamma)
}

#[pyfunction]
#[pyo3(name = "fluids_fanno_function")]
pub fn fluids_fanno_function_py(mach: f64, gamma: f64) -> f64 {
    feldspar_library::fluids::fluids_fanno_function(mach, gamma)
}

// ---------------------------------------------------------------------------
// heat (WO-20)
// ---------------------------------------------------------------------------

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

/// See `feldspar_library::mech::sdof_first_mode` for the formula and
/// citation (Rao, *Mechanical Vibrations*, SDOF undamped natural
/// frequency).
#[pyfunction]
#[pyo3(name = "mech_sdof_first_mode")]
pub fn mech_sdof_first_mode_py(stiffness: f64, mass: f64) -> f64 {
    feldspar_library::mech::sdof_first_mode(stiffness, mass)
}

/// See `feldspar_library::mech::beam_cantilever_first_mode` for the
/// formula and citation (Blevins, *Formulas for Natural Frequency and
/// Mode Shape*, Table 8-1).
#[pyfunction]
#[pyo3(name = "mech_beam_cantilever_first_mode")]
pub fn mech_beam_cantilever_first_mode_py(
    youngs_modulus: f64,
    second_moment: f64,
    density: f64,
    area: f64,
    length: f64,
) -> f64 {
    feldspar_library::mech::beam_cantilever_first_mode(
        youngs_modulus,
        second_moment,
        density,
        area,
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

/// See `feldspar_library::mech::miles_grms` for the formula and
/// citation (Steinberg, *Vibration Analysis for Electronic Equipment*,
/// ch. 2, Miles' equation).
#[pyfunction]
#[pyo3(name = "mech_miles_grms")]
pub fn mech_miles_grms_py(fn_hz: f64, q: f64, asd: f64) -> f64 {
    feldspar_library::mech::miles_grms(fn_hz, q, asd)
}
