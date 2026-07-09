# WO-21: Phase 6 library wave -- civil/structural (the `frame` consumer)

Status: todo
Depends: WO-12 (payload ports -- `frame` is a payload kind), WO-14
(contract v2), and LITHOS WO-48 producing `frame` payloads in the
wild (HARD gate: do not dispatch before it lands; the payload
schema is Rust-sourced lithos-side, consumed here by digest).
Language: Rust formula/matrix homes + Python registration
Spec: 07 mech.struct + Phase 6 (added 2026-07-08), 09 sec. 4
(`frame` kind row), lithos:docs/spec/calcite/03-lowering.md secs. 4-5
(the payload fields + obligation shapes this discharges)

## Goal

Calcite's structural claims discharge for real: a direct-stiffness
frame tier over `frame` payloads, member design checks
(`civil.utilization` code packs' numeric halves), deflection/drift/
modal outputs, support reactions feeding bearing-pressure claims.

## Deliverables

- `mech.struct` matrix direct stiffness (truss/beam/frame/grid, the
  07 (r) row): assemble from the payload's joints/members/releases/
  supports; per-case load application; combination sweeps as
  discrete axes (structured Coverage); reactions + member force
  diagrams + displacements out (rank-native where vector, WO-16).
- Member design checks: AISC/Eurocode-shaped interaction
  utilization, lateral-torsional and plate buckling curves (t),
  connection checks (bolt/weld groups, block shear) -- each cited
  to its manual clause, calibrated per 03; registered under the
  claim kinds calcite/03 sec. 5 names.
- Frame modal (Rayleigh/Dunkerley + eigen (r)) backing
  `mech.first_mode(structure)` (the footbridge corpus claim).
- Classical indeterminate methods (slope-deflection, moment
  distribution) as cheap tiers/calibration partners where they
  price in.
- Geotech record consumers the retaining-wall corpus names
  (Rankine/Coulomb active pressure as cited entries; soil records
  are lithos-side registry content -- wrap, never copy).
- Conformance against lithos's calcite corpus obligations
  (bus_shelter through small_office): every structural claim either
  discharges or names its honest gap in the close-out.

## Acceptance

- The small_office frame: utilization sweep over the combination
  set, deflection, drift, bearing reactions -- all discharged with
  stable digests; footbridge first-mode > 3Hz discharges at frame
  tier; planner tier-blind; citations complete.
