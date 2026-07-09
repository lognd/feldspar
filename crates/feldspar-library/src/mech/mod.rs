//! Mechanical-engineering closed-form formula home (WO-07), split by
//! subdomain: [`sections`] (cross-section properties), [`statics`]
//! (beam deflection, thick-cylinder Lame/von Mises stress), and
//! [`vibration`] (SDOF/beam natural frequency, Miles' equation).
//!
//! Every formula is defined once as `#[no_mangle] pub extern "C" fn`
//! (AD-3): this makes it BOTH the plain Rust `pub fn` other Rust code
//! calls (PyO3 bindings, other formulas, tests) AND the symbol visible
//! to `dlopen`/`nm` from outside the crate -- a single definition per
//! formula, no separate wrapper, so there is exactly one home per law
//! (NO DUPLICATION). All math here uses only `+ - * / powi sqrt`, which
//! are IEEE-754 exempt (AD-13); no transcendentals appear, so `libm` is
//! not needed in this module.
//!
//! `pub use` re-exports below keep every `feldspar_library::mech::X`
//! path IDENTICAL to before the split (crate consumers, PyO3 bindings,
//! and the `extern "C"` symbol table are all unaffected).

mod sections;
mod statics;
mod vibration;

pub use sections::rect_second_moment;
pub use statics::{
    bore_von_mises, cantilever_required_youngs_modulus, cantilever_tip_deflection,
    lame_hoop_stress_bore, lame_radial_stress_bore, von_mises_principal,
};
pub use vibration::{beam_cantilever_first_mode, miles_grms, sdof_first_mode};
