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
use crate::symbolic::{differentiate, EvalError, Expr};

/// One propagation protocol behind every uncertainty representation (02
/// "Values are uncertain"): `Interval` (v1, the only strategy
/// implemented in M1) now, `Normal`/`Quantile` at later milestones.
/// `to_interval()` is the one lossy collapse every representation must
/// offer, because the regolith boundary and the margin rule always
/// speak intervals (02) -- a future representation is a new `impl`,
/// never a second dispatch path.
// frob:doc docs/modules/feldspar-core.md#core_propagation
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
// frob:doc docs/modules/feldspar-core.md#core_propagation
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
// frob:doc docs/modules/feldspar-core.md#core_propagation
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

/// WO-15 (09 sec. 6): the fold-only half of `corner_sweep`, split out so
/// a caller can evaluate `enumerate_corners(box_)` OFF the hot fold path
/// -- in particular, in parallel (rayon, a thread pool, or a Python-side
/// `concurrent.futures` dispatch when `eval` is a GIL-bound callback,
/// see `feldspar.plan.parallel`) -- and then hull the results here.
///
/// `results` MUST be the per-corner outputs in the SAME order as
/// `enumerate_corners(box_)` produced them (the caller's responsibility;
/// this function has no `box_` to re-derive that order from). Determinism
/// (FINV-9) holds independent of how `results` was PRODUCED (any thread
/// count, any completion order) because the fold itself is `Interval::hull`
/// (elementwise min/max), which is commutative and associative over a
/// FIXED finite multiset of finite values -- only the multiset (not the
/// arrival order) can affect the outcome, and `results`'s order here is
/// always the same corner order regardless of how it was computed.
///
/// Panics under the same caller contract as `corner_sweep`: every value
/// in `results` is assumed finite.
// frob:doc docs/modules/feldspar-core.md#core_propagation
pub fn hull_from_results(results: &[BTreeMap<String, f64>]) -> BTreeMap<String, Interval> {
    let mut hull: BTreeMap<String, Interval> = BTreeMap::new();
    for outputs in results {
        for (port, value) in outputs {
            let point = Interval::point(*value)
                .expect("hull_from_results's caller contract: values are always finite");
            hull.entry(port.clone())
                .and_modify(|existing| *existing = existing.hull(&point))
                .or_insert(point);
        }
    }
    hull
}

/// `[lo - eps, hi + eps]`; THE accumulation primitive (02, audit A-1),
/// applied to every consumed intermediate port before the consuming
/// step's sweep and domain checks (02-edge-cases WO-04: "inflate() then
/// domain check -> subset rule applies to the INFLATED interval").
/// Constructs the result directly (like `Accuracy`'s derived
/// arithmetic): `eps` is a solver-declared non-negative model error, not
/// untrusted literal data, so this is not a checked `Result` path.
// frob:doc docs/modules/feldspar-core.md#core_propagation
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
// frob:doc docs/modules/feldspar-core.md#core_propagation
pub fn total_error(out_hull: Interval, model_eps: f64) -> f64 {
    out_hull.half_width() + model_eps
}

/// The `Normal` (mean + standard deviation) uncertainty representation
/// (02 "Values are uncertain": "Normal ... first-order (delta-method)
/// propagation ... Planned, not v1"; landed here, WO-22, R4). Frozen,
/// `stddev >= 0`.
// frob:doc docs/modules/feldspar-core.md#core_propagation
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Normal {
    pub mean: f64,
    pub stddev: f64,
}

/// The conservative multiplier `Normal::to_interval` widens by (02:
/// "Each MUST implement a conservative `to_interval()` collapse ...
/// explicit in the API and logged when it happens"). 3 standard
/// deviations is the documented, fixed choice -- changing it is a
/// visible, versioned event exactly like a `CANON_VERSION` bump, not a
/// silent tuning knob.
// frob:doc docs/modules/feldspar-core.md#core_propagation
pub const NORMAL_TO_INTERVAL_SIGMA: f64 = 3.0;

