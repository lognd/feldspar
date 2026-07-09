# 03 -- Solvers

One sentence: a solver is one directed, typed edge bundle in the
solution graph -- declared metadata the planner can search plus a
callable the executor runs -- registered by decorator into a frozen,
deterministic registry.

## The protocol

A solver DIRECTION (one inputs -> outputs mapping) is the unit of
registration. Conceptually:

```python
class SolverInfo(BaseModel):            # frozen; what the planner sees
    solver_id: str                      # "thermo.ideal_gas.pv_to_t"
    namespace: str                      # "thermo"
    version: str                        # folded into digests
    inputs: tuple[PortName, ...]        # all required
    outputs: tuple[PortName, ...]       # all produced
    domain: Domain
    cost: float                         # relative expected seconds
    accuracy: Mapping[PortName, Accuracy]   # model-error bound per output
    citations: tuple[Citation, ...]     # REQUIRED non-empty (below)
    deterministic: bool = True          # False forces settings digest
    corner_monotone: bool = True        # sweep-exactness contract (02)
    conservative_for: ClaimSenses = both  # sense-aware conservatism
                                        # (below; friction G4)

SolveFn = Callable[[Mapping[PortName, float]],
                   Result[Mapping[PortName, float], SolveError]]
```

The callable receives POINT values (one corner; the engine owns the
sweep, 02) and returns point outputs. It must be pure with respect to
its inputs plus its declared settings: same inputs, same version, same
settings digest => same outputs (FINV-2, 00-architecture.md).

## Registration

```python
from feldspar.solve import solver, SolverRegistry

@solver(
    namespace="thermo",
    inputs=("thermo.pressure", "thermo.specific_volume"),
    outputs=("thermo.temperature",),
    domain=Domain(box={...}, tags=frozenset({"ideal_gas"})),
    cost=1e-6,
    accuracy={"thermo.temperature": Accuracy(eps_abs=0.0, eps_rel=0.0)},
    version="1",
)
def ideal_gas_pv_to_t(x: Mapping[str, float]) -> Result[...]: ...
```

- The decorator builds `(SolverInfo, SolveFn)` and attaches it; it does
  NOT touch any global state. Registries are explicit objects populated
  by module-level `register(registry)` functions (mirrors regolith D-B;
  import order can never change behavior).
- Third-party solver packs plug in through the
  `feldspar.solver_packs` entry point with a conformance kit
  (DECIDED 2026-07-07; design + etiquette rules: 10 sec. 3,
  scheduled M9).
