# Examples -- the spec's pressure tests

Three suites: this directory (target-API sketches, friction log F1-F6
below), `solvers/` (the solver-authoring DX study, rungs 0-6,
decisions F7-F17 in its README), and `lithos/` (hematite/cuprite
end-to-end fixtures: G1-G12 in its README, G13-G21 in
`lithos/reaction_wheel/`, G22-G33 in `lithos/regen_engine/`,
G34-G43 in `lithos/dune_buggy/` -- the whole-vehicle stress test
with its per-claim SOLVER-TRACE).

Target-API sketches, written BEFORE the implementation (regolith's
`examples/` precedent): each file is what the API must feel like; if
implementing a WO makes an example uglier, the spec loses, not the
example. WO-10 turns these into executable doctests.

- `01_register_and_solve.py` -- minimal: register, freeze, solve,
  explain.
- `02_tier_competition.py` -- two tiers on one port; budget decides;
  fallback policy.
- `03_fea_cantilever.py` -- FEA through the identical call shape;
  measured eps; cache hit.
- `04_pack_discharge.py` -- the host's view through regolith's
  registry; entry-point discovery; margin-rule discharge.

## Friction log (writing these motivated spec changes)

Frictions found by writing the examples, and their resolutions.
Fixed items were folded into the spec in the same change; open items
carry an owner question.

- **F1 (fixed, 03): where do a solver's settings come from?** The
  `SolveFn` signature only receives port values, but tunable solvers
  (mesh density) need settings. Resolution: a solver CLOSES OVER a
  frozen settings model passed to the decorator (`settings=`); the
  decorator digests it (AD-5) into the direction's settings digest.
  Settings are per-registration, not per-call -- a different tuning
  is a different registered direction, which keeps FINV-2 trivially
  honest.
- **F2 (fixed, 05): geometry/material/load port names were
  undefined.** Examples 03/04 need concrete names. Resolution: 05
  now specifies the convention: `mech.geom.<family>.<param>`,
  `mech.material.<property>`, `mech.load.<case>` -- the pack
  signature and the engine ports are the same strings by
  construction.
- **F3 (open, v1-accepted): one target per solve.** Real callers
  want stress AND deflection from one input set. v1 stays
  single-target (two solves share the plan cache and every step
  cache), because multi-target changes the search's termination
  condition. Revisit if profiling shows repeated-plan cost matters;
  candidate: `solve_many(targets)` sharing labels.
- **F4 (open, owner question): eps_budget ergonomics.** The budget
  is absolute in target units (04); engineers often think in
  relative terms. Candidate: accept `EpsBudget.abs(x) | .rel(r)`
  with rel resolved against the solved value iteratively -- but that
  makes feasibility value-dependent (planner complexity). Parked;
  callers can pre-scale.
- **F5 (fixed, 03): namespace of a cross-namespace bridge.**
  `SolverInfo.namespace` is the solver's HOME (registry shard,
  logging identity); its ports may live in any namespace. Stated
  in 03 explicitly.
- **F6 (observed, no change): decorator returns the function, so
  registration needs the attached direction.** The examples use
  `registry.register(*fn.solver_direction)`; bulk module
  registration uses the `register(registry)` convention (AD-4). Both
  shapes shown deliberately.
