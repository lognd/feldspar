//! Planner search (WO-05, 04-routing): deterministic forward AND-graph
//! search from known ports to a target port, minimizing cost subject to
//! domain validity and an eps budget (FINV-1/5/8).
//!
//! **M1 estimation convention** (spec 04 says expansion "executes
//! nothing" and estimates from hull corners, but a `SolverInfo` snapshot
//! carries no executable formula -- only `Domain`, `Accuracy`, and
//! `cost` -- and search never calls back into Python): a step's output
//! value at each corner is estimated as the SUM of that corner's input
//! values, then hulled via `corner_sweep` exactly like the executor
//! will later hull the REAL sweep (FINV-4: same core routine, hull
//! corners). This is a documented placeholder magnitude used only to
//! drive route SELECTION (domain admission on inflated hulls, and the
//! declared `Accuracy.worst_over` eps estimate) -- WO-06's executor
//! replaces it with the real `SolveFn` sweep before anything is
//! reported to a caller as a `Solution`.
//!
//! **Cost accounting**: the frontier's per-label `cost` is an additive
//! upper bound (own cost + each chosen input label's cost) used purely
//! to prioritize expansion in a diamond-free registry (07: "real
//! registries are small and layered"); a route sharing one ancestor
//! step across two input branches would double-count that ancestor's
//! cost in intermediate label costs. `Route.total_cost` does NOT
//! inherit this: it is computed after search, by walking the winning
//! label's step tree and summing each DISTINCT step exactly once
//! (`walk_route`), so the reported total is always correct even if the
//! search heuristic over-counted while comparing candidates.

use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet, HashSet};
use std::rc::Rc;

use crate::digest::canonical_digest;
use crate::domain::Domain;
use crate::interval::Interval;
use crate::propagation::{corner_sweep, inflate, total_error};
use crate::Accuracy;

use serde::Serialize;

/// Which one-sided claim(s) a solver is conservative for (03 `ClaimSenses`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Sense {
    Upper,
    Lower,
    Both,
}

impl Sense {
    /// Case-insensitive parse of the Python-side `ClaimSenses` value
    /// (`"upper"`/`"lower"`/`"both"`); an unrecognized string is a
    /// caller contract bug (the Python facade only ever sends these
    /// three), so this panics rather than returning a `Result`.
    pub fn parse(s: &str) -> Self {
        match s.to_ascii_lowercase().as_str() {
            "upper" => Sense::Upper,
            "lower" => Sense::Lower,
            "both" => Sense::Both,
            other => panic!("unknown ClaimSenses value: {other}"),
        }
    }
}

/// A frozen, marshalled snapshot of one registered solver's planning-
/// relevant metadata (01-interfaces `SolverInfo`, minus everything the
/// search never reads -- notably `tier`, which FINV-8 forbids the
/// search from touching at all).
#[derive(Debug, Clone)]
pub struct SolverSummary {
    pub solver_id: String,
    pub inputs: Vec<String>,
    pub outputs: Vec<String>,
    pub domain: Domain,
    pub cost: f64,
    pub accuracy: BTreeMap<String, Accuracy>,
    pub conservative_for: Sense,
}

/// The planner's total error union (01-interfaces `PlanError`, FINV-5).
#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum PlanError {
    #[error("eps_budget must be > 0 and finite")]
    InvalidBudget,
    #[error("target port `{0}` is not known and no solver produces it")]
    UnknownTarget(String),
    #[error("no admissible route reaches the target port")]
    NoApplicableSolver,
    #[error("target reachable but not within the eps budget (best found: {best_eps})")]
    BudgetUnreachable { best_eps: f64 },
    #[error("cyclic port equivalence detected among single-input/single-output solvers")]
    CyclicPortEquivalence,
}

/// One committed step in a `Route` (01-interfaces `RouteStep`).
#[derive(Debug, Clone, Serialize)]
pub struct RouteStep {
    pub solver_id: String,
    pub realized_domain: SerDomain,
    pub predicted_eps: f64,
    pub cost: f64,
}

/// A digestible mirror of `Domain` (`Domain` itself has no `Serialize`
/// impl; adding one just for the route digest would reach outside this
/// module's business, so the route keeps its own small serializable
/// shape instead).
#[derive(Debug, Clone, Serialize)]
pub struct SerDomain {
    pub port_box: BTreeMap<String, (f64, f64)>,
    pub tags: BTreeSet<String>,
}

