# WO-16: structured ports + the vibration tier (M6)

Status: todo
Depends: WO-12 (payload machinery), WO-14 (boundary channel for
spectrum/profile/mask refs)
Language: Python (+ `feldspar-core` for rank-native port model)
Spec: 02 (non-scalar quantities -- OPEN-12's rank-native model;
OPEN-11's payload adoption incl. the D102 temporal split), 09
secs. 4/8 (M6), 07 vibration (the consuming tier)

## Goal

Spectrum/profile/mask payloads and ranked (vector/complex/tensor)
ports go live, unblocking the vibration tier (07 Phase 3): Miles'
equation, PSD/GRMS arithmetic, SDOF/MDOF entries, ccx modal reusing
the WO-12 mesh step.

## Deliverables

- Ranked ports registered beyond scalar (per-component
  uncertainty; scalar reductions -- magnitude, von Mises -- are
  ordinary edges, never implicit casts; rank mismatch = registration
  error). v1's scalar-only registration restriction lifts.
- `spectrum`/`profile`/`mask` payload kinds consumed by real
  solvers: Miles (spectrum -> GRMS), rainflow/Miner with
  mech.design, mask containment checks. Claim-form reductions
  follow the D102 split: `peak`/`rms(band)`/`overshoot` are edges
  to ranked ports with EXTERNAL comparators;
  `settles`/`stays_within` are verdict-shaped containments.
- Modal tier: ccx modal/harmonic instantiating the 05 pipeline
  pattern over the M2 mesh step (frequencies + mode shapes; the 07
  vibration (d) row); closed-form SDOF/beam-table entries as its
  cheap competitors and calibration partners.
- 02-edge-cases rows: rank mismatch, band outside spectrum domain,
  mask/profile domain misalignment (honest errors, never clipping).

## Acceptance

- A `mech.first_mode`-shaped claim discharges at closed-form tier
  on a clean beam and escalates to ccx modal when the margin
  demands (fea-marked); a random-vibe GRMS claim consumes a
  spectrum payload end to end; planner tier-blind; determinism
  suite green.
