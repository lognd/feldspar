//! `UnitSystem`: unit label -> (Dimension, scale-to-coherent-SI), ingest/
//! print conversion ONLY (02-quantities "Unit algebra", FINV-11). The
//! built-in table is `feldspar-core`'s dependency-free default; regolith-
//! qty may back the same protocol when regolith is installed (FINV-3).

use std::collections::BTreeMap;

use crate::dimension::Dimension;
use crate::error::UnitError;

/// One table entry: `to_si(v) = v * scale + offset`; `from_si(v) = (v -
/// offset) / scale`. Only ingest/print-legal (affine) units carry a
/// nonzero `offset` (degC, degF); every derived/compound unit must be
/// built from zero-offset components (FINV-11, G3).
#[derive(Debug, Clone, PartialEq)]
struct UnitEntry {
    dimension: Dimension,
    scale: f64,
    offset: f64,
}

impl UnitEntry {
    const fn simple(dimension: Dimension, scale: f64) -> Self {
        Self {
            dimension,
            scale,
            offset: 0.0,
        }
    }

    const fn affine(dimension: Dimension, scale: f64, offset: f64) -> Self {
        Self {
            dimension,
            scale,
            offset,
        }
    }

    fn is_affine(&self) -> bool {
        self.offset != 0.0
    }
}

/// The unit dimension-lookup/conversion/compatibility protocol
/// (01-interfaces `UnitSystem`). An interface, not a hard dependency
/// (02-quantities): `feldspar-core`'s built-in table is one
/// implementation; regolith-qty may back another.
// frob:doc docs/modules/feldspar-core.md#core_units
pub trait UnitSystem {
    fn dimension_of(&self, unit: &str) -> Result<Dimension, UnitError>;
    fn to_si(&self, value: f64, unit: &str) -> Result<f64, UnitError>;
    // Name is the 01-interfaces normative signature, not a `From` conversion.
    #[allow(clippy::wrong_self_convention)]
    fn from_si(&self, value: f64, unit: &str) -> Result<f64, UnitError>;
    fn compatible(&self, a: &str, b: &str) -> bool;
}

/// The built-in, dependency-free `UnitSystem` implementation. Seeded
/// with every unit named in 01-interfaces' M1 port table plus its ingest
/// aliases, the 02-edge-cases rows, and K/W-style compounds for Phase 2.
// frob:doc docs/modules/feldspar-core.md#core_units
#[derive(Debug, Clone)]
pub struct BuiltinUnitSystem {
    table: BTreeMap<String, UnitEntry>,
}

/// SI base dimension helper constants (m, kg, s, A, K, mol, cd order).
mod dim {
    use crate::dimension::Dimension;

    // frob:doc docs/modules/feldspar-core.md#core_units
    pub const DIMENSIONLESS: Dimension = Dimension::new([0, 0, 0, 0, 0, 0, 0]);
    // frob:doc docs/modules/feldspar-core.md#core_units
    pub const LENGTH: Dimension = Dimension::new([1, 0, 0, 0, 0, 0, 0]);
    // frob:doc docs/modules/feldspar-core.md#core_units
    pub const TEMPERATURE: Dimension = Dimension::new([0, 0, 0, 0, 1, 0, 0]);
    // force = kg*m/s^2
    // frob:doc docs/modules/feldspar-core.md#core_units
    pub const FORCE: Dimension = Dimension::new([1, 1, -2, 0, 0, 0, 0]);
    // pressure = kg/(m*s^2)
    // frob:doc docs/modules/feldspar-core.md#core_units
    pub const PRESSURE: Dimension = Dimension::new([-1, 1, -2, 0, 0, 0, 0]);
    // angular rate = 1/s (radian is dimensionless)
    // frob:doc docs/modules/feldspar-core.md#core_units
    pub const ANGULAR_RATE: Dimension = Dimension::new([0, 0, -1, 0, 0, 0, 0]);
    // velocity = m/s
    // frob:doc docs/modules/feldspar-core.md#core_units
    pub const VELOCITY: Dimension = Dimension::new([1, 0, -1, 0, 0, 0, 0]);
    // power = kg*m^2/s^3
    // frob:doc docs/modules/feldspar-core.md#core_units
    pub const POWER: Dimension = Dimension::new([2, 1, -3, 0, 0, 0, 0]);
}