impl From<&Domain> for SerDomain {
    fn from(d: &Domain) -> Self {
        SerDomain {
            port_box: d
                .port_box
                .iter()
                .map(|(k, v)| (k.clone(), (v.lo, v.hi)))
                .collect(),
            tags: d.tags.clone(),
        }
    }
}

/// The ordered result of a successful `plan()` (01-interfaces `Route`,
/// AD-5 digest convention).
#[derive(Debug, Clone, Serialize)]
pub struct Route {
    pub target: String,
    pub steps: Vec<RouteStep>,
    pub predicted_eps: f64,
    pub total_cost: f64,
    pub digest: String,
}

/// Digest input mirror of `Route` MINUS the digest field itself (AD-5:
/// a digest can't include itself).
#[derive(Serialize)]
struct RouteDigestInput<'a> {
    target: &'a str,
    steps: &'a [RouteStep],
    predicted_eps: f64,
    total_cost: f64,
}

fn route_digest(target: &str, steps: &[RouteStep], predicted_eps: f64, total_cost: f64) -> String {
    canonical_digest(&RouteDigestInput {
        target,
        steps,
        predicted_eps,
        total_cost,
    })
}

/// One committed application of a solver: shared (via `Rc`) by every
/// output-port `Label` it produced, so route reconstruction can walk
/// backward from the target and dedupe a step that fed two branches.
struct StepNode {
    solver_id: String,
    own_cost: f64,
    tags: BTreeSet<String>,
    inputs: BTreeMap<String, Label>,
    outputs: BTreeMap<String, (Interval, f64)>,
}

/// An achieved port label: (interval, producing step's own model eps,
/// additive cost-so-far heuristic, producing step) -- 04's "achieved-
/// port labels".
#[derive(Clone)]
struct Label {
    interval: Interval,
    eps: f64,
    cost: f64,
    node: Option<Rc<StepNode>>,
}

impl Label {
    fn known(interval: Interval) -> Self {
        Label {
            interval,
            eps: 0.0,
            cost: 0.0,
            node: None,
        }
    }

    fn inflated(&self) -> Interval {
        inflate(self.interval, self.eps)
    }
}

/// `a` dominates `b` for the SAME port iff `a` is no more expensive and
/// `a`'s inflated interval sits inside (or equals) `b`'s (04: "subset
/// dominance subsumes the eps comparison exactly").
fn dominates(a: &Label, b: &Label) -> bool {
    a.cost <= b.cost && a.inflated().is_subset(&b.inflated())
}

fn insert_with_dominance(set: &mut Vec<Label>, new_label: Label) -> bool {
    if set.iter().any(|existing| dominates(existing, &new_label)) {
        return false;
    }
    set.retain(|existing| !dominates(&new_label, existing));
    set.push(new_label);
    true
}

/// Detects a cycle among solvers shaped like a pure port equivalence
/// (exactly one input, exactly one output): builds the directed graph
/// `input_port -> output_port` over just those solvers and runs a
/// three-color DFS. A cycle here means two or more solvers alias ports
/// back into each other with no way to ever terminate a chain of pure
/// renames (FINV-5 `CyclicPortEquivalence`).
fn detect_port_equivalence_cycle(solvers: &[SolverSummary]) -> bool {
    let mut adj: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
    for s in solvers {
        if s.inputs.len() == 1 && s.outputs.len() == 1 {
            adj.entry(s.inputs[0].as_str())
                .or_default()
                .push(s.outputs[0].as_str());
        }
    }
    #[derive(Clone, Copy, PartialEq)]
    enum Color {
        White,
        Gray,
        Black,
    }
    let mut color: BTreeMap<&str, Color> = BTreeMap::new();
    for &node in adj.keys() {
        color.entry(node).or_insert(Color::White);
    }
    fn visit<'a>(
        node: &'a str,
        adj: &BTreeMap<&'a str, Vec<&'a str>>,
        color: &mut BTreeMap<&'a str, Color>,
    ) -> bool {
        match color.get(node).copied().unwrap_or(Color::White) {
            Color::Black => return false,
            Color::Gray => return true,
            Color::White => {}
        }
        color.insert(node, Color::Gray);
        if let Some(children) = adj.get(node) {
            for &child in children {
                if visit(child, adj, color) {
                    return true;
                }
            }
        }
        color.insert(node, Color::Black);
        false
    }
    let nodes: Vec<&str> = adj.keys().copied().collect();
    for node in nodes {
        if visit(node, &adj, &mut color) {
            return true;
        }
    }
    false
}

