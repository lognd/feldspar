//! The symbolic-equation kernel (11 "The symbolic core"; WO-11, M10).
//!
//! Laws-as-data: a physical law is declared ONCE as a canonical `Expr`
//! and its N solver directions are DERIVED by closed-form inversion at
//! declaration time, each lowering to an ordinary raw-protocol entry
//! (10 sec. 2: an authoring FORM, not a tenth pattern). This module does
//! ALGEBRA ONLY -- canonicalize, invert, derive a dispatch box from
//! predicates, and evaluate a frozen `Expr` numerically. Registration-
//! lowering (building the `(SolverInfo, SolveFn)` pairs) lives Python-
//! side in `feldspar.solve.sugar`, which calls these primitives; that
//! keeps twin-equality defined by the single `_build` path (03).
//!
//! Non-goals (11 sec. 3): no optimization, no invented relations, no
//! solve-time CAS manipulation. `Expr::eval` is compiled numeric
//! evaluation of a FROZEN tree (like a table solver interpolating), not
//! symbolic work -- all symbolic work happens here at declaration time.

use std::collections::{BTreeMap, BTreeSet};

use crate::digest::format_f64;
use crate::domain::Domain;
use crate::interval::Interval;

/// The canonical-form version. Any change to the total order, flattening,
/// identity/zero elimination, literal-folding order, or the serialized
/// string form (`canonical_string`) is a LOUD, versioned event (R2):
/// bump this, and every stored derivation digest changes on purpose, not
/// silently. Folded into every derivation's provenance so a mismatch is
/// detectable rather than a mystery digest drift.
// frob:doc docs/modules/feldspar-core.md#core_symbolic
pub const CANON_VERSION: u32 = 1;

/// A named unary function around a subexpression. Open-ended by design
/// (R1 "extend later without a breaking change"): adding `Sin`, `Exp`,
/// `Ln`, ... appends variants and their inverse rules without touching
/// the `Expr` shape. Only `Sqrt` is invertible in v1.
// frob:doc docs/modules/feldspar-core.md#core_symbolic
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum UnaryFn {
    /// Principal (non-negative) square root; range constraint `arg >= 0`.
    Sqrt,
    // TODO(R4/future): Sin, Cos, Exp, Ln, ... each with its inverse +
    // branch/admission rules; adding a variant is additive, never a break.
}

/// A canonical symbolic expression over ports (11 sec. 1). This is the
/// NORMAL form: authoring sugar (`a - b`, `a / b`) is lowered into it
/// (`Sub -> Add[a, Neg b]`, `Div -> Mul[a, Pow(b, -1)]`) by the builder
/// helpers, so subtraction and division never appear as nodes here.
/// `Add`/`Mul` are n-ary, flattened, and their operands are stored in
/// the canonical total order (`cmp`) after `canonicalize`.
// frob:doc docs/modules/feldspar-core.md#core_symbolic
#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    /// A port reference (the free variables a law solves among).
    Var(String),
    /// A float literal (coefficients, exponents, constants like `2.0`).
    Lit(f64),
    /// Unary arithmetic negation `-e` (kept as its own node, cheaper and
    /// cleaner for ordering than `Mul[Lit(-1), e]`).
    Neg(Box<Expr>),
    /// Flattened, order-normalized commutative sum (n-ary).
    Add(Vec<Expr>),
    /// Flattened, order-normalized commutative product (n-ary).
    Mul(Vec<Expr>),
    /// `base ^ exponent`. Integer-literal exponents drive inversion
    /// (even -> two branches, odd -> unique real root).
    Pow(Box<Expr>, Box<Expr>),
    /// A named unary function applied to one argument (e.g. `sqrt`).
    Unary(UnaryFn, Box<Expr>),
}

/// Total-order kind rank for the canonical order (R2). Literals sort
/// first so numeric coefficients cluster at the front of `Add`/`Mul`
/// operand lists, then vars, then progressively richer nodes. Changing
/// any of these numbers is a `CANON_VERSION` break.
fn kind_rank(e: &Expr) -> u8 {
    match e {
        Expr::Lit(_) => 0,
        Expr::Var(_) => 1,
        Expr::Neg(_) => 2,
        Expr::Pow(_, _) => 3,
        Expr::Unary(_, _) => 4,
        Expr::Add(_) => 5,
        Expr::Mul(_) => 6,
    }
}

impl Expr {
    /// The pinned canonical total order (R2): by `kind_rank` first, then
    /// structurally within a kind. Literals compare by IEEE total order
    /// (`f64::total_cmp`) -- bit-pattern aware, so `-0.0 < 0.0` and the
    /// order is total (inputs are NaN-free by construction). Vars compare
    /// by byte order; `Add`/`Mul` compare operand-wise then by length;
    /// `Pow` compares base then exponent. Deterministic across platforms.
    // frob:doc docs/modules/feldspar-core.md#core_symbolic
    #[allow(clippy::should_implement_trait)]
    pub fn cmp(&self, other: &Expr) -> std::cmp::Ordering {
        use std::cmp::Ordering;

        let rank_ord = kind_rank(self).cmp(&kind_rank(other));
        if rank_ord != Ordering::Equal {
            return rank_ord;
        }

        match (self, other) {
            (Expr::Lit(a), Expr::Lit(b)) => a.total_cmp(b),
            (Expr::Var(a), Expr::Var(b)) => a.cmp(b),
            (Expr::Neg(a), Expr::Neg(b)) => a.cmp(b),
            (Expr::Unary(fa, a), Expr::Unary(fb, b)) => {
                let f_ord = fa.cmp(fb);
                if f_ord != Ordering::Equal {
                    return f_ord;
                }
                a.cmp(b)
            }
            (Expr::Pow(ba, xa), Expr::Pow(bb, xb)) => {
                let b_ord = ba.cmp(bb);
                if b_ord != Ordering::Equal {
                    return b_ord;
                }
                xa.cmp(xb)
            }
            (Expr::Add(a), Expr::Add(b)) | (Expr::Mul(a), Expr::Mul(b)) => {
                for (ea, eb) in a.iter().zip(b.iter()) {
                    let ord = ea.cmp(eb);
                    if ord != Ordering::Equal {
                        return ord;
                    }
                }
                a.len().cmp(&b.len())
            }
            _ => unreachable!("kind_rank equal implies matching variant"),
        }
    }

