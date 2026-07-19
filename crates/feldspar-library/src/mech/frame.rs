//! 2D direct-stiffness frame solver (WO-21 `mech.struct`, Phase 6).
//!
//! Unlike the rest of [`crate::mech`] this is a variable-size MATRIX
//! assemble/solve, not a single closed-form scalar law -- it does not
//! fit the one-formula `extern "C"` shape (AD-3) the sibling modules
//! use, so it is exposed as an ordinary `pub fn` plus a PyO3 wrapper
//! only (cut recorded in the WO-21 close-out).
//!
//! Scope (honest, not the full 07 mech.struct Phase 6 wave): a 2D
//! (planar) frame element with axial + Euler-Bernoulli bending
//! stiffness, an optional moment release (hinge) at either end handled
//! by static condensation of that end's rotational DOF, assembled into
//! a global stiffness system and solved for displacements/reactions/
//! member-end forces. Distributed-load member loads are handled by the
//! CALLER supplying local fixed-end forces (the standard FEA
//! equivalent-nodal-load technique) -- this module only assembles and
//! solves.
//!
//! NOT built here (named cuts, WO-21 close-out): 3D/grid elements,
//! shear deformation (Timoshenko), buckling/plate/connection design
//! checks, and any section/material PROPERTY resolution (this module
//! consumes already-resolved `ea`/`ei` scalars; resolving a
//! `RecordRef`'s digest to numeric section/material properties is a
//! separate, unbuilt registry-resolution channel -- see the WO file).

/// One 2D frame member's assembled input: node indices, the member's
/// GLOBAL projected geometry (`dx`, `dy` -- length and direction folded
/// together, since the payload carries a categorical orientation, not
/// an angle), resolved axial (`ea`) and bending (`ei`) rigidities, an
/// optional moment release at each end, and the member's local fixed-
/// end force vector (`[n1, v1, m1, n2, v2, m2]`, zero when no
/// distributed/interior load acts on the member).
// frob:doc docs/modules/feldspar-library.md#library_mech_frame
#[derive(Debug, Clone, Copy)]
pub struct FrameMemberInput {
    pub i: usize,
    pub j: usize,
    pub dx: f64,
    pub dy: f64,
    pub ea: f64,
    pub ei: f64,
    pub release_a_rz: bool,
    pub release_b_rz: bool,
    pub fef_local: [f64; 6],
}

/// Fallible outcomes of [`frame2d_solve`]: a member whose two ends
/// coincide (zero length, division by zero in the geometry) or a
/// global system whose free-DOF partition is singular (an
/// unrestrained mechanism -- e.g. every support fixity unresolved).
// frob:doc docs/modules/feldspar-library.md#library_mech_frame
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FrameError {
    DegenerateMember(usize),
    SingularSystem,
    InvalidShape(String),
}

impl std::fmt::Display for FrameError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::DegenerateMember(idx) => {
                write!(f, "member {idx} has zero length (coincident ends)")
            }
            Self::SingularSystem => {
                write!(f, "global free-DOF stiffness partition is singular")
            }
            Self::InvalidShape(msg) => write!(f, "invalid input shape: {msg}"),
        }
    }
}

impl std::error::Error for FrameError {}

/// The solved system: per-node displacements/reactions (`[ux, uy,
/// rz]`, global axes) and per-member local end forces (`[n1, v1, m1,
/// n2, v2, m2]`, member-local axes, sign convention matching the input
/// `fef_local`).
// frob:doc docs/modules/feldspar-library.md#library_mech_frame
#[derive(Debug, Clone)]
pub struct FrameSolution {
    pub displacements: Vec<[f64; 3]>,
    pub reactions: Vec<[f64; 3]>,
    pub member_end_forces_local: Vec<[f64; 6]>,
}

const DOF_PER_NODE: usize = 3;
const DEGENERATE_LENGTH_EPS: f64 = 1e-9;

