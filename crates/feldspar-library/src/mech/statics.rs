//! Static structural formulas: Euler-Bernoulli cantilever beam
//! deflection and thick-walled-cylinder Lame/von Mises stress. Same
//! AD-3 `#[no_mangle] pub extern "C" fn` discipline as the rest of
//! `mech` (see `mech/mod.rs` doc comment).

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

#[cfg(test)]
mod tests {
    use super::*;

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
}