- A multi-direction method (the README's overloaded-`__call__` sketch)
  is expressed as one implementation object registering N directions,
  each its own `SolverInfo` with its own id suffix. Rejected: actual
  `@override`-overloaded `__call__` -- undispatchable at runtime and
  unsearchable by the planner; the graph needs one row per direction
  anyway.
- Expensive solvers (FEA) use the same protocol; their `SolveFn`
  internally meshes/runs/parses and their accuracy is produced
  per-solve rather than from the static bound (05 explains how the
  static `Accuracy` remains a declared CEILING the planner can search
  on, while the realized eps replaces it at execution time).

`SolverRegistry`:

- `declare_ports(*decls) -> Result[None, RegistryError]` -- namespace
  modules declare their port table ONCE; registering a solver naming
  an undeclared port is `RegistryError.UnknownPort` (typo safety for
  agent-written catalogs; DX study F12).
- `register(info, fn) -> Result[None, RegistryError]` -- duplicate
  `solver_id`, a port unit conflict, an undeclared port, or EMPTY
  CITATIONS is an `Err`, never a warning.
- `freeze()` -- after which registration errors; the planner only
  accepts frozen registries (routing over a mutating registry is a
  programmer bug).
- Iteration order is sorted by `solver_id` everywhere (determinism).

## Registration ergonomics (DX-SETTLED 2026-07-07)

Settled by the authoring study (`examples/solvers/README.md`, F7-F16;
the worked forms live there). Governing rule: every sugar form lowers
AT DECORATION TIME to the one raw protocol above -- a sugar-built
direction is digest-equal to its hand-built twin; there is never a
second registration path.

- Coercions accepted by `@solver` and its function-call twin
  `make_direction`: box values as `(lo, hi)` tuples; a bare dict as a
  tagless Domain; tags as any iterable; citations as
  `"kind: ref -- note"` strings; `accuracy=EXACT` or a single
  Accuracy for all outputs.
- Return normalization: a `SolveFn` may return a `Result`, a plain
  mapping (auto-`Ok`), or a bare float when there is exactly one
  output.
- Measured-eps channel (F16): a measuring solver returns
  `SolveOutput(values, measured_eps=...)` inside its Ok; the executor
  substitutes it for the declared ceiling (04/05). A plain mapping
  means "no measurement; charge the declared accuracy".
- `Relation`: one law, N directions -- shared
  domain/citations/version declared once, each direction an explicit
  small function, ids auto-suffixed. (Rejected: N independent
  decorators -- metadata drift.) The original rejection here of
  symbolic inversion as "magic" is REVERSED (owner, 2026-07-08,
  spec home 11 / OPEN-15) and LANDED (WO-11, 2026-07-08):
  `Relation.law(lhs, rhs, ...)` declares one symbolic equation
  (`feldspar.core.Expr`) whose directions are DERIVED at declaration
  time via closed-form inversion -- lowering through the same
  `_build.build_solver_info_and_fn` path as `.direction()`,
  digest-equal to a hand-built twin (5 provenance fields are
  `Field(exclude=True)`, invisible to the digest), citations
  inherited, non-invertible variables an `Err(RegistryError.
  NonInvertible)` naming them (hand-write those directions beside
  the derived ones via `.direction()`), and multi-branch inversions
  an `Err(RegistryError.MultiBranch)` until the author passes
  `branches={var: "+"|"-"}`. Details: `docs/workflow/work-orders/
  WO-11-symbolic-core.md` closing report.
- `table_solver_1d/2d`: domain box auto = data extent; interpolation
  eps EXPLICIT and cited, never auto-derived.
- `Correlation`: published formula + published validity box +
  published accuracy band + citation as one object, because the
  literature ships them together.
- Families: plain factories over `make_direction`, registered in
  sorted order. No family class.

## Sense-aware conservatism (friction G4)

An edge whose output is exact-or-conservative in one DIRECTION only
(an envelope that relocates a load to the tip, an abstraction edge
that thickens a wall, a bound rather than an estimate) declares
`conservative_for: upper | lower | both`. Routing to a target whose
claim sense the edge does not serve treats the edge as out-of-domain
-- a tip-load envelope may discharge an upper deflection claim and
must NEVER touch a lower-bound stiffness or first-mode claim. `both`
(the default) means the output is a genuine two-sided estimate within
declared eps. The pack maps regolith's `ClaimSense` onto this field
one-to-one (06) and passes it into `plan(sense=...)` (04).

Composition rule (audit A-2): a one-sided edge's output is NOT a
two-sided interval, so feeding it through a further solver whose
sensitivity in that input is negative would invert the bound.
In v1 a `conservative_for != both` edge is therefore admissible only
as the FINAL step of a route (its outputs must include the target
port); anywhere else the planner treats it as out-of-domain.
Sense-preserving composition (edges declaring per-input monotone
sign, letting the planner track bound orientation through a chain)
is deliberately future schema -- it must arrive as SolverInfo
metadata, never as a planner special case.

## Citations and calibration (DECIDED 2026-07-07, closes OPEN-10)

Every registered solver must be defensible, not just declared:

```python
class Citation(BaseModel):              # frozen
    kind: Literal["paper", "handbook", "standard", "calibration"]
    ref: str                            # DOI, ISBN+section, standard id,
                                        # or calibration-run digest
    note: str = ""                      # what the source backs
```

- `citations` must contain at least one method source (paper /
  handbook / standard): where the formula, table, or algorithm comes
  from. Registration without one is a `RegistryError`.
- Declared NON-ZERO `Accuracy` ceilings are engineering claims and
  must be backed by `calibration` citations: outputs of the
  **calibration harness**, which sweeps a solver against a reference tier (a
  higher-fidelity solver or published test data, itself cited) over
  sampled domains and records the observed worst error as a
  content-addressed run digest. A ceiling tighter than its newest
  calibration evidence is a harness failure, loudly.
- `accuracy=EXACT` (`Accuracy(0, 0)`) declares exactness in real
  arithmetic -- definitional identities and exact algebra only
  (audit A-7). It needs method citations like any solver but no
  calibration citation: there is nothing to measure. Float roundoff
  is not model error (AD-13 keeps it deterministic; bounding its
  magnitude is out of eps scope in v1). EXACT is banned for
  `tier=coupled` (09 sec. 4b) and for table solvers (interpolation
  eps is mandatory and cited, F8).
- Citations ride into the justification report (04): every step of a
  delivered answer traces to sources, so a complete solve can be
  rendered as a step-by-step, reviewable engineering argument.

The calibration harness is cross-phase infrastructure (07): it ships
with Phase 1 and every later phase's solvers register through it.

## Rust computation homes

The closed-form formula tier (`library/<namespace>`, 07) is
implemented in Rust inside `feldspar-core`'s workspace with thin
Python bindings -- NOT in Python -- so that the extraction goal (01)
holds: any subset of the formula tier compiles standalone behind
PyO3 or `extern "C"`. Python-side solver modules are the sanctioned
pattern only for wrappers whose value IS the Python ecosystem (scipy,
CoolProp) or subprocess orchestration (ccx); pure formulas written in
Python are a registration-review smell.

## Namespaces are capabilities

`namespace` is the capability axis (DECIDED 2026-07-07, closes
OPEN-7): `mech`, `thermo`, `fluids`, `elec`, ... one backend, one
protocol, namespaced registries preventing collision. Cross-namespace
connections are ordinary solver edges (a port in, a port out) so the
planner routes across disciplines with zero special casing; declaring
such a bridge must be the same one-decorator registration as any
solver -- minimal boilerplate is a design requirement, not a nicety.
`SolverInfo.namespace` is the solver's HOME (registry shard, logging
identity); its ports may live in any namespace (friction F5,
examples/README.md).

