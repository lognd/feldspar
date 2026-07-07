# WO-02: Quantity core (Rust)

Status: todo
Depends: WO-01
Language: Rust (`feldspar-core`), PyO3 exposure in `feldspar-py`
Spec: 02 (all sections), 00-architecture AD-1/2/5, FINV-11

## Goal

The frozen, deterministic core types every other WO consumes:
intervals, accuracy, domains, ports with rank, dimensions, units,
digests.

## Deliverables

- `Interval` (lo <= hi, finite; constructors return Result),
  `Accuracy` (eps_abs/eps_rel, `eps(v)` evaluation), `Domain`
  (BTreeMap box + BTreeSet tags; `admits(inputs) -> Result`),
  `PortDecl` with `Rank` (Scalar | Complex | Vector(n) |
  Tensor(n, m); Payload kinds are M2, leave the enum arm reserved),
  `Dimension` ([i8; 7]).
- `UnitSystem` trait + built-in implementation: unit label ->
  (Dimension, scale-to-coherent-SI); compatibility check; ingest/
  print conversion ONLY (FINV-11 -- no convert-on-stored-value API
  exists). Seed the table with every unit named in 02/07 Phase 1-2
  ports.
- Digest home: canonical-JSON -> blake3 (AD-5), exposed to Python as
  `feldspar.solve.digest`.
- PyO3: all types as frozen classes, same field names, no Python
  mirrors (AD-2); `__repr__`, `__hash__`, equality; shortest
  round-trip f64 formatting helper (`format_f64`, the 05 deck's one
  home, lives here).
- Property tests (proptest): interval ordering/finiteness, domain
  subset logic, digest stability across map insertion orders,
  unit round-trips.

## Acceptance

- `cargo test` + Python-side type smoke tests green.
- Digest of a reference struct is byte-stable across platforms (CI
  matrix compares) and map orderings.
- Registering the 02 port-table sample and converting a MPa ingest
  to Pa works; a dimension mismatch is an Err value.
