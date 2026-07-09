# Implementation work orders

Agent-executable decomposition of milestone M1 (09 sec. 8) -- the v1
engine + FEA pack that satisfies regolith WO-27. Each `WO-nn-*.md` is
self-contained: goal, normative spec references, deliverables,
acceptance; an implementer agent executes one WO end-to-end reading
only that file, the referenced spec sections, and
`00-architecture.md` (NORMATIVE: where a WO conflicts, architecture
wins; WO acceptance criteria stand).

Ground rules are regolith's, adopted verbatim
(`lithos:docs/workflow/README.md` sec. "Ground rules"): pydantic
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
- `../../examples/` -- API pressure tests; if an implementation
  makes an example uglier, the spec loses, not the example.
  `../../examples/lithos/` is a verbatim MIRROR of the lithos
  repo's corpus (lithos D148): fixture changes land in lithos and
  arrive via `make sync-examples`, never by editing the mirror.

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
regolith WO-27's acceptance list. WO-11 (symbolic core, M10 phase 1)
landed 2026-07-08 after the R1 owner decision.

The forward queue (SCHEDULED 2026-07-08, owner closure directive --
lithos cycle 27 D146; designs normative in the cited spec homes):

```
WO-03/06 (done)
  -> WO-12 payload ports (M2; 09 sec. 4)
       -> WO-13 budget-seeking + cost curves (M3; 09 sec. 3)
            -> WO-15 parallel execution (M5; 09 sec. 6)
            -> WO-17 ngspice elec tier (M7; 05 pattern, 07 elec)
            -> WO-18 CoupledGroup (M8; 09 sec. 4b, example 06)
       -> WO-14 regolith boundary v2 (M4; 06 + lithos sec. 8 -- lithos
          WO-30 is DONE, so WO-14 is live the moment WO-12 lands)
            -> WO-16 structured ports + vibration (M6; 02, 07 Phase 3)
            -> WO-20 Phase 2 thermal-fluids wave (07; incl. the D141
               compressible tier over flownet payloads)
            -> WO-21 Phase 6 civil/structural wave (07; the `frame`
               consumer -- HARD-gated on lithos WO-48)
WO-03 (done), WO-14
  -> WO-19 solver-pack kit (M9) + the AD-26 entry-point migration
     (migration half gated on lithos WO-44)
WO-11 (done), WO-04/07
  -> WO-22 symbolic follow-ups (R4/R5; 11 sec. 4 -- DECIDED)
```

Dispatch order and gates live in `../../TODO.md` (the one live
queue).
