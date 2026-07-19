//! Incompressible internal-flow formulas: pipe friction factors,
//! Darcy-Weisbach/minor losses, pipe-network combination, pump/system
//! operating point, NPSH, and water hammer. Same AD-3
//! `#[no_mangle] pub extern "C" fn` discipline as the rest of `fluids`
//! (see `fluids/mod.rs` doc comment).
//!
//! Every function here evaluates its DECLARED closed-form model
//! exactly (A-7) -- Haaland and Dittus-Boelter are themselves
//! approximations of reality, but this module computes their formulas
//! to floating-point precision, which is what `accuracy=EXACT`
//! certifies (same convention `mech`'s Lame equations use: the model
//! is textbook-approximate, the evaluation is exact). Colebrook is the
//! one implicit root in this file; it is solved by Newton iteration to
//! a tight, fixed tolerance (`_COLEBROOK_TOL`), which is evaluating the
//! SAME defining equation to floating-point precision, not a separate
//! approximate model.

#![allow(clippy::too_many_arguments)]

const _COLEBROOK_TOL: f64 = 1e-12;
const _COLEBROOK_MAX_ITER: u32 = 100;

/// Reynolds number for internal pipe flow: `Re = rho * v * D / mu`.
///
/// Citation: White, *Fluid Mechanics*, 8th ed., ch. 6 (internal flow,
/// Reynolds number definition).
// frob:doc docs/modules/feldspar-library.md#library_fluids_incompressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_reynolds_number(
    density: f64,
    velocity: f64,
    diameter: f64,
    viscosity: f64,
) -> f64 {
    density * velocity * diameter / viscosity
}

/// Hagen-Poiseuille laminar friction factor: `f = 64 / Re`. Exact for
/// fully-developed laminar pipe flow (Re < 2300).
///
/// Citation: White, *Fluid Mechanics*, 8th ed., sec. 6.4 (laminar
/// fully developed pipe flow, Darcy friction factor).
// frob:doc docs/modules/feldspar-library.md#library_fluids_incompressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_laminar_friction_factor(reynolds: f64) -> f64 {
    64.0 / reynolds
}

/// Colebrook-White implicit turbulent friction factor, solved by
/// Newton iteration on `g(f) = 1/sqrt(f) + 2*log10(eps/(3.7 D) +
/// 2.51/(Re sqrt(f)))` to `_COLEBROOK_TOL`. Seeded from the Haaland
/// explicit approximation (below) for fast, deterministic convergence.
///
/// Citation: Colebrook, "Turbulent Flow in Pipes", J. Inst. Civ. Eng.,
/// 1939; White, *Fluid Mechanics*, 8th ed., sec. 6.8 (Moody chart /
/// Colebrook equation).
// frob:doc docs/modules/feldspar-library.md#library_fluids_incompressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_colebrook_friction_factor(reynolds: f64, relative_roughness: f64) -> f64 {
    // Fixed-point iteration on x = 1/sqrt(f):
    // x_{n+1} = -2 * log10( rr/3.7 + 2.51 * x_n / Re ), the standard
    // convergent scheme for the Colebrook-White equation (seeded from
    // the Haaland explicit approximation for a fast, deterministic
    // start).
    let f0 = fluids_haaland_friction_factor(reynolds, relative_roughness);
    let mut x = 1.0 / f0.sqrt();
    for _ in 0.._COLEBROOK_MAX_ITER {
        let x_next = -2.0 * (relative_roughness / 3.7 + 2.51 * x / reynolds).log10();
        let delta = (x_next - x).abs();
        x = x_next;
        if delta < _COLEBROOK_TOL {
            break;
        }
    }
    1.0 / (x * x)
}

/// Haaland explicit approximation to Colebrook:
/// `1/sqrt(f) = -1.8 * log10( (eps/D/3.7)^1.11 + 6.9/Re )`.
///
/// Citation: Haaland, "Simple and Explicit Formulas for the Friction
/// Factor in Turbulent Pipe Flow", J. Fluids Eng., 1983.
// frob:doc docs/modules/feldspar-library.md#library_fluids_incompressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_haaland_friction_factor(reynolds: f64, relative_roughness: f64) -> f64 {
    let inner = (relative_roughness / 3.7).powf(1.11) + 6.9 / reynolds;
    let inv_sqrt_f = -1.8 * inner.log10();
    1.0 / (inv_sqrt_f * inv_sqrt_f)
}