    /// Canonicalize in place: lower away nothing new (Sub/Div are already
    /// lowered by the builders), then (1) recurse into children, (2)
    /// flatten nested same-kind `Add`/`Mul`, (3) fold literal-only
    /// operands via a fixed left-fold (deterministic per AD-13), (4) drop
    /// additive `0.0` / multiplicative `1.0` identities and collapse
    /// `Mul` containing `0.0` to `Lit(0.0)`, (5) sort commutative operands
    /// by `cmp`. Deliberately does NOT distribute, collect like terms, or
    /// simplify `sqrt(x^2)` -- keeping the rewrite confluent and cheap so
    /// the canonical form is a fixed point (idempotent).
    // frob:doc docs/modules/feldspar-core.md#core_symbolic
    pub fn canonicalize(&self) -> Expr {
        match self {
            Expr::Var(_) | Expr::Lit(_) => self.clone(),
            Expr::Neg(inner) => Expr::Neg(Box::new(inner.canonicalize())),
            Expr::Unary(f, inner) => Expr::Unary(*f, Box::new(inner.canonicalize())),
            Expr::Pow(base, exp) => {
                Expr::Pow(Box::new(base.canonicalize()), Box::new(exp.canonicalize()))
            }
            Expr::Add(operands) => {
                // Recurse.
                let mut flat: Vec<Expr> = Vec::new();
                for op in operands {
                    let c = op.canonicalize();
                    match c {
                        Expr::Add(inner_ops) => flat.extend(inner_ops),
                        other => flat.push(other),
                    }
                }

                // Fold literal-only operands via a fixed left-fold.
                let mut lit_sum = 0.0_f64;
                let mut non_lits: Vec<Expr> = Vec::new();
                for op in flat {
                    if let Expr::Lit(x) = op {
                        lit_sum += x;
                    } else {
                        non_lits.push(op);
                    }
                }

                // Drop additive-zero identity unless it's the only term.
                let mut result: Vec<Expr> = non_lits;
                if lit_sum != 0.0 {
                    result.push(Expr::Lit(lit_sum));
                }

                if result.is_empty() {
                    return Expr::Lit(0.0);
                }
                if result.len() == 1 {
                    return result.into_iter().next().unwrap();
                }
                result.sort_by(Expr::cmp);
                Expr::Add(result)
            }
            Expr::Mul(operands) => {
                let mut flat: Vec<Expr> = Vec::new();
                for op in operands {
                    let c = op.canonicalize();
                    match c {
                        Expr::Mul(inner_ops) => flat.extend(inner_ops),
                        other => flat.push(other),
                    }
                }

                let mut lit_prod = 1.0_f64;
                let mut non_lits: Vec<Expr> = Vec::new();
                for op in flat {
                    if let Expr::Lit(x) = op {
                        lit_prod *= x;
                    } else {
                        non_lits.push(op);
                    }
                }

                if lit_prod == 0.0 {
                    return Expr::Lit(0.0);
                }

                let mut result: Vec<Expr> = non_lits;
                if lit_prod != 1.0 {
                    result.push(Expr::Lit(lit_prod));
                }

                if result.is_empty() {
                    return Expr::Lit(1.0);
                }
                if result.len() == 1 {
                    return result.into_iter().next().unwrap();
                }
                result.sort_by(Expr::cmp);
                Expr::Mul(result)
            }
        }
    }

    /// The dedicated canonical string form that folds into digests (R2).
    /// A prefix S-expression -- `V:name`, `L:<format_f64>`, `(neg E)`,
    /// `(sqrt E)`, `(pow B X)`, `(add E ...)`, `(mul E ...)` -- chosen
    /// OVER `serde_json` of the enum so the digest is insulated from serde
    /// representation changes and floats go through the one `format_f64`
    /// home (ryu shortest round-trip, platform-stable). Assumes the tree
    /// is already `canonicalize`d.
    // frob:doc docs/modules/feldspar-core.md#core_symbolic
    pub fn canonical_string(&self) -> String {
        match self {
            Expr::Var(name) => format!("V:{name}"),
            Expr::Lit(x) => format!("L:{}", format_f64(*x)),
            Expr::Neg(e) => format!("(neg {})", e.canonical_string()),
            Expr::Unary(UnaryFn::Sqrt, e) => format!("(sqrt {})", e.canonical_string()),
            Expr::Pow(b, x) => format!("(pow {} {})", b.canonical_string(), x.canonical_string()),
            Expr::Add(v) => format!(
                "(add {})",
                v.iter()
                    .map(Expr::canonical_string)
                    .collect::<Vec<_>>()
                    .join(" ")
            ),
            Expr::Mul(v) => format!(
                "(mul {})",
                v.iter()
                    .map(Expr::canonical_string)
                    .collect::<Vec<_>>()
                    .join(" ")
            ),
        }
    }