struct Candidate {
    solver_idx: usize,
    cost: f64,
    tie_key: String,
    inputs: BTreeMap<String, Label>,
}

fn tie_key_for(inputs: &BTreeMap<String, Label>) -> String {
    // Deterministic across runs: bit-pattern of each chosen label's
    // inflated bounds and cost, in port-name (BTreeMap) order.
    let mut parts = Vec::new();
    for (port, label) in inputs {
        let iv = label.inflated();
        parts.push(format!(
            "{}:{}:{}:{}",
            port,
            iv.lo.to_bits(),
            iv.hi.to_bits(),
            label.cost.to_bits()
        ));
    }
    parts.join("|")
}

/// Cartesian product of each input port's current Pareto label set, in
/// deterministic (BTreeMap, then Vec-index) order.
fn combos_for(
    inputs: &[String],
    labels: &BTreeMap<String, Vec<Label>>,
) -> Vec<BTreeMap<String, Label>> {
    let mut acc: Vec<BTreeMap<String, Label>> = vec![BTreeMap::new()];
    for port in inputs {
        let choices = match labels.get(port) {
            Some(v) if !v.is_empty() => v,
            _ => return Vec::new(),
        };
        let mut next = Vec::with_capacity(acc.len() * choices.len());
        for combo in &acc {
            for choice in choices {
                let mut c = combo.clone();
                c.insert(port.clone(), choice.clone());
                next.push(c);
            }
        }
        acc = next;
    }
    acc
}

fn regenerate_candidates(
    solvers: &[SolverSummary],
    labels: &BTreeMap<String, Vec<Label>>,
    sense: Sense,
    target: &str,
    frontier: &mut Vec<Candidate>,
    pushed: &mut HashSet<(usize, String)>,
) {
    for (idx, s) in solvers.iter().enumerate() {
        if s.conservative_for != Sense::Both && s.conservative_for != sense {
            continue;
        }
        if s.conservative_for != Sense::Both && !s.outputs.iter().any(|o| o == target) {
            continue;
        }
        for combo in combos_for(&s.inputs, labels) {
            let tie_key = tie_key_for(&combo);
            let key = (idx, tie_key.clone());
            if pushed.contains(&key) {
                continue;
            }
            pushed.insert(key);
            let cost = s.cost + combo.values().map(|l| l.cost).sum::<f64>();
            frontier.push(Candidate {
                solver_idx: idx,
                cost,
                tie_key,
                inputs: combo,
            });
        }
    }
}

