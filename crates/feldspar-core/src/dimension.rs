//! `Dimension`: a vector of integer exponents over the seven SI base
//! dimensions (02-quantities "Unit algebra").

/// SI base dimension vector, ordered `[length, mass, time, current,
/// temperature, amount, luminous_intensity]` (m, kg, s, A, K, mol, cd).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Dimension {
    pub exponents: [i8; 7],
}

impl Dimension {
    pub const DIMENSIONLESS: Dimension = Dimension { exponents: [0; 7] };

    pub const fn new(exponents: [i8; 7]) -> Self {
        Self { exponents }
    }

    /// Componentwise sum; the dimension of a product of two quantities.
    pub fn mul(&self, other: &Dimension) -> Dimension {
        let mut out = [0i8; 7];
        for i in 0..7 {
            out[i] = self.exponents[i] + other.exponents[i];
        }
        Dimension::new(out)
    }

    /// Componentwise difference; the dimension of a quotient.
    pub fn div(&self, other: &Dimension) -> Dimension {
        let mut out = [0i8; 7];
        for i in 0..7 {
            out[i] = self.exponents[i] - other.exponents[i];
        }
        Dimension::new(out)
    }
}