/// Gaussian elimination with partial pivoting: solves `a * x = b` in
/// place, returning [`FrameError::SingularSystem`] if a pivot is
/// numerically zero. Small dense systems only (frame DOF counts); no
/// attempt at sparsity.
#[allow(clippy::needless_range_loop)] // dense 2D matrix indexing reads clearer than enumerate here
fn solve_dense(mut a: Vec<Vec<f64>>, mut b: Vec<f64>) -> Result<Vec<f64>, FrameError> {
    let n = b.len();
    if n == 0 {
        return Ok(Vec::new());
    }
    for col in 0..n {
        let mut pivot_row = col;
        let mut pivot_val = a[col][col].abs();
        for row in (col + 1)..n {
            if a[row][col].abs() > pivot_val {
                pivot_row = row;
                pivot_val = a[row][col].abs();
            }
        }
        if pivot_val < 1e-12 {
            return Err(FrameError::SingularSystem);
        }
        if pivot_row != col {
            a.swap(col, pivot_row);
            b.swap(col, pivot_row);
        }
        for row in (col + 1)..n {
            let factor = a[row][col] / a[col][col];
            if factor == 0.0 {
                continue;
            }
            for k in col..n {
                a[row][k] -= factor * a[col][k];
            }
            b[row] -= factor * b[col];
        }
    }
    let mut x = vec![0.0; n];
    for row in (0..n).rev() {
        let mut sum = b[row];
        for k in (row + 1)..n {
            sum -= a[row][k] * x[k];
        }
        x[row] = sum / a[row][row];
    }
    Ok(x)
}

/// The full (unreleased) 6x6 local stiffness matrix, DOF order `[u1,
/// v1, th1, u2, v2, th2]`.
fn local_stiffness_full(ea: f64, ei: f64, length: f64) -> Vec<Vec<f64>> {
    let l = length;
    let a = ea / l;
    let b1 = 12.0 * ei / l.powi(3);
    let b2 = 6.0 * ei / l.powi(2);
    let b3 = 4.0 * ei / l;
    let b4 = 2.0 * ei / l;
    vec![
        vec![a, 0.0, 0.0, -a, 0.0, 0.0],
        vec![0.0, b1, b2, 0.0, -b1, b2],
        vec![0.0, b2, b3, 0.0, -b2, b4],
        vec![-a, 0.0, 0.0, a, 0.0, 0.0],
        vec![0.0, -b1, -b2, 0.0, b1, -b2],
        vec![0.0, b2, b4, 0.0, -b2, b3],
    ]
}

/// Static condensation: eliminates the DOFs at indices in `condensed`
/// from `k`/`fef` (both 6-sized), returning the reduced stiffness/load
/// over the retained indices (in their original relative order) plus
/// the retained index list itself. Condensed DOFs are assumed to carry
/// zero applied moment (the release condition), i.e. `k_cc * d_c +
/// k_cr * d_r + fef_c = 0`.
#[allow(clippy::type_complexity)] // internal helper: plain (matrix, vec, index-list) tuple, no natural named type
fn condense(
    k: &[Vec<f64>],
    fef: &[f64; 6],
    condensed: &[usize],
) -> Result<(Vec<Vec<f64>>, Vec<f64>, Vec<usize>), FrameError> {
    let retained: Vec<usize> = (0..6).filter(|i| !condensed.contains(i)).collect();
    if condensed.is_empty() {
        return Ok((k.to_vec(), fef.to_vec(), retained));
    }
    let nc = condensed.len();
    let kcc: Vec<Vec<f64>> = condensed
        .iter()
        .map(|&r| condensed.iter().map(|&c| k[r][c]).collect())
        .collect();
    // Kcc^-1 * Kcr and Kcc^-1 * fef_c, one solve per retained column
    // plus one for the load vector (Kcc is 1x1 or 2x2 in practice).
    // Kcc IS reachable-singular (a released end whose `ei == 0`);
    // propagate as `FrameError::SingularSystem` rather than panicking
    // across the PyO3 boundary.
    let mut kcc_inv_kcr = vec![vec![0.0; retained.len()]; nc];
    for (col_idx, &rcol) in retained.iter().enumerate() {
        let rhs: Vec<f64> = condensed.iter().map(|&r| k[r][rcol]).collect();
        let sol = solve_dense(kcc.clone(), rhs)?;
        for row in 0..nc {
            kcc_inv_kcr[row][col_idx] = sol[row];
        }
    }
    let fef_c: Vec<f64> = condensed.iter().map(|&r| fef[r]).collect();
    let kcc_inv_fefc = solve_dense(kcc, fef_c)?;

    let mut k_red = vec![vec![0.0; retained.len()]; retained.len()];
    let mut fef_red = vec![0.0; retained.len()];
    for (pi, &rp) in retained.iter().enumerate() {
        for (qi, &rq) in retained.iter().enumerate() {
            let mut krc_kccinv_kcr = 0.0;
            for c in 0..nc {
                krc_kccinv_kcr += k[rp][condensed[c]] * kcc_inv_kcr[c][qi];
            }
            k_red[pi][qi] = k[rp][rq] - krc_kccinv_kcr;
        }
        let mut krc_kccinv_fefc = 0.0;
        for c in 0..nc {
            krc_kccinv_fefc += k[rp][condensed[c]] * kcc_inv_fefc[c];
        }
        fef_red[pi] = fef[rp] - krc_kccinv_fefc;
    }
    Ok((k_red, fef_red, retained))
}

