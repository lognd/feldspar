//! The ONE corner-sweep and accumulation-rule home (FINV-4, audit A-1):
//! shared verbatim by planner estimates (WO-05) and executor exact
//! sweeps (WO-06) via PyO3 (`corner_sweep`, `inflate`, `total_error`).
//!
//! 02 "The error split": input uncertainty is propagated by evaluating
//! a solver at every corner of its input box and hulling the results;
//! model error is a separate, solver-declared `Accuracy` ceiling.
//! Accumulation along a route is BY INFLATION (`inflate`), never by
//! summing eps scalars -- summing is unsound the instant a step's gain
//! differs from 1 (`y = 1000*x` turns an upstream eps of 0.1 into 100;
//! a sum reports ~0.1). `total_error` is the budget-checked quantity at
//! a target: propagated half-width (which, under inflation, already
//! carries every upstream eps through the route's real sensitivities)
//! plus the FINAL step's own model eps.

use std::collections::BTreeMap;

use crate::interval::Interval;

/// One propagation protocol behind every uncertainty representation (02
/// "Values are uncertain"): `Interval` (v1, the only strategy
/// implemented in M1) now, `Normal`/`Quantile` at later milestones.
/// `to_interval()` is the one lossy collapse every representation must
/// offer, because the regolith boundary and the margin rule always
/// speak intervals (02) -- a future representation is a new `impl`,
/// never a second dispatch path.
pub trait Propagation {
    /// The (possibly lossy) collapse to the pack-boundary `Interval`
    /// representation. Identity for `Interval` itself.
    fn to_interval(&self) -> Interval;
}

impl Propagation for Interval {
    fn to_interval(&self) -> Interval {
        *self
    }
}

/// The deduplicated candidate values a port contributes to the corner
/// product: one value for a degenerate (point) interval, two otherwise.
/// This is what makes `enumerate_corners` naturally dedup (02-edge-cases
/// WO-04: "3 interval inputs, 1 degenerate -> 4 corners after dedup")
/// without a separate post-hoc dedup pass.
fn corner_candidates(iv: &Interval) -> [f64; 2] {
    [iv.lo, iv.hi]
}

/// Deterministic, deduplicated, sorted corner enumeration over a box of
/// named intervals: the cartesian product of each port's candidate
/// values (1 for degenerate, 2 otherwise), sorted lexicographically by
/// value in port-name order (BTreeMap's key order) so serial and future
/// parallel (M5, AD-10) assembly are bit-identical (FINV-1/FINV-9).
pub fn enumerate_corners(box_: &BTreeMap<String, Interval>) -> Vec<BTreeMap<String, f64>> {
    let ports: Vec<&String> = box_.keys().collect();
    let mut corners: Vec<BTreeMap<String, f64>> = vec![BTreeMap::new()];
    for port in ports {
        let iv = &box_[port];
        let candidates = corner_candidates(iv);
        let deduped: &[f64] = if candidates[0] == candidates[1] {
            &candidates[..1]
        } else {
            &candidates[..]
        };
        let mut next = Vec::with_capacity(corners.len() * deduped.len());
        for corner in &corners {
            for &v in deduped {
                let mut c = corner.clone();
                c.insert(port.clone(), v);
                next.push(c);
            }
        }
        corners = next;
    }
    corners.sort_by(|a, b| {
        for (av, bv) in a.values().zip(b.values()) {
            match av
                .partial_cmp(bv)
                .expect("corner values come from finite Interval bounds; never NaN")
            {
                std::cmp::Ordering::Equal => continue,
                other => return other,
            }
        }
        std::cmp::Ordering::Equal
    });
    corners
}

