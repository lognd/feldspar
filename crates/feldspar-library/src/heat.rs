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

/// Gnielinski forced-convection Nusselt correlation, f-coupled
/// (consumes a Darcy friction factor from `fluids_colebrook_friction_
/// factor`/`fluids_haaland_friction_factor`, the natural pairing --
/// Nu depends on f): `Nu = (f/8)(Re - 1000)Pr / (1 + 12.7*(f/8)^0.5 *
/// (Pr^(2/3) - 1))`. Valid `3000 < Re < 5e6`, `0.5 <= Pr <= 2000`
/// (enforced as the Python direction's `Domain` box, not here).
///
/// Citation: Gnielinski, V. (1976), "New Equations for Heat and Mass
/// Transfer in Turbulent Pipe and Channel Flow", Int. Chem. Eng.
/// 16(2):359-368.
// frob:doc docs/modules/feldspar-library.md#library_heat
// frob:ticket T-0020
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_gnielinski_nusselt(reynolds: f64, prandtl: f64, friction_factor: f64) -> f64 {
    let f8 = friction_factor / 8.0;
    let numerator = f8 * (reynolds - 1000.0) * prandtl;
    let denominator = 1.0 + 12.7 * f8.sqrt() * (prandtl.powf(2.0 / 3.0) - 1.0);
    numerator / denominator
}

/// Laminar fully-developed internal-flow Nusselt number: a constant
/// per boundary condition, `Nu = 3.66` (constant wall temperature) or
/// `Nu = 4.36` (constant surface heat flux) -- no Re/Pr dependence in
/// the fully-developed laminar regime.
///
/// Citation: Incropera & DeWitt, *Fundamentals of Heat and Mass
/// Transfer*, 7th ed., Table 8.1 (fully developed laminar flow,
/// circular tube, constant q'' vs. constant T_s).
// frob:doc docs/modules/feldspar-library.md#library_heat
// frob:ticket T-0020
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_laminar_nusselt(constant_wall_temp: bool) -> f64 {
    if constant_wall_temp {
        3.66
    } else {
        4.36
    }
}

/// Churchill-Chu (1975) natural-convection Nusselt correlation for a
/// long horizontal cylinder, valid over the full Rayleigh range
/// (`Ra <= 1e12`): `Nu^0.5 = 0.60 + 0.387*Ra^(1/6) /
/// [1 + (0.559/Pr)^(9/16)]^(8/27)`.
///
/// Citation: Churchill, S.W. & Chu, H.H.S. (1975), "Correlating
/// Equations for Laminar and Turbulent Free Convection from a
/// Horizontal Cylinder", Int. J. Heat Mass Transfer 18:1049-1053
/// (primary paywalled; restated Incropera & DeWitt, 7th ed., eq.
/// 9.34).
// frob:doc docs/modules/feldspar-library.md#library_heat
// frob:ticket T-0020
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_churchill_chu_horizontal_cylinder_nusselt(rayleigh: f64, prandtl: f64) -> f64 {
    let bracket = 1.0 + (0.559 / prandtl).powf(9.0 / 16.0);
    let sqrt_nu = 0.60 + 0.387 * rayleigh.powf(1.0 / 6.0) / bracket.powf(8.0 / 27.0);
    sqrt_nu * sqrt_nu
}

/// Churchill-Chu (1975) natural-convection Nusselt correlation for a
/// vertical plate, valid over the full Rayleigh range:
/// `Nu^0.5 = 0.825 + 0.387*Ra^(1/6) /
/// [1 + (0.492/Pr)^(9/16)]^(8/27)`.
///
/// Citation: Churchill, S.W. & Chu, H.H.S. (1975), "Correlating
/// Equations for Laminar and Turbulent Free Convection from a
/// Vertical Plate", Int. J. Heat Mass Transfer 18:1323-1329 (primary
/// paywalled; restated Incropera & DeWitt, 7th ed., eq. 9.26).
// frob:doc docs/modules/feldspar-library.md#library_heat
// frob:ticket T-0020
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_churchill_chu_vertical_plate_nusselt(rayleigh: f64, prandtl: f64) -> f64 {
    let bracket = 1.0 + (0.492 / prandtl).powf(9.0 / 16.0);
    let sqrt_nu = 0.825 + 0.387 * rayleigh.powf(1.0 / 6.0) / bracket.powf(8.0 / 27.0);
    sqrt_nu * sqrt_nu
}

