//! Mechanical-engineering closed-form formula home (WO-07).
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
//! The workspace denies `unsafe_code`, but `#[no_mangle]` on an
//! `extern "C" fn` requires an explicit, function-scoped
//! `#[allow(unsafe_code)]` (AD-3's whole point is these symbols being
//! link-visible via a C ABI, which is what the lint is warning about);
//! the allow is scoped to each function, not the module, so it cannot
//! silently mask an unrelated unsafe block elsewhere in this file.

/// Second moment of area (area moment of inertia) of a rectangular
/// cross-section about its centroidal axis: `I = width * height^3 / 12`.
///
/// Citation: Gere, *Mechanics of Materials*, 9th ed., App. E
/// (rectangular section, second moment about centroidal axis).
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn rect_second_moment(width: f64, height: f64) -> f64 {
    width * height.powi(3) / 12.0
}

/// Tip deflection of an Euler-Bernoulli cantilever beam under a
/// concentrated end load: `delta = F * L^3 / (3 * E * I)`.
///
/// Citation: Gere, *Mechanics of Materials*, 9th ed., Table (cantilever,
/// concentrated load at free end); see also Young & Budynas, *Roark's
/// Formulas for Stress and Strain*, 8th ed., Table 8.1 (secondary
/// handbook citation).
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn cantilever_tip_deflection(
    force: f64,
    length: f64,
    youngs_modulus: f64,
    second_moment: f64,
) -> f64 {
    force * length.powi(3) / (3.0 * youngs_modulus * second_moment)
}

/// Young's modulus required to hit a target tip deflection: the
/// algebraic inverse of [`cantilever_tip_deflection`] solving for `E`,
/// `E = F * L^3 / (3 * delta * I)`.
///
/// Citation: same law as [`cantilever_tip_deflection`] (Gere,
/// *Mechanics of Materials*, 9th ed.), solved for a different unknown.
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn cantilever_required_youngs_modulus(
    force: f64,
    length: f64,
    second_moment: f64,
    deflection: f64,
) -> f64 {
    force * length.powi(3) / (3.0 * deflection * second_moment)
}

/// Hoop (tangential) stress at the bore (`r = inner_radius`) of a
/// thick-walled cylinder under internal pressure only:
/// `sigma_t = p * (a^2 + b^2) / (b^2 - a^2)`, with `a` = inner_radius,
/// `b` = outer_radius.
///
/// Citation: Budynas & Nisbett, *Shigley's Mechanical Engineering
/// Design*, latest ed., "Thick-Walled Cylinders" section (Lame's
/// equations).
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn lame_hoop_stress_bore(
    pressure: f64,
    inner_radius: f64,
    outer_radius: f64,
) -> f64 {
    pressure * (inner_radius.powi(2) + outer_radius.powi(2))
        / (outer_radius.powi(2) - inner_radius.powi(2))
}

/// Radial stress at the bore of an internally-pressurized thick
/// cylinder. The general Lame radial-stress formula is
/// `sigma_r(r) = p*a^2/(b^2-a^2) * (1 - b^2/r^2)`; evaluated at `r = a`
/// (the bore) this algebraically reduces to `-p` (the applied internal
/// pressure, as the boundary condition requires).
///
/// Citation: Budynas & Nisbett, *Shigley's Mechanical Engineering
/// Design*, latest ed., "Thick-Walled Cylinders" section (Lame's
/// equations).
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn lame_radial_stress_bore(
    pressure: f64,
    _inner_radius: f64,
    _outer_radius: f64,
) -> f64 {
    -pressure
}

/// Von Mises equivalent stress from three principal stresses. THIS IS
/// THE ONLY von Mises implementation in the crate (NO DUPLICATION);
/// every other function that needs it (e.g. [`bore_von_mises`]) must
/// call through here.
///
/// `sigma_vm = sqrt(0.5 * ((s1-s2)^2 + (s2-s3)^2 + (s3-s1)^2))`.
///
/// Citation: Budynas & Nisbett, *Shigley's Mechanical Engineering
/// Design*, latest ed., distortion-energy (von Mises) equivalent
/// stress definition.
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn von_mises_principal(sigma1: f64, sigma2: f64, sigma3: f64) -> f64 {
    (0.5 * ((sigma1 - sigma2).powi(2) + (sigma2 - sigma3).powi(2) + (sigma3 - sigma1).powi(2)))
        .sqrt()
}

