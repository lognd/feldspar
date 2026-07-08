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
