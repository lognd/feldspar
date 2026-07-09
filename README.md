# feldspar

**A graph of typed engineering solvers, and a deterministic FEA workhorse
that plugs into it.**

feldspar turns "an intelligent engineer picks a sequence of solution
methods" into a searchable graph of typed solvers -- then ships the first
heavyweight node of that graph, a deterministic gmsh + CalculiX static FEA
pipeline, as the reference external model pack for the lithos toolchain
(regolith, WO-27).

The name follows the geology theme (hematite, cuprite, magnetite, regolith,
lithos): feldspar is the most abundant mineral in the crust -- the
workhorse material regolith is mostly made of.

## The problem

Every engineering quantity can be reached by many methods of varying cost
and fidelity: a table lookup, a closed-form law, a reduced-order numeric
model, a full FEA solve. Traditionally an engineer chooses the method,
checks it is valid for the regime, and accounts for its error. feldspar
makes that choice mechanical. Every solver declares:

- **what it consumes and produces** -- typed ports,
- **where it is valid** -- a domain,
- **what it costs** -- a scalar,
- **how wrong it can be** -- an accuracy model.

Given known quantities with bounds and a target quantity with an error
budget, the planner finds the **cheapest valid route** through the solver
graph whose accumulated worst-case error fits the budget -- accounting
both for each model's own error and for the propagation of input
uncertainty through every step.

## What makes it different

- **Fidelity hierarchy, resolved at the cheapest level.** Table lookup,
  closed form, reduced numeric, and full numeric are competing routes to
  the same port. Dispatch always resolves at the cheapest level whose
  domain and error budget hold. Richer inputs add solvers to the graph;
  they never bypass the hierarchy.
- **Defensible by construction.** Every solver cites its sources (papers,
  handbooks, standards) and its calibration evidence at registration.
  Every solve can render a step-by-step justification report: the route
  taken, why each step was valid, the error decomposition, and the
  citations backing each step.
