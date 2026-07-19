//! PyO3 wrappers for `feldspar_library::elec` (WO-17): marshalling
//! only, no logic (AD-1 layering). Same thin pass-through contract as
//! `library::mech`.

use pyo3::prelude::*;

/// See `feldspar_library::elec::divider_loaded_vout` for the formula
/// and citation (Sedra & Smith, *Microelectronic Circuits*).
// frob:doc docs/modules/feldspar-py.md#py_library_elec
#[pyfunction]
#[pyo3(name = "elec_divider_loaded_vout")]
pub fn elec_divider_loaded_vout_py(vin: f64, r1: f64, r2: f64, rl: f64) -> f64 {
    feldspar_library::elec::divider_loaded_vout(vin, r1, r2, rl)
}

/// See `feldspar_library::elec::rc_step_response` for the formula and
/// citation (Nilsson & Riedel, *Electric Circuits*).
// frob:doc docs/modules/feldspar-py.md#py_library_elec
#[pyfunction]
#[pyo3(name = "elec_rc_step_response")]
pub fn elec_rc_step_response_py(vf: f64, r: f64, c: f64, t: f64) -> f64 {
    feldspar_library::elec::rc_step_response(vf, r, c, t)
}

/// See `feldspar_library::elec::rlc_resonant_frequency` for the
/// formula and citation (Nilsson & Riedel, *Electric Circuits*).
// frob:doc docs/modules/feldspar-py.md#py_library_elec
#[pyfunction]
#[pyo3(name = "elec_rlc_resonant_frequency")]
pub fn elec_rlc_resonant_frequency_py(inductance: f64, capacitance: f64) -> f64 {
    feldspar_library::elec::rlc_resonant_frequency(inductance, capacitance)
}

/// See `feldspar_library::elec::rlc_quality_factor` for the formula
/// and citation (Nilsson & Riedel, *Electric Circuits*).
// frob:doc docs/modules/feldspar-py.md#py_library_elec
#[pyfunction]
#[pyo3(name = "elec_rlc_quality_factor")]
pub fn elec_rlc_quality_factor_py(resistance: f64, inductance: f64, capacitance: f64) -> f64 {
    feldspar_library::elec::rlc_quality_factor(resistance, inductance, capacitance)
}

/// See `feldspar_library::elec::bjt_bias_collector_current` for the
/// formula and citation (Sedra & Smith, *Microelectronic Circuits*).
// frob:doc docs/modules/feldspar-py.md#py_library_elec
#[pyfunction]
#[pyo3(name = "elec_bjt_bias_collector_current")]
pub fn elec_bjt_bias_collector_current_py(
    vcc: f64,
    r1: f64,
    r2: f64,
    re: f64,
    beta: f64,
    vbe: f64,
) -> f64 {
    feldspar_library::elec::bjt_bias_collector_current(vcc, r1, r2, re, beta, vbe)
}

/// See `feldspar_library::elec::bjt_bias_collector_voltage` for the
/// formula and citation (Sedra & Smith, *Microelectronic Circuits*).
// frob:doc docs/modules/feldspar-py.md#py_library_elec
#[pyfunction]
#[pyo3(name = "elec_bjt_bias_collector_voltage")]
pub fn elec_bjt_bias_collector_voltage_py(vcc: f64, collector_current: f64, rc: f64) -> f64 {
    feldspar_library::elec::bjt_bias_collector_voltage(vcc, collector_current, rc)
}

/// See `feldspar_library::elec::nmos_saturation_drain_current` for the
/// formula and citation (Razavi, *Design of Analog CMOS Integrated
/// Circuits*).
// frob:doc docs/modules/feldspar-py.md#py_library_elec
#[pyfunction]
#[pyo3(name = "elec_nmos_saturation_drain_current")]
pub fn elec_nmos_saturation_drain_current_py(k: f64, vgs: f64, vth: f64) -> f64 {
    feldspar_library::elec::nmos_saturation_drain_current(k, vgs, vth)
}
