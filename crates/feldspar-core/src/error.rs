//! `CoreError` and `UnitError`: total error variants for the quantity core
//! (01-interfaces `feldspar.core`; FINV-5 -- error values, never exceptions).

/// Errors from `Interval` construction (01-interfaces `CoreError`).
#[derive(Debug, Clone, Copy, PartialEq, thiserror::Error)]
pub enum CoreError {
    /// A bound was NaN or +/-infinity.
    #[error("non-finite interval bound: {0}")]
    NonFiniteBound(f64),
    /// `lo > hi`.
    #[error("inverted interval: lo {lo} > hi {hi}")]
    InvertedInterval { lo: f64, hi: f64 },
}

/// Errors from `UnitSystem` lookups and table construction (01-interfaces
/// `UnitError`; FINV-11 -- storage is coherent SI, conversion at the
/// ingest/print boundary only).
#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum UnitError {
    /// The unit label has no table entry; never guessed (02-edge-cases).
    #[error("unknown unit `{0}`")]
    UnknownUnit(String),
    /// Two units named in the same expression have incompatible dimensions.
    #[error("incompatible dimensions: `{a}` vs `{b}`")]
    IncompatibleDimensions { a: String, b: String },
    /// An affine (offset) unit was used as a component of a compound unit
    /// (friction G3: `degC/W` is a table-load error, `K/W` is fine).
    #[error("offset unit `{0}` is not allowed inside a compound unit")]
    OffsetInCompound(String),
}
