//! Circuits/electronics closed-form formula home (WO-17, 07 "elec").
//!
//! Same AD-3 contract as `mech.rs`: every formula is a single
//! `#[no_mangle] pub extern "C" fn`, both the plain Rust `pub fn`
//! callers use and the link-visible C ABI symbol. `rc_step_response`
//! is the one formula in this module with a transcendental term
//! (`exp`), so it goes through `libm` (AD-13) rather than `std`'s
//! platform-dependent `f64::exp`; every other formula here uses only
//! `+ - * / powi sqrt`, which are IEEE-754 exempt.

/// Loaded resistive divider output voltage: `Vout = Vin * Rp / (R1 +
/// Rp)` where `Rp = R2 * RL / (R2 + RL)` is `R2` in parallel with the
/// load `RL`. Passing a very large `RL` degenerates to the unloaded
/// divider `Vout = Vin * R2 / (R1 + R2)`.
///
/// Citation: Sedra & Smith, *Microelectronic Circuits*, resistive
/// divider under load (also Horowitz & Hill, *The Art of
/// Electronics*).
// frob:doc docs/modules/feldspar-library.md#library_elec
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn divider_loaded_vout(vin: f64, r1: f64, r2: f64, rl: f64) -> f64 {
    let r_parallel = (r2 * rl) / (r2 + rl);
    vin * r_parallel / (r1 + r_parallel)
}

/// Series RC step response: `v_C(t) = Vf * (1 - exp(-t / (R*C)))`,
/// the charging voltage across `C` `t` seconds after a step from 0 to
/// `Vf` is applied through `R`.
///
/// Citation: Sedra & Smith, *Microelectronic Circuits*; Nilsson &
/// Riedel, *Electric Circuits*, first-order RC step response.
// frob:doc docs/modules/feldspar-library.md#library_elec
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn rc_step_response(vf: f64, r: f64, c: f64, t: f64) -> f64 {
    let tau = r * c;
    vf * (1.0 - libm::exp(-t / tau))
}

/// Series RLC undamped resonant frequency: `f0 = 1 / (2*pi*sqrt(L*C))`.
///
/// Citation: Nilsson & Riedel, *Electric Circuits*, series RLC
/// resonance.
// frob:doc docs/modules/feldspar-library.md#library_elec
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn rlc_resonant_frequency(inductance: f64, capacitance: f64) -> f64 {
    1.0 / (2.0 * std::f64::consts::PI * (inductance * capacitance).sqrt())
}

/// Series RLC quality factor: `Q = (1/R) * sqrt(L/C)`.
///
/// Citation: Nilsson & Riedel, *Electric Circuits*, series RLC
/// resonance (bandwidth/Q).
// frob:doc docs/modules/feldspar-library.md#library_elec
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn rlc_quality_factor(resistance: f64, inductance: f64, capacitance: f64) -> f64 {
    (1.0 / resistance) * (inductance / capacitance).sqrt()
}

/// BJT 4-resistor bias network collector current via the Thevenin-
/// equivalent base network: `V_th = Vcc*R2/(R1+R2)`, `R_th =
/// R1*R2/(R1+R2)`, `I_B = (V_th - V_BE) / (R_th + (beta+1)*RE)`,
/// `I_C = beta * I_B`.
///
/// Citation: Sedra & Smith, *Microelectronic Circuits*, 4-resistor
/// bias analysis.
// frob:doc docs/modules/feldspar-library.md#library_elec
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn bjt_bias_collector_current(
    vcc: f64,
    r1: f64,
    r2: f64,
    re: f64,
    beta: f64,
    vbe: f64,
) -> f64 {
    let v_th = vcc * r2 / (r1 + r2);
    let r_th = (r1 * r2) / (r1 + r2);
    let i_b = (v_th - vbe) / (r_th + (beta + 1.0) * re);
    beta * i_b
}

