# 02 -- Quantities and uncertainty

One sentence: every quantity is a named port carrying an uncertain
value in coherent SI units -- an interval in v1, a distribution behind
the same propagation protocol later -- and total error splits into
propagated input uncertainty (the engine's job) and declared model
error (the solver's job).

## Ports

A **port** is a dotted, namespaced quantity name with a fixed unit:

```
mech.stress.von_mises      Pa
mech.deflection.tip        m
thermo.pressure            Pa
thermo.temperature         K
thermo.specific_volume     m^3/kg
```

- Names are `namespace(.sub)*.quantity`, ASCII, lowercase, `_` words.
- The unit is a label in coherent SI (no prefixes: Pa not MPa, m not
  mm). Values are STORED and computed in coherent SI always;
  conversion exists only at the boundary (below). Connecting two ports
  with incompatible dimensions is an error value, never a silent cast.
- The port table is data owned by whoever registers solvers touching
  it; the engine only requires that two solvers naming the same port
  mean the same quantity in the same unit. Duplicate port declarations
  with conflicting units are a registration error.

## Unit algebra (DECIDED 2026-07-07, closes OPEN-1)

`feldspar-core` owns a small unit core: a `Dimension` (vector of
integer exponents over the seven SI base dimensions) per unit label,
and a conversion table (scale factor to the coherent SI unit of that
dimension). Two rules:

- **Storage is coherent SI.** Conversion happens at parse/ingest and
  print time only; solvers, propagation, digests, and caches never see
  a non-coherent value. (This mirrors regolith's log-view rule,
  regolith/02 sec. 5a: views affect IO, never the stored value.)
- **Affine units convert at ingest only** (friction G3,
  examples/lithos/feldspar-fixtures.md): table entries are (scale, offset);
  offset units (`degC`, `degF`) are legal at ingest/print and BANNED
  inside derived/compound units (`K/W` fine, `degC/W` is a table-load
  error). The dimensionless unit is `"1"`; `%` is an ingest alias
  for 0.01 (friction G11).
- **The unit core is an interface, not a hard dependency.** The
  `UnitSystem` protocol (dimension lookup, conversion, compatibility
  check) is implemented by the built-in table, and MAY be backed by
  regolith-qty's Rust quantity core when regolith is installed -- but
  the built-in keeps `feldspar-core` dependency-free (FINV-3). The
  pack's test session validates the built-in table against
  regolith-qty over every unit the port table names, so the two
  systems cannot silently disagree.

Dimensional analysis at registration: a solver whose declared ports
mix dimensions inconsistently with the port table is a registration
error, before any solve runs.

## Values are uncertain; intervals are the v1 representation

A known quantity is an **uncertain value**: a representation of spread
plus the rule for pushing that spread through a solver. Uncertainty
representations live behind ONE `Propagation` protocol in
`feldspar-core` (DECIDED 2026-07-07, part of closing OPEN-1):

- **Interval** `[lo, hi]` (`lo <= hi`, both finite f64) -- worst-case
  bounds propagated by deterministic corner sweep. The v1
  representation, and the ONLY one that crosses the pack boundary.
  A point value is the degenerate interval `[x, x]`. Measurement
  uncertainty, tolerance bands, and swept design ranges are all
  encoded as interval width by the caller.
- **Normal** (mean + standard deviation) -- first-order (delta-method)
  propagation via differentiation of the solver: analytic derivative
  when the solver declares one, deterministic central finite
  difference otherwise. Planned, not v1.
- **Quantile bands** (deciles, quartiles, arbitrary p-grids) --
  empirical propagation by deterministic seeded sampling; the seed and
  sample count fold into the settings digest (FINV-2). Planned, not
  v1.

Rules that hold for every representation:

- Each MUST implement a conservative `to_interval()` collapse, because
  the regolith boundary speaks intervals and the margin rule charges
  worst case (regolith/07 sec. 4-5). Collapse is the one lossy step;
  it is explicit in the API and logged when it happens.
- Mixing representations along a route collapses to interval at the
  mixing point (conservative over clever), logged.
- Error accumulation (below) is defined per representation, but there
  is exactly one accumulation implementation per representation, in
  `feldspar-core` (NO DUPLICATION).

The corner sweep described below is the Interval strategy's
implementation -- one strategy of the protocol, not a special case
bolted to the engine.

This matches regolith's worst-corner discipline (regolith/07 sec. 5):
the pack boundary converts `regolith.harness.Interval` to the core
interval one-to-one (06).

## Non-scalar and structured quantities (DECIDED 2026-07-07)

Non-scalar support is NATIVE, not a naming convention (closes
OPEN-12): `PortDecl` carries a rank mirroring regolith/02 sec. 1 --

```
rank: scalar | complex | vector(n) | tensor(n, m)
```

- A ranked value is a fixed-shape bundle of uncertain components;
  uncertainty is per-component (an interval box around a vector, not
  an interval on its magnitude). The `Propagation` protocol operates
  componentwise plus the reductions below; nothing in it may assume
  scalar-only (the OPEN-11 guard).
- Reductions to scalars (magnitude, von Mises from a stress tensor,
  worst component) are ordinary solver edges -- one formula home
  each, searchable like any direction, never implicit casts.
- Rank mismatch at connection is a registration error, exactly like
  a unit mismatch.

Time/frequency-STRUCTURED quantities (spectra, time profiles, masks;
regolith/02 sec. 5) are not ranked bundles: they are exact-by-
reference **payloads**, carried by payload ports (09 sec. 4).
The dividing rule: if it has uncertainty, it is a ranked quantity;
if it is exact by reference (hash-pinned), it is a payload.
Claim-form reductions over structured data (`peak`, `rms(band)`,
`settles`) are solver edges from payload ports to ranked ports --
which is how regolith's time/frequency claim vocabulary lands on the
engine without a second dispatch path (OPEN-11 direction; the
boundary crossing is the generalized ref channel, regolith-side
sec. 7).

## The error split

The README's question -- "model accuracy needs some bound, and then
there's uncertainty in the measurements; maybe split?" -- is answered
YES, and the split is an ownership rule:

1. **Input uncertainty** (interval width) is propagated by the ENGINE:
   a solver is evaluated at the corners of its input box (corner
   sweep, deduplicated and deterministic) and the output interval is
   the hull of corner results. Solvers see point values per corner and
   never reason about spread themselves.
2. **Model error** is declared by the SOLVER as an `Accuracy` bound on
   its own method: `eps(v) = eps_abs + eps_rel * |v|` for closed-form
   and table solvers; measured per-solve for FEA (the Richardson
   estimate, 05). It answers "if the inputs were exact, how far can
   this method's answer be from the true value?"

Total worst-case error at a port = half-width of its propagated
interval + the producing step's model eps at the worst corner.

Accumulation along a route is BY INFLATION, never by summing eps
scalars (DECIDED 2026-07-07, audit A-1): when a step consumes a port
produced by an earlier step, the consumed interval is first inflated
by that port's charged model eps (`[lo - eps, hi + eps]`), so the
corner sweep pushes upstream model error through the consuming
solver's ACTUAL sensitivity. Summing eps along the route is unsound
the moment any step's gain differs from one (`y = 1000*x` turns an
upstream eps of 0.1 into 100; a sum reports ~0.1). Under inflation
the error reaching the target is exactly the propagated half-width
(which now carries every upstream eps through real sensitivities)
plus the FINAL step's own model eps. The planner (04) applies the
same rule with declared ceilings; the executor applies it with
realized eps. There is exactly one implementation of the corner
sweep and of the inflate/total-error rule (NO DUPLICATION), in
`feldspar-core`.

The inflation argument is exact for corner-monotone steps; as with
the sweep itself, non-monotone solvers discharge the gap through
their widened declared eps (below).

Corner sweeps are exact only for corner-monotone models; that
assumption is part of a solver's declared contract (03) exactly as it
is for regolith's closed-form models (INV-9 precedent). Non-monotone
models must widen their declared eps to cover interior extrema.

IDEALIZATION error needs no third term (friction G1): mapping real
geometry onto a parametric family is itself a solver -- an
abstraction edge (09 sec. 4a) -- and the idealization error is THAT
edge's declared model error, accumulated like any step's. The split
stays two-way by making the third error source a first-class step.

## Domains

A **Domain** is where a solver may be trusted:

- `box`: map of port -> allowed interval. Valid iff every supplied
  input interval is a SUBSET of its box entry (the whole corner sweep
  must sit inside, not just one corner).
- `tags`: free strings for regime assertions the box cannot express
  (`linear_elastic`, `small_deflection`, `ideal_gas`). Tags supplied
  by the caller must be a superset of the solver's required tags.

Out-of-domain is a first-class answer (an error value that routing
treats as "this edge does not exist here"), never an exception and
never a silently extrapolated number.

## Core types (Rust `feldspar-core`, PyO3-exposed)

```
Interval   { lo: f64, hi: f64 }            # frozen; lo <= hi, finite
Accuracy   { eps_abs: f64, eps_rel: f64 }  # model-error bound model
Domain     { box: BTreeMap<PortName, Interval>, tags: BTreeSet<String> }
PortDecl   { name: PortName, unit: String, rank: Rank }
Rank       = Scalar | Complex | Vector(n) | Tensor(n, m)
           | Payload(kind)                 # exact-by-ref (09 sec. 4)
Dimension  { exponents: [i8; 7] }          # SI base-dimension vector
Uncertain  = Interval | Normal | Quantile  # one Propagation protocol;
                                           # Interval only in v1;
                                           # per-component on ranks
```

All are ordered/hashed deterministically (BTree collections) because
they feed digests and route caching. Python sees frozen pydantic-like
PyO3 classes with the same field names; there is no separate Python
mirror to desync.