/// Number of transfer units from conductance and the minimum heat
/// capacity rate: `NTU = UA / C_min`.
///
/// Citation: Kays & London, *Compact Heat Exchangers*, 3rd ed. (1984);
/// restated Incropera & DeWitt, 7th ed., sec. 11.4 (NTU definition).
// frob:doc docs/modules/feldspar-library.md#library_heat
// frob:ticket T-0020
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_ntu_from_ua(ua: f64, c_min: f64) -> f64 {
    ua / c_min
}

/// Effectiveness-NTU relation, parallel-flow (co-current) arrangement:
/// `eff = (1 - exp(-NTU(1 + Cr))) / (1 + Cr)`.
///
/// Citation: Kays & London, *Compact Heat Exchangers*, 3rd ed. (1984);
/// restated Incropera & DeWitt, 7th ed., Table 11.4 (parallel flow).
// frob:doc docs/modules/feldspar-library.md#library_heat
// frob:ticket T-0020
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_effectiveness_parallel_flow(ntu: f64, c_r: f64) -> f64 {
    (1.0 - (-ntu * (1.0 + c_r)).exp()) / (1.0 + c_r)
}

/// Effectiveness-NTU relation, counterflow arrangement:
/// `eff = (1 - exp(-NTU(1 - Cr))) / (1 - Cr*exp(-NTU(1 - Cr)))` for
/// `Cr < 1`; the `Cr = 1` limit `eff = NTU / (1 + NTU)` is used when
/// `Cr` is within `1e-9` of 1 to avoid the removable 0/0 singularity.
///
/// Citation: Kays & London, *Compact Heat Exchangers*, 3rd ed. (1984);
/// restated Incropera & DeWitt, 7th ed., Table 11.4 (counterflow).
// frob:doc docs/modules/feldspar-library.md#library_heat
// frob:ticket T-0020
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_effectiveness_counterflow(ntu: f64, c_r: f64) -> f64 {
    if (c_r - 1.0).abs() < 1e-9 {
        ntu / (1.0 + ntu)
    } else {
        let exp_term = (-ntu * (1.0 - c_r)).exp();
        (1.0 - exp_term) / (1.0 - c_r * exp_term)
    }
}

/// Effectiveness-NTU relation, shell-and-tube, one shell pass (2, 4,
/// ... tube passes):
/// `eff = 2 / (1 + Cr + sqrt(1+Cr^2) *
/// (1 + exp(-NTU*sqrt(1+Cr^2))) / (1 - exp(-NTU*sqrt(1+Cr^2))))`.
///
/// Citation: Kays & London, *Compact Heat Exchangers*, 3rd ed. (1984);
/// restated Incropera & DeWitt, 7th ed., Table 11.4 (shell-and-tube,
/// one shell pass).
// frob:doc docs/modules/feldspar-library.md#library_heat
// frob:ticket T-0020
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_effectiveness_shell_and_tube_one_pass(ntu: f64, c_r: f64) -> f64 {
    let root = (1.0 + c_r * c_r).sqrt();
    let exp_term = (-ntu * root).exp();
    2.0 / (1.0 + c_r + root * (1.0 + exp_term) / (1.0 - exp_term))
}

/// Heat-exchanger duty from effectiveness: `q = eff * C_min *
/// (T_hot_in - T_cold_in)`.
///
/// Citation: Incropera & DeWitt, 7th ed., sec. 11.3 (effectiveness
/// definition, `q = eff * q_max`).
// frob:doc docs/modules/feldspar-library.md#library_heat
// frob:ticket T-0020
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_hx_rate_from_effectiveness(
    effectiveness: f64,
    c_min: f64,
    t_hot_in: f64,
    t_cold_in: f64,
) -> f64 {
    effectiveness * c_min * (t_hot_in - t_cold_in)
}