/// Evaluates `eval` at every deduplicated, sorted corner of `box_` and
/// hulls the per-port results (02 "input uncertainty ... propagated by
/// the ENGINE"). Short-circuits on the first `Err`, exactly like a
/// route step whose corner-sweep fails outright (02-edge-cases WO-04:
/// "solver Err at one corner -> whole sweep Err").
///
/// Corner-monotonicity is NOT checked here: the sweep always runs
/// regardless of a solver's declared `corner_monotone` flag (03); a
/// non-monotone solver's obligation to widen its declared `Accuracy` to
/// cover interior extrema is the SOLVER's contract (02), not something
/// this function can verify from corner samples alone
/// (02-edge-cases WO-04: "non-monotone flag set -> sweep still runs").
///
/// Callers are responsible for inflating any CONSUMED intermediate
/// port's interval by its producing step's model eps (via `inflate`)
/// before calling this -- `corner_sweep` itself has no notion of
/// "upstream" or "producing step"; it only evaluates the box it is
/// given (02, audit A-1).
///
/// `eval`'s `Ok` values are assumed finite (NaN rejection is an
/// EXECUTOR-level concern, WO-06's `SolveError::NonFinite`, wired
/// above this layer) -- constructing a degenerate `Interval` from a
/// non-finite value here would be a caller contract violation, not a
/// recoverable condition this function should paper over.
pub fn corner_sweep<E>(
    box_: &BTreeMap<String, Interval>,
    mut eval: impl FnMut(&BTreeMap<String, f64>) -> Result<BTreeMap<String, f64>, E>,
) -> Result<BTreeMap<String, Interval>, E> {
    let corners = enumerate_corners(box_);
    let mut hull: BTreeMap<String, Interval> = BTreeMap::new();
    for corner in &corners {
        let outputs = eval(corner)?;
        for (port, value) in outputs {
            let point = Interval::point(value)
                .expect("corner_sweep's eval contract: Ok values are always finite");
            hull.entry(port)
                .and_modify(|existing| *existing = existing.hull(&point))
                .or_insert(point);
        }
    }
    Ok(hull)
}

/// `[lo - eps, hi + eps]`; THE accumulation primitive (02, audit A-1),
/// applied to every consumed intermediate port before the consuming
/// step's sweep and domain checks (02-edge-cases WO-04: "inflate() then
/// domain check -> subset rule applies to the INFLATED interval").
/// Constructs the result directly (like `Accuracy`'s derived
/// arithmetic): `eps` is a solver-declared non-negative model error, not
/// untrusted literal data, so this is not a checked `Result` path.
pub fn inflate(iv: Interval, eps: f64) -> Interval {
    Interval {
        lo: iv.lo - eps,
        hi: iv.hi + eps,
    }
}

/// `half_width(out_hull) + model_eps`: the budget-checked total
/// worst-case error at a route's target (02). `model_eps` is the FINAL
/// step's own declared/measured model error; every upstream step's
/// error already rides in `out_hull`'s width via `inflate` at each
/// consuming step -- summing eps scalars along the route is exactly
/// the unsound shortcut this function replaces (audit A-1).
pub fn total_error(out_hull: Interval, model_eps: f64) -> f64 {
    out_hull.half_width() + model_eps
}

#[cfg(test)]
mod tests {
    use super::*;

    fn iv(lo: f64, hi: f64) -> Interval {
        Interval::new(lo, hi).unwrap()
    }

