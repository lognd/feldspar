//! Compressible-flow formulas (D141): isentropic relations, normal
//! shocks, and the Fanno function. Registered under the SAME `fluids`
//! namespace as the incompressible regime (see `fluids/mod.rs` doc
//! comment); Python side distinguishes the regime via `Domain.tags`
//! ("compressible" / "incompressible") since the low-Mach/choked
//! screening lives there (09 sec. 4/lithos WO-14 regime channel).

/// Isentropic stagnation-to-static temperature ratio:
/// `T0/T = 1 + (k-1)/2 * M^2`.
///
/// Citation: Anderson, *Modern Compressible Flow*, 3rd ed., ch. 3
/// (isentropic flow relations).
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_isentropic_stagnation_temp_ratio(mach: f64, gamma: f64) -> f64 {
    1.0 + (gamma - 1.0) / 2.0 * mach * mach
}

/// Isentropic stagnation-to-static pressure ratio:
/// `p0/p = (T0/T)^(k/(k-1))`.
///
/// Citation: Anderson, *Modern Compressible Flow*, 3rd ed., ch. 3
/// (isentropic flow relations).
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_isentropic_stagnation_pressure_ratio(mach: f64, gamma: f64) -> f64 {
    let temp_ratio = fluids_isentropic_stagnation_temp_ratio(mach, gamma);
    temp_ratio.powf(gamma / (gamma - 1.0))
}

/// Downstream Mach number squared across a normal shock (Rankine-
/// Hugoniot): `M2^2 = (1 + (k-1)/2 M1^2) / (k M1^2 - (k-1)/2)`.
///
/// Citation: Anderson, *Modern Compressible Flow*, 3rd ed., ch. 3
/// (normal shock relations).
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_normal_shock_mach2(mach1: f64, gamma: f64) -> f64 {
    let m1_sq = mach1 * mach1;
    let numerator = 1.0 + (gamma - 1.0) / 2.0 * m1_sq;
    let denominator = gamma * m1_sq - (gamma - 1.0) / 2.0;
    (numerator / denominator).sqrt()
}

/// Static pressure ratio across a normal shock:
/// `p2/p1 = 1 + 2*k/(k+1) * (M1^2 - 1)`.
///
/// Citation: Anderson, *Modern Compressible Flow*, 3rd ed., ch. 3
/// (normal shock relations).
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_normal_shock_pressure_ratio(mach1: f64, gamma: f64) -> f64 {
    1.0 + 2.0 * gamma / (gamma + 1.0) * (mach1 * mach1 - 1.0)
}

/// Fanno-flow function `4 f Lmax / D` for adiabatic flow with friction
/// in a constant-area duct, at Mach number `M`:
/// `(1-M^2)/(k M^2) + (k+1)/(2k) * ln[ (k+1) M^2 / (2 + (k-1) M^2) ]`.
/// The distance to choking (M=1) along a Fanno line is the difference
/// of this function at two stations; this is the per-segment building
/// block for gas-subnet Fanno-line network delivery (D141).
///
/// Citation: Anderson, *Modern Compressible Flow*, 3rd ed., ch. 3
/// (Fanno flow); Shapiro, *The Dynamics and Thermodynamics of
/// Compressible Fluid Flow*, vol. 1, ch. 6.
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_fanno_function(mach: f64, gamma: f64) -> f64 {
    let m_sq = mach * mach;
    let term1 = (1.0 - m_sq) / (gamma * m_sq);
    let term2 =
        (gamma + 1.0) / (2.0 * gamma) * ((gamma + 1.0) * m_sq / (2.0 + (gamma - 1.0) * m_sq)).ln();
    term1 + term2
}