- **Extractable computation.** `feldspar-core` and the closed-form solver
  library are Rust, exposed through both PyO3 bindings and an `extern "C"`
  surface -- so a chosen subsystem (the solvers of one route, one
  namespace's formula tier) can be extracted and compiled standalone,
  including for microcontroller targets. Python is orchestration and
  interop; the computation homes are Rust.
- **A symbolic core** (decided direction, 2026-07-08). Laws are data, not
  only compiled function bodies: declare one symbolic equation and its
  directions are derived at declaration time (digest-stable, citations
  inherited, still the one solver protocol); validity domains are tracked
  as symbolic predicates that dispatch boxes are derived from; rules that
  are equations stay symbolic all the way into the justification report.
  Spec: `docs/spec/11-symbolic.md`.

## Two personas, one codebase

1. **The engine** (`feldspar.solve`, `feldspar.plan`, `feldspar-core`) --
   domain-neutral. It knows nothing about FEA, regolith, or any particular
   physics. Solvers register into namespaced registries; routing is pure
   computation over their declared metadata.
2. **The pack** (`feldspar.pack`, `feldspar.fea`) -- the WO-27 deliverable.
   Static stress/deflection FEA solvers built on the engine's protocol,
   wrapped as `regolith.harness.Model` subclasses and exposed through the
   `regolith.model_packs` entry point. Evidence is deterministic
   (byte-identical hash for identical requests) and signable.

The pack is deliberately the engine's first, hardest customer: if the
solver protocol can express "mesh a parametric geometry, run CalculiX at
two refinements, Richardson-extrapolate an error bound," it can express a
table lookup.

The dependency arrow is one-way: feldspar optionally depends on regolith;
regolith never depends on feldspar.

## Illustrative shape

Solvers declare their ports, domain, and accuracy; the planner does the
rest (spirit, not exact syntax):

```python
@solver(namespace="thermo")
class TableLookup(Solver):
    def __call__(self, *, pressure, temperature) -> Result[specific_volume, ...]: ...
    def get_domain(self) -> Domain: ...       # where this model is valid
    def get_accuracy(self, *args, **kwargs) -> Accuracy: ...  # model error + input uncertainty

@solver(namespace="thermo")
class IdealGasLaw(Solver):
    def __call__(self, ...): ...
```

## Roadmap (designed-for now, not out of scope)

v1 is linear-elastic small-deflection statics over two parametric families
(cantilever box beam, thick-walled cylinder), propagating interval
uncertainty. The architecture is shaped so the following land later
without new dispatch paths:

- general CAD geometry (arrives as more solvers via regolith's ref channel),
- distribution-based uncertainty (normal, quantile bands) behind the one
  `Propagation` protocol,
- nonlinear/dynamic FEA tiers,
- a wire-format solver executable,
- a growing capability map: mechanics -> thermal/fluids -> vibration ->
  electrical -> controls,
- the symbolic core (M10): derived directions, symbolic domain
  predicates, derivation-aware justification reports.

## Non-goals

- Optimization: routing selects among declared solvers and laws; it does
  not search parameter spaces. (Symbolic math left this list on
  2026-07-08 -- see the symbolic core above; derivation transforms
  declared, cited laws and never invents one.)
- Signing logic of its own: attestation is regolith consumer-side
  machinery.

## Quickstart

Install (editable dev install; builds the Rust extension via maturin):

```bash
make install   # uv sync --all-extras
make build     # uv run maturin develop
```

Register a solver and solve for a target, then render the justification
report -- this exact script runs against the current API:

```python
from feldspar.core import Accuracy, Domain, Interval
from feldspar.solve import Citation, SolverRegistry, solver
from feldspar.plan import solve

registry = SolverRegistry()

@solver(
    namespace="thermo",
    inputs=("thermo.pressure", "thermo.specific_volume"),
    outputs=("thermo.temperature",),
    domain=Domain(
        box={
            "thermo.pressure": Interval(1e3, 1e7),
            "thermo.specific_volume": Interval(1e-3, 10.0),
        },
        tags=frozenset({"ideal_gas"}),
    ),
    cost=1e-6,
    accuracy={"thermo.temperature": Accuracy(eps_abs=0.0, eps_rel=0.0)},
    citations=(Citation(kind="handbook", ref="Cengel, Thermodynamics, ch.3"),),
    version="1",
)
def ideal_gas_pv_to_t(x):
    R = 287.0  # J/(kg K), air
    return {"thermo.temperature": x["thermo.pressure"] * x["thermo.specific_volume"] / R}

registry.register(*ideal_gas_pv_to_t.solver_direction)
registry.freeze()

known = {
    "thermo.pressure": Interval(1.0e5, 1.01e5),
    "thermo.specific_volume": Interval(0.80, 0.82),
}

result = solve(
    registry,
    known=known,
    tags={"ideal_gas"},
    target="thermo.temperature",
    eps_budget=1000.0,  # loose: the planner budgets against the
                        # SOLVER'S DECLARED domain, not the narrower
                        # known interval, so tighten only after
                        # checking `PlanError.BudgetUnreachable`'s
                        # reported `best_eps`
)
solution = result.danger_ok  # typani Result: .danger_ok asserts Ok
print(solution.explain())    # step-by-step justification report
```

`explain()` prints the route (one line per solver step), each step's
method citations, the declared vs. realized domain, the predicted and
charged model error, the running eps-vs-budget decomposition, any
reroute trail, and cache provenance -- `solution.to_dict()` returns the
same data as a JSON-safe dict for machine consumers.

## Documentation

- `docs/spec/` -- the spec, numbered in reading order (overview,
  quantities and uncertainty, solvers, routing, FEA pipeline, regolith
  pack, capability map, model integration, solver metamodel, symbolic
  core).
- `docs/spec/` -- the concept docs + `toolchain/` (normative
  architecture, interfaces, edge-case matrix); `docs/workflow/` --
  ground rules + the agent-executable work orders (WO-nn).

Docs are the contract: a code/spec disagreement is a bug in one of them,
and the fix updates both in the same change.