/// Heat exchanger outlet temperature from an inlet temperature, duty,
/// and that stream's heat capacity rate: `T_out = T_in -/+ q/C`
/// (`cooling=true` subtracts for the hot stream being cooled,
/// `cooling=false` adds for the cold stream being heated).
///
/// Citation: Incropera & DeWitt, 7th ed., sec. 11.1 (energy balance,
/// `q = C*(T_in - T_out)` hot side / `q = C*(T_out - T_in)` cold side).
// frob:doc docs/modules/feldspar-library.md#library_heat
// frob:ticket T-0020
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn heat_hx_outlet_temp(t_in: f64, rate: f64, capacity_rate: f64, cooling: bool) -> f64 {
    if cooling {
        t_in - rate / capacity_rate
    } else {
        t_in + rate / capacity_rate
    }
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

    // frob:tests crates/feldspar-library/src/heat.rs::heat_gnielinski_nusselt kind="unit"
    // frob:ticket T-0020
    #[test]
    fn gnielinski_known_answer() {
        // Re=1e5, Pr=5.0, f=0.0180 (Colebrook-ish smooth-pipe value at
        // Re=1e5) -- direct evaluation of the closed form itself.
        let re = 1.0e5;
        let pr = 5.0;
        let f = 0.0180;
        let nu = heat_gnielinski_nusselt(re, pr, f);
        let f8 = f / 8.0;
        let expected = (f8 * (re - 1000.0) * pr) / (1.0 + 12.7 * f8.sqrt() * (pr.powf(2.0 / 3.0) - 1.0));
        assert!((nu - expected).abs() / expected < 1e-9);
        // Sanity range check: Gnielinski should sit within ~20% of
        // Dittus-Boelter at the same Re/Pr for a smooth pipe (both
        // model the same physical turbulent regime).
        let db = heat_dittus_boelter_nusselt(re, pr, true);
        assert!((nu - db).abs() / db < 0.2);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_laminar_nusselt kind="unit"
    // frob:ticket T-0020
    #[test]
    fn laminar_nusselt_constants() {
        assert!((heat_laminar_nusselt(true) - 3.66).abs() < 1e-12);
        assert!((heat_laminar_nusselt(false) - 4.36).abs() < 1e-12);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_churchill_chu_horizontal_cylinder_nusselt kind="unit"
    // frob:ticket T-0020
    #[test]
    fn churchill_chu_horizontal_cylinder_known_answer() {
        // Ra=1.0e7, Pr=0.7 (air) -- direct evaluation of the closed
        // form against its own restated equation (Incropera & DeWitt
        // 7th ed., eq. 9.34).
        let ra = 1.0e7;
        let pr = 0.7;
        let nu = heat_churchill_chu_horizontal_cylinder_nusselt(ra, pr);
        let bracket = 1.0 + (0.559f64 / pr).powf(9.0 / 16.0);
        let sqrt_nu = 0.60 + 0.387 * ra.powf(1.0 / 6.0) / bracket.powf(8.0 / 27.0);
        let expected = sqrt_nu * sqrt_nu;
        assert!((nu - expected).abs() / expected < 1e-9);
        // Physical sanity: Nu must increase monotonically with Ra at
        // fixed Pr over the natural-convection range.
        let nu_lower_ra = heat_churchill_chu_horizontal_cylinder_nusselt(1.0e5, pr);
        assert!(nu > nu_lower_ra);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_churchill_chu_vertical_plate_nusselt kind="unit"
    // frob:ticket T-0020
    #[test]
    fn churchill_chu_vertical_plate_matches_formula() {
        let ra = 1.0e9;
        let pr = 0.7;
        let nu = heat_churchill_chu_vertical_plate_nusselt(ra, pr);
        let bracket = 1.0 + (0.492f64 / pr).powf(9.0 / 16.0);
        let sqrt_nu = 0.825 + 0.387 * ra.powf(1.0 / 6.0) / bracket.powf(8.0 / 27.0);
        let expected = sqrt_nu * sqrt_nu;
        assert!((nu - expected).abs() / expected < 1e-9);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_ntu_from_ua kind="unit"
    // frob:ticket T-0020
    #[test]
    fn ntu_from_ua_matches_ratio() {
        let ntu = heat_ntu_from_ua(500.0, 250.0);
        assert!((ntu - 2.0).abs() < 1e-12);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_effectiveness_parallel_flow kind="unit"
    // frob:ticket T-0020
    #[test]
    fn effectiveness_parallel_flow_known_answer() {
        // Incropera & DeWitt Table 11.3/example pattern: NTU=2.0, Cr=0.5.
        let ntu = 2.0;
        let cr = 0.5;
        let eff = heat_effectiveness_parallel_flow(ntu, cr);
        let expected = (1.0 - (-ntu * (1.0 + cr)).exp()) / (1.0 + cr);
        assert!((eff - expected).abs() / expected < 1e-9);
        // Parallel-flow effectiveness is bounded by 1/(1+Cr) as NTU -> inf.
        assert!(eff < 1.0 / (1.0 + cr));
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_effectiveness_counterflow kind="unit"
    // frob:ticket T-0020
    #[test]
    fn effectiveness_counterflow_known_answer() {
        let ntu = 2.0;
        let cr = 0.5;
        let eff = heat_effectiveness_counterflow(ntu, cr);
        let exp_term = (-ntu * (1.0 - cr)).exp();
        let expected = (1.0 - exp_term) / (1.0 - cr * exp_term);
        assert!((eff - expected).abs() / expected < 1e-9);
        // Counterflow always outperforms parallel flow at equal NTU/Cr.
        let parallel = heat_effectiveness_parallel_flow(ntu, cr);
        assert!(eff > parallel);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_effectiveness_counterflow kind="unit"
    // frob:ticket T-0020
    #[test]
    fn effectiveness_counterflow_cr_one_limit() {
        let ntu = 3.0;
        let eff = heat_effectiveness_counterflow(ntu, 1.0);
        let expected = ntu / (1.0 + ntu);
        assert!((eff - expected).abs() / expected < 1e-6);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_effectiveness_shell_and_tube_one_pass kind="unit"
    // frob:ticket T-0020
    #[test]
    fn effectiveness_shell_and_tube_matches_formula() {
        let ntu = 1.5;
        let cr = 0.6;
        let eff = heat_effectiveness_shell_and_tube_one_pass(ntu, cr);
        let root = (1.0 + cr * cr).sqrt();
        let exp_term = (-ntu * root).exp();
        let expected = 2.0 / (1.0 + cr + root * (1.0 + exp_term) / (1.0 - exp_term));
        assert!((eff - expected).abs() / expected < 1e-9);
    }

    // frob:tests crates/feldspar-library/src/heat.rs::heat_hx_rate_from_effectiveness kind="unit"
    // frob:tests crates/feldspar-library/src/heat.rs::heat_hx_outlet_temp kind="unit"
    // frob:ticket T-0020
    #[test]
    fn hx_rate_and_outlet_temps_energy_balance() {
        // C_min=1000 W/K, C_max=2000 W/K, eff=0.6, T_hot_in=80C, T_cold_in=20C.
        let c_min = 1000.0;
        let c_hot = 2000.0;
        let c_cold = c_min;
        let eff = 0.6;
        let t_hot_in = 80.0;
        let t_cold_in = 20.0;
        let q = heat_hx_rate_from_effectiveness(eff, c_min, t_hot_in, t_cold_in);
        let expected_q = 0.6 * 1000.0 * 60.0;
        assert!((q - expected_q).abs() / expected_q < 1e-9);

        let t_hot_out = heat_hx_outlet_temp(t_hot_in, q, c_hot, true);
        let t_cold_out = heat_hx_outlet_temp(t_cold_in, q, c_cold, false);
        assert!((t_hot_out - (t_hot_in - q / c_hot)).abs() < 1e-9);
        assert!((t_cold_out - (t_cold_in + q / c_cold)).abs() < 1e-9);
        // Energy balance sanity: hot side must cool, cold side must heat.
        assert!(t_hot_out < t_hot_in);
        assert!(t_cold_out > t_cold_in);
    }
}