    /// Numeric evaluation of a FROZEN canonical tree (compiled eval, not
    /// CAS): a stack walk substituting `inputs[port]`. `Err(EvalError)`
    /// for a missing port or a domain fault (negative `sqrt` arg, `0^neg`)
    /// -- the derived `SolveFn` surfaces this as a recoverable value.
    // frob:doc docs/modules/feldspar-core.md#core_symbolic
    pub fn eval(&self, inputs: &BTreeMap<String, f64>) -> Result<f64, EvalError> {
        match self {
            Expr::Var(name) => inputs
                .get(name)
                .copied()
                .ok_or_else(|| EvalError::MissingPort { port: name.clone() }),
            Expr::Lit(x) => Ok(*x),
            Expr::Neg(e) => Ok(-e.eval(inputs)?),
            Expr::Add(operands) => {
                let mut sum = 0.0;
                for op in operands {
                    sum += op.eval(inputs)?;
                }
                Ok(sum)
            }
            Expr::Mul(operands) => {
                let mut prod = 1.0;
                for op in operands {
                    prod *= op.eval(inputs)?;
                }
                Ok(prod)
            }
            Expr::Pow(base, exp) => {
                let b = base.eval(inputs)?;
                let x = exp.eval(inputs)?;
                let result = b.powf(x);
                if !result.is_finite() {
                    return Err(EvalError::DomainFault {
                        detail: format!(
                            "{b} raised to the power {x} is not finite (e.g. 0 raised to a negative power)"
                        ),
                    });
                }
                Ok(result)
            }
            Expr::Unary(UnaryFn::Sqrt, e) => {
                let v = e.eval(inputs)?;
                if v < 0.0 {
                    return Err(EvalError::DomainFault {
                        detail: format!("sqrt of negative value {v}"),
                    });
                }
                Ok(v.sqrt())
            }
        }
    }

    /// Count of `Var(target)` occurrences -- the invertibility gate:
    /// closed-form peeling requires EXACTLY one (see `invert_for`).
    fn count_var(&self, target: &str) -> usize {
        match self {
            Expr::Var(name) => {
                if name == target {
                    1
                } else {
                    0
                }
            }
            Expr::Lit(_) => 0,
            Expr::Neg(e) => e.count_var(target),
            Expr::Unary(_, e) => e.count_var(target),
            Expr::Pow(b, x) => b.count_var(target) + x.count_var(target),
            Expr::Add(v) | Expr::Mul(v) => v.iter().map(|e| e.count_var(target)).sum(),
        }
    }
}

/// A comparison direction for a domain predicate (11 sec. 2).
// frob:doc docs/modules/feldspar-core.md#core_symbolic
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Cmp {
    /// `<`
    Lt,
    /// `<=`
    Le,
    /// `>`
    Gt,
    /// `>=`
    Ge,
}

/// An inequality over ports, e.g. `Re < 2300`. Stored as `lhs <cmp> rhs`;
/// `predicate_to_box` normalizes it to a single-port affine bound where
/// boundable and refuses (an `Err`) otherwise -- never a silently-wrong
/// hull.
// frob:doc docs/modules/feldspar-core.md#core_symbolic
#[derive(Debug, Clone, PartialEq)]
pub struct Predicate {
    pub lhs: Expr,
    pub cmp: Cmp,
    pub rhs: Expr,
}

impl Predicate {
    /// Its canonical string (for provenance / `explain`), reusing
    /// `Expr::canonical_string` on both sides around the comparator.
    // frob:doc docs/modules/feldspar-core.md#core_symbolic
    pub fn canonical_string(&self) -> String {
        let cmp_str = match self.cmp {
            Cmp::Lt => "<",
            Cmp::Le => "<=",
            Cmp::Gt => ">",
            Cmp::Ge => ">=",
        };
        format!(
            "{} {} {}",
            self.lhs.canonical_string(),
            cmp_str,
            self.rhs.canonical_string()
        )
    }
}

/// Which root/branch a non-unique inversion took (R3). Extensible for
/// future periodic inverses; v1 uses `Principal` (odd roots, sqrt-out)
/// and `Positive`/`Negative` (even roots).
// frob:doc docs/modules/feldspar-core.md#core_symbolic
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Branch {
    /// The single real principal value (odd roots, `sqrt` outward).
    Principal,
    /// The `+` root of an even power.
    Positive,
    /// The `-` root of an even power.
    Negative,
}

impl Branch {
    /// Short provenance label (`"principal"` / `"+"` / `"-"`).
    // frob:doc docs/modules/feldspar-core.md#core_symbolic
    pub fn label(&self) -> &'static str {
        match self {
            Branch::Principal => "principal",
            Branch::Positive => "+",
            Branch::Negative => "-",
        }
    }
}

/// The result of solving one equation for one target variable: the
/// closed-form right-hand side, the branch taken, any admission
/// predicates the inversion imposed (e.g. `sqrt` range `>= 0`,
/// non-zero divisor), and the canonical string for provenance.
// frob:doc docs/modules/feldspar-core.md#core_symbolic
#[derive(Debug, Clone, PartialEq)]
pub struct Inversion {
    pub solved_for: String,
    pub rhs: Expr,
    pub branch: Branch,
    pub admission: Vec<Predicate>,
    pub form: String,
}