/// The rotation-matrix ROW for local DOF `local_idx` (0-based into the
/// full 6-DOF ordering): translations mix with their node's sibling
/// translation via `(c, s)`; rotations pass through unchanged (planar
/// frame -- rz is invariant under an in-plane rotation of axes).
fn transform_row(local_idx: usize, c: f64, s: f64) -> [f64; 6] {
    let mut row = [0.0; 6];
    match local_idx {
        0 => {
            row[0] = c;
            row[1] = s;
        }
        1 => {
            row[0] = -s;
            row[1] = c;
        }
        2 => row[2] = 1.0,
        3 => {
            row[3] = c;
            row[4] = s;
        }
        4 => {
            row[3] = -s;
            row[4] = c;
        }
        5 => row[5] = 1.0,
        _ => unreachable!("local DOF index out of range 0..6"),
    }
    row
}

/// Solves a 2D frame direct-stiffness system: assembles the global
/// stiffness matrix from `members`, applies `fixed` (length `3 *
/// n_nodes`, true = restrained, displacement pinned to zero) and
/// `loads` (length `3 * n_nodes`, applied global nodal loads), and
/// returns nodal displacements/reactions plus per-member local end
/// forces.
///
/// # Errors
/// [`FrameError::DegenerateMember`] for a zero-length member;
/// [`FrameError::SingularSystem`] if the free-DOF partition cannot be
/// solved (an unrestrained mechanism).
// frob:doc docs/modules/feldspar-library.md#library_mech_frame
#[allow(clippy::needless_range_loop)] // dense stiffness/DOF matrix indexing reads clearer than enumerate here
pub fn frame2d_solve(
    n_nodes: usize,
    members: &[FrameMemberInput],
    fixed: &[bool],
    loads: &[f64],
) -> Result<FrameSolution, FrameError> {
    let ndof = n_nodes * DOF_PER_NODE;
    if fixed.len() != ndof {
        return Err(FrameError::InvalidShape(format!(
            "fixed mask length {} != 3*n_nodes ({})",
            fixed.len(),
            ndof
        )));
    }
    if loads.len() != ndof {
        return Err(FrameError::InvalidShape(format!(
            "load vector length {} != 3*n_nodes ({})",
            loads.len(),
            ndof
        )));
    }
    for (idx, m) in members.iter().enumerate() {
        if m.i >= n_nodes || m.j >= n_nodes {
            return Err(FrameError::InvalidShape(format!(
                "member {idx} node index i={} j={} out of range (n_nodes={n_nodes})",
                m.i, m.j
            )));
        }
    }

    let mut k_global = vec![vec![0.0; ndof]; ndof];
    let mut f_global = loads.to_vec();

    // Per-member reduced data kept for the end-force recovery pass.
    struct Reduced {
        retained: Vec<usize>,
        condensed: Vec<usize>,
        k_full: Vec<Vec<f64>>,
        fef_full: [f64; 6],
        global_dof: [usize; 6],
        c: f64,
        s: f64,
    }
    let mut reduced_members = Vec::with_capacity(members.len());

    for (idx, m) in members.iter().enumerate() {
        let length = (m.dx * m.dx + m.dy * m.dy).sqrt();
        if length < DEGENERATE_LENGTH_EPS {
            return Err(FrameError::DegenerateMember(idx));
        }
        let c = m.dx / length;
        let s = m.dy / length;
        let global_dof = [
            m.i * DOF_PER_NODE,
            m.i * DOF_PER_NODE + 1,
            m.i * DOF_PER_NODE + 2,
            m.j * DOF_PER_NODE,
            m.j * DOF_PER_NODE + 1,
            m.j * DOF_PER_NODE + 2,
        ];

        let k_full = local_stiffness_full(m.ea, m.ei, length);
        let mut condensed = Vec::new();
        if m.release_a_rz {
            condensed.push(2);
        }
        if m.release_b_rz {
            condensed.push(5);
        }
        let (k_red, fef_red, retained) = condense(&k_full, &m.fef_local, &condensed)?;

        // Build the retained-DOF transform rows and assemble, for
        // every pair of FULL local-axis positions (full_a, full_b):
        //   K_global[global_dof[full_a]][global_dof[full_b]] +=
        //     sum_{p,q in retained} T[p][full_a] * Kred[p][q] * T[q][full_b]
        // (i.e. K_global_elem = T_red^T * K_red * T_red, expanded
        // directly into global indices without materializing the
        // intermediate 6x6).
        let t_rows: Vec<[f64; 6]> = retained.iter().map(|&li| transform_row(li, c, s)).collect();
        for full_a in 0..6 {
            for full_b in 0..6 {
                let mut acc = 0.0;
                for (p, _) in retained.iter().enumerate() {
                    if t_rows[p][full_a] == 0.0 {
                        continue;
                    }
                    for (q, _) in retained.iter().enumerate() {
                        if t_rows[q][full_b] == 0.0 {
                            continue;
                        }
                        acc += t_rows[p][full_a] * k_red[p][q] * t_rows[q][full_b];
                    }
                }
                if acc != 0.0 {
                    k_global[global_dof[full_a]][global_dof[full_b]] += acc;
                }
            }
        }
        for full_a in 0..6 {
            let mut acc = 0.0;
            for (p, _) in retained.iter().enumerate() {
                if t_rows[p][full_a] == 0.0 {
                    continue;
                }
                acc += t_rows[p][full_a] * fef_red[p];
            }
            f_global[global_dof[full_a]] -= acc;
        }

        reduced_members.push(Reduced {
            retained,
            condensed,
            k_full,
            fef_full: m.fef_local,
            global_dof,
            c,
            s,
        });
    }

    // Partition into free/fixed DOFs and solve K_ff * d_f = F_f.
    let free_dofs: Vec<usize> = (0..ndof).filter(|&d| !fixed[d]).collect();
    let a_ff: Vec<Vec<f64>> = free_dofs
        .iter()
        .map(|&r| free_dofs.iter().map(|&c| k_global[r][c]).collect())
        .collect();
    let b_f: Vec<f64> = free_dofs.iter().map(|&r| f_global[r]).collect();
    let d_f = solve_dense(a_ff, b_f)?;

    let mut d_full = vec![0.0; ndof];
    for (i, &dof) in free_dofs.iter().enumerate() {
        d_full[dof] = d_f[i];
    }

    // Reactions: R = K * d - F, evaluated at every DOF (zero at free
    // DOFs by construction of the solve).
    let mut reactions = vec![[0.0; 3]; n_nodes];
    let mut displacements = vec![[0.0; 3]; n_nodes];
    for node in 0..n_nodes {
        for local in 0..3 {
            let dof = node * 3 + local;
            displacements[node][local] = d_full[dof];
            if fixed[dof] {
                let mut kd = 0.0;
                for c in 0..ndof {
                    kd += k_global[dof][c] * d_full[c];
                }
                reactions[node][local] = kd - f_global[dof];
            }
        }
    }

    // Member end forces: gather retained local displacements, recover
    // condensed rotations via the release equilibrium condition, then
    // apply the FULL local stiffness to the FULL local displacement
    // vector (plus the full FEF) for consistent end forces/moments.
    let mut member_end_forces_local = Vec::with_capacity(members.len());
    for rm in &reduced_members {
        let d_global_member = [
            d_full[rm.global_dof[0]],
            d_full[rm.global_dof[1]],
            d_full[rm.global_dof[2]],
            d_full[rm.global_dof[3]],
            d_full[rm.global_dof[4]],
            d_full[rm.global_dof[5]],
        ];
        let mut d_local_full = [0.0; 6];
        for &li in &rm.retained {
            let row = transform_row(li, rm.c, rm.s);
            let mut val = 0.0;
            for a in 0..6 {
                val += row[a] * d_global_member[a];
            }
            d_local_full[li] = val;
        }
        if !rm.condensed.is_empty() {
            // d_c = -Kcc^-1 * (Kcr * d_r + fef_c); recompute directly
            // via the retained-displacement vector d_r (in retained
            // order) since Kcc/Kcr aren't kept standalone above.
            let d_r: Vec<f64> = rm.retained.iter().map(|&li| d_local_full[li]).collect();
            let kcc: Vec<Vec<f64>> = rm
                .condensed
                .iter()
                .map(|&r| rm.condensed.iter().map(|&c| rm.k_full[r][c]).collect())
                .collect();
            let mut rhs: Vec<f64> = rm.condensed.iter().map(|&r| rm.fef_full[r]).collect();
            for (ci, &r) in rm.condensed.iter().enumerate() {
                let mut kcr_dr = 0.0;
                for (p, &rp) in rm.retained.iter().enumerate() {
                    kcr_dr += rm.k_full[r][rp] * d_r[p];
                }
                rhs[ci] += kcr_dr;
            }
            let neg_rhs: Vec<f64> = rhs.iter().map(|v| -v).collect();
            let d_c = solve_dense(kcc, neg_rhs)?;
            for (ci, &r) in rm.condensed.iter().enumerate() {
                d_local_full[r] = d_c[ci];
            }
        }
        let mut end_forces = [0.0; 6];
        for row in 0..6 {
            let mut val = rm.fef_full[row];
            for col in 0..6 {
                val += rm.k_full[row][col] * d_local_full[col];
            }
            end_forces[row] = val;
        }
        member_end_forces_local.push(end_forces);
    }

    Ok(FrameSolution {
        displacements,
        reactions,
        member_end_forces_local,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const TOL: f64 = 1e-3; // relative

    fn close(a: f64, b: f64, tol: f64) -> bool {
        if b.abs() < 1e-9 {
            (a - b).abs() < 1e-6
        } else {
            ((a - b) / b).abs() < tol
        }
    }

    /// Benchmarks memo 1.1: propped cantilever, uniform load.
    /// Fixed at A (node 0, x=0), roller at B (node 1, x=L).
    // frob:tests crates/feldspar-library/src/mech/frame.rs::frame2d_solve kind="unit"
    #[test]
    fn propped_cantilever_udl() {
        let w = 10e3; // N/m
        let l = 6.0; // m
        let ei = 6.0e7; // N m^2
        let ea = 1e12; // effectively rigid axially (irrelevant here)
                       // Equivalent nodal loads for a UDL on a beam element: FEF
                       // shear = wL/2 each end, FEF moment = +wL^2/12 at end 1,
                       // -wL^2/12 at end 2 (Hibbeler sign convention: local axes
                       // in-plane, load acting in -y).
        let fef = [
            0.0,
            w * l / 2.0,
            w * l * l / 12.0,
            0.0,
            w * l / 2.0,
            -w * l * l / 12.0,
        ];
        let members = [FrameMemberInput {
            i: 0,
            j: 1,
            dx: l,
            dy: 0.0,
            ea,
            ei,
            release_a_rz: false,
            release_b_rz: false,
            fef_local: fef,
        }];
        // node 0: fixed (x,y,rz); node 1: roller (y fixed only)
        let fixed = [true, true, true, false, true, false];
        let loads = [0.0; 6];
        let sol = frame2d_solve(2, &members, &fixed, &loads).unwrap();

        let r_a_y = sol.reactions[0][1];
        let r_b_y = sol.reactions[1][1];
        let m_a = sol.reactions[0][2];
        assert!(
            close(r_b_y, 3.0 * w * l / 8.0, TOL),
            "R_B={} expected {}",
            r_b_y,
            3.0 * w * l / 8.0
        );
        assert!(
            close(r_a_y, 5.0 * w * l / 8.0, TOL),
            "R_A={} expected {}",
            r_a_y,
            5.0 * w * l / 8.0
        );
        // Magnitude checked, not sign: this element's positive-moment
        // DOF convention is CCW-positive in the LOCAL stiffness basis,
        // not the "sagging positive" beam-theory convention the
        // benchmarks memo quotes -- the reaction magnitude is the
        // physically meaningful, convention-independent check.
        assert!(
            close(m_a.abs(), w * l * l / 8.0, TOL),
            "M_A={} expected magnitude {}",
            m_a,
            w * l * l / 8.0
        );
    }

    /// Benchmarks memo 1.5: fixed-fixed beam, central point load.
    /// Modeled as TWO elements meeting at midspan (node 1) so the
    /// point load lands on a node -- no FEF needed.
    #[test]
    fn fixed_fixed_beam_central_point_load() {
        let p = 30e3; // N
        let l = 4.0; // m
        let half = l / 2.0;
        let ei = 6.0e7;
        let ea = 1e12;
        let members = [
            FrameMemberInput {
                i: 0,
                j: 1,
                dx: half,
                dy: 0.0,
                ea,
                ei,
                release_a_rz: false,
                release_b_rz: false,
                fef_local: [0.0; 6],
            },
            FrameMemberInput {
                i: 1,
                j: 2,
                dx: half,
                dy: 0.0,
                ea,
                ei,
                release_a_rz: false,
                release_b_rz: false,
                fef_local: [0.0; 6],
            },
        ];
        let fixed = [true, true, true, false, false, false, true, true, true];
        let mut loads = [0.0; 9];
        loads[4] = -p; // downward point load at midspan node, y-dof
        let sol = frame2d_solve(3, &members, &fixed, &loads).unwrap();

        let r_a_y = sol.reactions[0][1];
        let r_c_y = sol.reactions[2][1];
        let m_a = sol.reactions[0][2];
        let m_c = sol.reactions[2][2];
        assert!(close(r_a_y, p / 2.0, TOL));
        assert!(close(r_c_y, p / 2.0, TOL));
        assert!(close(m_a.abs(), p * l / 8.0, TOL));
        assert!(close(m_c.abs(), p * l / 8.0, TOL));

        let d_mid_y = sol.displacements[1][1];
        let expected = p * l.powi(3) / (192.0 * ei);
        assert!(
            close(d_mid_y.abs(), expected, 5e-3),
            "d_mid={} expected {}",
            d_mid_y.abs(),
            expected
        );
    }

    /// Benchmarks memo 1.3: two-span continuous beam, uniform load,
    /// simple supports at both ends and midspan.
    #[test]
    fn two_span_continuous_beam_udl() {
        let w = 12e3;
        let l = 5.0;
        let ei = 6.0e7;
        let ea = 1e12;
        let fef = [
            0.0,
            w * l / 2.0,
            w * l * l / 12.0,
            0.0,
            w * l / 2.0,
            -w * l * l / 12.0,
        ];
        let members = [
            FrameMemberInput {
                i: 0,
                j: 1,
                dx: l,
                dy: 0.0,
                ea,
                ei,
                release_a_rz: false,
                release_b_rz: false,
                fef_local: fef,
            },
            FrameMemberInput {
                i: 1,
                j: 2,
                dx: l,
                dy: 0.0,
                ea,
                ei,
                release_a_rz: false,
                release_b_rz: false,
                fef_local: fef,
            },
        ];
        // Simple supports: y fixed at all three nodes, rz free
        // everywhere (pin/roller chain); node A additionally pinned in
        // x (one horizontal restraint is required or the chain is a
        // rigid-body mechanism in x -- a real support requirement, not
        // a solver artifact).
        let fixed = [true, true, false, false, true, false, false, true, false];
        let loads = [0.0; 9];
        let sol = frame2d_solve(3, &members, &fixed, &loads).unwrap();

        let r_a = sol.reactions[0][1];
        let r_b = sol.reactions[1][1];
        let r_c = sol.reactions[2][1];
        assert!(close(r_a, 0.375 * w * l, TOL), "R_A={}", r_a);
        assert!(close(r_c, 0.375 * w * l, TOL), "R_C={}", r_c);
        assert!(close(r_b, 1.25 * w * l, TOL), "R_B={}", r_b);
    }

    #[test]
    fn degenerate_member_is_an_error() {
        let members = [FrameMemberInput {
            i: 0,
            j: 1,
            dx: 0.0,
            dy: 0.0,
            ea: 1.0,
            ei: 1.0,
            release_a_rz: false,
            release_b_rz: false,
            fef_local: [0.0; 6],
        }];
        let fixed = [true, true, true, true, true, true];
        let loads = [0.0; 6];
        assert_eq!(
            frame2d_solve(2, &members, &fixed, &loads).unwrap_err(),
            FrameError::DegenerateMember(0)
        );
    }

    /// A hinge (hinged member end) reproduces a simple beam's zero
    /// moment condition at the released end: a single-span member with
    /// a moment release at node j and a UDL should carry zero moment
    /// at that end even though it is otherwise assembled like a
    /// continuous member.
    #[test]
    fn hinge_release_carries_zero_moment_at_released_end() {
        let w = 8e3;
        let l = 5.0;
        let ei = 6.0e7;
        let ea = 1e12;
        let fef = [
            0.0,
            w * l / 2.0,
            -w * l * l / 12.0,
            0.0,
            w * l / 2.0,
            w * l * l / 12.0,
        ];
        let members = [FrameMemberInput {
            i: 0,
            j: 1,
            dx: l,
            dy: 0.0,
            ea,
            ei,
            release_a_rz: false,
            release_b_rz: true,
            fef_local: fef,
        }];
        // Node 1's rz DOF must be marked `fixed` here even though
        // nothing physically restrains it: with the member's b-end
        // moment released and no other member framing into node 1,
        // that global rotation carries ZERO stiffness from anywhere
        // (a real decoupled mechanism, not a solver artifact) -- an
        // unrestrained zero-stiffness DOF makes the free-DOF partition
        // singular. Excluding it from the solve (prescribing 0, which
        // is never read back since the actual hinge rotation is
        // recovered separately via condensation) is the correct way to
        // model a hinge whose far side has no other connection.
        let fixed = [true, true, true, false, true, true];
        let loads = [0.0; 6];
        let sol = frame2d_solve(2, &members, &fixed, &loads).unwrap();
        let m_b_local = sol.member_end_forces_local[0][5];
        assert!(m_b_local.abs() < 1e-3, "released-end moment={}", m_b_local);
    }
}