    #[test]
    fn three_inputs_one_degenerate_yields_four_corners() {
        let mut box_ = BTreeMap::new();
        box_.insert("a".to_string(), iv(0.0, 1.0));
        box_.insert("b".to_string(), iv(0.0, 1.0));
        box_.insert("c".to_string(), iv(5.0, 5.0)); // degenerate
        let corners = enumerate_corners(&box_);
        assert_eq!(corners.len(), 4);
        // sorted, deterministic
        let mut sorted_copy = corners.clone();
        sorted_copy.sort_by(|a, b| {
            a.values()
                .zip(b.values())
                .find_map(|(x, y)| {
                    let o = x.partial_cmp(y).unwrap();
                    (o != std::cmp::Ordering::Equal).then_some(o)
                })
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        assert_eq!(corners, sorted_copy);
    }

    #[test]
    fn all_degenerate_box_is_one_corner_equal_to_single_evaluation() {
        let mut box_ = BTreeMap::new();
        box_.insert("a".to_string(), iv(2.0, 2.0));
        box_.insert("b".to_string(), iv(3.0, 3.0));
        let corners = enumerate_corners(&box_);
        assert_eq!(corners.len(), 1);
        assert_eq!(corners[0]["a"], 2.0);
        assert_eq!(corners[0]["b"], 3.0);
    }

    #[test]
    fn eight_corners_for_three_non_degenerate_inputs() {
        let mut box_ = BTreeMap::new();
        box_.insert("a".to_string(), iv(0.0, 1.0));
        box_.insert("b".to_string(), iv(-1.0, 1.0));
        box_.insert("c".to_string(), iv(10.0, 20.0));
        assert_eq!(enumerate_corners(&box_).len(), 8);
    }

    #[test]
    fn corner_sweep_err_at_one_corner_fails_whole_sweep() {
        let mut box_ = BTreeMap::new();
        box_.insert("a".to_string(), iv(0.0, 1.0));
        let result: Result<BTreeMap<String, Interval>, &str> = corner_sweep(&box_, |corner| {
            if corner["a"] == 1.0 {
                Err("boom at a=1.0")
            } else {
                let mut out = BTreeMap::new();
                out.insert("y".to_string(), corner["a"]);
                Ok(out)
            }
        });
        assert_eq!(result, Err("boom at a=1.0"));
    }

    #[test]
    fn corner_sweep_hulls_a_linear_map() {
        let mut box_ = BTreeMap::new();
        box_.insert("x".to_string(), iv(2.0, 5.0));
        let result = corner_sweep(&box_, |corner| {
            let mut out = BTreeMap::new();
            out.insert("y".to_string(), 3.0 * corner["x"]);
            Ok::<_, ()>(out)
        })
        .unwrap();
        assert_eq!(result["y"], iv(6.0, 15.0));
    }

    #[test]
    fn inflate_widens_both_bounds_by_eps() {
        let widened = inflate(iv(1.0, 2.0), 0.5);
        assert_eq!(widened, iv(0.5, 2.5));
    }

    #[test]
    fn total_error_is_half_width_plus_model_eps() {
        assert_eq!(total_error(iv(0.0, 4.0), 0.25), 2.25);
    }

    #[test]
    fn accumulation_with_eps_zero_point_inputs_is_zero_exactly() {
        let mut box_ = BTreeMap::new();
        box_.insert("x".to_string(), iv(3.0, 3.0));
        let hull = corner_sweep(&box_, |corner| {
            let mut out = BTreeMap::new();
            out.insert("y".to_string(), corner["x"] * 2.0);
            Ok::<_, ()>(out)
        })
        .unwrap();
        assert_eq!(total_error(hull["y"], 0.0), 0.0);
    }

    /// The audit A-1 gain-counterexample (02-edge-cases WO-04): a
    /// step-2 gain `k` consuming step-1's output (carrying eps `e`)
    /// must see the target error track ~k*e via inflation, NOT ~e (the
    /// unsound summation result).
    #[test]
    fn gain_counterexample_tracks_k_times_e_not_e() {
        let e = 0.1_f64;
        let k = 1000.0_f64;
        let step1_point = iv(5.0, 5.0); // step 1's exact point output

        // Consuming step inflates the upstream interval by the
        // producing step's eps BEFORE sweeping (audit A-1 protocol).
        let inflated = inflate(step1_point, e);
        assert_eq!(inflated, iv(5.0 - e, 5.0 + e));

        let mut box_ = BTreeMap::new();
        box_.insert("x".to_string(), inflated);
        let hull = corner_sweep(&box_, |corner| {
            let mut out = BTreeMap::new();
            out.insert("y".to_string(), k * corner["x"]);
            Ok::<_, ()>(out)
        })
        .unwrap();

        let target_error = total_error(hull["y"], 0.0);
        // ~k*e, emphatically not ~e:
        assert!((target_error - k * e).abs() < 1e-9);
        assert!((target_error - e).abs() > 1.0); // nowhere near the unsound ~e answer
    }
}
