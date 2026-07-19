//! Cross-section geometric property formulas (area moment of inertia,
//! etc.). Same AD-3 `#[no_mangle] pub extern "C" fn` discipline as the
//! rest of `mech` (see `mech/mod.rs` doc comment).
//!
//! The workspace denies `unsafe_code`, but `#[no_mangle]` on an
//! `extern "C" fn` requires an explicit, function-scoped
//! `#[allow(unsafe_code)]` (AD-3's whole point is these symbols being
//! link-visible via a C ABI, which is what the lint is warning about);
//! the allow is scoped to each function, not the module, so it cannot
//! silently mask an unrelated unsafe block elsewhere in this file.

/// Second moment of area (area moment of inertia) of a rectangular
/// cross-section about its centroidal axis: `I = width * height^3 / 12`.
///
/// Citation: Gere, *Mechanics of Materials*, 9th ed., App. E
/// (rectangular section, second moment about centroidal axis).
// frob:doc docs/modules/feldspar-library.md#library_mech_sections
#[allow(unsafe_code)]
#[no_mangle]
pub extern "C" fn rect_second_moment(width: f64, height: f64) -> f64 {
    width * height.powi(3) / 12.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rect_second_moment_matches_textbook_formula() {
        // Gere 9e App. E: I = b*h^3/12 for a 0.04 m x 0.06 m rectangle.
        let expected = 0.04 * 0.06_f64.powi(3) / 12.0;
        assert!((rect_second_moment(0.04, 0.06) - expected).abs() < 1e-15);
    }
}
