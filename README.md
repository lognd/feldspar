# feldspar

A typed graph of engineering solvers, a planner that finds the cheapest
valid route through it under an error budget, and a regolith model pack
(lithos WO-27) built on top.

The name follows the geology theme (hematite, cuprite, magnetite,
regolith, lithos): feldspar is the most abundant mineral in the crust --
the workhorse material regolith is mostly made of.

## What it is

Every engineering quantity can be reached by several methods of varying
cost and fidelity: a table lookup, a closed-form law, a reduced-order
numeric model, a full FEA solve. In feldspar every method is a
"solver": a Python function (or a Rust-backed closed form) decorated
with its typed ports (`inputs`/`outputs`), a validity `Domain`, a
scalar `cost`, an `Accuracy` model per output, and citations. Solvers
register into a `SolverRegistry`; the registry is frozen before use.

Given known quantities (as `Interval`s, with bounds), a target port,
and an `eps_budget`, `feldspar.plan.solve()` searches the registered
solvers for the cheapest route to the target whose accumulated
worst-case error (each step's own model error plus propagated input
uncertainty) fits the budget. `solution.explain()` renders the route
taken: one line per step, its citation, its declared vs. realized
domain, predicted vs. charged error, the running eps-vs-budget
decomposition, and any reroute trail. `solution.to_dict()` returns the
same data as a JSON-safe dict.

`feldspar-core` (the quantity/domain/accuracy types) and the
closed-form solver library are Rust, exposed to Python through PyO3
(`feldspar._feldspar`, imported as `feldspar.core`). The FEA pipeline
(`feldspar.fea`) drives gmsh (meshing) and CalculiX/ccx (solving) for
two parametric families (cantilever box beam, thick-walled cylinder)
and Richardson-extrapolates an error bound across two mesh
refinements. `feldspar.pack` wraps selected engine routes as
`regolith.harness.Model` subclasses, discovered by lithos through the
`regolith.plugins` entry point. The dependency arrow is one-way:
feldspar optionally depends on regolith; regolith never depends on
feldspar.

## Install / dev setup

Default install does not need a sibling `lithos` checkout (the
`regolith` extra is an editable path dependency on `../lithos`):

```bash
make install   # uv sync --all-extras --no-extra regolith && uv run maturin develop
```

To also exercise the pack against a real lithos checkout (sibling
directory `../lithos`):

```bash
make install-regolith   # uv sync --all-extras && uv run maturin develop
```

`gmsh` (the `mesh` extra) is not installable on every host architecture
(e.g. aarch64) -- `fea`-marked tests and example 03's real solve path
are unavailable there; example 03 degrades gracefully instead of
crashing when gmsh is missing.

Gates:

```bash
make test         # uv run pytest tests/ -n auto -m "not regolith and not fea and not spice"
make lint          # ruff check
make import-lint   # import-linter (FINV-3/10 boundary: regolith only under feldspar.pack)
make typecheck     # ty check python/
make fmt-check     # ruff format --check + cargo fmt --check
make check         # fmt-check + lint + import-lint + typecheck + test + cargo clippy + cargo test
```

Test markers (`pyproject.toml`): `fea` (needs ccx + gmsh), `spice`
(needs ngspice), `regolith` (needs a local lithos checkout with
regolith installed). `make test` runs everything else; `make
regolith-test` runs the regolith-marked suite (`tests/regolith/`).

## Common usage

### 1. Register a solver, solve for a target

`examples/01_register_and_solve.py` (run: `uv run python
examples/01_register_and_solve.py`):

