# 01 -- M1 public interfaces (NORMATIVE)

The exact public surface WO-01..10 implement. Implementer agents make
NO design decisions: names, signatures, and error variants below are
the contract; bodies and private helpers are the WO's latitude. Rust
signatures are given in Python-visible form (PyO3 classes behave as
frozen dataclasses); `Result`/`Option` are typani.

## feldspar.core (Rust-backed; WO-02, WO-04)

```python
class Interval:                     # frozen, ordered, hashable
    lo: float; hi: float
    @staticmethod
    def new(lo: float, hi: float) -> Result[Interval, CoreError]
    @staticmethod
    def point(x: float) -> Result[Interval, CoreError]
    def width(self) -> float
    def half_width(self) -> float
    def midpoint(self) -> float
    def contains(self, x: float) -> bool
    def is_subset(self, outer: Interval) -> bool
    def hull(self, other: Interval) -> Interval

class Accuracy:                     # frozen
    eps_abs: float; eps_rel: float  # both >= 0, finite (ctor checks)
    def eps(self, v: float) -> float        # eps_abs + eps_rel*|v|
    def worst_over(self, iv: Interval) -> float  # max at |v| extremum

class Rank:                         # enum: SCALAR|COMPLEX|VECTOR(n)|
    ...                             # TENSOR(n,m)|PAYLOAD(kind) (WO-12)

class PortDecl:                     # frozen
    name: str; unit: str; rank: Rank = Rank.SCALAR

class Domain:                       # frozen; BTree-ordered internally
    box: Mapping[str, Interval]; tags: frozenset[str]
    def admits(self, inputs: Mapping[str, Interval],
               tags: frozenset[str]) -> Result[None, DomainViolation]
    # DomainViolation carries port/tag details (which, why)

class Dimension:                    # frozen; [i8; 7] SI exponents
    ...

class UnitSystem:                   # protocol + builtin()
    @staticmethod
    def builtin() -> UnitSystem
    def dimension_of(self, unit: str) -> Result[Dimension, UnitError]
    def to_si(self, value: float, unit: str) -> Result[float, UnitError]
    def from_si(self, value: float, unit: str) -> Result[float, UnitError]
    def compatible(self, a: str, b: str) -> bool
    # table entries: (unit, dimension, scale, offset); offset != 0
    # only on ingest/print-legal units; offset units in compound
    # expressions -> UnitError at table load (G3)

def canonical_digest(obj: Any) -> str        # canonical JSON -> blake3
def format_f64(x: float) -> str              # shortest round-trip

# WO-04:
def corner_sweep(box: Mapping[str, Interval],
                 fn: Callable[[Mapping[str, float]],
                              Result[Mapping[str, float], SolveError]],
                 ) -> Result[Mapping[str, Interval], SolveError]
    # deduplicated, sorted corner order; hull assembly; callers pass
    # eps-INFLATED intervals for intermediate ports (02, audit A-1)
def inflate(iv: Interval, eps: float) -> Interval
    # [lo - eps, hi + eps]; THE accumulation primitive (02): applied
    # to every consumed intermediate port before sweep/domain checks
def total_error(out_hull: Interval, model_eps: float) -> float
    # half_width + model_eps; the budget-checked quantity at target
```

`Interval(lo, hi)` direct construction raises on invalid bounds (a
programmer bug in literal code); `Interval.new`/`point` are the
checked Result path for untrusted data. Examples use both
deliberately.

`CoreError` variants: `NonFiniteBound`, `InvertedInterval`.
`UnitError` variants: `UnknownUnit`, `IncompatibleDimensions`,
`OffsetInCompound`.

## feldspar.solve (WO-03)