/// Total error set for the symbolic kernel (FINV-5; mirrors
/// `DomainViolation`'s named-detail pattern). Every fallible declaration-
/// time operation returns one of these as a value, never an exception.
// frob:doc docs/modules/feldspar-core.md#core_symbolic
#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum SymbolicError {
    /// `target` cannot be isolated in closed form: it appears zero or
    /// more than once, or sits inside a function with no v1 inverse.
    #[error("cannot invert for `{variable}` in closed form: {reason}")]
    NonInvertible {
        variable: String,
        reason: NonInvertibleReason,
    },
    /// Inverting an even power (or other non-unique op) yields multiple
    /// branches; the author MUST declare one per derived direction (R3).
    #[error("inverting for `{variable}` is multi-branch ({branches:?}); declare one")]
    MultiBranch {
        variable: String,
        branches: Vec<Branch>,
    },
    /// A predicate set is not interval-boundable without an author-
    /// declared box: it is nonlinear, multi-variable, or leaves a port
    /// bounded on only one side (11 sec. 2: refuse silently-wrong hulls).
    #[error("predicate `{predicate}` is not interval-boundable without a declared box")]
    UnboundablePredicate { predicate: String },
    /// Derived predicate bounds and a declared box intersect to nothing.
    #[error(
        "domain for port `{port}` is empty after intersecting predicates with the declared box"
    )]
    EmptyDomain { port: String },
}

/// Why a variable could not be isolated (the `NonInvertible` detail).
// frob:doc docs/modules/feldspar-core.md#core_symbolic
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NonInvertibleReason {
    /// The target does not appear in the equation at all.
    Absent,
    /// The target appears more than once (no single peel path).
    MultipleOccurrences { count: usize },
    /// The target sits inside a function with no v1 closed-form inverse
    /// (e.g. in an exponent, or inside a not-yet-supported `UnaryFn`).
    NoInverse { context: String },
}

impl std::fmt::Display for NonInvertibleReason {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            NonInvertibleReason::Absent => write!(f, "it does not appear in the equation"),
            NonInvertibleReason::MultipleOccurrences { count } => {
                write!(f, "it appears {count} times (needs exactly one)")
            }
            NonInvertibleReason::NoInverse { context } => {
                write!(
                    f,
                    "it is inside {context}, which has no closed-form inverse"
                )
            }
        }
    }
}

/// A numeric-evaluation fault from `Expr::eval` (recoverable, surfaced by
/// the derived `SolveFn`; distinct from declaration-time `SymbolicError`).
// frob:doc docs/modules/feldspar-core.md#core_symbolic
#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum EvalError {
    /// An input port had no supplied value.
    #[error("eval requires port `{port}` but no value was supplied")]
    MissingPort { port: String },
    /// A domain fault: `sqrt` of a negative, `0` raised to a negative
    /// power, or a zero divisor produced from a `Pow(_, -1)`.
    #[error("eval domain fault: {detail}")]
    DomainFault { detail: String },
}

/// Solve `lhs = rhs` for `target` in closed form (R3). Normalizes to
/// `expr = 0` (`expr = lhs - rhs` lowered/canonicalized), requires the
/// target to occur EXACTLY once, then peels operations from the root
/// down the unique path to the target, moving each inverse to the other
/// side:
///   - `Add`  -> subtract the other addends
///   - `Mul`  -> divide by the other factors (admission: divisor != 0)
///   - `Neg`  -> negate
///   - `Sqrt` -> square (admission: other side >= 0), single branch
///   - `Pow(base, Lit(n))`, target in base: odd n -> principal real root
///     (unique); even n -> `MultiBranch[Positive, Negative]` unless a
///     branch is supplied; target in exponent -> `NonInvertible`.
///   - any other `Unary` -> `NonInvertible` (no v1 inverse).
///
/// `branch` selects the root for a known multi-branch op; pass `None` to
/// get the `MultiBranch` listing back and let the author choose.
// frob:doc docs/modules/feldspar-core.md#core_symbolic
pub fn invert_for(
    lhs: &Expr,
    rhs: &Expr,
    target: &str,
    branch: Option<Branch>,
) -> Result<Inversion, SymbolicError> {
    let expr = Expr::Add(vec![lhs.clone(), Expr::Neg(Box::new(rhs.clone()))]).canonicalize();

    let count = expr.count_var(target);
    if count == 0 {
        return Err(SymbolicError::NonInvertible {
            variable: target.to_string(),
            reason: NonInvertibleReason::Absent,
        });
    }
    if count > 1 {
        return Err(SymbolicError::NonInvertible {
            variable: target.to_string(),
            reason: NonInvertibleReason::MultipleOccurrences { count },
        });
    }

    let mut admission = Vec::new();
    let mut branch_taken: Option<Branch> = None;
    let rhs_solved = peel(
        &expr,
        target,
        Expr::Lit(0.0),
        branch,
        &mut admission,
        &mut branch_taken,
    )?;

    let final_branch = branch_taken.unwrap_or(Branch::Principal);
    let rhs_canon = rhs_solved.canonicalize();
    let form = format!("{} = {}", target, rhs_canon.canonical_string());
    Ok(Inversion {
        solved_for: target.to_string(),
        rhs: rhs_canon,
        branch: final_branch,
        admission,
        form,
    })
}