/// Darcy-Weisbach pressure drop over a pipe run:
/// `dp = f * (L/D) * (rho * v^2 / 2)`.
///
/// Citation: White, *Fluid Mechanics*, 8th ed., sec. 6.6 (Darcy-Weisbach
/// head/pressure loss).
// frob:doc docs/modules/feldspar-library.md#library_fluids_incompressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_darcy_dp(
    friction_factor: f64,
    length: f64,
    diameter: f64,
    density: f64,
    velocity: f64,
) -> f64 {
    friction_factor * (length / diameter) * (density * velocity * velocity / 2.0)
}

/// Minor-loss pressure drop from a lumped loss coefficient K:
/// `dp = K * rho * v^2 / 2`.
///
/// Citation: Crane Technical Paper 410, "Flow of Fluids Through Valves,
/// Fittings, and Pipe" (K-factor method).
// frob:doc docs/modules/feldspar-library.md#library_fluids_incompressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_minor_loss_dp(k_factor: f64, density: f64, velocity: f64) -> f64 {
    k_factor * density * velocity * velocity / 2.0
}

/// Series pipe-network head/pressure loss combination: losses at a
/// shared flow rate add. `dp_total = dp1 + dp2`.
///
/// Citation: White, *Fluid Mechanics*, 8th ed., sec. 6.8 (pipe
/// networks, series combination).
// frob:doc docs/modules/feldspar-library.md#library_fluids_incompressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_series_dp(dp1: f64, dp2: f64) -> f64 {
    dp1 + dp2
}

/// Parallel pipe-network flow combination: branches sharing the same
/// delta-p add their flow rates. `Q_total = Q1 + Q2`.
///
/// Citation: White, *Fluid Mechanics*, 8th ed., sec. 6.8 (pipe
/// networks, parallel combination).
// frob:doc docs/modules/feldspar-library.md#library_fluids_incompressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_parallel_flow(q1: f64, q2: f64) -> f64 {
    q1 + q2
}

/// Pump/system operating-point flow rate, given a quadratic pump curve
/// `H_p = H0 - a*Q^2` and quadratic system curve `H_s = H_static + R*Q^2`:
/// `Q* = sqrt((H0 - H_static) / (a + R))`.
///
/// Citation: White, *Fluid Mechanics*, 8th ed., sec. 11.7 (pump/system
/// curve matching, operating point).
// frob:doc docs/modules/feldspar-library.md#library_fluids_incompressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_pump_operating_flow(h0: f64, a: f64, h_static: f64, r: f64) -> f64 {
    ((h0 - h_static) / (a + r)).sqrt()
}

/// Pump/system operating-point head at the flow rate `Q*` found by
/// [`fluids_pump_operating_flow`]: `H* = H_static + R*Q*^2`.
///
/// Citation: same as [`fluids_pump_operating_flow`].
// frob:doc docs/modules/feldspar-library.md#library_fluids_incompressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_pump_operating_head(h_static: f64, r: f64, q_star: f64) -> f64 {
    h_static + r * q_star * q_star
}

/// Net Positive Suction Head available at a pump suction, flooded-
/// suction sign convention (`static_head` positive = flooded, negative
/// = suction lift): `NPSHa = (p_atm - p_vapor)/(rho*g) + static_head -
/// friction_head`.
///
/// Citation: Cengel & Cimbala, *Fluid Mechanics: Fundamentals and
/// Applications*, latest ed., "Pumps and Turbines" (NPSH available).
// frob:doc docs/modules/feldspar-library.md#library_fluids_incompressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_npsh_available(
    p_atm: f64,
    p_vapor: f64,
    density: f64,
    gravity: f64,
    static_head: f64,
    friction_head: f64,
) -> f64 {
    (p_atm - p_vapor) / (density * gravity) + static_head - friction_head
}

/// Joukowsky water-hammer pressure surge: `dp = rho * a * dV`, where
/// `a` is the pressure-wave speed and `dV` the (signed) velocity change
/// at valve closure.
///
/// Citation: Wylie & Streeter, *Fluid Transients in Systems*, ch. 1
/// (Joukowsky equation); White, *Fluid Mechanics*, 8th ed., sec. 6.9
/// (water hammer).
// frob:doc docs/modules/feldspar-library.md#library_fluids_incompressible
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_joukowsky_dp(density: f64, wave_speed: f64, delta_velocity: f64) -> f64 {
    density * wave_speed * delta_velocity
}

#[cfg(test)]
mod tests {
    use super::*;

    // frob:tests crates/feldspar-library/src/fluids/incompressible.rs::fluids_reynolds_number kind="unit"
    #[test]
    fn reynolds_number_matches_rho_v_d_over_mu() {
        let re = fluids_reynolds_number(1000.0, 2.0, 0.05, 0.001);
        assert!((re - (1000.0 * 2.0 * 0.05 / 0.001)).abs() / re < 1e-9);
    }