```python
class Citation(BaseModel):          # frozen pydantic
    kind: Literal["paper", "handbook", "standard", "calibration"]
    ref: str
    note: str = ""

class ClaimSenses:                  # enum: UPPER | LOWER | BOTH (G4)

class SolverInfo(BaseModel):        # frozen
    solver_id: str; namespace: str; version: str
    inputs: tuple[str, ...]; outputs: tuple[str, ...]
    domain: Domain; cost: float     # cost > 0
    accuracy: Mapping[str, Accuracy]     # key: every output port
    citations: tuple[Citation, ...]      # >=1 non-calibration kind
    tier: Literal["table", "closed_form", "reduced",
                  "discretized", "coupled"]
    deterministic: bool = True
    corner_monotone: bool = True
    conservative_for: ClaimSenses = ClaimSenses.BOTH
    settings_digest: str            # from decorator settings= (F1)

class SolveOutput(BaseModel):       # frozen (DX F16)
    values: Mapping[str, float]
    measured_eps: float | None = None   # replaces declared ceiling
    payloads: Mapping[str, PayloadRef] = {}  # WO-12: payload-rank
                                        # outputs; corner-INVARIANT

SolveFn = Callable[[Mapping[str, float]],
                   Result[SolveOutput, SolveError]]
# AUTHOR-facing returns are looser; the decorator normalizes
# (DX F13/F14/F16): Result | SolveOutput | Mapping | float
# (float only when len(outputs) == 1). Registered SolveFns are
# always the strict form above.

EXACT: Accuracy                      # Accuracy(0.0, 0.0) constant

def solver(*, namespace, inputs, outputs, domain, cost, accuracy,
           citations, version, tier="closed_form", settings=None,
           deterministic=True, corner_monotone=True,
           conservative_for=ClaimSenses.BOTH,
           solver_id_suffix=None) -> Callable[[F], F]
    # attaches fn.solver_direction: tuple[SolverInfo, SolveFn];
    # NO global state (AD-4); solver_id =
    # f"{namespace}.{fn.__name__}" + ("." + suffix if suffix).
    # Coercions (DX F10/F11/F15, normalized at decoration time):
    #   domain: Domain | Mapping[str, Interval | tuple[float, float]]
    #   tags= kwarg: Iterable[str] (merged into Domain)
    #   citations: Iterable[Citation | str]  ("kind: ref -- note")
    #   accuracy: Mapping[str, Accuracy] | Accuracy (all outputs)

def make_direction(*, solver_id, fn, **same_kwargs_as_solver
                   ) -> tuple[SolverInfo, SolveFn]
    # function-call twin of @solver for factories (DX F9)

class Relation:                      # DX F7
    def __init__(self, *, namespace, ports, domain, cost, version,
                 citations, tags=(), tier="closed_form",
                 settings=None) -> None
    def direction(self, *, solves_for: str,
                  inputs: tuple[str, ...] | None = None,
                  accuracy: Accuracy | Mapping = EXACT,
                  domain: Mapping | None = None,   # override
                  corner_monotone: bool = True) -> Callable[[F], F]
    def register(self, registry) -> Result[None, RegistryError]

def table_solver_1d(*, namespace, x_port, y_port,
                    x: Sequence[float], y: Sequence[float],
                    method: Literal["linear", "pchip"],
                    eps_abs: float, citations, version,
                    cost: float = 1e-6) -> tuple[SolverInfo, SolveFn]
    # x strictly ascending (checked); domain box = [x[0], x[-1]];
    # eps_abs REQUIRED (never auto-derived). table_solver_2d mirrors.

class Correlation:                   # DX F8
    def __init__(self, *, namespace, inputs, output, domain,
                 accuracy_rel: float, citations, version,
                 cost: float = 1e-6, tags=()) -> None
    def formula(self, fn: F) -> F            # decorator
    def register(self, registry) -> Result[None, RegistryError]

class SolverRegistry:
    def declare_ports(self, *decls: PortDecl
                      ) -> Result[None, RegistryError]   # DX F12
    def register(self, info: SolverInfo, fn: SolveFn
                 ) -> Result[None, RegistryError]
    def freeze(self) -> None
    def is_frozen(self) -> bool
    def digest(self) -> str          # sorted SolverInfo fold; freeze-only
    def __iter__(self) -> Iterator[tuple[SolverInfo, SolveFn]]  # sorted
    def port_table(self) -> Mapping[str, PortDecl]
```