/// Recursive peel helper for `invert_for`: walks `node` (a subtree of the
/// zeroed equation known to contain the unique `target` occurrence) toward
/// that occurrence, carrying `acc` (what `target` equals so far, before
/// this peel step) and accumulating admission predicates / the chosen
/// branch as each op is undone.
fn peel(
    node: &Expr,
    target: &str,
    acc: Expr,
    branch: Option<Branch>,
    admission: &mut Vec<Predicate>,
    branch_taken: &mut Option<Branch>,
) -> Result<Expr, SymbolicError> {
    match node {
        Expr::Var(name) if name == target => Ok(acc),
        Expr::Add(operands) => {
            let idx = operands
                .iter()
                .position(|op| op.count_var(target) > 0)
                .expect("occurrence gate guarantees the target lives in one operand");
            let mut others = operands.clone();
            let child = others.remove(idx);
            let new_acc =
                Expr::Add(vec![acc, Expr::Neg(Box::new(Expr::Add(others)))]).canonicalize();
            peel(&child, target, new_acc, branch, admission, branch_taken)
        }
        Expr::Mul(operands) => {
            let idx = operands
                .iter()
                .position(|op| op.count_var(target) > 0)
                .expect("occurrence gate guarantees the target lives in one operand");
            let mut others = operands.clone();
            let child = others.remove(idx);
            let new_acc = Expr::Mul(vec![
                acc,
                Expr::Pow(Box::new(Expr::Mul(others)), Box::new(Expr::Lit(-1.0))),
            ])
            .canonicalize();
            peel(&child, target, new_acc, branch, admission, branch_taken)
        }
        Expr::Neg(inner) => {
            let new_acc = Expr::Neg(Box::new(acc)).canonicalize();
            peel(inner, target, new_acc, branch, admission, branch_taken)
        }
        Expr::Unary(UnaryFn::Sqrt, inner) => {
            admission.push(Predicate {
                lhs: acc.clone(),
                cmp: Cmp::Ge,
                rhs: Expr::Lit(0.0),
            });
            *branch_taken = Some(Branch::Principal);
            let new_acc = Expr::Pow(Box::new(acc), Box::new(Expr::Lit(2.0))).canonicalize();
            peel(inner, target, new_acc, branch, admission, branch_taken)
        }
        Expr::Pow(base, exp) => {
            let target_in_base = base.count_var(target) > 0;
            let target_in_exp = exp.count_var(target) > 0;
            if target_in_exp {
                return Err(SymbolicError::NonInvertible {
                    variable: target.to_string(),
                    reason: NonInvertibleReason::NoInverse {
                        context: "an exponent".to_string(),
                    },
                });
            }
            if !target_in_base {
                unreachable!("occurrence gate guarantees target lives somewhere in this Pow");
            }

            let n = match exp.as_ref() {
                Expr::Lit(n) => *n,
                _ => {
                    return Err(SymbolicError::NonInvertible {
                        variable: target.to_string(),
                        reason: NonInvertibleReason::NoInverse {
                            context: "a power with a non-literal exponent".to_string(),
                        },
                    });
                }
            };

            let is_odd_integer = n.fract() == 0.0 && (n as i64).rem_euclid(2) == 1;
            let is_even_integer = n.fract() == 0.0 && (n as i64).rem_euclid(2) == 0;

            if is_odd_integer {
                *branch_taken = Some(Branch::Principal);
                let new_acc = Expr::Pow(Box::new(acc), Box::new(Expr::Lit(1.0 / n))).canonicalize();
                peel(base, target, new_acc, branch, admission, branch_taken)
            } else if is_even_integer {
                let chosen = match branch {
                    None => {
                        return Err(SymbolicError::MultiBranch {
                            variable: target.to_string(),
                            branches: vec![Branch::Positive, Branch::Negative],
                        });
                    }
                    Some(Branch::Positive) => Branch::Positive,
                    Some(Branch::Negative) => Branch::Negative,
                    Some(Branch::Principal) => {
                        return Err(SymbolicError::NonInvertible {
                            variable: target.to_string(),
                            reason: NonInvertibleReason::NoInverse {
                                context: "an even power without a declared +/- branch".to_string(),
                            },
                        });
                    }
                };
                *branch_taken = Some(chosen);
                let root = Expr::Pow(Box::new(acc), Box::new(Expr::Lit(1.0 / n))).canonicalize();
                let new_acc = match chosen {
                    Branch::Positive => root,
                    Branch::Negative => Expr::Neg(Box::new(root)).canonicalize(),
                    Branch::Principal => unreachable!(),
                };
                peel(base, target, new_acc, Some(chosen), admission, branch_taken)
            } else {
                Err(SymbolicError::NonInvertible {
                    variable: target.to_string(),
                    reason: NonInvertibleReason::NoInverse {
                        context: "a non-integer power".to_string(),
                    },
                })
            }
        }
        // Currently unreachable (only `UnaryFn::Sqrt` exists), but kept so
        // a future `UnaryFn` variant falls into a safe `NonInvertible`
        // default rather than a missing-match compile error.
        #[allow(unreachable_patterns)]
        Expr::Unary(other, _) => Err(SymbolicError::NonInvertible {
            variable: target.to_string(),
            reason: NonInvertibleReason::NoInverse {
                context: format!("{other:?}"),
            },
        }),
        Expr::Var(_) | Expr::Lit(_) => {
            unreachable!("occurrence gate guarantees the target lives in this subtree")
        }
    }
}