impl Propagation for Normal {
    /// `[mean - k*stddev, mean + k*stddev]` (k = `NORMAL_TO_INTERVAL_SIGMA`):
    /// the one lossy, explicit collapse every representation must offer
    /// (02) so the pack boundary and margin rule always see an interval.
    fn to_interval(&self) -> Interval {
        let half = NORMAL_TO_INTERVAL_SIGMA * self.stddev;
        Interval {
            lo: self.mean - half,
            hi: self.mean + half,
        }
    }
}

/// A numeric step evaluation callback: `inputs -> Result<f64, EvalError>`
/// (named per clippy `type_complexity` -- this exact shape recurs across
/// `DerivativeMode::Numeric` and its callers).
// frob:doc docs/modules/feldspar-core.md#core_propagation
pub type NumericEval<'a> = dyn Fn(&BTreeMap<String, f64>) -> Result<f64, EvalError> + 'a;

/// Which source a step's partial derivative comes from (11 sec. 4 R4):
/// `Symbolic` when the step's law is a symbolic `Relation` (kernel
/// differentiation over the canonical AST), `Numeric` otherwise
/// (deterministic central finite difference over the step's compiled
/// eval). Chosen PER STEP, never per solve -- the one `Propagation`
/// protocol, not a second dispatch path.
// frob:doc docs/modules/feldspar-core.md#core_propagation
pub enum DerivativeMode<'a> {
    /// Differentiate `expr` symbolically and evaluate the derivative at
    /// `inputs` (exact, up to the underlying law's own accuracy band).
    Symbolic { expr: &'a Expr },
    /// Deterministic central finite difference of `eval` around
    /// `inputs`, step size `h` (the pre-existing numeric path: no
    /// symbolic law is declared for this step).
    Numeric { eval: &'a NumericEval<'a>, h: f64 },
}

/// One input port's contribution to a delta-method propagation: its
/// `Normal` uncertainty and which derivative source to use for it.
// frob:doc docs/modules/feldspar-core.md#core_propagation
pub struct DeltaInput<'a> {
    pub port: String,
    pub value: Normal,
    pub mode: DerivativeMode<'a>,
}

/// The partial derivative of one step w.r.t. one input port (11 sec. 4
/// R4): symbolic (kernel `differentiate` + `eval`) or numeric (central
/// finite difference), per the caller's chosen `DerivativeMode` for
/// that port. Both branches share the exact same `inputs` point so the
/// two modes are directly comparable (the determinism/agreement suite,
/// WO-22 acceptance).
fn partial_derivative(
    mode: &DerivativeMode<'_>,
    port: &str,
    inputs: &BTreeMap<String, f64>,
) -> Result<f64, EvalError> {
    match mode {
        DerivativeMode::Symbolic { expr } => {
            let d_expr = differentiate(expr, port);
            d_expr.eval(inputs)
        }
        DerivativeMode::Numeric { eval, h } => {
            let mut plus = inputs.clone();
            let mut minus = inputs.clone();
            *plus.get_mut(port).expect("port present in inputs") += h;
            *minus.get_mut(port).expect("port present in inputs") -= h;
            let f_plus = eval(&plus)?;
            let f_minus = eval(&minus)?;
            Ok((f_plus - f_minus) / (2.0 * h))
        }
    }
}