/// BJT 4-resistor bias network collector voltage:
/// `V_C = Vcc - I_C * RC`, given the collector current from
/// [`bjt_bias_collector_current`].
///
/// Citation: same source as [`bjt_bias_collector_current`].
// frob:doc docs/modules/feldspar-library.md#library_elec
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn bjt_bias_collector_voltage(vcc: f64, collector_current: f64, rc: f64) -> f64 {
    vcc - collector_current * rc
}

/// NMOS saturation drain current: `I_D = (k/2) * (V_GS - V_th)^2`
/// (level-1 square-law model, lambda/body effect ignored).
///
/// Citation: Razavi, *Design of Analog CMOS Integrated Circuits*,
/// square-law MOSFET saturation model.
// frob:doc docs/modules/feldspar-library.md#library_elec
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn nmos_saturation_drain_current(k: f64, vgs: f64, vth: f64) -> f64 {
    (k / 2.0) * (vgs - vth).powi(2)
}

#[cfg(test)]
mod tests {
    use super::*;

    // Worked fixtures from `lithos:docs/workflow/research/
    // 2026-07-08-benchmarks-and-datasets.md` sec. 4 (the WO-17
    // calibration cases).

    // frob:tests crates/feldspar-library/src/elec.rs::divider_loaded_vout kind="unit"
    #[test]
    fn divider_loaded_matches_benchmark_memo() {
        // Vin=10V, R1=R2=10k, RL=100k -> Vout=4.762V.
        let vout = divider_loaded_vout(10.0, 10e3, 10e3, 100e3);
        assert!((vout - 4.761904761904762).abs() < 1e-9);
    }

    #[test]
    fn divider_unloaded_degenerates_to_plain_divider() {
        // A very large RL should recover the unloaded divider ratio.
        let vout = divider_loaded_vout(10.0, 10e3, 10e3, 1e15);
        assert!((vout - 5.0).abs() < 1e-6);
    }

    #[test]
    fn rc_step_response_matches_benchmark_memo() {
        // R=1k, C=1uF (tau=1ms), Vf=5V, t=1ms -> v_C=3.161V (63.21% Vf).
        let vc = rc_step_response(5.0, 1000.0, 1e-6, 1e-3);
        assert!((vc - 3.161).abs() < 1e-2);
    }

    #[test]
    fn rc_step_response_at_zero_time_is_zero() {
        assert_eq!(rc_step_response(5.0, 1000.0, 1e-6, 0.0), 0.0);
    }

    #[test]
    fn rlc_resonant_frequency_matches_benchmark_memo() {
        // L=10mH, C=100nF -> f0=5033 Hz.
        let f0 = rlc_resonant_frequency(10e-3, 100e-9);
        assert!((f0 - 5033.0).abs() / 5033.0 < 1e-2);
    }

    #[test]
    fn rlc_quality_factor_matches_benchmark_memo() {
        // R=10 ohm, L=10mH, C=100nF -> Q=31.6.
        let q = rlc_quality_factor(10.0, 10e-3, 100e-9);
        assert!((q - 31.6).abs() / 31.6 < 1e-2);
    }

    // frob:tests crates/feldspar-library/src/elec.rs::bjt_bias_collector_current kind="unit"
    // frob:tests crates/feldspar-library/src/elec.rs::bjt_bias_collector_voltage kind="unit"
    #[test]
    fn bjt_bias_matches_benchmark_memo() {
        // Vcc=12V, R1=47k, R2=10k, RE=1k, RC=2.2k, beta=100, Vbe=0.7V.
        let ic = bjt_bias_collector_current(12.0, 47e3, 10e3, 1e3, 100.0, 0.7);
        assert!((ic - 1.286e-3).abs() / 1.286e-3 < 1e-3);
        let vc = bjt_bias_collector_voltage(12.0, ic, 2.2e3);
        assert!((vc - 9.17).abs() / 9.17 < 1e-3);
    }

    #[test]
    fn nmos_saturation_drain_current_matches_benchmark_memo() {
        // k=1mA/V^2, Vgs=3V, Vth=1V -> Id=2.0mA.
        let id = nmos_saturation_drain_current(1e-3, 3.0, 1.0);
        assert!((id - 2.0e-3).abs() < 1e-12);
    }
}