```python
from feldspar.core import Accuracy, Domain, Interval
from feldspar.plan import solve
from feldspar.solve import Citation, SolverRegistry, solver

R_AIR = 287.05  # J/(kg K), dry air

@solver(
    namespace="thermo",
    inputs=("thermo.pressure", "thermo.specific_volume"),
    outputs=("thermo.temperature",),
    domain=Domain(
        box={
            "thermo.pressure": Interval(1e3, 1e7),
            "thermo.specific_volume": Interval(1e-3, 1e2),
        },
        tags=frozenset({"ideal_gas"}),
    ),
    cost=1e-6,
    accuracy={"thermo.temperature": Accuracy(eps_abs=0.0, eps_rel=0.0)},
    citations=(Citation(kind="handbook", ref="Moran, Fund. of Eng. Thermo., 9e, sec. 3.5"),),
    version="1",
)
def ideal_gas_pv_to_t(x):
    return {"thermo.temperature": x["thermo.pressure"] * x["thermo.specific_volume"] / R_AIR}

registry = SolverRegistry()
registry.register(*ideal_gas_pv_to_t.solver_direction).danger_ok
registry.freeze()

result = solve(
    registry,
    known={
        "thermo.pressure": Interval(101_000.0, 102_000.0),
        "thermo.specific_volume": Interval(0.83, 0.85),
    },
    tags={"ideal_gas"},
    target="thermo.temperature",
    eps_budget=1_000.0,
)
solution = result.danger_ok  # typani Result: .danger_ok asserts Ok
print(solution.value)        # Interval(lo=292.03..., hi=302.03...)
print(solution.explain())
```

Verified: prints `Interval(lo=292.0397143354816,
hi=302.03797247866225)` followed by the route explanation.

### 2. Two tiers competing on one port

`examples/02_tier_competition.py` registers a cheap digitized-chart
solver and an exact closed form both producing
`mech.stress.von_mises`; a loose `eps_budget` picks the cheap tier, a
tight one forces the exact one:

```bash
uv run python examples/02_tier_competition.py
```

Verified output:

```
loose budget picks: mech.lame_chart.chart
tight budget picks: mech.lame_exact.exact
tier competition demo complete
```

### 3. Multi-direction relation (one law, several solved-for ports)

Hand-writing one `@solver` function per direction of an invertible law
duplicates its domain/citations/version. `Relation` declares the
shared metadata once and each direction as a small explicit function;
`register()` emits one ordinary solver per direction
(`examples/solvers/02_relations.py`, verified to import and register
cleanly):

```python
from feldspar.solve import EXACT, Relation, SolverRegistry

R = 287.05  # J/(kg K)

ideal_gas = Relation(
    namespace="thermo",
    ports=("thermo.pressure", "thermo.specific_volume", "thermo.temperature"),
    domain={
        "thermo.pressure": (1e3, 1e7),
        "thermo.specific_volume": (1e-3, 1e2),
        "thermo.temperature": (200.0, 2000.0),
    },
    tags=("ideal_gas",),
    cost=1e-6,
    accuracy=EXACT,
    citations=("handbook: Moran, Fund. of Eng. Thermo. 9e, sec. 3.5",),
    version="1",
)

@ideal_gas.direction(solves_for="thermo.temperature")
def t_from_pv(x):
    return x["thermo.pressure"] * x["thermo.specific_volume"] / R

@ideal_gas.direction(solves_for="thermo.pressure")
def p_from_tv(x):
    return R * x["thermo.temperature"] / x["thermo.specific_volume"]

@ideal_gas.direction(solves_for="thermo.specific_volume")
def v_from_tp(x):
    return R * x["thermo.temperature"] / x["thermo.pressure"]

def register(registry: SolverRegistry) -> None:
    ideal_gas.register(registry).danger_ok
```

This emits `thermo.ideal_gas.t_from_pv`, `.p_from_tv`, `.v_from_tp` --
three graph rows sharing one metadata block.

### 4. Using feldspar as a regolith model pack

feldspar cannot be exercised as a pack from this repo alone (it needs
a real lithos/regolith checkout, `make install-regolith`); the claim
contract is pinned by `tests/regolith/test_pack_closed_form_models.py`
and `python/feldspar/pack/models.py`. `feldspar.pack.register()`
(the `regolith.plugins` entry point target, `feldspar.pack:MANIFEST`)
registers six `regolith.harness.Model` instances:

