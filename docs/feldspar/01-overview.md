# 01 -- Overview

One sentence: feldspar turns "an intelligent engineer picks a sequence
of solution methods" into a searchable graph of typed solvers, and
ships the first heavyweight node of that graph -- a deterministic
gmsh + CalculiX static FEA pipeline -- as regolith's reference external
model pack (WO-27).

## The problem

Every engineering quantity can be reached by many methods of varying
cost and fidelity: a table lookup, a closed-form law, a reduced-order
numeric model, a full FEA solve. Traditionally an engineer chooses the
method, checks it is valid for the regime, and accounts for its error.
feldspar makes that choice mechanical:

- every solver declares what it consumes and produces (typed ports),
- where it is valid (a domain),
- what it costs (a scalar),
- and how wrong it can be (an accuracy model).

Given known quantities with bounds and a target quantity with an error
budget, the planner finds the cheapest valid route through the solver
graph whose accumulated worst-case error fits the budget -- accounting
both for each model's own error and for the propagation of input
uncertainty through every step (02-quantities-and-uncertainty.md).

Three commitments follow from that framing and are load-bearing for
everything else (all DECIDED 2026-07-07, from the OPEN reviews in 08):

- **Fidelity hierarchy, resolved at the cheapest level.** The solver
  graph is a model hierarchy: table lookup, closed form, reduced
  numeric, full numeric are competing routes to the same port, and
  dispatch always resolves at the cheapest level whose domain and
  error budget hold. Richer inputs (real geometry, when the regolith
  ref channel lands -- OPEN-2 residual) add solvers to the graph; they
  never bypass the hierarchy. The full integration plan -- the tier
  axis, budget-seeking refinement, payload ports, milestones -- is 09.
- **Defensible by construction.** Every solver cites its sources
  (papers, handbooks, standards) and its calibration evidence at
  registration (03); every solve can render a step-by-step
  justification report -- the route taken, why each step was valid,
  the eps decomposition, and the citations backing each step (04).
- **Extractable computation.** `feldspar-core` and the closed-form
  solver library are Rust with PyO3 bindings AND an `extern "C"`
  surface, so a chosen subsystem (the solvers of one route, one
  namespace's formula tier) can be extracted and compiled standalone
  -- including for microcontroller targets. Python is orchestration
  and interop; the computation homes are Rust. feldspar is thus both
  a standard library of engineering models and the interop layer that
  reaches external resources (03, external interfacing).

## The two personas

**Engine** (`feldspar.solve`, `feldspar.plan` + `feldspar-core` in
Rust): domain-neutral. Knows nothing about FEA, regolith, or any
particular physics. Solvers are registered into namespaced registries;
routing is pure computation over their declared metadata.

**Pack** (`feldspar.pack` + `feldspar.fea`): the WO-27 deliverable.
Static stress/deflection FEA solvers built on the engine's protocol,
wrapped as `regolith.harness.Model` subclasses, registered via the
`regolith.model_packs` entry point, producing evidence that is
deterministic (byte-identical hash for identical requests) and
signable (WO-21 attestation).

The pack is deliberately the engine's first, hardest customer: if the
solver protocol can express "mesh a parametric geometry, run ccx at two
refinements, Richardson-extrapolate an eps," it can express a table
lookup.

## v1 sequencing (deferred, NOT out of scope)

These are designed-for now and land after v1 -- the architecture must
never make them harder:

- General CAD geometry: v1 solves two parametric families (cantilever
  box beam, thick-walled cylinder). Real geometry refs arrive with
  regolith's ref-passing channel (OPEN-2 residual, 08) and enter the
  fidelity hierarchy as more solvers, not a new dispatch path.
- Distribution-based uncertainty (normal, quantile bands): v1
  propagates intervals only, but behind the one `Propagation`
  protocol (02) so adding representations touches no engine code.
- Nonlinear/dynamic FEA: v1 is linear-elastic small-deflection
  statics; the 05 pipeline pattern is the template for further tiers.
- A wire-format solver executable: v1 registers in-process models
  (the ccx subprocess is an internal detail, 06); the wire seam is
  deliberately shaped like regolith's SubprocessSolverModel so one
  adapter serves both when regolith's Phase E split lands (03).
- Unit conversion beyond the boundary: storage is coherent SI forever;
  the conversion table grows with the port table (02).

## Non-goals

- Symbolic math or optimization: routing selects among declared
  solvers; it does not derive new ones.
- Signing logic of its own: attestation is regolith consumer-side
  machinery (06).

## Relationship to lithos components

- **regolith** is the host toolchain: its harness defines Model,
  DischargeRequest, Prediction, Evidence, the registry, plugin
  discovery, and signing. feldspar consumes those as a normal
  third-party pack (contract: `../cad/docs/implementation/`
  `20-solver-abstraction.md`, D-A..D-G).
- **hematite/cuprite** never see feldspar directly; their claims reach
  it through regolith's model registry.
- The engine persona is feldspar's own ambition beyond WO-27: the
  place where multi-step solution paths (which regolith's single-step
  registry deliberately does not model) live. A compiled route is
  presented to regolith as ONE model (06), so the two registries never
  disagree about selection semantics.