/// Standard gravity, g0 (m/s^2); the Isp "seconds" view's reference
/// scale (G31).
const G0: f64 = 9.80665;

impl BuiltinUnitSystem {
    /// Builds the seeded table (02/07 Phase 1-2 ports + 01-interfaces'
    /// required alias/edge-case list). Compound entries are composed
    /// from already-registered simple entries so an accidental
    /// offset-in-compound is caught here, at table-build time, exactly
    /// once (FINV-11).
    // frob:doc docs/modules/feldspar-core.md#core_units
    pub fn builtin() -> Self {
        let mut table = BTreeMap::new();

        let mut insert = |label: &str, entry: UnitEntry| {
            table.insert(label.to_string(), entry);
        };

        // Dimensionless and its ingest aliases.
        insert("1", UnitEntry::simple(dim::DIMENSIONLESS, 1.0));
        insert("%", UnitEntry::simple(dim::DIMENSIONLESS, 0.01));
        insert("rad", UnitEntry::simple(dim::DIMENSIONLESS, 1.0));
        insert(
            "deg",
            UnitEntry::simple(dim::DIMENSIONLESS, std::f64::consts::PI / 180.0),
        );

        // Length.
        insert("m", UnitEntry::simple(dim::LENGTH, 1.0));
        insert("mm", UnitEntry::simple(dim::LENGTH, 1e-3));

        // Temperature: K is coherent SI; degC/degF are affine, ingest/
        // print-legal only (G3, FINV-11).
        insert("K", UnitEntry::simple(dim::TEMPERATURE, 1.0));
        insert("degC", UnitEntry::affine(dim::TEMPERATURE, 1.0, 273.15));
        insert(
            "degF",
            UnitEntry::affine(dim::TEMPERATURE, 5.0 / 9.0, 273.15 - 32.0 * 5.0 / 9.0),
        );

        // Force and its ingest alias.
        insert("N", UnitEntry::simple(dim::FORCE, 1.0));
        insert("kN", UnitEntry::simple(dim::FORCE, 1e3));

        // Pressure/stress and its ingest aliases.
        insert("Pa", UnitEntry::simple(dim::PRESSURE, 1.0));
        insert("kPa", UnitEntry::simple(dim::PRESSURE, 1e3));
        insert("MPa", UnitEntry::simple(dim::PRESSURE, 1e6));
        insert("GPa", UnitEntry::simple(dim::PRESSURE, 1e9));

        // Angular rate and its ingest alias (G19: rpm -> rad/s).
        insert("rad/s", UnitEntry::simple(dim::ANGULAR_RATE, 1.0));
        insert(
            "rpm",
            UnitEntry::simple(dim::ANGULAR_RATE, std::f64::consts::PI / 30.0),
        );

        // Velocity and the g0-referenced Isp "seconds" view (G31): Isp
        // is physically a velocity; "s(Isp)" ingests/prints it divided
        // by g0 while the stored value is always coherent-SI m/s.
        insert("m/s", UnitEntry::simple(dim::VELOCITY, 1.0));
        insert("s(Isp)", UnitEntry::simple(dim::VELOCITY, G0));

        // Power, and the K/W thermal-resistance compound seeded for
        // Phase 2 (07). Composed from zero-offset components, so this
        // never trips OffsetInCompound; degC/W would (see units.rs
        // tests / 02-edge-cases).
        insert("W", UnitEntry::simple(dim::POWER, 1.0));
        let k_per_w = Self::compose_div(
            &UnitEntry::simple(dim::TEMPERATURE, 1.0),
            &UnitEntry::simple(dim::POWER, 1.0),
        )
        .expect("K and W are both zero-offset by construction");
        insert("K/W", k_per_w);

        Self { table }
    }

    /// Composes `a / b` into a new (unlabeled) entry: dimensions
    /// subtract, scales divide. `Err(OffsetInCompound)` if either
    /// component is affine -- the one place a compound unit is
    /// validated against FINV-11 (02-edge-cases: `degC/W` at table
    /// load).
    fn compose_div(a: &UnitEntry, b: &UnitEntry) -> Result<UnitEntry, UnitError> {
        if a.is_affine() {
            return Err(UnitError::OffsetInCompound("<numerator>".to_string()));
        }
        if b.is_affine() {
            return Err(UnitError::OffsetInCompound("<denominator>".to_string()));
        }
        Ok(UnitEntry::simple(
            a.dimension.div(&b.dimension),
            a.scale / b.scale,
        ))
    }

