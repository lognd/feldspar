# Implementation work orders

Agent-executable decomposition of milestone M1 (09 sec. 8) -- the v1
engine + FEA pack that satisfies regolith WO-27. Each `WO-nn-*.md` is
self-contained: goal, normative spec references, deliverables,
acceptance; an implementer agent executes one WO end-to-end reading
only that file, the referenced spec sections, and
`00-architecture.md` (NORMATIVE: where a WO conflicts, architecture
wins; WO acceptance criteria stand).

Ground rules are regolith's, adopted verbatim
(`../lithos/docs/implementation/README.md` sec. "Ground rules"): pydantic
v2 frozen models, typani Result values, tracing/pyo3-log + dictConfig
logging, docstrings as part of done, ASCII only, conventional
commits, frob for Python edits, `make check` green before close.
Docs are the contract: code/spec disagreement fixes both in the same
change. Every WO flips its entries in the repo `TODO.md` ledger.

Two additional NORMATIVE companions (implementer agents make no
design decisions):

- `01-interfaces.md` -- the exact M1 public surface: every symbol,
  signature, and error variant. Implement TO it; deviation is a spec
  bug filed, not a local choice.
- `02-edge-cases.md` -- the required-test matrix. Before closing a
  WO, grep it for the WO id and cover every matching row.
- `../../examples/` and `../../examples/lithos/` -- API pressure
  tests and lithos end-to-end fixtures; if an implementation makes an
  example uglier, the spec loses, not the example.

## Dependency graph

```
WO-01 scaffolding
  -> WO-02 quantity core (Rust)
       -> WO-03 solver protocol + registry
       -> WO-04 propagation + error accumulation (Rust)
            -> WO-05 planner search (Rust)
                 -> WO-06 solve facade: execute, reroute, cache
                      -> WO-07 library/mech formulas + calib harness
                           -> WO-08 FEA pipeline
                                -> WO-09 regolith pack + conformance
                      -> WO-10 explain() + acceptance close-out
                           (also depends on WO-09)
```

WO-03 and WO-04 are parallel after WO-02. WO-10 closes M1 against
regolith WO-27's acceptance list.

Later milestones (M2 payload ports, M3 budget-seeking, M4
regolith-gated boundary, M5 parallelism, M6 structured ports, M7
ngspice) get WO-11+ appended here when scheduled; their designs are
already normative in `../feldspar/09-model-integration.md`.