`RegistryError` variants: `DuplicateSolverId`, `PortUnitConflict`,
`PortRankConflict`, `UnknownPort`, `DuplicatePortDecl`,
`EmptyCitations`, `NonPositiveCost`, `AccuracyOutputMismatch`,
`Frozen`, `BadTable(reason)`; WO-12 adds
`PayloadKindConflict(port)` (same port declared with two different
payload kinds -- the unit-mismatch mirror, 09 sec. 4) and
`UnknownPayloadKind(port, payload_kind)` (kind string outside
`PAYLOAD_KINDS`).

### WO-12 (M2) payload ports

```python
PAYLOAD_KINDS: frozenset[str]        # the 09 sec. 4 kind table,
                                     # VERBATIM (single Python home;
                                     # includes `frame`)

class PayloadRef(BaseModel):         # frozen pydantic; exact by ref
    kind: str                        # must be in PAYLOAD_KINDS
    digest: str                      # content address (store-derived)
    origin: str = ""                 # provenance only; never digested

class PayloadResolver(Protocol):     # orchestrator-provided handle
    # (D96/OPEN-2: feldspar never does store IO)
    def resolve(self, ref: PayloadRef) -> Result[bytes, SolveError]
    def store(self, kind: str, content: bytes, origin: str) -> PayloadRef

def payload_feature_violation(port: str, feature: str) -> DomainViolation
    # the 09 sec. 4a execution-time payload-feature check's violation
    # value, for SolveError.OutOfDomain(violation)
```

Payload semantics REQUIRE declared ports: registration and execution
kind checks both read the declared `Rank.payload(kind)`, exactly as
unit checks read declared units (F12 opt-in extended). Accuracy for a
payload output is declared `EXACT` by convention (a payload is exact
by reference, 02); a payload in ANY digest folds as its `digest`
string alone (FINV-12).

## feldspar.plan (WO-05, WO-06, WO-10)

```python
class RouteStep(BaseModel):         # frozen
    solver_id: str; realized_domain: Domain
    predicted_eps: float; cost: float

class Route(BaseModel):             # frozen
    target: str; steps: tuple[RouteStep, ...]
    predicted_eps: float; total_cost: float; digest: str

def plan(registry, known: Mapping[str, Interval],
         tags: frozenset[str], target: str, eps_budget: float,
         sense: ClaimSenses = ClaimSenses.BOTH,
         payloads: Mapping[str, PayloadRef] | None = None  # WO-12
         ) -> Result[Route, PlanError]
    # zero-step Route when target in known (G12); sense filters
    # conservative_for edges and folds into the request digest (A-3);
    # one-sided edges admissible as the FINAL step only (A-2).
    # WO-12: known payload ports enter the search as width-0
    # placeholder labels; the search core stays payload-unaware;
    # planning over abstraction edges is OPTIMISTIC (09 sec. 4a);
    # target must be a scalar port in M2

class Solution(BaseModel):          # frozen; fields per 04
    target: str; value: Interval; eps: float; route: Route
    settings_digest: str; solver_versions: Mapping[str, str]
    attempts: tuple[AttemptRecord, ...]   # reroute trail
    cache_hit: bool
    def explain(self) -> str        # WO-10; pure rendering
    def to_dict(self) -> dict

class RoutePolicy(BaseModel):       # frozen
    fallback: bool = True; cache: bool = True; threads: int = 1

def execute(route: Route, registry, known,
            payloads: Mapping[str, PayloadRef] | None = None,   # WO-12
            step_cache: PayloadStepCache | None = None          # WO-12
            ) -> Result[Solution, SolveError]
def solve(registry, known, tags, target, eps_budget,
          sense: ClaimSenses = ClaimSenses.BOTH,
          policy: RoutePolicy = RoutePolicy(),
          payloads: Mapping[str, PayloadRef] | None = None,     # WO-12
          step_cache: PayloadStepCache | None = None            # WO-12
          ) -> Result[Solution, SolveError | PlanError]

class PayloadStepCache:             # WO-12; 04 "Solve cache" extension
    hits: int; misses: int          # contract-level counters
    def __init__(self, root: Path | None = None) -> None
    def key(self, info: SolverInfo, box, payload_inputs) -> str
    def get(self, key, probe_tools=None) -> StepEntry | None
    def put(self, key, hull, payloads, step_eps) -> None
    # per-rung/per-payload step cache (09 secs. 3-4): DETERMINISTIC,
    # payload-touching steps only; keyed on solver identity +
    # settings digest + scalar box + payload input DIGESTS +
    # feldspar_version; A-5-style per-step tool recheck on get()
```