/// Von Mises equivalent stress at the bore of an internally-pressurized
/// thick cylinder, composed from [`lame_hoop_stress_bore`] and
/// [`lame_radial_stress_bore`] with axial stress taken as `0.0` (an
/// open-ended cylinder / plane-stress simplification; a closed-ended
/// pressure vessel would carry a nonzero axial term). Calls
/// [`von_mises_principal`] rather than reimplementing the algebra
/// (NO DUPLICATION).
///
/// Citation: Budynas & Nisbett, *Shigley's Mechanical Engineering
/// Design*, latest ed., "Thick-Walled Cylinders" section (Lame's
/// equations) and distortion-energy (von Mises) equivalent stress
/// definition.
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn bore_von_mises(pressure: f64, inner_radius: f64, outer_radius: f64) -> f64 {
    let hoop = lame_hoop_stress_bore(pressure, inner_radius, outer_radius);
    let radial = lame_radial_stress_bore(pressure, inner_radius, outer_radius);
    von_mises_principal(hoop, radial, 0.0)
}

/// First natural (angular-derived) frequency of an undamped SDOF
/// system, in Hz: `f = (1 / 2*pi) * sqrt(k / m)`.
///
/// Citation: Rao, *Mechanical Vibrations*, latest ed., ch. 2 (SDOF
/// free vibration, undamped natural frequency).
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
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn miles_grms(fn_hz: f64, q: f64, asd: f64) -> f64 {
    ((std::f64::consts::PI / 2.0) * fn_hz * q * asd).sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rect_second_moment_matches_textbook_formula() {
        // Gere 9e App. E: I = b*h^3/12 for a 0.04 m x 0.06 m rectangle.
        let expected = 0.04 * 0.06_f64.powi(3) / 12.0;
        assert!((rect_second_moment(0.04, 0.06) - expected).abs() < 1e-15);
    }

    #[test]
    fn cantilever_tip_deflection_known_case() {
        // F=1000 N, L=1 m, E=200e9 Pa (steel), I=8e-6 m^4.
        let force = 1000.0;
        let length: f64 = 1.0;
        let e = 200e9;
        let i = 8e-6;
        let expected = force * length.powi(3) / (3.0 * e * i);
        assert!((cantilever_tip_deflection(force, length, e, i) - expected).abs() < 1e-12);
    }

    #[test]
    fn cantilever_required_youngs_modulus_is_inverse_of_deflection() {
        let force = 1000.0;
        let length: f64 = 1.0;
        let i = 8e-6;
        let e = 200e9;
        let deflection = cantilever_tip_deflection(force, length, e, i);
        let recovered = cantilever_required_youngs_modulus(force, length, i, deflection);
        assert!((recovered - e).abs() / e < 1e-9);
    }

    #[test]
    fn lame_hoop_stress_clean_ratio() {
        // a=1, b=2 (ratio 2): sigma_t = p*(1+4)/(4-1) = 5p/3.
        let p = 30.0;
        let expected = p * 5.0 / 3.0;
        assert!((lame_hoop_stress_bore(p, 1.0, 2.0) - expected).abs() < 1e-12);
    }

    #[test]
    fn lame_radial_stress_bore_equals_negative_pressure() {
        assert_eq!(lame_radial_stress_bore(42.0, 1.0, 2.0), -42.0);
    }

    #[test]
    fn von_mises_uniaxial_state_equals_the_stress_itself() {
        // sigma1=100, sigma2=sigma3=0 -> von Mises = 100 (standard identity).
        assert!((von_mises_principal(100.0, 0.0, 0.0) - 100.0).abs() < 1e-12);
    }

    #[test]
    fn bore_von_mises_composes_lame_and_von_mises() {
        let p = 30.0;
        let a = 1.0;
        let b = 2.0;
        let hoop = lame_hoop_stress_bore(p, a, b);
        let radial = lame_radial_stress_bore(p, a, b);
        let expected = von_mises_principal(hoop, radial, 0.0);
        assert!((bore_von_mises(p, a, b) - expected).abs() < 1e-12);
    }

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