    // frob:tests crates/feldspar-library/src/fluids/incompressible.rs::fluids_darcy_dp kind="unit"
    #[test]
    fn darcy_dp_matches_f_l_over_d_rho_v2_over_2() {
        let dp = fluids_darcy_dp(0.02, 10.0, 0.05, 1000.0, 2.0);
        let expected = 0.02 * (10.0 / 0.05) * (1000.0 * 2.0 * 2.0 / 2.0);
        assert!((dp - expected).abs() / expected < 1e-9);
    }

    // frob:tests crates/feldspar-library/src/fluids/incompressible.rs::fluids_minor_loss_dp kind="unit"
    #[test]
    fn minor_loss_dp_matches_k_rho_v2_over_2() {
        let dp = fluids_minor_loss_dp(0.9, 1000.0, 2.0);
        assert!((dp - (0.9 * 1000.0 * 2.0 * 2.0 / 2.0)).abs() < 1e-9);
    }

    // frob:tests crates/feldspar-library/src/fluids/incompressible.rs::fluids_npsh_available kind="unit"
    #[test]
    fn npsh_available_matches_hand_formula() {
        let npsh = fluids_npsh_available(101325.0, 2340.0, 998.0, 9.81, 2.0, 0.5);
        let expected = (101325.0 - 2340.0) / (998.0 * 9.81) + 2.0 - 0.5;
        assert!((npsh - expected).abs() / expected < 1e-9);
    }

    // frob:tests crates/feldspar-library/src/fluids/incompressible.rs::fluids_joukowsky_dp kind="unit"
    #[test]
    fn joukowsky_dp_matches_rho_a_dv() {
        let dp = fluids_joukowsky_dp(1000.0, 1200.0, 1.5);
        assert!((dp - (1000.0 * 1200.0 * 1.5)).abs() < 1e-6);
    }

    // frob:tests crates/feldspar-library/src/fluids/incompressible.rs::fluids_laminar_friction_factor kind="unit"
    #[test]
    fn laminar_floor_matches_64_over_re() {
        let f = fluids_laminar_friction_factor(1000.0);
        assert!((f - 0.0640).abs() < 1e-6);
    }

    // frob:tests crates/feldspar-library/src/fluids/incompressible.rs::fluids_haaland_friction_factor kind="unit"
    // frob:tests crates/feldspar-library/src/fluids/incompressible.rs::fluids_colebrook_friction_factor kind="unit"
    #[test]
    fn haaland_and_colebrook_agree_within_two_percent() {
        // Commercial steel, D=0.1m, eps=0.045mm, Re=1e5 (benchmarks memo
        // 3.1). NOTE (WO-20 close-out): re-deriving the Colebrook root
        // both by this fixed-point scheme and independently by bisection
        // on the defining residual gives f=0.02012, not the memo's
        // quoted 0.0195 (memo is explicitly advisory/non-normative, sec.
        // "How to read this"); the analytically-verified root is used
        // here instead of the memo's rounded figure. Haaland-vs-Colebrook
        // agreement (the memo's actual solver-conformance tolerance) is
        // what's asserted below.
        let rel_rough = 0.045e-3 / 0.1;
        let re = 1.0e5;
        let f_haaland = fluids_haaland_friction_factor(re, rel_rough);
        let f_colebrook = fluids_colebrook_friction_factor(re, rel_rough);
        assert!((f_colebrook - 0.02012).abs() / 0.02012 < 0.005);
        assert!((f_haaland - f_colebrook).abs() / f_colebrook < 0.02);
    }

    // frob:tests crates/feldspar-library/src/fluids/incompressible.rs::fluids_pump_operating_flow kind="unit"
    // frob:tests crates/feldspar-library/src/fluids/incompressible.rs::fluids_pump_operating_head kind="unit"
    #[test]
    fn pump_operating_point_matches_memo_case() {
        let q_star = fluids_pump_operating_flow(50.0, 2000.0, 10.0, 3000.0);
        assert!((q_star - 0.08944).abs() / 0.08944 < 1e-3);
        let h_star = fluids_pump_operating_head(10.0, 3000.0, q_star);
        assert!((h_star - 34.0).abs() / 34.0 < 1e-3);
    }

    // frob:tests crates/feldspar-library/src/fluids/incompressible.rs::fluids_series_dp kind="unit"
    // frob:tests crates/feldspar-library/src/fluids/incompressible.rs::fluids_parallel_flow kind="unit"
    #[test]
    fn series_and_parallel_network_reduction() {
        assert!((fluids_series_dp(3.0, 2.0) - 5.0).abs() < 1e-12);
        assert!((fluids_parallel_flow(0.006, 0.006) - 0.012).abs() < 1e-12);
    }
}