## External interfacing

Three sanctioned ways the graph reaches non-feldspar computation, all
behind the same `SolveFn` protocol so the planner cannot tell them
apart:

1. **In-process Python** libraries (scipy, CoolProp, ...): plain
   functions; the wrapping module owns pinning the library version
   into `SolverInfo.version`.
2. **External binaries** (ccx, ngspice, ...): the wrapping module owns
   spawn/timeout/parse and maps every infrastructure failure to a
   `SolveError` variant (ToolMissing / ToolFailed / Timeout /
   ParseFailed) -- exit codes and stderr never leak upward as
   exceptions. ccx (05) is the reference implementation of this
   pattern. (The executor adds `NonFinite` for any solver returning
   NaN/inf -- caught as a value, friction G12.)
3. **Remote/wire solvers**: deferred (OPEN-3); the seam is the same
   protocol serialized, deliberately shaped like regolith's
   SubprocessSolverModel wire form so one adapter can serve both.

## Settings digests

Any solver whose answer depends on tuning knobs (mesh density, seeds,
iteration limits, tool versions) must fold ALL of them into a
`settings_digest` string (one canonical JSON -> blake3 helper in
`feldspar.solve.digest`; single home). Delivery convention (friction
F1, examples/README.md): the `SolveFn` closes over a frozen settings
model passed to the decorator (`settings=`), which digests it --
settings are per-REGISTRATION, not per-call; a different tuning is a
different registered direction, keeping FINV-2 trivially honest. The digest rides with results
into route digests and, at the pack boundary, into regolith's evidence
hash via `Prediction.settings_digest` (06). A solver is only as
deterministic as its digest is honest (regolith INV-10, adopted
verbatim as FINV-2).
