# Reaction-wheel assembly -- the big mixed pressure test

Four files, three languages' worth of claims, one solver backend:
`flywheel.hema` (rotor: spin stress, burst, inertia, balance),
`shaft_bearings.hema` (machine-design tier: DIN 743, press fit,
fatigue, bearing life, critical speed), `driver.cupr` (three-phase
drive: losses, ripple, control loop, FET thermal), and
`wheel_assembly.hema` (housing, random vib, cross-domain promise
chains, exported jitter). Exercises catalog areas: mech.materials,
mech.design, mech.struct, vibration, dynamics, thermo/heat, elec,
control, signal, mfg -- deliberately touching every committed phase.

## Findings G13-G21 (continuing examples/lithos/README.md's log)

- **G13 (fixture, Phase 1+): body-load cases.** Centrifugal loading
  makes omega an INPUT PORT of the rotating-disk family -- families
  carry body-load cases as ports, not surface-load specs. No spec
  change (ports already express it); the catalog entry is the fix.
- **G14 (FIXED, 09 sec. 4): payloads are not an FEA-only mechanism.**
  Miner damage, bearing L10, and Miles' equation are CLOSED-FORM
  solvers consuming `spectrum`/`profile` payloads. 09 sec. 4 now says
  so explicitly -- the cheap tier reads payloads too.
- **G15 (fixture, Phase 1): contact-pair records.** Press-fit torque
  capacity needs `contact{17-4PH, 4140}.mu` -- pair records lower to
  table-solver edges exactly like G5's single-material records; the
  pair identity is part of the record edge's identity, nothing new.
- **G16 (no change): claim-expression algebra stays regolith-side.**
  Summed loss terms vs a limit is the claim's arithmetic; feldspar
  supplies quantities only. The seam is already right.
- **G17 (fixture, motivates 02 Normal/Quantile): statistical
  tolerance claims.** ISO 1940 balance grade under machining scatter
  is absurd as worst-case; it is the concrete customer for the
  quantile propagation mode ("P99 unbalance < limit"). Schedule with
  the mfg namespace, not before.
- **G18 (confirms 06/psu example): promise chains compose.** Driver
  dissipation -> housing rise -> mount face temperature crosses two
  files and two domains with zero new mechanism.
- **G19 (FIXED, 02-edge-cases row): angular units.** rpm/deg ingest
  aliases (rad/s, rad coherent); stress-monotone-in-omega sweeps
  collapse to the top corner via corner_monotone.
- **G20 (fixture + 09 note): cyclic port dependence.** R_ds_on(T)
  with T(loss(R_ds_on)): the cheap tier breaks the cycle with a
  cited hot-corner envelope edge (conservative_for-aware); the
  numeric tier iterates internally. The PLANNER never loops -- the
  graph stays a DAG by construction; cycles are resolved inside
  solvers or by envelope edges.
- **G21 (no change): assembly algebra is the orchestrator's.**
  Exported jitter = f(torque ripple, inertia, mount stiffness) is a
  cross-part obligation regolith composes; feldspar discharges each
  quantity leaf. Confirms the one-way seam.

## What this project is FOR

- The conformance suite's end-state fixture set (WO-09 grows into
  it as regolith-side asks land).
- The catalog's demand signal: every solver named here must exist in
  07's catalog (checked -- they do) and carries its phase.
- The DX study's realism check: `examples/solvers/` patterns must be
  able to express every solver this project needs without new
  concepts (checked against rungs 0-5).
