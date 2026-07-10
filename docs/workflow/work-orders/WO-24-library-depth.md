# WO-24: solver library depth wave (the AD-34/D174 program, feldspar half)

Status: todo (dispatch AFTER WO-23 integrates -- both grow the
library surface; serialize)
Depends: WO-21/23 (struct tier), WO-20 (thermal-fluids wave),
WO-11/22 (symbolic core -- validity-domain predicates for every new
model), the benchmarks memo (every calibration case cites it or a
new memo section added in the same change).
Language: Rust formula/matrix homes + Python registration (the
standing split).
Spec: docs/spec 07 (library phases) + 10 (solver metamodel);
lithos:docs/spec/toolchain/32-stdlib-depth.md sec. 3 (the NORMATIVE
target list for this WO); lithos design-log 2026-07-09-cycle-31
D174.

## Goal

The solver library grows to the charter sec. 3 set, each model
under the standing law: memo-cited equations, calibration cases
within stated tolerances, symbolic validity-domain predicates, no
invented physics.

## Deliverables (each = model + citations + calibration + predicates + registration)

0. Member capacity forms (added per lithos D176, closing the
   WO-21/23 cut-1 seam consumer-side): AISC 360-16 F2 compact-
   section flexural yield (Mp = Fy*Zx, phi_b) and E3 axial
   yield/flexural-buckling basic forms, over caller-supplied section
   properties (Zx/A/r from record data) + material Fy -- cited,
   calibrated against hand-computed cases, validity predicates
   narrow (compact, braced; LTB stays the recorded WO-23 cut).
1. Bolted joints: VDI 2230-class single-bolt tier (preload, load
   factor, working-load margins) + bolt-group shear/tension
   distribution (elastic method).
2. Weld groups: elastic line method statics (fillet groups under
   in-plane + out-of-plane loading).
3. Bearing life: ISO 281 L10 form over std.bearings-shaped rating
   records.
4. Shaft/member fatigue tier: Goodman/Soderberg mean-stress with
   CITED modifying-factor tables; validity predicates narrow
   (steel, HCF) -- honesty over reach.
5. Beam/plate deflection catalog completion: the remaining Roark
   cases the memo lists as gaps.
6. Lumped thermal transient tier (RC-network step/duty responses)
   extending the WO-20 wave.
7. Drive sizing checks: belt (GT2 class tooth shear/tension
   ratings) + leadscrew (torque/efficiency/critical speed).
8. Column buckling completion (the WO-21 residual, if WO-23 did
   not absorb it -- coordinate via its close-out).
9. Docs: spec 07 phase tables, memo additions with sources, full
   close-out ledger.

## Acceptance criteria

- Every model: >= 1 memo calibration case green within stated
  tolerance; validity predicates reject out-of-domain inputs with
  the standard indeterminate reason; registered through the pack
  protocol; NOTHING uncited.
- A model that cannot be calibrated this dispatch is RECORDED and
  cut, never landed uncalibrated.
- Repo gates green; Status flipped with the ledger.
