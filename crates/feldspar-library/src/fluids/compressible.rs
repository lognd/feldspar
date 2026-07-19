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
// frob:doc docs/modules/feldspar-library.md#library_fluids_compressible
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
// frob:doc docs/modules/feldspar-library.md#library_fluids_compressible
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
// frob:doc docs/modules/feldspar-library.md#library_fluids_compressible
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
// frob:doc docs/modules/feldspar-library.md#library_fluids_compressible
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
// frob:doc docs/modules/feldspar-library.md#library_fluids_compressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_fanno_function(mach: f64, gamma: f64) -> f64 {
    let m_sq = mach * mach;
    let term1 = (1.0 - m_sq) / (gamma * m_sq);
    let term2 =
        (gamma + 1.0) / (2.0 * gamma) * ((gamma + 1.0) * m_sq / (2.0 + (gamma - 1.0) * m_sq)).ln();
    term1 + term2
}

#[cfg(test)]
mod tests {
    use super::*;

    // frob:tests crates/feldspar-library/src/fluids/compressible.rs::fluids_isentropic_stagnation_temp_ratio kind="unit"
    // frob:tests crates/feldspar-library/src/fluids/compressible.rs::fluids_isentropic_stagnation_pressure_ratio kind="unit"
    #[test]
    fn isentropic_stagnation_ratios_matches_hand_formula() {
        // M=2.0, gamma=1.4 -> T0/T = 1 + 0.2*4 = 1.8
        let t_ratio = fluids_isentropic_stagnation_temp_ratio(2.0, 1.4);
        assert!((t_ratio - 1.8).abs() < 1e-9);
        let p_ratio = fluids_isentropic_stagnation_pressure_ratio(2.0, 1.4);
        let expected = 1.8f64.powf(1.4 / 0.4);
        assert!((p_ratio - expected).abs() / expected < 1e-9);
    }

    // frob:tests crates/feldspar-library/src/fluids/compressible.rs::fluids_normal_shock_mach2 kind="unit"
    // frob:tests crates/feldspar-library/src/fluids/compressible.rs::fluids_normal_shock_pressure_ratio kind="unit"
    #[test]
    fn normal_shock_relations_match_hand_formula() {
        // M1=2.0, gamma=1.4 -> M2 ~ 0.5774 (classic textbook value)
        let m2 = fluids_normal_shock_mach2(2.0, 1.4);
        assert!((m2 - 0.5774).abs() < 1e-3);
        let p_ratio = fluids_normal_shock_pressure_ratio(2.0, 1.4);
        // p2/p1 = 1 + 2*1.4/2.4 * (4-1) = 4.5
        assert!((p_ratio - 4.5).abs() < 1e-9);
    }

    // frob:tests crates/feldspar-library/src/fluids/compressible.rs::fluids_fanno_function kind="unit"
    #[test]
    fn fanno_function_vanishes_at_choking() {
        // At M=1.0 the Fanno function is exactly 0 (the choking point).
        let f = fluids_fanno_function(1.0, 1.4);
        assert!(f.abs() < 1e-9);
    }
}
