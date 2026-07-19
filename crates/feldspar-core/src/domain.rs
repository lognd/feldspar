//! `Domain`: where a solver may be trusted (02-quantities "Domains").

use std::collections::{BTreeMap, BTreeSet};

use crate::interval::Interval;

/// Why an `admits()` check failed; carries enough detail to explain the
/// rejection (01-interfaces: "DomainViolation carries port/tag details").
// frob:doc docs/modules/feldspar-core.md#core_domain
#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum DomainViolation {
    /// A required port was not supplied by the caller at all.
    #[error("domain requires port `{port}` but no value was supplied")]
    MissingInput { port: String },
    /// A supplied interval is not a subset of the domain's box entry for
    /// that port (the whole corner sweep must sit inside, not one corner).
    #[error("port `{port}` value [{lo}, {hi}] is not inside domain box [{box_lo}, {box_hi}]")]
    OutOfBox {
        port: String,
        lo: f64,
        hi: f64,
        box_lo: f64,
        box_hi: f64,
    },
    /// The caller's tag set is missing a tag the domain requires.
    #[error("domain requires tag `{tag}` which the caller did not supply")]
    MissingTag { tag: String },
}

/// A solver's validity region: a box of per-port allowed intervals plus
/// free-string regime tags. BTree-backed for deterministic, sorted
/// iteration (FINV-1) since domains feed digests.
// frob:doc docs/modules/feldspar-core.md#core_domain
#[derive(Debug, Clone, PartialEq, Default)]
pub struct Domain {
    pub port_box: BTreeMap<String, Interval>,
    pub tags: BTreeSet<String>,
}

impl Domain {
    // frob:doc docs/modules/feldspar-core.md#core_domain
    pub fn new(port_box: BTreeMap<String, Interval>, tags: BTreeSet<String>) -> Self {
        Self { port_box, tags }
    }

    /// `Ok(())` iff every box entry has a supplied, subset-matching input
    /// and every required tag is present in the caller's tag set. Checked
    /// in sorted (BTree) order so the first violation is deterministic.
    // frob:doc docs/modules/feldspar-core.md#core_domain
    pub fn admits(
        &self,
        inputs: &BTreeMap<String, Interval>,
        tags: &BTreeSet<String>,
    ) -> Result<(), DomainViolation> {
        for required_tag in &self.tags {
            if !tags.contains(required_tag) {
                return Err(DomainViolation::MissingTag {
                    tag: required_tag.clone(),
                });
            }
        }
        for (port, allowed) in &self.port_box {
            match inputs.get(port) {
                None => {
                    return Err(DomainViolation::MissingInput { port: port.clone() });
                }
                Some(value) => {
                    if !value.is_subset(allowed) {
                        return Err(DomainViolation::OutOfBox {
                            port: port.clone(),
                            lo: value.lo,
                            hi: value.hi,
                            box_lo: allowed.lo,
                            box_hi: allowed.hi,
                        });
                    }
                }
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_domain() -> Domain {
        let mut port_box = BTreeMap::new();
        port_box.insert(
            "mech.load.tip_force".to_string(),
            Interval::new(0.0, 100.0).unwrap(),
        );
        let mut tags = BTreeSet::new();
        tags.insert("linear_elastic".to_string());
        Domain::new(port_box, tags)
    }

    #[test]
    fn admits_full_subset_and_tags() {
        let domain = make_domain();
        let mut inputs = BTreeMap::new();
        inputs.insert(
            "mech.load.tip_force".to_string(),
            Interval::new(10.0, 20.0).unwrap(),
        );
        let mut tags = BTreeSet::new();
        tags.insert("linear_elastic".to_string());
        assert_eq!(domain.admits(&inputs, &tags), Ok(()));
    }

    #[test]
    fn admits_rejects_out_of_box_whole_sweep() {
        let domain = make_domain();
        let mut inputs = BTreeMap::new();
        // partially outside the box (upper bound exceeds 100)
        inputs.insert(
            "mech.load.tip_force".to_string(),
            Interval::new(10.0, 200.0).unwrap(),
        );
        let mut tags = BTreeSet::new();
        tags.insert("linear_elastic".to_string());
        assert!(matches!(
            domain.admits(&inputs, &tags),
            Err(DomainViolation::OutOfBox { .. })
        ));
    }

    #[test]
    fn admits_rejects_missing_tag() {
        let domain = make_domain();
        let mut inputs = BTreeMap::new();
        inputs.insert(
            "mech.load.tip_force".to_string(),
            Interval::new(10.0, 20.0).unwrap(),
        );
        let tags = BTreeSet::new();
        assert!(matches!(
            domain.admits(&inputs, &tags),
            Err(DomainViolation::MissingTag { .. })
        ));
    }

    #[test]
    fn admits_rejects_missing_input() {
        let domain = make_domain();
        let inputs = BTreeMap::new();
        let mut tags = BTreeSet::new();
        tags.insert("linear_elastic".to_string());
        assert!(matches!(
            domain.admits(&inputs, &tags),
            Err(DomainViolation::MissingInput { .. })
        ));
    }
}