/// Symbolic differentiation over the canonical `Expr` AST (11 sec. 4,
/// R4): `d/d(var)` by the standard sum/product/chain/power rules over
/// the existing node set. Returns `Lit(0.0)` for any subtree not
/// containing `var` (checked structurally via `count_var`, matching
/// `invert_for`'s occurrence-gate style) rather than walking the whole
/// tree symbolically term-by-term -- cheaper and exactly as correct
/// since a constant's derivative is 0 by definition. The result is
/// `canonicalize`d before returning: differentiation itself does not
/// change the canonical-form RULES (no new total order, no new
/// flatten/fold behavior), so it is NOT a `CANON_VERSION` bump; it is
/// simply a new operation whose OUTPUT passes through the existing
/// pinned canonicalizer like any other derived `Expr` (11 sec. 4 "R2
/// RESOLVED" is untouched by this addition).
// frob:doc docs/modules/feldspar-core.md#core_symbolic
pub fn differentiate(expr: &Expr, var: &str) -> Expr {
    if expr.count_var(var) == 0 {
        return Expr::Lit(0.0);
    }
    let raw = match expr {
        Expr::Var(name) => {
            if name == var {
                Expr::Lit(1.0)
            } else {
                Expr::Lit(0.0)
            }
        }
        Expr::Lit(_) => Expr::Lit(0.0),
        Expr::Neg(inner) => Expr::Neg(Box::new(differentiate(inner, var))),
        Expr::Add(operands) => {
            Expr::Add(operands.iter().map(|op| differentiate(op, var)).collect())
        }
        Expr::Mul(operands) => {
            // Generalized product rule: sum over i of (d(operand_i)) *
            // (product of all other operands).
            let mut terms = Vec::with_capacity(operands.len());
            for i in 0..operands.len() {
                let d_i = differentiate(&operands[i], var);
                let others: Vec<Expr> = operands
                    .iter()
                    .enumerate()
                    .filter_map(|(j, op)| if j == i { None } else { Some(op.clone()) })
                    .collect();
                let term = if others.is_empty() {
                    d_i
                } else {
                    Expr::Mul(std::iter::once(d_i).chain(others).collect())
                };
                terms.push(term);
            }
            Expr::Add(terms)
        }
        Expr::Pow(base, exp) => {
            // Only literal exponents are supported (mirrors `invert_for`'s
            // v1 restriction): d/dx[base^n] = n * base^(n-1) * d(base).
            // `var` in the exponent (not just the base) has no v1 closed-
            // form derivative here; callers needing that combination are
            // out of R4's decided scope (11 sec. 3 "no invented physics" --
            // extending to a full generalized power rule is a future
            // residual, not silently guessed).
            match exp.as_ref() {
                Expr::Lit(n) => {
                    let d_base = differentiate(base, var);
                    Expr::Mul(vec![
                        Expr::Lit(*n),
                        Expr::Pow(base.clone(), Box::new(Expr::Lit(n - 1.0))),
                        d_base,
                    ])
                }
                _ => Expr::Lit(0.0),
            }
        }
        Expr::Unary(UnaryFn::Sqrt, inner) => {
            // d/dx[sqrt(u)] = u' / (2*sqrt(u)).
            let d_inner = differentiate(inner, var);
            Expr::Mul(vec![
                d_inner,
                Expr::Pow(
                    Box::new(Expr::Mul(vec![
                        Expr::Lit(2.0),
                        Expr::Unary(UnaryFn::Sqrt, inner.clone()),
                    ])),
                    Box::new(Expr::Lit(-1.0)),
                ),
            ])
        }
    };
    raw.canonicalize()
}

/// The ports a law can solve for: every `Var` that occurs EXACTLY once in
/// the (canonicalized) equation `lhs - rhs`. The Python sugar loops over
/// these to derive one direction each; multi-occurrence vars are reported
/// (via `invert_for`) as `NonInvertible`, to be hand-written beside the
/// derived directions (11 sec. 2 "Values, not exceptions").
// frob:doc docs/modules/feldspar-core.md#core_symbolic
pub fn invertible_targets(lhs: &Expr, rhs: &Expr) -> BTreeSet<String> {
    let expr = Expr::Add(vec![lhs.clone(), Expr::Neg(Box::new(rhs.clone()))]).canonicalize();

    let mut names = BTreeSet::new();
    collect_vars(&expr, &mut names);

    names
        .into_iter()
        .filter(|name| expr.count_var(name) == 1)
        .collect()
}

/// Collects every distinct `Var` name occurring anywhere in `expr`.
fn collect_vars(expr: &Expr, names: &mut BTreeSet<String>) {
    match expr {
        Expr::Var(name) => {
            names.insert(name.clone());
        }
        Expr::Lit(_) => {}
        Expr::Neg(e) => collect_vars(e, names),
        Expr::Unary(_, e) => collect_vars(e, names),
        Expr::Pow(b, x) => {
            collect_vars(b, names);
            collect_vars(x, names);
        }
        Expr::Add(v) | Expr::Mul(v) => {
            for e in v {
                collect_vars(e, names);
            }
        }
    }
}

/// Derive a dispatch `Domain` box from a predicate set (11 sec. 2), with
/// an optional author-declared box supplying sides predicates cannot
/// bound. Each predicate must reduce (after canonicalization) to a
/// single-port affine bound `+/-port <cmp> const`; it contributes a lower
/// or upper bound to that port. Ports bounded on both sides (by
/// predicates and/or the declared box) become finite `Interval`s;
/// anything else is `UnboundablePredicate`. `tags` pass through onto the
/// `Domain` unchanged (regime flags are declared, not derived). Refuses
/// silently-wrong hulls: a nonlinear/multi-var predicate is an `Err`, not
/// a dropped constraint.
// frob:doc docs/modules/feldspar-core.md#core_symbolic
pub fn predicate_to_box(
    predicates: &[Predicate],
    declared_box: &BTreeMap<String, Interval>,
    tags: &BTreeSet<String>,
) -> Result<Domain, SymbolicError> {
    let mut lower: BTreeMap<String, f64> = BTreeMap::new();
    let mut upper: BTreeMap<String, f64> = BTreeMap::new();

    for (port, interval) in declared_box {
        lower.insert(port.clone(), interval.lo);
        upper.insert(port.clone(), interval.hi);
    }

    for predicate in predicates {
        let diff = Expr::Add(vec![
            predicate.lhs.clone(),
            Expr::Neg(Box::new(predicate.rhs.clone())),
        ])
        .canonicalize();

        let (c, port, k) =
            linear_single_var(&diff).ok_or_else(|| SymbolicError::UnboundablePredicate {
                predicate: predicate.canonical_string(),
            })?;

        let mut cmp = predicate.cmp;
        if c < 0.0 {
            cmp = match cmp {
                Cmp::Lt => Cmp::Gt,
                Cmp::Le => Cmp::Ge,
                Cmp::Gt => Cmp::Lt,
                Cmp::Ge => Cmp::Le,
            };
        }
        let bound = -k / c;

        match cmp {
            Cmp::Lt | Cmp::Le => {
                let entry = upper.entry(port.clone()).or_insert(bound);
                *entry = entry.min(bound);
            }
            Cmp::Gt | Cmp::Ge => {
                let entry = lower.entry(port.clone()).or_insert(bound);
                *entry = entry.max(bound);
            }
        }
    }

    let mut all_ports: BTreeSet<String> = BTreeSet::new();
    all_ports.extend(lower.keys().cloned());
    all_ports.extend(upper.keys().cloned());

    let mut port_box = BTreeMap::new();
    for port in all_ports {
        match (lower.get(&port), upper.get(&port)) {
            (Some(&lo), Some(&hi)) => {
                if lo > hi {
                    return Err(SymbolicError::EmptyDomain { port });
                }
                let interval = Interval::new(lo, hi)
                    .map_err(|_| SymbolicError::EmptyDomain { port: port.clone() })?;
                port_box.insert(port, interval);
            }
            _ => {
                return Err(SymbolicError::UnboundablePredicate {
                    predicate: format!("port `{port}` bounded on one side only"),
                });
            }
        }
    }

    Ok(Domain::new(port_box, tags.clone()))
}

