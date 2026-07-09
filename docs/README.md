# feldspar -- Documentation

feldspar is the external solver pack for the lithos toolchain: a
graph-theoretic solution-path engine ("which sequence of models gets me
from what I know to what I need, cheaply enough and accurately enough")
with a native FEA workhorse (gmsh + CalculiX), exposed to regolith as a
`regolith.model_packs` plugin per WO-27.

The name joins the geology theme (hematite, cuprite, magnetite, regolith,
lithos): feldspar is the most abundant mineral in the crust -- the
workhorse material regolith is mostly made of.

Two personas, one codebase:

1. **The engine**: solvers declare typed inputs/outputs, a validity
   domain, a cost, and an accuracy model. A planner searches the solver
   graph for the cheapest route from given quantities to a requested
   quantity whose accumulated worst-case error fits the caller's budget.
2. **The regolith pack**: selected routes/solvers are wrapped as
   `regolith.harness.Model` instances behind the pack entry point,
   discharging stress/deflection obligations with signed, deterministic
   evidence (WO-27).

The dependency arrow is one-way: feldspar depends on regolith
(optionally); regolith never depends on feldspar.

## Reading order

1. `spec/` -- the technical truth: engine concepts, FEA pipeline, pack
   contract, plus `spec/toolchain/` (normative architecture,
   interfaces, edge-case matrix).
2. `workflow/` -- process: ground rules + agent-executable work orders
   (`work-orders/WO-nn`) + the FINV audit ledger.
(Taxonomy per lithos D138, cycle 26: spec / workflow / guide; the
guide role is served by the top-level README quickstart.)

## Directory map

```
docs/
  spec/        the spec (concept docs, numbered in reading order)
    01-overview.md                vision, personas, non-goals
    02-quantities-and-uncertainty.md  ports, unit algebra, uncertainty
                                  models (interval/normal/quantile), the
                                  model-error / input-uncertainty split
    03-solvers.md                 solver protocol, registration,
                                  citations + calibration, namespaces,
                                  determinism
    04-routing.md                 the planner: graph model, cost,
                                  eps budget, search algorithm, fallback
                                  rerouting, solve cache, explain()
    05-fea-pipeline.md            gmsh meshing, ccx decks, result
                                  parsing, Richardson eps
    06-regolith-pack.md           WO-27 contract mapping: entry point,
                                  models, evidence, signing
    07-capability-map.md          namespaces-as-capabilities, the
                                  curriculum-derived method catalog,
                                  phased roadmap (mechanics ->
                                  thermal/fluids -> vibration ->
                                  electrical -> controls)
    08-open-questions.md          OPEN/DECIDED ledger, consolidated
    09-model-integration.md       the model/FEA integration plan: the
                                  tier axis, budget-seeking
                                  refinement, payload ports, coupled
                                  groups, pack seam, parallelism
                                  policy, milestones
    10-solver-metamodel.md        the nine-field anatomy, the eight
                                  (+planner) authoring patterns,
                                  plug-and-play solver packs +
                                  conformance kit, generated tooling,
                                  CAM/manufacturability seam
    11-symbolic.md                the symbolic core (owner-decided
                                  direction, 2026-07-08 / OPEN-15):
                                  equations as data, derived
                                  directions, symbolic domain
                                  predicates, residual list

    toolchain/   NORMATIVE technical docs:
      00-architecture.md          repo layout, AD-1..12, the
                                  FINV-1..12 invariant ledger,
                                  language assignment, CI jobs
      01-interfaces.md            exact M1 public surface
                                  (signatures + error variants)
      02-edge-cases.md            required-test matrix, rows keyed
                                  by WO

  workflow/    process
    README.md                     ground rules, conventions, the WO
                                  dependency graph
    work-orders/WO-01..WO-11      agent-executable work orders (all
                                  DONE as of 2026-07-08)
    FINV-audit.md                 the invariant audit checklist

examples/          target-API pressure tests (written before code;
                   friction log -> spec changes in its README)
  lithos/          hematite/cuprite end-to-end fixtures + the
                   geometry/edge-case friction log (G-nn)
```

## Conventions

- Docs are the contract: code disagreement with a spec doc is a bug in
  one of them, and the fix updates both in the same change.
- Every guarantee lives in the invariant table (`00-architecture.md`)
  with its enforcement mechanism; new guarantees enter the table in the
  same change as their implementation.
- External contracts are cited by their home, repo-qualified and
  never filesystem-relative: `lithos:docs/spec/...` means that path
  in the lithos repo (github.com/lognd/lithos); `../` paths out of
  this repository are banned in docs (they do not resolve on
  GitHub). Contracts are never copied here (NO DUPLICATION); this
  repo documents only the feldspar side of each seam. The
  `pyproject.toml` editable path source and the conformance
  conftest's sys.path hop are FUNCTIONAL local-dev mechanisms (they
  do assume a sibling checkout), not doc links.