    fn lookup(&self, unit: &str) -> Result<&UnitEntry, UnitError> {
        self.table
            .get(unit)
            .ok_or_else(|| UnitError::UnknownUnit(unit.to_string()))
    }
}

impl Default for BuiltinUnitSystem {
    fn default() -> Self {
        Self::builtin()
    }
}

impl UnitSystem for BuiltinUnitSystem {
    fn dimension_of(&self, unit: &str) -> Result<Dimension, UnitError> {
        Ok(self.lookup(unit)?.dimension)
    }

    fn to_si(&self, value: f64, unit: &str) -> Result<f64, UnitError> {
        let entry = self.lookup(unit)?;
        Ok(value * entry.scale + entry.offset)
    }

    fn from_si(&self, value: f64, unit: &str) -> Result<f64, UnitError> {
        let entry = self.lookup(unit)?;
        Ok((value - entry.offset) / entry.scale)
    }

    fn compatible(&self, a: &str, b: &str) -> bool {
        match (self.lookup(a), self.lookup(b)) {
            (Ok(ea), Ok(eb)) => ea.dimension == eb.dimension,
            _ => false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // frob:tests crates/feldspar-core/src/units.rs::BuiltinUnitSystem.builtin kind="unit"
    #[test]
    fn degc_to_si_applies_offset() {
        let sys = BuiltinUnitSystem::builtin();
        assert!((sys.to_si(25.0, "degC").unwrap() - 298.15).abs() < 1e-9);
    }

    #[test]
    fn degc_inside_compound_is_offset_in_compound_err() {
        let sys = BuiltinUnitSystem::builtin();
        let degc = sys.table.get("degC").unwrap().clone();
        let w = sys.table.get("W").unwrap().clone();
        let err = BuiltinUnitSystem::compose_div(&degc, &w).unwrap_err();
        assert!(matches!(err, UnitError::OffsetInCompound(_)));
    }

    #[test]
    fn percent_ingest_is_scale_001_to_dimensionless() {
        let sys = BuiltinUnitSystem::builtin();
        assert!((sys.to_si(1.0, "%").unwrap() - 0.01).abs() < 1e-12);
        assert_eq!(
            sys.dimension_of("%").unwrap(),
            sys.dimension_of("1").unwrap()
        );
    }

    #[test]
    fn unknown_unit_is_err_never_a_guess() {
        let sys = BuiltinUnitSystem::builtin();
        assert!(matches!(
            sys.to_si(1.0, "furlong"),
            Err(UnitError::UnknownUnit(_))
        ));
    }

    #[test]
    fn rpm_to_si_matches_g19() {
        let sys = BuiltinUnitSystem::builtin();
        let got = sys.to_si(6000.0, "rpm").unwrap();
        assert!((got - 628.3185307).abs() < 1e-6);
    }

    #[test]
    fn isp_seconds_view_round_trips_through_stored_mps() {
        let sys = BuiltinUnitSystem::builtin();
        let stored = sys.to_si(285.0, "s(Isp)").unwrap();
        assert!((stored - 285.0 * G0).abs() < 1e-9);
        let printed = sys.from_si(stored, "s(Isp)").unwrap();
        assert!((printed - 285.0).abs() < 1e-9);
    }

    #[test]
    fn k_per_w_compound_is_dimensionally_consistent_and_offset_free() {
        let sys = BuiltinUnitSystem::builtin();
        let k_per_w = sys.dimension_of("K/W").unwrap();
        let k = sys.dimension_of("K").unwrap();
        let w = sys.dimension_of("W").unwrap();
        assert_eq!(k_per_w, k.div(&w));
    }

    #[test]
    fn mpa_ingest_converts_to_pa() {
        let sys = BuiltinUnitSystem::builtin();
        assert!((sys.to_si(1.0, "MPa").unwrap() - 1e6).abs() < 1e-6);
        assert!(sys.compatible("MPa", "Pa"));
    }

    #[test]
    fn incompatible_dimensions_are_not_compatible() {
        let sys = BuiltinUnitSystem::builtin();
        assert!(!sys.compatible("Pa", "m"));
    }
}