`PlanError` variants: `UnknownTarget`, `NoApplicableSolver`,
`BudgetUnreachable(best_eps)`, `CyclicPortEquivalence`,
`InvalidBudget`.
`SolveError` variants: `ToolMissing(tool, guidance)`,
`ToolFailed(tool, log_tail)`, `Timeout(tool, seconds)`,
`ParseFailed(context)`, `OutOfDomain(violation)`, `NonFinite(port)`,
`MissingOutput(port)`, `InvalidMeasurement(reason)`,
`BudgetExceeded(realized, budget)`, `NoRouteRemaining(attempts)`;
WO-12 adds `PayloadKindMismatch(port, expected_kind, actual_kind)`
(execution-time twin of the registration kind check),
`MissingPayload(port)` (declared payload port with no supplied ref),
and `DanglingDigest(digest)` (a ref the resolver's store has no
content for).
(`NoConvergence` is reserved for M8 coupled groups, 09 sec. 4b.)

## feldspar.fea (WO-08) and feldspar.pack (WO-09)

Shapes per 05/06 verbatim; the only interface freedoms already
settled there: `find_ccx() -> Result[Path, SolveError]`,
`run_ccx(deck: str, timeout_s: float) -> Result[CcxRun, SolveError]`,
`register(registry) -> None` (fea), `register(registry) -> None`
(pack entry point).

### M1 port table (NORMATIVE, audit A-8)

These exact strings are the engine ports AND the pack signature
inputs (06: the boundary converter never renames); regolith-side
resolution (sec. 7 item 4) must land on them. All rank SCALAR.

| port | unit |
|---|---|
| `mech.geom.cantilever.length` | m |
| `mech.geom.cantilever.width` | m |
| `mech.geom.cantilever.height` | m |
| `mech.geom.cylinder.inner_radius` | m |
| `mech.geom.cylinder.outer_radius` | m |
| `mech.geom.cylinder.length` | m |
| `mech.material.youngs_modulus` | Pa |
| `mech.material.poisson` | 1 |
| `mech.material.sigma_y` | Pa |
| `mech.load.tip_force` | N |
| `mech.load.internal_pressure` | Pa |
| `mech.deflection.tip` | m |
| `mech.stress.von_mises` | Pa |

The WO-02 unit table must cover at least: the units above, their
ingest aliases (mm, MPa, kN, GPa, %), the 02-edge-cases rows (degC,
degF, rpm, deg, s(Isp) view), and K/W-style compounds for Phase 2
seeding.

## feldspar.calib (WO-07)

```python
class CalibRecord(BaseModel):       # frozen; content-addressed
    solver_id: str; reference_id: str; n_samples: int; seed: int
    worst_abs_error: float; worst_rel_error: float; digest: str

def calibrate(solver_id: str, reference_id: str, registry,
              n_samples: int = 256, seed: int = 0
              ) -> Result[CalibRecord, CalibError]
def check_ceilings(registry, records_dir: Path) -> Result[None, CalibError]
```

`CalibError` variants: `UnknownSolver`, `DomainMismatch`,
`CeilingBusted(solver_id, declared, observed)`, `NoRecord(solver_id)`.