/// Deterministic forward AND-graph search (04-routing "Algorithm (v1)").
/// `solvers` is the frozen registry snapshot crossed once at freeze time
/// (marshalling done by the caller -- this function never touches
/// Python); `known` and `tags` are the request's known ports/tag set;
/// `sense` filters `conservative_for` edges (A-3).
pub fn plan(
    solvers: &[SolverSummary],
    known: &BTreeMap<String, Interval>,
    tags: &BTreeSet<String>,
    target: &str,
    eps_budget: f64,
    sense: Sense,
) -> Result<Route, PlanError> {
    if !eps_budget.is_finite() || eps_budget <= 0.0 {
        return Err(PlanError::InvalidBudget);
    }

    // G12: target already known -> zero-step Route.
    if let Some(iv) = known.get(target) {
        let steps: Vec<RouteStep> = Vec::new();
        let digest = route_digest(target, &steps, 0.0, 0.0);
        let _ = iv; // value carried by `known`, not re-stated on the zero-step Route
        return Ok(Route {
            target: target.to_string(),
            steps,
            predicted_eps: 0.0,
            total_cost: 0.0,
            digest,
        });
    }

    let target_is_producible = solvers
        .iter()
        .any(|s| s.outputs.iter().any(|o| o == target));
    if !target_is_producible {
        return Err(PlanError::UnknownTarget(target.to_string()));
    }

    if detect_port_equivalence_cycle(solvers) {
        tracing::warn!(target: "feldspar_core::search", "cyclic port equivalence detected");
        return Err(PlanError::CyclicPortEquivalence);
    }

    let mut labels: BTreeMap<String, Vec<Label>> = BTreeMap::new();
    for (port, iv) in known {
        labels.insert(port.clone(), vec![Label::known(*iv)]);
    }

    let mut frontier: Vec<Candidate> = Vec::new();
    let mut pushed: HashSet<(usize, String)> = HashSet::new();

    loop {
        regenerate_candidates(solvers, &labels, sense, target, &mut frontier, &mut pushed);
        if frontier.is_empty() {
            break;
        }
        // Global-minimum pop: (cost, solver_id, tie_key) -- 04's
        // frontier order, extended with the combo tie-key for full
        // determinism when the same solver has several incomparable
        // input combos at equal cost.
        let mut best_idx = 0usize;
        for i in 1..frontier.len() {
            let a = &frontier[i];
            let b = &frontier[best_idx];
            let better = match a.cost.total_cmp(&b.cost) {
                std::cmp::Ordering::Less => true,
                std::cmp::Ordering::Greater => false,
                std::cmp::Ordering::Equal => {
                    let sa = &solvers[a.solver_idx].solver_id;
                    let sb = &solvers[b.solver_idx].solver_id;
                    (sa, &a.tie_key) < (sb, &b.tie_key)
                }
            };
            if better {
                best_idx = i;
            }
        }
        let candidate = frontier.remove(best_idx);
        let s = &solvers[candidate.solver_idx];

        let inflated_inputs: BTreeMap<String, Interval> = candidate
            .inputs
            .iter()
            .map(|(p, l)| (p.clone(), l.inflated()))
            .collect();

        // Plan-time admission checks ONLY the solver's declared INPUT
        // ports against the box (04-routing point 2: "in-domain for the
        // interval hull actually reaching it" -- the hull of ports that
        // have REACHED the step, which by construction excludes its own
        // not-yet-produced outputs). A `Domain.box` entry for one of the
        // solver's OUTPUT ports (the documented multi-direction `Relation`
        // shape, e.g. `mech.cantilever`'s single box spanning inputs and
        // outputs) is a VALIDITY constraint on the result, not a
        // precondition to admit the step -- it is checked against the
        // realized output hull at execution time instead (`execute.py`'s
        // output-domain check). Filtering here is what makes a
        // `Relation`-declared solver plannable in either direction at all;
        // without it, any box entry on an output port makes the step
        // permanently inadmissible (that port is never "known" before the
        // step runs), which silently made every multi-direction Relation
        // unroutable.
        let input_ports: BTreeSet<&str> = s.inputs.iter().map(String::as_str).collect();
        let input_box: BTreeMap<String, Interval> = s
            .domain
            .port_box
            .iter()
            .filter(|(port, _)| input_ports.contains(port.as_str()))
            .map(|(p, iv)| (p.clone(), *iv))
            .collect();
        let input_domain = Domain::new(input_box, s.domain.tags.clone());

        if let Err(violation) = input_domain.admits(&inflated_inputs, tags) {
            tracing::info!(
                target: "feldspar_core::search",
                solver_id = %s.solver_id,
                ?violation,
                "domain rejection during expansion"
            );
            continue;
        }

        let estimate: Result<BTreeMap<String, Interval>, ()> =
            corner_sweep(&inflated_inputs, |corner: &BTreeMap<String, f64>| {
                let sum: f64 = corner.values().sum();
                let outs: BTreeMap<String, f64> =
                    s.outputs.iter().map(|o| (o.clone(), sum)).collect();
                Ok::<_, ()>(outs)
            });
        let hull = estimate.expect("sum-surrogate eval never errs");

        let outputs: BTreeMap<String, (Interval, f64)> = s
            .outputs
            .iter()
            .map(|o| {
                let iv = hull[o];
                let eps = s
                    .accuracy
                    .get(o)
                    .map(|acc| acc.worst_over(&iv))
                    .unwrap_or(0.0);
                (o.clone(), (iv, eps))
            })
            .collect();

        let node = Rc::new(StepNode {
            solver_id: s.solver_id.clone(),
            own_cost: s.cost,
            tags: s.domain.tags.clone(),
            inputs: candidate.inputs.clone(),
            outputs: outputs.clone(),
        });

        let mut any_committed = false;
        for (port, (iv, eps)) in &outputs {
            let label = Label {
                interval: *iv,
                eps: *eps,
                cost: candidate.cost,
                node: Some(node.clone()),
            };
            let committed = insert_with_dominance(labels.entry(port.clone()).or_default(), label);
            any_committed = any_committed || committed;
            if !committed {
                tracing::info!(
                    target: "feldspar_core::search",
                    solver_id = %s.solver_id,
                    port = %port,
                    "label pruned by Pareto dominance"
                );
            }
        }
        if !any_committed {
            continue;
        }

        if let Some(target_labels) = labels.get(target) {
            if let Some(winner) = target_labels
                .iter()
                .filter(|l| total_error(l.interval, l.eps) <= eps_budget)
                .min_by(|a, b| a.cost.total_cmp(&b.cost))
            {
                return Ok(build_route(target, winner));
            }
        }
    }

    match labels.get(target) {
        Some(target_labels) if !target_labels.is_empty() => {
            let best_eps = target_labels
                .iter()
                .map(|l| total_error(l.interval, l.eps))
                .fold(f64::INFINITY, f64::min);
            Err(PlanError::BudgetUnreachable { best_eps })
        }
        _ => Err(PlanError::NoApplicableSolver),
    }
}

