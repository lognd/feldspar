//! `Dimension`: a vector of integer exponents over the seven SI base
//! dimensions (02-quantities "Unit algebra").

/// SI base dimension vector, ordered `[length, mass, time, current,
/// temperature, amount, luminous_intensity]` (m, kg, s, A, K, mol, cd).
// frob:doc docs/modules/feldspar-core.md#core_dimension
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Dimension {
    pub exponents: [i8; 7],
}

impl Dimension {
    // frob:doc docs/modules/feldspar-core.md#core_dimension
    pub const DIMENSIONLESS: Dimension = Dimension { exponents: [0; 7] };

    // frob:doc docs/modules/feldspar-core.md#core_dimension
    pub const fn new(exponents: [i8; 7]) -> Self {
        Self { exponents }
    }

    /// Componentwise sum; the dimension of a product of two quantities.
    // frob:doc docs/modules/feldspar-core.md#core_dimension
    pub fn mul(&self, other: &Dimension) -> Dimension {
        let mut out = [0i8; 7];
        for (o, (a, b)) in out
            .iter_mut()
            .zip(self.exponents.iter().zip(other.exponents.iter()))
        {
            *o = a + b;
        }
        Dimension::new(out)
    }

    /// Componentwise difference; the dimension of a quotient.
    // frob:doc docs/modules/feldspar-core.md#core_dimension
    pub fn div(&self, other: &Dimension) -> Dimension {
        let mut out = [0i8; 7];
        for (o, (a, b)) in out
            .iter_mut()
            .zip(self.exponents.iter().zip(other.exponents.iter()))
        {
            *o = a - b;
        }
        Dimension::new(out)
    }
}
