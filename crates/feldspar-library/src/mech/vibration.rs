//! Vibration formulas: SDOF/cantilever-beam natural frequency and
//! Miles' equation random-vibration response. Same AD-3
//! `#[no_mangle] pub extern "C" fn` discipline as the rest of `mech`
//! (see `mech/mod.rs` doc comment).

/// First natural (angular-derived) frequency of an undamped SDOF
/// system, in Hz: `f = (1 / 2*pi) * sqrt(k / m)`.
///
/// Citation: Rao, *Mechanical Vibrations*, latest ed., ch. 2 (SDOF
/// free vibration, undamped natural frequency).
// frob:doc docs/modules/feldspar-library.md#library_mech_vibration
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn sdof_first_mode(stiffness: f64, mass: f64) -> f64 {
    (1.0 / (2.0 * std::f64::consts::PI)) * (stiffness / mass).sqrt()
}

/// First natural frequency of a uniform Euler-Bernoulli cantilever beam
/// (fixed-free), in Hz:
/// `f1 = (beta1^2 / (2*pi*L^2)) * sqrt(E*I / (rho*A))`, with
/// `beta1 = 1.87510407` the first cantilever eigenvalue root.
///
/// Citation: Blevins, *Formulas for Natural Frequency and Mode Shape*,
/// Table 8-1 (cantilever beam, case 1).
// frob:doc docs/modules/feldspar-library.md#library_mech_vibration
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn beam_cantilever_first_mode(
    youngs_modulus: f64,
    second_moment: f64,
    density: f64,
    area: f64,
    length: f64,
) -> f64 {
    const BETA1: f64 = 1.875_104_07;
    let beta1_sq = BETA1 * BETA1;
    (beta1_sq / (2.0 * std::f64::consts::PI * length.powi(2)))
        * ((youngs_modulus * second_moment) / (density * area)).sqrt()
}

/// Miles' equation: 1-sigma RMS response (GRMS) of an SDOF system to a
/// flat base-input acceleration PSD `asd` (g^2/Hz) at its own natural
/// frequency `fn_hz` (Hz), amplification factor `q`:
/// `grms = sqrt((pi / 2) * fn_hz * q * asd)`.
///
/// Citation: Steinberg, *Vibration Analysis for Electronic Equipment*,
/// 3rd ed., ch. 2 (Miles' equation, random vibration).
// frob:doc docs/modules/feldspar-library.md#library_mech_vibration
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn miles_grms(fn_hz: f64, q: f64, asd: f64) -> f64 {
    ((std::f64::consts::PI / 2.0) * fn_hz * q * asd).sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sdof_first_mode_matches_textbook_formula() {
        // k=1000 N/m, m=2 kg -> f = 1/(2*pi) * sqrt(500).
        let expected = (1.0 / (2.0 * std::f64::consts::PI)) * 500.0_f64.sqrt();
        assert!((sdof_first_mode(1000.0, 2.0) - expected).abs() < 1e-12);
    }

    #[test]
    fn beam_cantilever_first_mode_matches_blevins_table() {
        // Steel cantilever, E=200e9, I=8e-6, rho=7850, A=0.01, L=1.0.
        let e: f64 = 200e9;
        let i: f64 = 8e-6;
        let rho: f64 = 7850.0;
        let a: f64 = 0.01;
        let l: f64 = 1.0;
        let beta1_sq = 1.875_104_07_f64.powi(2);
        let expected =
            (beta1_sq / (2.0 * std::f64::consts::PI * l.powi(2))) * ((e * i) / (rho * a)).sqrt();
        assert!((beam_cantilever_first_mode(e, i, rho, a, l) - expected).abs() < 1e-9);
    }

    #[test]
    fn miles_grms_known_case() {
        // fn=100 Hz, Q=10, ASD=0.1 g^2/Hz.
        let expected = ((std::f64::consts::PI / 2.0) * 100.0 * 10.0 * 0.1_f64).sqrt();
        assert!((miles_grms(100.0, 10.0, 0.1) - expected).abs() < 1e-12);
    }

    #[test]
    fn miles_grms_zero_asd_is_zero() {
        assert_eq!(miles_grms(50.0, 5.0, 0.0), 0.0);
    }
}
