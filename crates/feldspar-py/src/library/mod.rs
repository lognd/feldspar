//! PyO3 wrappers for `feldspar_library`, split by namespace: `mech`,
//! `fluids`, `heat`, `elec`. Marshalling only, no logic (AD-1 layering)
//! -- each `#[pyfunction]` is a thin, zero-logic pass-through to the
//! single Rust home of the formula in `feldspar-library`.
//!
//! `pub use` re-exports below keep `crate::library::X` paths (used by
//! `feldspar-py/src/lib.rs`'s pymodule registration) IDENTICAL to
//! before the split.

mod elec;
mod fluids;
mod heat;
mod mech;

pub use elec::{
    elec_bjt_bias_collector_current_py, elec_bjt_bias_collector_voltage_py,
    elec_divider_loaded_vout_py, elec_nmos_saturation_drain_current_py, elec_rc_step_response_py,
    elec_rlc_quality_factor_py, elec_rlc_resonant_frequency_py,
};
pub use fluids::{
    fluids_colebrook_friction_factor_py, fluids_darcy_dp_py, fluids_fanno_function_py,
    fluids_haaland_friction_factor_py, fluids_isentropic_stagnation_pressure_ratio_py,
    fluids_isentropic_stagnation_temp_ratio_py, fluids_joukowsky_dp_py,
    fluids_laminar_friction_factor_py, fluids_minor_loss_dp_py, fluids_normal_shock_mach2_py,
    fluids_normal_shock_pressure_ratio_py, fluids_npsh_available_py, fluids_parallel_flow_py,
    fluids_pump_operating_flow_py, fluids_pump_operating_head_py, fluids_reynolds_number_py,
    fluids_series_dp_py,
};
pub use heat::{
    heat_coefficient_from_nusselt_py, heat_convection_resistance_py,
    heat_cylindrical_wall_resistance_py, heat_dittus_boelter_nusselt_py,
    heat_plane_wall_resistance_py, heat_rate_from_resistance_py, heat_series_resistance_py,
};
pub use mech::{
    mech_beam_cantilever_first_mode_py, mech_bore_von_mises_py,
    mech_cantilever_required_youngs_modulus_py, mech_cantilever_tip_deflection_py,
    mech_lame_hoop_stress_bore_py, mech_lame_radial_stress_bore_py, mech_miles_grms_py,
    mech_rect_second_moment_py, mech_sdof_first_mode_py, mech_von_mises_principal_py,
};