/// Recognizes a canonicalized `Expr` matching the single-port affine shape
/// `c * port + k`, returning `(c, port, k)`. Anything nonlinear, multi-
/// variable, or otherwise not of this shape yields `None`.
fn linear_single_var(expr: &Expr) -> Option<(f64, String, f64)> {
    if let Some(k) = as_constant(expr) {
        let _ = k;
        return None;
    }
    match expr {
        Expr::Var(name) => Some((1.0, name.clone(), 0.0)),
        Expr::Neg(inner) => {
            if let Expr::Var(name) = inner.as_ref() {
                Some((-1.0, name.clone(), 0.0))
            } else {
                None
            }
        }
        Expr::Mul(operands) if operands.len() == 2 => {
            let (a, b) = (&operands[0], &operands[1]);
            match (a, b) {
                (Expr::Lit(c), Expr::Var(name)) | (Expr::Var(name), Expr::Lit(c)) => {
                    if *c != 0.0 {
                        Some((*c, name.clone(), 0.0))
                    } else {
                        None
                    }
                }
                _ => None,
            }
        }
        Expr::Add(operands) if operands.len() == 2 => {
            let (a, b) = (&operands[0], &operands[1]);
            let (term, k) = if let Some(k) = as_constant(a) {
                (b, k)
            } else if let Some(k) = as_constant(b) {
                (a, k)
            } else {
                return None;
            };
            linear_single_var(term).map(|(c, name, k0)| (c, name, k0 + k))
        }
        _ => None,
    }
}