/// First-order (delta-method) `Normal` propagation through one step (02
/// "Normal ... first-order (delta-method) propagation via
/// differentiation of the solver"; 11 sec. 4 R4). The output mean is
/// `eval` at the input means; the output standard deviation is the
/// standard linearized combination `sqrt(sum((d(step)/d(port) *
/// stddev_port)^2))` over every `DeltaInput`, each port's partial taken
/// via ITS OWN chosen `DerivativeMode` (symbolic where the step's law is
/// a `Relation`, numeric otherwise -- mixed per step is fine; the
/// combination formula does not care which source produced a given
/// partial). `eval` computes the step's OWN output (used for the mean);
/// callers needing a symbolic mean should pass an `eval` that simply
/// calls `Expr::eval`.
// frob:doc docs/modules/feldspar-core.md#core_propagation
pub fn delta_propagate(
    inputs: &[DeltaInput<'_>],
    eval: impl Fn(&BTreeMap<String, f64>) -> Result<f64, EvalError>,
) -> Result<Normal, EvalError> {
    let mean_point: BTreeMap<String, f64> = inputs
        .iter()
        .map(|i| (i.port.clone(), i.value.mean))
        .collect();
    let mean = eval(&mean_point)?;

    let mut variance = 0.0_f64;
    for input in inputs {
        let partial = partial_derivative(&input.mode, &input.port, &mean_point)?;
        let term = partial * input.value.stddev;
        variance += term * term;
    }
    Ok(Normal {
        mean,
        stddev: variance.sqrt(),
    })
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
    fn hull_from_results_matches_corner_sweep_regardless_of_result_order() {
        // WO-15 (09 sec. 6) determinism proof: `hull_from_results` folding
        // the SAME per-corner outputs in a SHUFFLED order (standing in for
        // "any thread count/completion order") must still match
        // `corner_sweep`'s serial, corner-ordered result byte-for-byte --
        // the fold (elementwise min/max) is commutative/associative over a
        // fixed finite multiset of finite values.
        let mut box_ = BTreeMap::new();
        box_.insert("a".to_string(), iv(0.0, 1.0));
        box_.insert("b".to_string(), iv(-2.0, 3.0));

        let serial = corner_sweep(&box_, |corner| {
            let mut out = BTreeMap::new();
            out.insert("y".to_string(), corner["a"] + corner["b"]);
            out.insert("z".to_string(), corner["a"] * corner["b"]);
            Ok::<_, ()>(out)
        })
        .unwrap();

        let corners = enumerate_corners(&box_);
        let mut results: Vec<BTreeMap<String, f64>> = corners
            .iter()
            .map(|corner| {
                let mut out = BTreeMap::new();
                out.insert("y".to_string(), corner["a"] + corner["b"]);
                out.insert("z".to_string(), corner["a"] * corner["b"]);
                out
            })
            .collect();
        // Reverse to simulate arrival in a different (e.g. worker-thread
        // completion) order than `enumerate_corners` produced them.
        results.reverse();
        let parallel_like = hull_from_results(&results);

        assert_eq!(serial, parallel_like);
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

    fn orifice_rhs() -> Expr {
        // Q = C_d * A * sqrt(2 * dp / rho).
        Expr::Mul(vec![
            Expr::Var("C_d".into()),
            Expr::Var("A".into()),
            Expr::Unary(
                crate::symbolic::UnaryFn::Sqrt,
                Box::new(Expr::Mul(vec![
                    Expr::Lit(2.0),
                    Expr::Var("dp".into()),
                    Expr::Pow(Box::new(Expr::Var("rho".into())), Box::new(Expr::Lit(-1.0))),
                ])),
            ),
        ])
    }

    fn orifice_inputs(rhs: &Expr) -> Vec<DeltaInput<'_>> {
        vec![
            DeltaInput {
                port: "C_d".to_string(),
                value: Normal {
                    mean: 0.62,
                    stddev: 0.01,
                },
                mode: DerivativeMode::Symbolic { expr: rhs },
            },
            DeltaInput {
                port: "A".to_string(),
                value: Normal {
                    mean: 0.002,
                    stddev: 0.0001,
                },
                mode: DerivativeMode::Symbolic { expr: rhs },
            },
            DeltaInput {
                port: "dp".to_string(),
                value: Normal {
                    mean: 5000.0,
                    stddev: 50.0,
                },
                mode: DerivativeMode::Symbolic { expr: rhs },
            },
            DeltaInput {
                port: "rho".to_string(),
                value: Normal {
                    mean: 1000.0,
                    stddev: 2.0,
                },
                mode: DerivativeMode::Symbolic { expr: rhs },
            },
        ]
    }

    #[test]
    fn normal_to_interval_is_conservative_three_sigma() {
        let n = Normal {
            mean: 10.0,
            stddev: 2.0,
        };
        let iv = n.to_interval();
        assert_eq!(iv, Interval::new(4.0, 16.0).unwrap());
    }

    #[test]
    fn delta_propagate_symbolic_mode_is_deterministic() {
        let rhs = orifice_rhs();
        let inputs = orifice_inputs(&rhs);
        let eval_fn = |pt: &BTreeMap<String, f64>| rhs.eval(pt);

        let run1 = delta_propagate(&inputs, eval_fn).unwrap();
        let inputs2 = orifice_inputs(&rhs);
        let run2 = delta_propagate(&inputs2, eval_fn).unwrap();

        assert_eq!(run1.mean, run2.mean);
        assert_eq!(run1.stddev, run2.stddev);
    }

    #[test]
    fn delta_propagate_symbolic_and_numeric_modes_agree() {
        let rhs = orifice_rhs();
        let eval_fn = |pt: &BTreeMap<String, f64>| rhs.eval(pt);

        let symbolic_inputs = orifice_inputs(&rhs);
        let symbolic = delta_propagate(&symbolic_inputs, eval_fn).unwrap();

        let numeric_inputs = vec![
            DeltaInput {
                port: "C_d".to_string(),
                value: Normal {
                    mean: 0.62,
                    stddev: 0.01,
                },
                mode: DerivativeMode::Numeric {
                    eval: &eval_fn,
                    h: 1e-5,
                },
            },
            DeltaInput {
                port: "A".to_string(),
                value: Normal {
                    mean: 0.002,
                    stddev: 0.0001,
                },
                mode: DerivativeMode::Numeric {
                    eval: &eval_fn,
                    h: 1e-7,
                },
            },
            DeltaInput {
                port: "dp".to_string(),
                value: Normal {
                    mean: 5000.0,
                    stddev: 50.0,
                },
                mode: DerivativeMode::Numeric {
                    eval: &eval_fn,
                    h: 1e-2,
                },
            },
            DeltaInput {
                port: "rho".to_string(),
                value: Normal {
                    mean: 1000.0,
                    stddev: 2.0,
                },
                mode: DerivativeMode::Numeric {
                    eval: &eval_fn,
                    h: 1e-2,
                },
            },
        ];
        let numeric = delta_propagate(&numeric_inputs, eval_fn).unwrap();

        assert_eq!(symbolic.mean, numeric.mean); // same mean eval either way
        let rel_diff = (symbolic.stddev - numeric.stddev).abs() / symbolic.stddev;
        assert!(
            rel_diff < 1e-4,
            "symbolic stddev={} numeric stddev={}",
            symbolic.stddev,
            numeric.stddev
        );
    }

    #[test]
    fn delta_propagate_mixed_modes_per_input() {
        // A step may pick symbolic for one port and numeric for another
        // (11 sec. 4: "mode chosen per step" -- per-input here is the
        // finer-grained analogue, and the combination formula does not
        // care which source produced a given partial).
        let rhs = orifice_rhs();
        let eval_fn = |pt: &BTreeMap<String, f64>| rhs.eval(pt);
        let inputs = vec![
            DeltaInput {
                port: "C_d".to_string(),
                value: Normal {
                    mean: 0.62,
                    stddev: 0.01,
                },
                mode: DerivativeMode::Symbolic { expr: &rhs },
            },
            DeltaInput {
                port: "A".to_string(),
                value: Normal {
                    mean: 0.002,
                    stddev: 0.0001,
                },
                mode: DerivativeMode::Numeric {
                    eval: &eval_fn,
                    h: 1e-7,
                },
            },
            DeltaInput {
                port: "dp".to_string(),
                value: Normal {
                    mean: 5000.0,
                    stddev: 50.0,
                },
                mode: DerivativeMode::Symbolic { expr: &rhs },
            },
            DeltaInput {
                port: "rho".to_string(),
                value: Normal {
                    mean: 1000.0,
                    stddev: 2.0,
                },
                mode: DerivativeMode::Numeric {
                    eval: &eval_fn,
                    h: 1e-2,
                },
            },
        ];
        let result = delta_propagate(&inputs, eval_fn).unwrap();
        assert!(result.stddev > 0.0);
        assert!(result.mean.is_finite());
    }
}
