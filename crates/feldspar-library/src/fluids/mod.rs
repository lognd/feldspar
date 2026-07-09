//! Fluid-mechanics closed-form formula home (WO-20 Phase 2), split by
//! regime: [`incompressible`] (internal flow, pipe networks,
//! turbomachinery, water hammer) and [`compressible`] (D141 isentropic
//! relations, normal shocks, the Fanno function). Same
//! `#[no_mangle] pub extern "C" fn` discipline as `mech` (AD-3): one
//! link-visible definition per formula, callable from Rust, PyO3, and
//! `dlopen`/`nm` alike.
//!
//! Both regimes are registered under the SAME `fluids` namespace via
//! the `pub use` re-exports below (paths stay IDENTICAL to before the
//! split); Python side distinguishes the regime via `Domain.tags`
//! ("compressible" / "incompressible") since the low-Mach/choked
//! screening lives there (09 sec. 4/lithos WO-14 regime channel).

mod compressible;
mod incompressible;

pub use compressible::{
    fluids_fanno_function, fluids_isentropic_stagnation_pressure_ratio,
    fluids_isentropic_stagnation_temp_ratio, fluids_normal_shock_mach2,
    fluids_normal_shock_pressure_ratio,
};
pub use incompressible::{
    fluids_colebrook_friction_factor, fluids_darcy_dp, fluids_haaland_friction_factor,
    fluids_joukowsky_dp, fluids_laminar_friction_factor, fluids_minor_loss_dp,
    fluids_npsh_available, fluids_parallel_flow, fluids_pump_operating_flow,
    fluids_pump_operating_head, fluids_reynolds_number, fluids_series_dp,
};
