//! Fluid-mechanics closed-form formula home (WO-20 Phase 2): internal
//! flow, pipe networks, turbomachinery, water hammer, and the D141
//! compressible tier (isentropic relations, normal shocks, the Fanno
//! function). Same `#[no_mangle] pub extern "C" fn` discipline as
//! `mech.rs` (AD-3): one link-visible definition per formula, callable
//! from Rust, PyO3, and `dlopen`/`nm` alike.
//!
//! Every function here evaluates its DECLARED closed-form model
//! exactly (A-7) -- Haaland and Dittus-Boelter are themselves
//! approximations of reality, but this module computes their formulas
//! to floating-point precision, which is what `accuracy=EXACT`
//! certifies (same convention `mech.rs`'s Lame equations use: the
//! model is textbook-approximate, the evaluation is exact). Colebrook
//! is the one implicit root in this file; it is solved by Newton
//! iteration to a tight, fixed tolerance (`_COLEBROOK_TOL`), which is
//! evaluating the SAME defining equation to floating-point precision,
//! not a separate approximate model.

#![allow(clippy::too_many_arguments)]

const _COLEBROOK_TOL: f64 = 1e-12;
const _COLEBROOK_MAX_ITER: u32 = 100;

/// Reynolds number for internal pipe flow: `Re = rho * v * D / mu`.
///
/// Citation: White, *Fluid Mechanics*, 8th ed., ch. 6 (internal flow,
/// Reynolds number definition).
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
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_pump_operating_flow(h0: f64, a: f64, h_static: f64, r: f64) -> f64 {
    ((h0 - h_static) / (a + r)).sqrt()
}

/// Pump/system operating-point head at the flow rate `Q*` found by
/// [`fluids_pump_operating_flow`]: `H* = H_static + R*Q*^2`.
///
/// Citation: same as [`fluids_pump_operating_flow`].
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
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn fluids_joukowsky_dp(density: f64, wave_speed: f64, delta_velocity: f64) -> f64 {
    density * wave_speed * delta_velocity
}

// ---------------------------------------------------------------------------
// Compressible tier (D141): isentropic relations, normal shocks, Fanno
// function. Registered under the SAME `fluids` namespace; Python side
// distinguishes the regime via `Domain.tags` ("compressible" /
// "incompressible") since the low-Mach/choked screening lives there
// (09 sec. 4/lithos WO-14 regime channel).
// ---------------------------------------------------------------------------

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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn laminar_floor_matches_64_over_re() {
        let f = fluids_laminar_friction_factor(1000.0);
        assert!((f - 0.0640).abs() < 1e-6);
    }

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

    #[test]
    fn pump_operating_point_matches_memo_case() {
        let q_star = fluids_pump_operating_flow(50.0, 2000.0, 10.0, 3000.0);
        assert!((q_star - 0.08944).abs() / 0.08944 < 1e-3);
        let h_star = fluids_pump_operating_head(10.0, 3000.0, q_star);
        assert!((h_star - 34.0).abs() / 34.0 < 1e-3);
    }

    #[test]
    fn series_and_parallel_network_reduction() {
        assert!((fluids_series_dp(3.0, 2.0) - 5.0).abs() < 1e-12);
        assert!((fluids_parallel_flow(0.006, 0.006) - 0.012).abs() < 1e-12);
    }
}