fn build_route(target: &str, winner: &Label) -> Route {
    let predicted_eps = total_error(winner.interval, winner.eps);
    let mut steps: Vec<RouteStep> = Vec::new();
    if let Some(node) = &winner.node {
        let visited: RefCell<HashSet<usize>> = RefCell::new(HashSet::new());
        walk_route(node, &visited, &mut steps);
    }
    let total_cost: f64 = steps.iter().map(|s| s.cost).sum();
    let digest = route_digest(target, &steps, predicted_eps, total_cost);
    Route {
        target: target.to_string(),
        steps,
        predicted_eps,
        total_cost,
        digest,
    }
}

fn walk_route(node: &Rc<StepNode>, visited: &RefCell<HashSet<usize>>, steps: &mut Vec<RouteStep>) {
    let ptr = Rc::as_ptr(node) as usize;
    if visited.borrow().contains(&ptr) {
        return;
    }
    visited.borrow_mut().insert(ptr);
    for label in node.inputs.values() {
        if let Some(child) = &label.node {
            walk_route(child, visited, steps);
        }
    }
    let box_: BTreeMap<String, Interval> = node
        .inputs
        .iter()
        .map(|(p, l)| (p.clone(), l.inflated()))
        .collect();
    let realized_domain = Domain::new(box_, node.tags.clone());
    let predicted_eps = node
        .outputs
        .values()
        .map(|(_, eps)| *eps)
        .fold(0.0_f64, f64::max);
    steps.push(RouteStep {
        solver_id: node.solver_id.clone(),
        realized_domain: SerDomain::from(&realized_domain),
        predicted_eps,
        cost: node.own_cost,
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn iv(lo: f64, hi: f64) -> Interval {
        Interval::new(lo, hi).unwrap()
    }

    fn acc(eps_abs: f64, eps_rel: f64) -> Accuracy {
        Accuracy::new(eps_abs, eps_rel)
    }

    fn simple_domain(inputs: &[(&str, f64, f64)]) -> Domain {
        let mut box_ = BTreeMap::new();
        for (p, lo, hi) in inputs {
            box_.insert(p.to_string(), iv(*lo, *hi));
        }
        Domain::new(box_, BTreeSet::new())
    }

    fn solver(
        id: &str,
        inputs: &[&str],
        outputs: &[&str],
        domain: Domain,
        cost: f64,
        eps_abs: f64,
    ) -> SolverSummary {
        SolverSummary {
            solver_id: id.to_string(),
            inputs: inputs.iter().map(|s| s.to_string()).collect(),
            outputs: outputs.iter().map(|s| s.to_string()).collect(),
            domain,
            cost,
            accuracy: outputs
                .iter()
                .map(|o| (o.to_string(), acc(eps_abs, 0.0)))
                .collect(),
            conservative_for: Sense::Both,
        }
    }

    #[test]
    fn zero_step_route_when_target_known() {
        let mut known = BTreeMap::new();
        known.insert("p".to_string(), iv(1.0, 2.0));
        let route = plan(&[], &known, &BTreeSet::new(), "p", 1.0, Sense::Both).unwrap();
        assert!(route.steps.is_empty());
        assert_eq!(route.predicted_eps, 0.0);
        assert_eq!(route.total_cost, 0.0);
    }

    #[test]
    fn invalid_budget_rejected_before_search() {
        let known = BTreeMap::new();
        let err = plan(&[], &known, &BTreeSet::new(), "p", 0.0, Sense::Both).unwrap_err();
        assert_eq!(err, PlanError::InvalidBudget);
        let err2 = plan(&[], &known, &BTreeSet::new(), "p", f64::NAN, Sense::Both).unwrap_err();
        assert_eq!(err2, PlanError::InvalidBudget);
    }

    #[test]
    fn unknown_target_when_nothing_produces_it() {
        let known = BTreeMap::new();
        let err = plan(&[], &known, &BTreeSet::new(), "ghost", 1.0, Sense::Both).unwrap_err();
        assert_eq!(err, PlanError::UnknownTarget("ghost".to_string()));
    }

    #[test]
    fn cheap_route_selected_within_budget() {
        let mut known = BTreeMap::new();
        known.insert("x".to_string(), iv(1.0, 1.0));
        let cheap = solver(
            "cheap",
            &["x"],
            &["y"],
            simple_domain(&[("x", 0.0, 10.0)]),
            1.0,
            0.5,
        );
        let solvers = vec![cheap];
        let route = plan(&solvers, &known, &BTreeSet::new(), "y", 1.0, Sense::Both).unwrap();
        assert_eq!(route.steps.len(), 1);
        assert_eq!(route.steps[0].solver_id, "cheap");
    }

    #[test]
    fn budget_selects_costly_tight_route_over_cheap_sloppy_one() {
        let mut known = BTreeMap::new();
        known.insert("x".to_string(), iv(1.0, 1.0));
        let cheap_sloppy = solver(
            "cheap_sloppy",
            &["x"],
            &["y"],
            simple_domain(&[("x", 0.0, 10.0)]),
            1.0,
            5.0,
        );
        let costly_tight = solver(
            "costly_tight",
            &["x"],
            &["y"],
            simple_domain(&[("x", 0.0, 10.0)]),
            10.0,
            0.01,
        );
        let solvers = vec![cheap_sloppy, costly_tight];
        // Tight budget: only the costly/tight route qualifies.
        let route = plan(&solvers, &known, &BTreeSet::new(), "y", 0.1, Sense::Both).unwrap();
        assert_eq!(route.steps[0].solver_id, "costly_tight");
        // Loose budget: cheapest admissible route wins (uniform-cost).
        let route2 = plan(&solvers, &known, &BTreeSet::new(), "y", 100.0, Sense::Both).unwrap();
        assert_eq!(route2.steps[0].solver_id, "cheap_sloppy");
    }

    #[test]
    fn budget_unreachable_reports_best_eps() {
        let mut known = BTreeMap::new();
        known.insert("x".to_string(), iv(1.0, 1.0));
        let sloppy = solver(
            "sloppy",
            &["x"],
            &["y"],
            simple_domain(&[("x", 0.0, 10.0)]),
            1.0,
            5.0,
        );
        let solvers = vec![sloppy];
        let err = plan(&solvers, &known, &BTreeSet::new(), "y", 0.001, Sense::Both).unwrap_err();
        match err {
            PlanError::BudgetUnreachable { best_eps } => assert!((best_eps - 5.0).abs() < 1e-9),
            other => panic!("expected BudgetUnreachable, got {other:?}"),
        }
    }

    #[test]
    fn no_applicable_solver_when_domain_excludes_known_hull() {
        let mut known = BTreeMap::new();
        known.insert("x".to_string(), iv(100.0, 100.0));
        let s = solver(
            "s",
            &["x"],
            &["y"],
            simple_domain(&[("x", 0.0, 10.0)]),
            1.0,
            0.1,
        );
        let solvers = vec![s];
        let err = plan(&solvers, &known, &BTreeSet::new(), "y", 1.0, Sense::Both).unwrap_err();
        assert_eq!(err, PlanError::NoApplicableSolver);
    }

    /// Regression for the coordinator-verified bug: a `Domain.box` entry
    /// on the solver's OWN OUTPUT port (the `Relation` shape -- one box
    /// spanning every port, inputs and outputs alike) must not make the
    /// step inadmissible just because the output isn't known yet. Only
    /// the INPUT-side box entry should gate admission; an out-of-box
    /// INPUT must still reject.
    #[test]
    fn output_port_box_entry_does_not_block_admission() {
        let mut known = BTreeMap::new();
        known.insert("x".to_string(), iv(1.0, 2.0));
        // domain.box covers BOTH the input "x" and the output "y" --
        // exactly the Relation pattern (e.g. mech.cantilever's single
        // domain over all five ports).
        let s = solver(
            "s",
            &["x"],
            &["y"],
            simple_domain(&[("x", 0.0, 10.0), ("y", -1000.0, 1000.0)]),
            1.0,
            0.1,
        );
        let solvers = vec![s];
        let route = plan(&solvers, &known, &BTreeSet::new(), "y", 1.0, Sense::Both).unwrap();
        assert_eq!(route.steps[0].solver_id, "s");
    }

    /// Companion to the above: an out-of-box INPUT must still be
    /// rejected even when the domain also carries an output-port entry
    /// -- the fix only exempts OUTPUT ports from the plan-time check.
    #[test]
    fn out_of_box_input_still_rejected_alongside_output_box_entry() {
        let mut known = BTreeMap::new();
        known.insert("x".to_string(), iv(100.0, 100.0));
        let s = solver(
            "s",
            &["x"],
            &["y"],
            simple_domain(&[("x", 0.0, 10.0), ("y", -1000.0, 1000.0)]),
            1.0,
            0.1,
        );
        let solvers = vec![s];
        let err = plan(&solvers, &known, &BTreeSet::new(), "y", 1.0, Sense::Both).unwrap_err();
        assert_eq!(err, PlanError::NoApplicableSolver);
    }

    #[test]
    fn tag_required_and_missing_makes_edge_absent() {
        let mut known = BTreeMap::new();
        known.insert("x".to_string(), iv(1.0, 1.0));
        let mut domain = simple_domain(&[("x", 0.0, 10.0)]);
        domain.tags.insert("linear".to_string());
        let s = solver("s", &["x"], &["y"], domain, 1.0, 0.1);
        let solvers = vec![s];
        let err = plan(&solvers, &known, &BTreeSet::new(), "y", 1.0, Sense::Both).unwrap_err();
        assert_eq!(err, PlanError::NoApplicableSolver);
    }

    #[test]
    fn one_sided_edge_admissible_only_as_final_step() {
        let mut known = BTreeMap::new();
        known.insert("x".to_string(), iv(1.0, 1.0));
        let mut one_sided = solver(
            "one_sided",
            &["x"],
            &["y"],
            simple_domain(&[("x", 0.0, 10.0)]),
            1.0,
            0.1,
        );
        one_sided.conservative_for = Sense::Upper;
        let solvers = vec![one_sided];
        // As the final step producing the target directly: admissible.
        let route = plan(&solvers, &known, &BTreeSet::new(), "y", 1.0, Sense::Upper).unwrap();
        assert_eq!(route.steps.len(), 1);
        // Wrong sense entirely: inadmissible.
        let err = plan(&solvers, &known, &BTreeSet::new(), "y", 1.0, Sense::Lower).unwrap_err();
        assert_eq!(err, PlanError::NoApplicableSolver);
    }

    #[test]
    fn one_sided_edge_producing_non_target_port_is_absent() {
        let mut known = BTreeMap::new();
        known.insert("x".to_string(), iv(1.0, 1.0));
        let mut one_sided = solver(
            "one_sided",
            &["x"],
            &["mid"],
            simple_domain(&[("x", 0.0, 10.0)]),
            1.0,
            0.1,
        );
        one_sided.conservative_for = Sense::Upper;
        let last = solver(
            "last",
            &["mid"],
            &["y"],
            simple_domain(&[("mid", -100.0, 100.0)]),
            1.0,
            0.1,
        );
        let solvers = vec![one_sided, last];
        // `one_sided` produces `mid`, not the target `y` -- A-2 says a
        // one-sided edge is admissible ONLY when it's the final step,
        // i.e. its outputs include the target. Here it never does, so
        // the whole route is unreachable under sense=Upper.
        let err = plan(&solvers, &known, &BTreeSet::new(), "y", 1.0, Sense::Upper).unwrap_err();
        assert_eq!(err, PlanError::NoApplicableSolver);
    }

    #[test]
    fn cyclic_port_equivalence_detected() {
        let a = solver(
            "a",
            &["p1"],
            &["p2"],
            simple_domain(&[("p1", -1e9, 1e9)]),
            1.0,
            0.0,
        );
        let b = solver(
            "b",
            &["p2"],
            &["p1"],
            simple_domain(&[("p2", -1e9, 1e9)]),
            1.0,
            0.0,
        );
        let solvers = vec![a, b];
        let mut known = BTreeMap::new();
        known.insert("p1".to_string(), iv(1.0, 1.0));
        let err = plan(&solvers, &known, &BTreeSet::new(), "p2", 1.0, Sense::Both).unwrap_err();
        assert_eq!(err, PlanError::CyclicPortEquivalence);
    }

    #[test]
    fn equal_cost_routes_break_ties_lexicographically_by_solver_id() {
        let mut known = BTreeMap::new();
        known.insert("x".to_string(), iv(1.0, 1.0));
        let b_solver = solver(
            "b_route",
            &["x"],
            &["y"],
            simple_domain(&[("x", 0.0, 10.0)]),
            1.0,
            0.1,
        );
        let a_solver = solver(
            "a_route",
            &["x"],
            &["y"],
            simple_domain(&[("x", 0.0, 10.0)]),
            1.0,
            0.1,
        );
        let solvers = vec![b_solver, a_solver];
        let route1 = plan(&solvers, &known, &BTreeSet::new(), "y", 1.0, Sense::Both).unwrap();
        let route2 = plan(&solvers, &known, &BTreeSet::new(), "y", 1.0, Sense::Both).unwrap();
        assert_eq!(route1.steps[0].solver_id, "a_route");
        assert_eq!(route1.digest, route2.digest);
    }

    #[test]
    fn determinism_running_twice_yields_identical_digests() {
        let mut known = BTreeMap::new();
        known.insert("x".to_string(), iv(1.0, 3.0));
        let s1 = solver(
            "s1",
            &["x"],
            &["mid"],
            simple_domain(&[("x", 0.0, 10.0)]),
            2.0,
            0.2,
        );
        let s2 = solver(
            "s2",
            &["mid"],
            &["y"],
            simple_domain(&[("mid", -50.0, 50.0)]),
            3.0,
            0.1,
        );
        let solvers = vec![s1, s2];
        let r1 = plan(&solvers, &known, &BTreeSet::new(), "y", 10.0, Sense::Both).unwrap();
        let r2 = plan(&solvers, &known, &BTreeSet::new(), "y", 10.0, Sense::Both).unwrap();
        assert_eq!(r1.digest, r2.digest);
        assert_eq!(r1.steps.len(), 2);
        assert_eq!(r1.total_cost, 5.0);
    }

    /// FINV-8: search reads cost/accuracy/domain only, never a tier
    /// label. There is no `tier` field on `SolverSummary` at all (the
    /// snapshot the search operates over never carries one), so
    /// permuting tiers on the Python side cannot change anything this
    /// function sees -- this test pins that by constructing two
    /// snapshots that would carry different tiers upstream (modeled
    /// here as differently-ordered/otherwise-identical solver lists)
    /// and asserting identical routes.
    #[test]
    fn tier_blindness_permutation_yields_identical_route() {
        let mut known = BTreeMap::new();
        known.insert("x".to_string(), iv(1.0, 1.0));
        let s1 = solver(
            "alpha",
            &["x"],
            &["y"],
            simple_domain(&[("x", 0.0, 10.0)]),
            1.0,
            0.1,
        );
        let s2 = solver(
            "beta",
            &["x"],
            &["y"],
            simple_domain(&[("x", 0.0, 10.0)]),
            2.0,
            0.05,
        );
        let forward = vec![s1.clone(), s2.clone()];
        let reversed = vec![s2, s1];
        let route_forward =
            plan(&forward, &known, &BTreeSet::new(), "y", 10.0, Sense::Both).unwrap();
        let route_reversed =
            plan(&reversed, &known, &BTreeSet::new(), "y", 10.0, Sense::Both).unwrap();
        assert_eq!(route_forward.digest, route_reversed.digest);
    }
}
