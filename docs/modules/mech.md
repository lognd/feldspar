# feldspar.mech

Mechanical-engineering solver directions: the WO-07 closed-form core
(beams, bores) plus the WO-24/WO-111 deliverable set (bearings, bolted
joints, weld groups, fatigue, leadscrews, member capacity, plates,
shaft critical speed, drive sizing, civil frame stiffness, vibration).
Each submodule is HONEST-NARROW: named cuts recorded in its own
docstring, never silent gaps.

## mech_bearing_life

<!-- frob:describes python/feldspar/mech/bearing_life.py::bearing_basic_rating_life_l10_ball -->
<!-- frob:describes python/feldspar/mech/bearing_life.py::bearing_basic_rating_life_l10_roller -->
<!-- frob:describes python/feldspar/mech/bearing_life.py::bearing_basic_rating_life_l10h -->
<!-- frob:describes python/feldspar/mech/bearing_life.py::register -->

Rolling-bearing basic dynamic rating life, ISO 281:2007 (WO-24
deliverable 3). `bearing_basic_rating_life_l10_ball`/`_l10_roller`
compute `L10 = (C/P)^p` (millions of revolutions) with the load-life
exponent `p` baked per bearing kind (3 for ball, 10/3 for roller --
the standard's own fixed values). `bearing_basic_rating_life_l10h`
converts to hours at a given speed. `register(registry)` registers
the family.

## mech_bolted_joints

<!-- frob:describes python/feldspar/mech/bolted_joints.py::bolt_single_load_factor_vdi2230 -->
<!-- frob:describes python/feldspar/mech/bolted_joints.py::bolt_group_shear_torsion -->
<!-- frob:describes python/feldspar/mech/bolted_joints.py::bolt_group_tension_from_moment -->
<!-- frob:describes python/feldspar/mech/bolted_joints.py::register -->

Bolted-joint solver directions (WO-24 deliverable 1): a VDI 2230-class
single-bolt elastic tier and an elastic-method bolt-group distribution.
`bolt_single_load_factor_vdi2230` is VDI 2230 Part 1:2015's simplified
two-body elastic model (concentric axial loading only, no embedding/
settling loss or eccentric loading). `bolt_group_shear_torsion` gives
in-plane shear + torsion about the group centroid; `bolt_group_
tension_from_moment` gives tension from an out-of-plane moment about
the group's neutral axis (linear). `register(registry)` registers the
family.

## mech_closed_form

<!-- frob:describes python/feldspar/mech/closed_form.py::declare_core_ports -->
<!-- frob:describes python/feldspar/mech/closed_form.py::rect_second_moment -->
<!-- frob:describes python/feldspar/mech/closed_form.py::cantilever_tip_deflection -->
<!-- frob:describes python/feldspar/mech/closed_form.py::cantilever_required_youngs_modulus -->
<!-- frob:describes python/feldspar/mech/closed_form.py::bore_von_mises -->
<!-- frob:describes python/feldspar/mech/closed_form.py::register -->

Mechanical-engineering closed-form solver directions (WO-07 Phase 1):
pure marshalling over `feldspar._feldspar.mech_*` (NO DUPLICATION),
`accuracy=EXACT` throughout (the oracles the WO-08 FEA tier calibrates
against). `declare_core_ports` is the ONE declaration home for the
shared cross-family mech core vocabulary (`mech.material.*`,
`mech.geom.*`, `mech.load.*`, `mech.section.*`, `mech.deflection.tip`,
`mech.stress.von_mises`) -- `register` calls it first so every
later-registering module (fea, payload_steps) finds that vocabulary
already declared (WO-118, spec 12 sec. 1). `rect_second_moment`,
`cantilever_tip_deflection`, `cantilever_required_youngs_modulus`, and
`bore_von_mises` are the beam/bore closed forms themselves.
`register(registry)` registers the family.

## mech_critical_speed

<!-- frob:describes python/feldspar/mech/critical_speed.py::shaft_critical_speed_from_stiffness -->
<!-- frob:describes python/feldspar/mech/critical_speed.py::shaft_critical_speed_rayleigh_single_mass -->
<!-- frob:describes python/feldspar/mech/critical_speed.py::register -->
<!-- frob:describes python/feldspar/mech/critical_speed.py::G_STANDARD -->

Shaft critical (whirl) speed tier (WO-111 Class-C growth, D223): the
first critical speed equals the first bending natural frequency
(Shigley 11e ch. 7 sec. 7-6). `shaft_critical_speed_from_stiffness` is
the SDOF relation `omega_c = sqrt(k/m)` over a caller-supplied lateral
stiffness and lumped mass (EXACT). `shaft_critical_speed_rayleigh_
single_mass` is Rayleigh's method for a single lumped mass on a
massless shaft. Both single lumped mass, undamped, first mode only.
`register(registry)` registers the family. `G_STANDARD` is standard
gravity (9.80665 m/s^2, CODATA/ISO 80000-3) used by the Rayleigh
static-deflection direction.

## mech_drive

<!-- frob:describes python/feldspar/mech/drive.py::drive_acceleration_torque -->
<!-- frob:describes python/feldspar/mech/drive.py::register -->

Rotary drive-sizing tier (WO-111 Class-C growth, WO-24 deliverable 7):
`drive_acceleration_torque` computes the peak motor torque required to
accelerate a geared inertial load, reflected through a speed-reduction
ratio `N` and drive efficiency `eta` (`J_total = J_motor + J_load/N^2`,
`T_required = J_total*alpha + T_load/(N*eta)`, standard rotational
dynamics per Norton/Slocum). `register(registry)` registers it.

## mech_fatigue

<!-- frob:describes python/feldspar/mech/fatigue.py::fatigue_endurance_limit_baseline -->
<!-- frob:describes python/feldspar/mech/fatigue.py::fatigue_marin_surface_factor -->
<!-- frob:describes python/feldspar/mech/fatigue.py::fatigue_marin_endurance_limit -->
<!-- frob:describes python/feldspar/mech/fatigue.py::fatigue_goodman_factor_of_safety -->
<!-- frob:describes python/feldspar/mech/fatigue.py::fatigue_gerber_factor_of_safety -->
<!-- frob:describes python/feldspar/mech/fatigue.py::fatigue_sn_cycles_to_failure -->
<!-- frob:describes python/feldspar/mech/fatigue.py::register -->
<!-- frob:describes python/feldspar/mech/fatigue.py::MINER_SPECTRUM_PORT -->
<!-- frob:describes python/feldspar/mech/fatigue.py::KC_BENDING -->
<!-- frob:describes python/feldspar/mech/fatigue.py::KC_AXIAL -->
<!-- frob:describes python/feldspar/mech/fatigue.py::KC_TORSION -->

Shaft/member fatigue tier -- stress-life mean-stress (WO-24 deliverable
4): the Marin-modified endurance limit chain and modified-Goodman/
Gerber fatigue factors of safety, calibrated against a worked textbook
example. `fatigue_endurance_limit_baseline` is `Se' = 0.5*Sut` (Shigley
11e eq. 6-8, steel only, `Sut <= 1400 MPa`). `fatigue_marin_surface_
factor` and `fatigue_marin_endurance_limit` apply the Marin modifying
factors. `fatigue_goodman_factor_of_safety`/`fatigue_gerber_factor_of_
safety` are the two mean-stress failure criteria. `fatigue_sn_cycles_
to_failure` inverts the S-N curve for cycles at a given stress.
`register(registry)` registers the family. `MINER_SPECTRUM_PORT` is
the Miner cumulative-damage load-block spectrum payload port (JSON
`{"sigma_a": [...], "cycles": [...]}`, WO111b deliverable 1).
`KC_BENDING`/`KC_AXIAL`/`KC_TORSION` are the Shigley 11e ch. 6 sec. 6-9
load-type Marin factor constants (a fixed lookup, not a fitted
formula).

## mech_leadscrew

<!-- frob:describes python/feldspar/mech/leadscrew.py::leadscrew_torque_raise -->
<!-- frob:describes python/feldspar/mech/leadscrew.py::leadscrew_torque_lower -->
<!-- frob:describes python/feldspar/mech/leadscrew.py::leadscrew_efficiency -->
<!-- frob:describes python/feldspar/mech/leadscrew.py::leadscrew_self_locking_margin -->
<!-- frob:describes python/feldspar/mech/leadscrew.py::leadscrew_collar_torque -->
<!-- frob:describes python/feldspar/mech/leadscrew.py::register -->

Leadscrew (square-thread power screw) drive sizing (WO-24 deliverable
7, leadscrew half): torque to raise/lower a load (`leadscrew_torque_
raise`/`_lower`), mechanical efficiency (`leadscrew_efficiency`),
self-locking margin (`leadscrew_self_locking_margin`), and collar
friction torque (`leadscrew_collar_torque`) -- all exact-algebra
square-thread power-screw mechanics (Shigley 11e ch. 8 sec. 8-2/8-3).
`register(registry)` registers the family.

## mech_member_capacity

<!-- frob:describes python/feldspar/mech/member_capacity.py::flexural_yield_capacity_f2 -->
<!-- frob:describes python/feldspar/mech/member_capacity.py::axial_yield_buckling_capacity_e3 -->
<!-- frob:describes python/feldspar/mech/member_capacity.py::euler_critical_buckling_load -->
<!-- frob:describes python/feldspar/mech/member_capacity.py::register -->

Structural-steel member CAPACITY forms (WO-24 deliverable 0): AISC
360-16 F2 compact-section flexural yield and E3 axial yield/flexural-
buckling, over caller-supplied section properties and material Fy.
`flexural_yield_capacity_f2` is sec. F2.1 eq. F2-1 (compact, laterally
braced only -- lateral-torsional buckling is a named cut).
`axial_yield_buckling_capacity_e3` is sec. E3 flexural buckling.
`euler_critical_buckling_load` is the classical Euler column formula.
`register(registry)` registers the family.

## mech_plate

<!-- frob:describes python/feldspar/mech/plate.py::flexural_rigidity -->
<!-- frob:describes python/feldspar/mech/plate.py::plate_circular_uniform_ss_max_stress -->
<!-- frob:describes python/feldspar/mech/plate.py::plate_circular_uniform_ss_max_deflection -->
<!-- frob:describes python/feldspar/mech/plate.py::plate_circular_uniform_clamped_max_stress -->
<!-- frob:describes python/feldspar/mech/plate.py::plate_circular_uniform_clamped_max_deflection -->
<!-- frob:describes python/feldspar/mech/plate.py::register -->

Flat-plate uniform-load tier (WO-24 deliverable 5, WO-111 Class-C
growth): circular flat plates under uniform pressure (Roark's Formulas
for Stress and Strain, 8th ed., Table 11.2, cases 10a/10b).
`flexural_rigidity` computes `D = E*t^3/(12*(1-nu^2))`. The four
`plate_circular_uniform_*` directions cover simply-supported and
clamped edges, each for max stress and max deflection at the center.
`register(registry)` registers the family.

## mech_struct

<!-- frob:describes python/feldspar/mech/struct.py::solve_frame_payload -->
<!-- frob:describes python/feldspar/mech/struct.py::resolve_tributary_loads -->
<!-- frob:describes python/feldspar/mech/struct.py::extract_member_demands -->
<!-- frob:describes python/feldspar/mech/struct.py::civil_utilization_h1 -->
<!-- frob:describes python/feldspar/mech/struct.py::register -->
<!-- frob:describes python/feldspar/mech/struct.py::FRAME_PORT -->
<!-- frob:describes python/feldspar/mech/struct.py::FRAME_RESULT_PORT -->

Civil/structural direct-stiffness solver direction (WO-21, 07
mech.struct Phase 6): consumes a `frame` payload (`regolith-oblig::
frame::FramePayload`) and produces a `frame_result` payload carrying
every joint displacement, support reaction, and member end force from
a 2D direct-stiffness solve (`feldspar._feldspar.mech_frame2d_solve`).
`solve_frame_payload` runs the solve end to end; `resolve_tributary_
loads` derives member loads from tributary-area assignments;
`extract_member_demands` reads per-member forces back out of a solved
result; `civil_utilization_h1` checks combined axial+flexural
utilization (AISC H1). 2D planar frame elements only (a named WO-21
cut list covers the rest). `register(registry)` registers the
direction. `FRAME_PORT` is the `frame` payload input port (calcite/03
sec. 4); `FRAME_RESULT_PORT` is the result payload output port (reuses
the generic `"table"` payload kind rather than minting a new one).

## mech_vibe

<!-- frob:describes python/feldspar/mech/vibe.py::beam_cantilever_first_mode -->
<!-- frob:describes python/feldspar/mech/vibe.py::sdof_first_mode -->
<!-- frob:describes python/feldspar/mech/vibe.py::register -->
<!-- frob:describes python/feldspar/mech/vibe.py::FIRST_MODE_PORT -->
<!-- frob:describes python/feldspar/mech/vibe.py::GRMS_PORT -->
<!-- frob:describes python/feldspar/mech/vibe.py::SPECTRUM_PORT -->
<!-- frob:describes python/feldspar/mech/vibe.py::PROFILE_PORT -->
<!-- frob:describes python/feldspar/mech/vibe.py::MASK_PORT -->
<!-- frob:describes python/feldspar/mech/vibe.py::MASK_CONTAINMENT_PORT -->

Vibration-tier closed-form + payload-consuming solver directions
(WO-16, 07 vibration Phase 3): the closed-form fundamental-frequency
competitors `feldspar.fea.modal`'s ccx modal direction escalates from.
`beam_cantilever_first_mode` and `sdof_first_mode` are the two
closed-form fundamental-frequency estimators; the module also carries
Miles' equation over a `spectrum` payload (random-vibe GRMS) and a
mask-containment check over a `profile`/`mask` payload (own JSON
payload schemas, no external dependency). `register(registry)`
registers the family. `FIRST_MODE_PORT` is the fundamental-frequency
port both this module's beam direction and `feldspar.fea.modal`'s ccx
direction target; `GRMS_PORT`/`SPECTRUM_PORT` are the Miles'-equation
random-vibe ports; `PROFILE_PORT`/`MASK_PORT`/`MASK_CONTAINMENT_PORT`
are the mask-containment check's payload/result ports.

## mech_weld_groups

<!-- frob:describes python/feldspar/mech/weld_groups.py::weld_group_inplane_shear_torsion -->
<!-- frob:describes python/feldspar/mech/weld_groups.py::weld_group_outofplane_bending -->
<!-- frob:describes python/feldspar/mech/weld_groups.py::weld_group_utilization -->
<!-- frob:describes python/feldspar/mech/weld_groups.py::register -->

Fillet-weld-group elastic line method (WO-24 deliverable 2): the
classical "treat-the-weld-as-a-line" statics for a fillet weld group.
`weld_group_inplane_shear_torsion` (Shigley 11e ch. 9 sec. 9-5/9-6,
Blodgett sec. 4.3-4.4) gives primary+secondary unit line forces for
in-plane loading; `weld_group_outofplane_bending` gives the bending
unit line force for an out-of-plane moment; `weld_group_utilization`
vector-sums both to a peak line force checked against a caller-supplied
allowable. `Aw`/`Jw` are caller-supplied throughout (no weld-line
geometry catalog). `register(registry)` registers the family.
