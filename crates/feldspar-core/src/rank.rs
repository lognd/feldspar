//! `Rank` and `PortDecl`: non-scalar quantity shape declarations
//! (02-quantities "Non-scalar and structured quantities").

/// The shape of a port's uncertain value. `Payload` is reserved for M2
/// (09 sec. 4 payload ports); the arm exists so registration code can
/// match exhaustively today without a breaking enum change later.
// frob:doc docs/modules/feldspar-core.md#core_rank
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Default)]
pub enum Rank {
    #[default]
    Scalar,
    Complex,
    Vector(u32),
    Tensor(u32, u32),
    /// Reserved for M2 (09 sec. 4); `kind` names the payload's exact-by-
    /// reference content type. Not constructed or matched on elsewhere
    /// in M1.
    Payload(String),
}

/// A namespaced port declaration: name, coherent-SI unit label, and rank
/// (02-quantities "Ports").
// frob:doc docs/modules/feldspar-core.md#core_rank
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct PortDecl {
    pub name: String,
    pub unit: String,
    pub rank: Rank,
}

impl PortDecl {
    // frob:doc docs/modules/feldspar-core.md#core_rank
    pub fn new(name: impl Into<String>, unit: impl Into<String>, rank: Rank) -> Self {
        Self {
            name: name.into(),
            unit: unit.into(),
            rank,
        }
    }

    /// A scalar port declaration; the common case (all M1 ports, 01-interfaces).
    // frob:doc docs/modules/feldspar-core.md#core_rank
    pub fn scalar(name: impl Into<String>, unit: impl Into<String>) -> Self {
        Self::new(name, unit, Rank::Scalar)
    }
}