| model | claim kind | sense | required inputs |
|---|---|---|---|
| `FeaStaticStressModel` | `mech.static_stress` | upper bound | `mech.load.internal_pressure`, `mech.geom.cylinder.inner_radius`, `mech.geom.cylinder.outer_radius`, `mech.material.youngs_modulus`, `mech.material.poisson` |
| `FeaStaticDeflectionModel` | `mech.static_deflection` | upper bound | `mech.geom.cantilever.{length,width,height}`, `mech.material.youngs_modulus`, `mech.material.poisson`, `mech.load.tip_force` |
| `FeaStaticDeflectionFromGeometryModel` | `mech.static_deflection` | upper bound | `mech.material.youngs_modulus`, `mech.material.poisson`, `mech.load.tip_force` + a `geometry.parametric` payload ref |
| `MechStiffnessModel` | `mech.stiffness` | lower bound (floor) | `e_modulus`, `i_area`, `length` (SI: Pa, m^4, m) |
| `ElecRailModel` (lo) | `elec.rail.lo` | lower bound | `vin`, `r1`, `r2`, `rload` (SI: V, ohm, ohm, ohm) |
| `ElecRailModel` (hi) | `elec.rail.hi` | upper bound | `vin`, `r1`, `r2`, `rload` (SI: V, ohm, ohm, ohm) |

`MechStiffnessModel` computes `k = 3*E*I/L**3` (the exact algebraic
inverse of the cantilever tip-deflection formula at unit force, cost
1: the cheapest tier). `ElecRailModel` computes a loaded
resistor-divider output voltage (`elec_divider_loaded_vout`, cost 1).
Both do an exhaustive corner sweep over the input interval box and
report the worst corner for their claim sense (floor claims report the
minimum, ceiling claims the maximum). A lithos project scaffolding a
`mech.stiffness` or `elec.rail` claim with these four/three scalar
inputs discharges against these models with no FEA involved. The three
FEA-backed models above are the more expensive tiers (`cost=10` for
the scalar-geometry models, `cost=20` for the payload/mesh-generation
model) and additionally require gmsh + ccx at solve time;
`examples/04_pack_discharge.py` (regolith-marked, needs `make
install-regolith`) exercises the deflection claim end to end.

## Repository layout

```
python/feldspar/
  core.py           re-exports the PyO3-bound Rust types (Interval, Domain, Accuracy, ...)
  solve/            solver protocol, registry, digesting, Relation/sugar builders, payload ports
  plan/             the planner: route search, cache, execute, parallel execution, policy, explain()
  fea/               gmsh meshing, ccx deck generation/parsing, Richardson eps, payload-step solvers
  elec/              ngspice deck generation/parsing, the elec.rail closed-form + spice-tier solvers
  library/           closed-form solver modules (mech, thermo, heat, elec, struct, vibe, fluids/)
  pack/              regolith Model wrappers + the regolith.plugins entry point (ALL regolith imports live here)
  calib/             calibration evidence store + harness for solver accuracy claims
  logging_setup/     module logger / dictConfig setup shared across the package
  testing/           shared test helpers

crates/
  feldspar-core/     quantity, interval, domain, accuracy, digest types (pure Rust)
  feldspar-library/  closed-form physics formulas (Rust, called from python/feldspar/library)
  feldspar-py/       PyO3 bindings exposing feldspar-core + feldspar-library as feldspar._feldspar
```

## Documentation

- `docs/spec/` -- the spec: concepts (overview, quantities/uncertainty,
  solvers, routing, FEA pipeline, regolith pack, capability map, model
  integration, solver metamodel, symbolic core) plus `docs/spec/toolchain/`
  (normative architecture, interfaces, edge-case matrix).
- `docs/workflow/` -- ground rules, the agent-executable work orders
  (WO-nn), and the FINV invariant audit ledger.
- `examples/README.md` -- what each numbered example demonstrates.

Docs are the contract: a code/spec disagreement is a bug in one of
them, and the fix updates both in the same change.

## License

GPL-2.0-only, matching the lithos repo. Full text in `LICENSE`.
