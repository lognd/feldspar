//! Heat-transfer closed-form formula home (WO-20 Phase 2): 1-D
//! conduction resistance networks and forced-convection correlations.
//! Same `#[no_mangle] pub extern "C" fn` discipline as `mech.rs`/
//! `fluids.rs` (AD-3).
//!
//! Scope note (WO-20 close-out): this file covers 1-D resistance
//! networks (plane/cylindrical wall, convection) and Dittus-Boelter
//! forced convection, the entries needed for the acceptance-tested
//! benchmark cases. The rest of the 07 heat catalog (transient lumped/
//! Heisler, natural convection, boiling/condensation, radiation
//! networks, LMTD/effectiveness-NTU heat exchangers) is EXPLICITLY
//! CUT from this WO and flagged in the close-out report -- not
//! silently dropped.

/// Plane-wall conduction thermal resistance: `R = L / (k * A)`.
///
/// Citation: Incropera & DeWitt, *Fundamentals of Heat and Mass
/// Transfer*, 7th ed., ch. 3 (1-D steady conduction, plane wall
/// resistance).
// frob:doc docs/modules/feldspar-library.md#library_heat
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_plane_wall_resistance(thickness: f64, conductivity: f64, area: f64) -> f64 {
    thickness / (conductivity * area)
}

/// Cylindrical-wall conduction thermal resistance:
/// `R = ln(r2/r1) / (2 * pi * k * L)`.
///
/// Citation: Incropera & DeWitt, *Fundamentals of Heat and Mass
/// Transfer*, 7th ed., ch. 3 (1-D steady conduction, radial systems).
// frob:doc docs/modules/feldspar-library.md#library_heat
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_cylindrical_wall_resistance(
    inner_radius: f64,
    outer_radius: f64,
    conductivity: f64,
    length: f64,
) -> f64 {
    (outer_radius / inner_radius).ln() / (2.0 * std::f64::consts::PI * conductivity * length)
}

/// Convection thermal resistance: `R = 1 / (h * A)`.
///
/// Citation: Incropera & DeWitt, *Fundamentals of Heat and Mass
/// Transfer*, 7th ed., ch. 3 (Newton's law of cooling, convection
/// resistance).
// frob:doc docs/modules/feldspar-library.md#library_heat
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_convection_resistance(coefficient: f64, area: f64) -> f64 {
    1.0 / (coefficient * area)
}

/// Series thermal-resistance-network combination: resistances at a
/// shared heat rate add. `R_total = R1 + R2`.
///
/// Citation: Incropera & DeWitt, *Fundamentals of Heat and Mass
/// Transfer*, 7th ed., ch. 3 (composite walls, series resistance
/// network).
// frob:doc docs/modules/feldspar-library.md#library_heat
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_series_resistance(r1: f64, r2: f64) -> f64 {
    r1 + r2
}

/// Steady 1-D heat rate through a resistance network:
/// `q = delta_T / R_total`.
///
/// Citation: Incropera & DeWitt, *Fundamentals of Heat and Mass
/// Transfer*, 7th ed., ch. 3 (thermal circuit analogy).
// frob:doc docs/modules/feldspar-library.md#library_heat
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_rate_from_resistance(delta_temp: f64, resistance: f64) -> f64 {
    delta_temp / resistance
}

/// Dittus-Boelter forced-convection Nusselt correlation for fully
/// developed turbulent flow in a smooth pipe:
/// `Nu = 0.023 * Re^0.8 * Pr^n`, `n = 0.4` heating (fluid being
/// heated), `n = 0.3` cooling. Valid `Re >= 1e4`, `0.6 <= Pr <= 160`,
/// `L/D >= 10` (enforced as the Python direction's `Domain` box, not
/// here).
///
/// Citation: Dittus & Boelter (1930), reprinted Incropera & DeWitt,
/// *Fundamentals of Heat and Mass Transfer*, 7th ed., ch. 8 (internal
/// flow, turbulent correlations).
// frob:doc docs/modules/feldspar-library.md#library_heat
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_dittus_boelter_nusselt(reynolds: f64, prandtl: f64, heating: bool) -> f64 {
    let n = if heating { 0.4 } else { 0.3 };
    0.023 * reynolds.powf(0.8) * prandtl.powf(n)
}

/// Convection coefficient from a Nusselt number:
/// `h = Nu * k_fluid / D`.
///
/// Citation: Incropera & DeWitt, *Fundamentals of Heat and Mass
/// Transfer*, 7th ed., ch. 8 (Nusselt-number definition).
// frob:doc docs/modules/feldspar-library.md#library_heat
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_coefficient_from_nusselt(
    nusselt: f64,
    fluid_conductivity: f64,
    diameter: f64,
) -> f64 {
    nusselt * fluid_conductivity / diameter
}

#[cfg(test)]
mod tests {
    use super::*;

    // frob:tests crates/feldspar-library/src/heat.rs::heat_plane_wall_resistance kind="unit"
    #[test]
    fn plane_wall_resistance_matches_l_over_ka() {
        let r = heat_plane_wall_resistance(0.1, 0.8, 2.0);
        assert!((r - (0.1 / (0.8 * 2.0))).abs() < 1e-12);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_series_resistance kind="unit"
    // frob:tests crates/feldspar-library/src/heat.rs::heat_rate_from_resistance kind="unit"
    #[test]
    fn series_resistance_and_rate() {
        let r_total = heat_series_resistance(0.05, 0.02);
        assert!((r_total - 0.07).abs() < 1e-12);
        let q = heat_rate_from_resistance(70.0, r_total);
        assert!((q - 1000.0).abs() < 1e-6);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_dittus_boelter_nusselt kind="unit"
    #[test]
    fn dittus_boelter_known_answer() {
        // Re=1e5, Pr=5.0, heating -> Nu = 0.023 * 1e5^0.8 * 5^0.4
        let nu = heat_dittus_boelter_nusselt(1.0e5, 5.0, true);
        let expected = 0.023 * (1.0e5f64).powf(0.8) * (5.0f64).powf(0.4);
        assert!((nu - expected).abs() / expected < 1e-9);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_cylindrical_wall_resistance kind="unit"
    #[test]
    fn cylindrical_wall_resistance_matches_ln_ratio_formula() {
        // r1=0.01 m, r2=0.02 m, k=0.5 W/mK, L=1 m
        // R = ln(2) / (2*pi*0.5*1)
        let r = heat_cylindrical_wall_resistance(0.01, 0.02, 0.5, 1.0);
        let expected = (2.0f64).ln() / (2.0 * std::f64::consts::PI * 0.5 * 1.0);
        assert!((r - expected).abs() / expected < 1e-9);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_convection_resistance kind="unit"
    #[test]
    fn convection_resistance_matches_one_over_ha() {
        let r = heat_convection_resistance(25.0, 2.0);
        assert!((r - (1.0 / (25.0 * 2.0))).abs() < 1e-12);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_coefficient_from_nusselt kind="unit"
    #[test]
    fn coefficient_from_nusselt_matches_nu_k_over_d() {
        let h = heat_coefficient_from_nusselt(100.0, 0.6, 0.02);
        assert!((h - (100.0 * 0.6 / 0.02)).abs() < 1e-9);
    }
}
