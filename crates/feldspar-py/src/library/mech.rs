//! PyO3 wrappers for `feldspar_library::mech` (WO-07): marshalling only,
//! no logic (AD-1 layering) -- each `#[pyfunction]` here is a thin,
//! zero-logic pass-through to the single Rust home of the formula in
//! `feldspar-library`. Python-visible names carry a `mech_` prefix to
//! keep the flat `_feldspar` namespace collision-free with future
//! namespaces (thermo, fluids, ...).

use pyo3::prelude::*;

/// See `feldspar_library::mech::rect_second_moment` for the formula and
/// citation (Gere, *Mechanics of Materials*, 9th ed., App. E).
// frob:doc docs/modules/feldspar-py.md#py_library_mech
#[pyfunction]
#[pyo3(name = "mech_rect_second_moment")]
pub fn mech_rect_second_moment_py(width: f64, height: f64) -> f64 {
    feldspar_library::mech::rect_second_moment(width, height)
}

/// See `feldspar_library::mech::cantilever_tip_deflection` for the
/// formula and citation (Gere, *Mechanics of Materials*, 9th ed.).
// frob:doc docs/modules/feldspar-py.md#py_library_mech
#[pyfunction]
#[pyo3(name = "mech_cantilever_tip_deflection")]
pub fn mech_cantilever_tip_deflection_py(
    force: f64,
    length: f64,
    youngs_modulus: f64,
    second_moment: f64,
) -> f64 {
    feldspar_library::mech::cantilever_tip_deflection(force, length, youngs_modulus, second_moment)
}

/// See `feldspar_library::mech::cantilever_required_youngs_modulus` for
/// the formula and citation (same law as the tip-deflection formula,
/// solved for `E`).
// frob:doc docs/modules/feldspar-py.md#py_library_mech
#[pyfunction]
#[pyo3(name = "mech_cantilever_required_youngs_modulus")]
pub fn mech_cantilever_required_youngs_modulus_py(
    force: f64,
    length: f64,
    second_moment: f64,
    deflection: f64,
) -> f64 {
    feldspar_library::mech::cantilever_required_youngs_modulus(
        force,
        length,
        second_moment,
        deflection,
    )
}

/// See `feldspar_library::mech::lame_hoop_stress_bore` for the formula
/// and citation (Budynas & Nisbett, *Shigley's Mechanical Engineering
/// Design*, "Thick-Walled Cylinders").
// frob:doc docs/modules/feldspar-py.md#py_library_mech
#[pyfunction]
#[pyo3(name = "mech_lame_hoop_stress_bore")]
pub fn mech_lame_hoop_stress_bore_py(pressure: f64, inner_radius: f64, outer_radius: f64) -> f64 {
    feldspar_library::mech::lame_hoop_stress_bore(pressure, inner_radius, outer_radius)
}

/// See `feldspar_library::mech::lame_radial_stress_bore` for the
/// formula and citation (Budynas & Nisbett, *Shigley's Mechanical
/// Engineering Design*, "Thick-Walled Cylinders").
// frob:doc docs/modules/feldspar-py.md#py_library_mech
#[pyfunction]
#[pyo3(name = "mech_lame_radial_stress_bore")]
pub fn mech_lame_radial_stress_bore_py(pressure: f64, inner_radius: f64, outer_radius: f64) -> f64 {
    feldspar_library::mech::lame_radial_stress_bore(pressure, inner_radius, outer_radius)
}

/// See `feldspar_library::mech::von_mises_principal` for the formula
/// and citation (Budynas & Nisbett, *Shigley's Mechanical Engineering
/// Design*, distortion-energy equivalent stress).
// frob:doc docs/modules/feldspar-py.md#py_library_mech
#[pyfunction]
#[pyo3(name = "mech_von_mises_principal")]
pub fn mech_von_mises_principal_py(sigma1: f64, sigma2: f64, sigma3: f64) -> f64 {
    feldspar_library::mech::von_mises_principal(sigma1, sigma2, sigma3)
}

/// See `feldspar_library::mech::bore_von_mises` for the formula and
/// citation (Budynas & Nisbett, *Shigley's Mechanical Engineering
/// Design*, "Thick-Walled Cylinders" and distortion-energy equivalent
/// stress).
// frob:doc docs/modules/feldspar-py.md#py_library_mech
#[pyfunction]
#[pyo3(name = "mech_bore_von_mises")]
pub fn mech_bore_von_mises_py(pressure: f64, inner_radius: f64, outer_radius: f64) -> f64 {
    feldspar_library::mech::bore_von_mises(pressure, inner_radius, outer_radius)
}

/// See `feldspar_library::mech::sdof_first_mode` for the formula and
/// citation (Rao, *Mechanical Vibrations*, SDOF undamped natural
/// frequency).
// frob:doc docs/modules/feldspar-py.md#py_library_mech
#[pyfunction]
#[pyo3(name = "mech_sdof_first_mode")]
pub fn mech_sdof_first_mode_py(stiffness: f64, mass: f64) -> f64 {
    feldspar_library::mech::sdof_first_mode(stiffness, mass)
}