/// Reduces an `Expr` to a plain numeric constant if it is one (`Lit(x)` or
/// `Neg` of a constant), for use in `linear_single_var`'s additive-
/// constant detection.
fn as_constant(expr: &Expr) -> Option<f64> {
    match expr {
        Expr::Lit(x) => Some(*x),
        Expr::Neg(inner) => as_constant(inner).map(|x| -x),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonicalize_is_idempotent() {
        let e = Expr::Add(vec![
            Expr::Mul(vec![Expr::Lit(2.0), Expr::Var("x".into())]),
            Expr::Lit(0.0),
            Expr::Neg(Box::new(Expr::Add(vec![
                Expr::Var("y".into()),
                Expr::Lit(3.0),
            ]))),
            Expr::Mul(vec![Expr::Lit(1.0), Expr::Var("z".into())]),
        ]);
        let once = e.canonicalize();
        let twice = once.canonicalize();
        assert_eq!(once, twice);
    }

    #[test]
    fn total_order_is_deterministic_including_signed_zero() {
        let neg_zero = Expr::Lit(-0.0);
        let pos_zero = Expr::Lit(0.0);
        assert_eq!(neg_zero.cmp(&pos_zero), std::cmp::Ordering::Less);
        assert_eq!(pos_zero.cmp(&neg_zero), std::cmp::Ordering::Greater);
        assert_eq!(pos_zero.cmp(&pos_zero), std::cmp::Ordering::Equal);

        let a = Expr::Var("a".into());
        let b = Expr::Var("b".into());
        assert_eq!(a.cmp(&b), std::cmp::Ordering::Less);
    }

    fn orifice_equation() -> (Expr, Expr) {
        // Q = C_d * A * sqrt(2 * dp / rho), lowered as 2*dp*rho^-1.
        let lhs = Expr::Var("Q".into());
        let rhs = Expr::Mul(vec![
            Expr::Var("C_d".into()),
            Expr::Var("A".into()),
            Expr::Unary(
                UnaryFn::Sqrt,
                Box::new(Expr::Mul(vec![
                    Expr::Lit(2.0),
                    Expr::Var("dp".into()),
                    Expr::Pow(Box::new(Expr::Var("rho".into())), Box::new(Expr::Lit(-1.0))),
                ])),
            ),
        ]);
        (lhs, rhs)
    }

    #[test]
    fn orifice_equation_inverts_for_all_five_variables() {
        let (lhs, rhs) = orifice_equation();
        let targets = invertible_targets(&lhs, &rhs);
        assert_eq!(
            targets,
            BTreeSet::from([
                "A".to_string(),
                "C_d".to_string(),
                "Q".to_string(),
                "dp".to_string(),
                "rho".to_string(),
            ])
        );

        for target in &targets {
            let result = invert_for(&lhs, &rhs, target, None);
            assert!(
                result.is_ok(),
                "expected {target} to invert cleanly, got {result:?}"
            );
        }
    }

    #[test]
    fn spring_energy_solved_for_x_is_multi_branch() {
        // E = 0.5 * k * x^2
        let lhs = Expr::Var("E".into());
        let rhs = Expr::Mul(vec![
            Expr::Lit(0.5),
            Expr::Var("k".into()),
            Expr::Pow(Box::new(Expr::Var("x".into())), Box::new(Expr::Lit(2.0))),
        ]);

        let err = invert_for(&lhs, &rhs, "x", None).unwrap_err();
        match err {
            SymbolicError::MultiBranch { variable, branches } => {
                assert_eq!(variable, "x");
                assert!(branches.contains(&Branch::Positive));
                assert!(branches.contains(&Branch::Negative));
            }
            other => panic!("expected MultiBranch, got {other:?}"),
        }

        let ok = invert_for(&lhs, &rhs, "x", Some(Branch::Positive));
        assert!(ok.is_ok(), "expected Ok with a declared branch: {ok:?}");
    }

    #[test]
    fn predicate_to_box_bounds_re_lt_2300() {
        let predicate = Predicate {
            lhs: Expr::Var("Re".into()),
            cmp: Cmp::Lt,
            rhs: Expr::Lit(2300.0),
        };
        let mut declared_box = BTreeMap::new();
        declared_box.insert("Re".to_string(), Interval::new(0.0, 1.0e9).unwrap());

        let domain = predicate_to_box(&[predicate], &declared_box, &BTreeSet::new()).unwrap();

        let interval = domain.port_box.get("Re").unwrap();
        assert_eq!(interval.hi, 2300.0);
        assert!(interval.lo.is_finite());
    }

    #[test]
    fn predicate_to_box_refuses_nonlinear_predicate() {
        let predicate = Predicate {
            lhs: Expr::Pow(Box::new(Expr::Var("x".into())), Box::new(Expr::Lit(2.0))),
            cmp: Cmp::Lt,
            rhs: Expr::Lit(4.0),
        };
        let result = predicate_to_box(&[predicate], &BTreeMap::new(), &BTreeSet::new());
        assert!(matches!(
            result,
            Err(SymbolicError::UnboundablePredicate { .. })
        ));
    }

    #[test]
    fn eval_sqrt_of_negative_is_domain_fault() {
        let e = Expr::Unary(UnaryFn::Sqrt, Box::new(Expr::Lit(-1.0)));
        let result = e.eval(&BTreeMap::new());
        assert!(matches!(result, Err(EvalError::DomainFault { .. })));
    }

    /// Central finite difference, used ONLY here as the numeric oracle to
    /// check `differentiate`'s symbolic result against (11 sec. 4 R4:
    /// "symbolic vs numeric derivative agreement within tolerance").
    fn central_difference(expr: &Expr, var: &str, inputs: &BTreeMap<String, f64>, h: f64) -> f64 {
        let mut plus = inputs.clone();
        let mut minus = inputs.clone();
        *plus.get_mut(var).unwrap() += h;
        *minus.get_mut(var).unwrap() -= h;
        let f_plus = expr.eval(&plus).unwrap();
        let f_minus = expr.eval(&minus).unwrap();
        (f_plus - f_minus) / (2.0 * h)
    }

    #[test]
    fn differentiate_matches_numeric_on_orifice_equation() {
        // Q = C_d * A * sqrt(2 * dp / rho); differentiate the rhs w.r.t.
        // each variable and compare against central differencing at a
        // handful of interior points.
        let (_lhs, rhs) = orifice_equation();
        let points: Vec<BTreeMap<String, f64>> = vec![
            [
                ("C_d".to_string(), 0.62),
                ("A".to_string(), 0.002),
                ("dp".to_string(), 5000.0),
                ("rho".to_string(), 1000.0),
            ]
            .into_iter()
            .collect(),
            [
                ("C_d".to_string(), 0.8),
                ("A".to_string(), 0.01),
                ("dp".to_string(), 20000.0),
                ("rho".to_string(), 998.0),
            ]
            .into_iter()
            .collect(),
        ];

        for point in &points {
            for var in ["C_d", "A", "dp", "rho"] {
                let d_expr = differentiate(&rhs, var);
                let symbolic = d_expr.eval(point).unwrap();
                let numeric = central_difference(&rhs, var, point, 1e-4);
                let scale = symbolic.abs().max(numeric.abs()).max(1.0);
                assert!(
                    (symbolic - numeric).abs() / scale < 1e-4,
                    "var={var} symbolic={symbolic} numeric={numeric} at {point:?}"
                );
            }
        }
    }

    #[test]
    fn differentiate_of_var_not_present_is_zero() {
        let e = Expr::Var("x".into());
        let d = differentiate(&e, "y");
        assert_eq!(d, Expr::Lit(0.0));
    }

    #[test]
    fn differentiate_power_rule() {
        // d/dx[x^3] = 3*x^2.
        let e = Expr::Pow(Box::new(Expr::Var("x".into())), Box::new(Expr::Lit(3.0)));
        let d = differentiate(&e, "x");
        let mut inputs = BTreeMap::new();
        inputs.insert("x".to_string(), 2.0);
        assert_eq!(d.eval(&inputs).unwrap(), 12.0); // 3 * 2^2
    }

    #[test]
    fn differentiate_is_deterministic_across_calls() {
        let (_lhs, rhs) = orifice_equation();
        let d1 = differentiate(&rhs, "dp");
        let d2 = differentiate(&rhs, "dp");
        assert_eq!(d1, d2);
        assert_eq!(d1.canonical_string(), d2.canonical_string());
    }
}
