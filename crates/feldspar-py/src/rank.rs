//! PyO3 wrapper for `feldspar_core::Rank` and `PortDecl` (01-interfaces
//! `Rank`, `PortDecl`).
//!
//! `Rank` is a Rust enum with per-variant payloads (`Vector(n)`,
//! `Tensor(n, m)`); PyO3 0.22's data-carrying "complex enum" support is
//! new enough that we take the lower-risk, well-understood path here:
//! one frozen class tagged by `kind`, with optional fields for the
//! variant's payload, plus `scalar()`/`complex()`/`vector(n)`/
//! `tensor(n, m)`/`payload(kind)` constructors mirroring the enum's
//! shape (01-interfaces "SCALAR|COMPLEX|VECTOR(n)|TENSOR(n,m)"). Flagged
//! as a WO-02 deviation in the closing report -- worth revisiting once a
//! native complex-enum binding is verified stable at the pinned pyo3
//! version.

use pyo3::basic::CompareOp;
use pyo3::prelude::*;

/// Tagged rank value; see module docs for the tagged-struct rationale.
#[pyclass(frozen, name = "Rank", get_all)]
#[derive(Clone, PartialEq, Eq, Hash)]
pub struct PyRank {
    pub kind: String,
    pub n: Option<u32>,
    pub m: Option<u32>,
    pub payload_kind: Option<String>,
}

impl From<feldspar_core::Rank> for PyRank {
    fn from(r: feldspar_core::Rank) -> Self {
        use feldspar_core::Rank::*;
        match r {
            Scalar => PyRank {
                kind: "scalar".to_string(),
                n: None,
                m: None,
                payload_kind: None,
            },
            Complex => PyRank {
                kind: "complex".to_string(),
                n: None,
                m: None,
                payload_kind: None,
            },
            Vector(n) => PyRank {
                kind: "vector".to_string(),
                n: Some(n),
                m: None,
                payload_kind: None,
            },
            Tensor(n, m) => PyRank {
                kind: "tensor".to_string(),
                n: Some(n),
                m: Some(m),
                payload_kind: None,
            },
            Payload(kind) => PyRank {
                kind: "payload".to_string(),
                n: None,
                m: None,
                payload_kind: Some(kind),
            },
        }
    }
}

impl PyRank {
    pub fn to_core(&self) -> feldspar_core::Rank {
        match self.kind.as_str() {
            "scalar" => feldspar_core::Rank::Scalar,
            "complex" => feldspar_core::Rank::Complex,
            "vector" => feldspar_core::Rank::Vector(self.n.unwrap_or(0)),
            "tensor" => feldspar_core::Rank::Tensor(self.n.unwrap_or(0), self.m.unwrap_or(0)),
            "payload" => {
                feldspar_core::Rank::Payload(self.payload_kind.clone().unwrap_or_default())
            }
            other => unreachable!("PyRank constructed with unknown kind {other:?}"),
        }
    }
}

#[pymethods]
impl PyRank {
    #[staticmethod]
    fn scalar() -> Self {
        feldspar_core::Rank::Scalar.into()
    }

    #[staticmethod]
    fn complex() -> Self {
        feldspar_core::Rank::Complex.into()
    }

    #[staticmethod]
    fn vector(n: u32) -> Self {
        feldspar_core::Rank::Vector(n).into()
    }

    #[staticmethod]
    fn tensor(n: u32, m: u32) -> Self {
        feldspar_core::Rank::Tensor(n, m).into()
    }

    /// Reserved for M2 (09 sec. 4); not used elsewhere in M1.
    #[staticmethod]
    fn payload(kind: String) -> Self {
        feldspar_core::Rank::Payload(kind).into()
    }

    fn __repr__(&self) -> String {
        match self.kind.as_str() {
            "vector" => format!("Rank.vector({})", self.n.unwrap_or(0)),
            "tensor" => format!(
                "Rank.tensor({}, {})",
                self.n.unwrap_or(0),
                self.m.unwrap_or(0)
            ),
            "payload" => format!(
                "Rank.payload({:?})",
                self.payload_kind.clone().unwrap_or_default()
            ),
            kind => format!("Rank.{kind}()"),
        }
    }

    fn __richcmp__(&self, other: &PyRank, op: CompareOp) -> PyResult<bool> {
        match op {
            CompareOp::Eq => Ok(self == other),
            CompareOp::Ne => Ok(self != other),
            _ => Err(pyo3::exceptions::PyTypeError::new_err(
                "Rank only supports == and !=",
            )),
        }
    }

    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        self.hash(&mut hasher);
        hasher.finish()
    }
}

/// Frozen namespaced port declaration: name, coherent-SI unit label, rank.
#[pyclass(frozen, name = "PortDecl", get_all)]
#[derive(Clone, PartialEq, Eq, Hash)]
pub struct PyPortDecl {
    pub name: String,
    pub unit: String,
    pub rank: PyRank,
}

#[pymethods]
impl PyPortDecl {
    #[new]
    #[pyo3(signature = (name, unit, rank=None))]
    fn py_new(name: String, unit: String, rank: Option<PyRank>) -> Self {
        PyPortDecl {
            name,
            unit,
            rank: rank.unwrap_or_else(PyRank::scalar),
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "PortDecl(name={:?}, unit={:?}, rank={})",
            self.name,
            self.unit,
            self.rank.__repr__()
        )
    }

    fn __richcmp__(&self, other: &PyPortDecl, op: CompareOp) -> PyResult<bool> {
        match op {
            CompareOp::Eq => Ok(self == other),
            CompareOp::Ne => Ok(self != other),
            _ => Err(pyo3::exceptions::PyTypeError::new_err(
                "PortDecl only supports == and !=",
            )),
        }
    }

    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        self.hash(&mut hasher);
        hasher.finish()
    }
}