/// See `feldspar_library::mech::beam_cantilever_first_mode` for the
/// formula and citation (Blevins, *Formulas for Natural Frequency and
/// Mode Shape*, Table 8-1).
// frob:doc docs/modules/feldspar-py.md#py_library_mech
#[pyfunction]
#[pyo3(name = "mech_beam_cantilever_first_mode")]
pub fn mech_beam_cantilever_first_mode_py(
    youngs_modulus: f64,
    second_moment: f64,
    density: f64,
    area: f64,
    length: f64,
) -> f64 {
    feldspar_library::mech::beam_cantilever_first_mode(
        youngs_modulus,
        second_moment,
        density,
        area,
        length,
    )
}

/// See `feldspar_library::mech::miles_grms` for the formula and
/// citation (Steinberg, *Vibration Analysis for Electronic Equipment*,
/// ch. 2, Miles' equation).
// frob:doc docs/modules/feldspar-py.md#py_library_mech
#[pyfunction]
#[pyo3(name = "mech_miles_grms")]
pub fn mech_miles_grms_py(fn_hz: f64, q: f64, asd: f64) -> f64 {
    feldspar_library::mech::miles_grms(fn_hz, q, asd)
}

/// PyO3 marshalling for `feldspar_library::mech::frame2d_solve` (WO-21
/// `mech.struct`): flattens the Rust struct-of-arrays into plain
/// Python-friendly Vecs (no numpy dependency, matching the rest of
/// this crate's zero-extra-dependency posture) and maps `FrameError`
/// to a `ValueError` (this is a marshalling boundary, not a `Result`-
/// returning solve-time API -- `python/feldspar/library/struct.py`
/// wraps this raw call in the typani `Result` the solver directions
/// promise, same pattern as every other `_feldspar.*` primitive).
///
/// Every `member_*` Vec must be the same length (one entry per
/// member); `member_fef` rows are `[n1, v1, m1, n2, v2, m2]` in the
/// member's LOCAL axes. `fixed`/`loads` are length `3 * n_nodes`
/// (`[ux, uy, rz]` per node, global axes).
///
/// Returns `(displacements, reactions, member_end_forces_local)`:
/// `displacements`/`reactions` are flattened `3 * n_nodes` Vecs (same
/// DOF order as `fixed`); `member_end_forces_local` is one 6-Vec per
/// member.
#[allow(clippy::too_many_arguments)] // marshalling boundary: one struct-of-arrays field per parameter
#[allow(clippy::type_complexity)] // marshalling boundary: plain (Vec, Vec, Vec<Vec>) tuple, no natural named type
#[pyfunction]
#[pyo3(name = "mech_frame2d_solve")]
// frob:doc docs/modules/feldspar-py.md#py_library_mech
pub fn mech_frame2d_solve_py(
    n_nodes: usize,
    member_i: Vec<usize>,
    member_j: Vec<usize>,
    member_dx: Vec<f64>,
    member_dy: Vec<f64>,
    member_ea: Vec<f64>,
    member_ei: Vec<f64>,
    member_release_a: Vec<bool>,
    member_release_b: Vec<bool>,
    member_fef: Vec<Vec<f64>>,
    fixed: Vec<bool>,
    loads: Vec<f64>,
) -> PyResult<(Vec<f64>, Vec<f64>, Vec<Vec<f64>>)> {
    let n_members = member_i.len();
    if [
        member_j.len(),
        member_dx.len(),
        member_dy.len(),
        member_ea.len(),
        member_ei.len(),
        member_release_a.len(),
        member_release_b.len(),
        member_fef.len(),
    ]
    .iter()
    .any(|&len| len != n_members)
    {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "mech_frame2d_solve: all member_* arguments must have equal length",
        ));
    }
    let members: Vec<feldspar_library::mech::FrameMemberInput> = (0..n_members)
        .map(|idx| {
            let fef = &member_fef[idx];
            if fef.len() != 6 {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "mech_frame2d_solve: member_fef[{idx}] must have exactly 6 entries"
                )));
            }
            Ok(feldspar_library::mech::FrameMemberInput {
                i: member_i[idx],
                j: member_j[idx],
                dx: member_dx[idx],
                dy: member_dy[idx],
                ea: member_ea[idx],
                ei: member_ei[idx],
                release_a_rz: member_release_a[idx],
                release_b_rz: member_release_b[idx],
                fef_local: [fef[0], fef[1], fef[2], fef[3], fef[4], fef[5]],
            })
        })
        .collect::<PyResult<_>>()?;

    let solution = feldspar_library::mech::frame2d_solve(n_nodes, &members, &fixed, &loads)
        .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))?;

    let flatten3 =
        |rows: &[[f64; 3]]| -> Vec<f64> { rows.iter().flat_map(|r| r.to_vec()).collect() };
    let displacements = flatten3(&solution.displacements);
    let reactions = flatten3(&solution.reactions);
    let member_end_forces_local: Vec<Vec<f64>> = solution
        .member_end_forces_local
        .iter()
        .map(|r| r.to_vec())
        .collect();
    Ok((displacements, reactions, member_end_forces_local))
}
