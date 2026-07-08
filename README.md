# feldspar

**A graph of typed engineering solvers, and a deterministic FEA workhorse
that plugs into it.**

feldspar turns "an intelligent engineer picks a sequence of solution
methods" into a searchable graph of typed solvers -- then ships the first
heavyweight node of that graph, a deterministic gmsh + CalculiX static FEA
pipeline, as the reference external model pack for the lithos toolchain
(regolith, WO-27).

The name follows the geology theme (hematite, cuprite, quarry, regolith,
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
  electrical -> controls.

## Non-goals

- Symbolic math or optimization: routing selects among declared solvers;
  it does not derive new ones.
- Signing logic of its own: attestation is regolith consumer-side
  machinery.

## Documentation

- `docs/feldspar/` -- the spec, numbered in reading order (overview,
  quantities and uncertainty, solvers, routing, FEA pipeline, regolith
  pack, capability map, model integration, solver metamodel).
- `docs/implementation/` -- normative architecture, interfaces, edge-case
  matrix, and the agent-executable work orders (WO-nn).

Docs are the contract: a code/spec disagreement is a bug in one of them,
and the fix updates both in the same change.
