# SOLVER-TRACE -- what feldspar must do, claim by claim

The companion deliverable to the dune-buggy fixture set: for every
claim group, the exact behavior the feldspar planner/executor must
produce -- the route (solvers by 07 catalog entry, tier in
parentheses), the eps story, the payloads crossing, and the
milestone/phase gate that unblocks it. Format per step:
`port(s) --[solver, tier]--> port(s)`.

Legend: (t)=table, (cf)=closed form, (r)=reduced, (d)=discretized,
(cg)=coupled group, (rec)=record edge, (abs)=abstraction edge,
(pp)=payload->payload transform. Gates: M1..M9 (09 sec. 8), P1..P5
(07 phases), ASK-n (regolith sec. 7 item n).

## 0. The shared preludes (routed once, cached per-rung forever)

Almost every trace below begins with one of these; the solve cache
(04) means the fleet of claims pays each prelude once.

- **PRELUDE-MAT** (per material, per environment corner):
  `thermo.temperature --[property record (rec/t)]-->
  mech.material.{youngs_modulus, poisson, sigma_y, ...}`
  G5 discipline: material ports are outputs, never free givens.
  Gate: P1 solvers + the given-resolution contract (ASK-4) for
  .hem-lowered flows; conformance fixtures pre-resolve by hand.
- **PRELUDE-TERRAIN** (G35): `spectrum(whoops_psd) + vehicle.speed
  --[psd speed transform (pp/cf)]--> spectrum(hub_psd)`
  Payload in, payload out, content-addressed. Gate: M2 payload
  ports + M6 spectrum kind; ASK-3 to cross the regolith boundary.
- **PRELUDE-KIN** (G36): `mech.geom.suspension.* + z_wheel
  --[four-bar position (cf), dynamics: mechanisms]-->
  vehicle.camber, vehicle.toe, mech.joint_angle, motion_ratio`
  Today: swept scalar claims per travel corner; the CURVE-valued
  form is the ASK-7 extension. Gate: P3 (dynamics), M2 for curve
  payloads if adopted.

## 1. frame.hem

- `rail_stress` (upper): PRELUDE-MAT ->
  `tube graph + loads --[matrix direct stiffness (r), mech.struct]-->
  member forces --[section stress (cf)]--> mech.stress.von_mises`.
  eps: stiffness-method declared ceiling (calibrated vs FEA tier,
  09 sec. 7 upward direction). Thin margin at a joint -> reroute to
  `--[shell FEA (d)]--` through the SAME kind (G6). Gate: P1 waves
  (mech.struct is unphased catalog -- THIS FIXTURE IS ITS DEMAND
  SIGNAL); FEA fallback M1.
- `torsion` (LOWER, A-3): same stiffness route, sense=lower;
  every envelope edge in the graph declaring conservative_for=upper
  is ABSENT from this search (02-edge-cases WO-05 row). The matrix
  tier is `both`, so it discharges. eps: two-sided.
- `weld_life`: PRELUDE-TERRAIN ->
  `spectrum(hub_psd) --[rainflow (r), mech.design]--> cycle bins
  --[Eurocode detail class (t) + Miner (cf)]--> damage`.
  Closed-form solvers CONSUMING payloads (G14). Gate: M6 + P1
  fatigue wave.
- `pickup_true`: worst-case stackup (cf, mfg) now; quantile mode
  (02 Normal/Quantile) is the honest form -- G40/G17 customer.
  Gate: post-v1 propagation mode, scheduled with mfg namespace.

## 2. rollcage.hem

- `collapse` (LOWER): `tube layout + sigma_y --[plastic hinge
  mechanism enumeration (r), mech.struct]--> collapse load`.
  Deterministic mechanism enumeration = sorted, seeded; eps
  calibrated against shell-FEA limit loads (upward calibration).
  Gate: unphased mech.struct pull-forward.
- `crush_space` (upper): elastic-plastic deflection -- beyond the
  v1 linear-elastic domain tags; the LINEAR tier's domain box
  excludes it honestly -> route to nonlinear FEA tier: v1-deferred
  (01 overview: nonlinear is designed-for, post-v1). TODAY: honest
  BudgetUnreachable/NoApplicableSolver naming the missing tier --
  never a linear answer to a plastic question.
- `proof_crush` (G41): same route, scaled given -- proves the
  registry serves claim TRANSFORMS with zero new registration.
- `survivable`: NO ROUTE by design (G37/G27): assume!/test ladder.

## 3. suspension_front.hem / steering.hem (the kinematic cluster)

- `camber_band`, `no_bind`, `ackermann`, `bump_steer`: PRELUDE-KIN
  swept over the config domain. The planner sees ONE solver
  (four-bar position (cf)) swept at corners; interior extrema of
  Ackermann error mean corner_monotone=False -> widened declared
  eps (02 contract) or grid coverage (ASK-2: the encoding must
  state grid(k) per axis). Gate: P3.
- `buckle` (LOWER): PRELUDE-MAT ->
  `geometry --[Euler/Johnson column (cf), mech.materials]-->
  buckling load`. Domain: slenderness box decides Euler vs Johnson
  branch -- TWO registered directions, disjoint boxes; the planner
  picks by domain, not by if/else inside one solver (one row per
  regime keeps citations honest).
- `static_camber` build claim: G40 quantile mode again.

## 4. coilover.hem

- `rate` (two-sided window): `wire_dia, od, coils
  --[helical spring rate (cf), EXACT (A-7)]--> rate`. eps 0; the
  window claim needs BOTH senses -- conservative_for=both required.
- `shear_ok`: `--[Wahl-corrected shear (cf)]-->` at the x=180mm
  corner. Monotone -> top corner only (G19 pattern).
- `no_surge` (LOWER): `--[spring surge frequency (cf), vibration]-->`
  Gate: P3.
- `force_band`: TIER COMPETITION inside one claim: damper dyno
  RECORD (rec/t, vendor-cited) vs orifice+shim hydraulics chain
  (cf, fluids). Record is cheaper AND tighter inside its dyno
  domain; hydraulics covers the extrapolated corners -- the planner
  arbitrates per corner box, which is exactly the 01-overview
  promise. Gate: P2 fluids.
- `no_cavitate` (LOWER): `T_oil --[oil pv record (rec)]--> pv` +
  chamber pressure route; NPSH-analog. Gate: P2.
- `soak`: dissipation -> convection -> oil T -> viscosity record ->
  BACK into force_band givens: a one-way promise CHAIN (G18), not a
  cycle -- the loop closes across CLAIMS (orchestrator lazy loop),
  never inside the solver graph.

## 5. wheel_tire.hem (G34 showcase)

- `grip`/`flotation`: `F_z, p_tire --[tire record: friction
  ellipse / MF fit (rec/Correlation)]--> traction` COMPETES with
  `--[Bekker-Wong pressure-sinkage + drawbar (cf/t),
  vehicle.terra]-->` -- tier competition where the tiers are
  DIFFERENT PHYSICS selected by surface tag (domain tags carve the
  graph; cost only breaks the tie inside a tag regime). Gate: P-new
  (vehicle), G34's catalog addition.
- `impact`: energy methods (cf) -> thin margin -> explicit-dynamics
  FEA is OUT OF committed scope -- honest ladder: assume!/test if
  the margin will not close at (cf). The fixture accepts either
  outcome; what it forbids is a silent (cf) pass outside its
  calibrated domain.
- `carcass`: hysteresis power (rec) -> convection (cf, heat):
  cross-namespace route, zero new mechanism (G30).

## 6. engine files

- `pin_fillet`: PRELUDE-MAT -> `gas load + inertia --[DIN 743
  combined (cf), mech.design]--> sigma_vm`. corner_monotone=False
  in omega (gas vs inertia trade) -- the declared-honesty fixture.
- `crank_life`: `combustion spectrum (payload) --[rainflow (r) +
  Marin + Miner (cf)]--> damage`. M6 + P1.
- `film` (LOWER): `omega, load, oil mu(T) (rec) --[Raimondi-Boyd
  charts (t), fluids]--> h_min`. Chart tables with cited
  interpolation eps (F8 discipline). Gate: P2.
- `residual` (balance): rotating/reciprocating balance (cf,
  dynamics). Gate: P3.
- `bridge_temp` (G38-adjacent, M8 customer #3):
  CoupledGroup{gas-side Bartz-class convection (cf/prop-adjacent),
  head conduction (cf/r), coolant-side Gnielinski (cf, heat)} --
  composite over boundary ports, unit-calibrated eps, residual into
  measured_eps, NoConvergence reroutable. Boundary conditions
  arrive from cooling.fluo's flownet solve (ASK-6/fluorite).
- `no_float`/`surge`: cam kinematics (cf, dynamics) + spring modes
  (cf, vibration) over the speed domain. P3.
- `flow`: incompressible orifice chain (cf) vs compressible choked
  check (cf, fluids compressible) -- regime tags (`choked`) from a
  screening solver feed sibling domains (fluorite 03 sec. 3's
  regime-reporting pattern, engine-side). P2.

## 7. driveline (cvt_drive, gearbox_final, halfshaft, hub_rear)

- `no_slip`: 2-D forall (ratio x speed): capstan/wedge traction
  (cf, mech.statics belt friction) + contact mu(T_belt) record
  (rec) + flyweight centrifugal (cf, dynamics). Coverage must state
  grid(k x m) or per-axis monotonicity -- G29's exact shape again
  (ASK-2).
- `sheave_burst`: rotating disk (cf, G13 body-load family) -> thin
  margin at 11000rpm -> FEA (d) through the same kind: the manifold
  fat/thin pattern on a spinning part. M1-shaped once the rotating
  family lands (P1 wave).
- `bending`/`pitting`: AGMA (cf + K-factor tables (t)). P1 wave
  (mech.design gears).
- `capacity`/`elongation_life`: chain power tables (t) + sand
  derate record (rec). The DATA obligation (G28 flavor): the derate
  record must carry its test-dust citation.
- `angle_ok`/`derated`: PRELUDE-KIN (rear) -> CV vendor record
  (rec) derating curve. The travel config domain crosses FILES
  (suspension -> halfshaft) -- one config ledger (G33 analog for
  config variables).
- `spline_shear`, `pilot_fit` (G15), `axle_life`: mech.design (cf)
  + pair records + spectrum fatigue as above.

## 8. brakes (brake_corner, pedal_box, brake_hydraulics.fluo)

- `no_fade` (G38, M8 customer #2): CoupledGroup{friction power
  split by effusivity (cf), disc transient conduction (cf/r, heat),
  convection correlation (cf, heat -- published Re box as Domain,
  G9), pad mu(T, p, v) record (rec)}. The fade claim is the
  acceptance-shaped fixture: the uncoupled hot-corner envelope
  (G20) MUST fail its budget and the composite MUST close it --
  that ordering proves composite calibration earns its keep.
- `no_boil`: consumes the coupled solve's caliper-fluid soak output
  ACROSS TRACKS (calc file) -- field/scalar promise chain; wet
  boiling point column (rec).
- `line_p`, `volume`, `rise`, `release`, `half_system`: flownet
  payload (ASK-6/fluorite) -> `fluids.*` network solvers: series
  resistance (cf), compliance budget (cf; COPEN-5 extraction),
  transient line dynamics (r, method-of-characteristics class).
  `half_system` sweeps a DISCRETE failure-state axis (G43).
- `mount_stiff` (LOWER) + `reserve`: statics (cf) + the cross-track
  compliance budget -- three files, one claim, all promise-lowered.

## 9. fluids files (cooling.fluo, fuel_system.fluo)

- `reject`: flownet -> `pump curve (rec) + network dp (cf/r,
  Hardy-Cross class) + effectiveness-NTU (cf, heat)` -- the P2
  showcase route.
- `npsh`/`suction` (LOWER): pv(T) records (rec) + suction-side dp
  chain (cf). The vapor-lock claim's T given arrives from the
  vehicle soak promise -- cross-file, cross-track.
- `stat_snap`/`rise`: transient network tier (r) with Plenum
  capacitance + line compliance extracted from hematite walls
  (COPEN-5): the extraction rule is fluorite's open design item;
  feldspar's solver is ready (fluids: water hammer (cf/r)).
- `rail`: series chain (cf) with end-of-life filter record column
  (rec) -- worst-corner discipline over a RECORD CONDITION axis.

## 10. electrical (electrical_power, efi_ecu, dash)

- `pump_drop`/`ampacity`: IPC-class conductor formulas (cf, elec
  interconnect) -- ROUTE EXISTS, GIVENS DO NOT (G42): lengths and
  bundle factors are hand-asserted pending ASK-8 (wiring routing).
  The trace is: `length, awg, bundle, T_amb --[voltage drop /
  ampacity derating (cf/t)]--> drop, margin`. P4.
- `balance`: stator curve record (rec, f(rpm)) + load profile
  payload integration (cf). P4 + M6.
- `latency`/`oil_latency`: timing chains over the shared event
  ledger (G33) -- regolith-side algebra; feldspar supplies element
  delays (sensor lag record, CAN scheduling bound (cf, signal)).
- `dump_ok`: mask payload (ISO 7637 pulse) + clamp response --
  spectrum/mask vocabulary (M6) + elec transient (cf/r). P4.
- `vr_timing`, `adc_budget`, `oilp_noise`: signal-chain error
  budgets (cf, signal). P5.
- `lambda_stable`: dead-time plant + margins over the rpm domain
  (r evaluation, control). P5 -- deliberately the LAST-phase
  fixture, confirming 07's ordering rationale.
- `fet_t`, `lcd_temp`: G20-pattern envelope (cheap) or small
  CoupledGroup (check tier) -- the driver.cupr precedent verbatim.

## 11. vehicle.hem (the roof)

- `mass`/`cg_height`: entity-DB property claims (regolith WO-22
  territory); feldspar supplies section/solid property solvers
  (cf) where geometry is native. No FEA ever (the flywheel Iz
  precedent).
- `ssf` (LOWER), `gradeability`, `ride_f`, `flat_ratio`: vehicle
  namespace (cf) consuming PRELUDE-KIN outputs + corner rates +
  tire records: the G34 additions end to end.
- `accel`/`top_speed`: the four-namespace chain (thermo Otto (cf)
  -> shaft torque -> CVT ratio sweep -> chain -> traction limit
  (rec/terra) -> longitudinal dynamics (cf)) -- G30's "performance
  chain is pure routing" at vehicle scale. The single most
  route-deep trace in the corpus (5+ steps): the A-1 INFLATION rule
  is load-bearing here -- summed eps would understate the torque
  error's effect on accel by the driveline ratio (~9x gain).
- `thermal_ok`: mixed discrete x continuous forall (G43) over the
  M8 head group: coverage encoding ask, squared.
- `landing`/`first_mode`: SRS mask + modal (d, ccx modal over the
  M2 shared mesh). M6 + P3.
- `fade_decel`, `decel`: the brake cluster's outputs composed by
  regolith's assembly algebra (G21) -- feldspar sees four quantity
  leaves, never the composition.

## 12. Roll-up: the demand this project places

| mechanism | fixture count here | gate |
|---|---|---|
| record/pair/condition edges (G5/G15/G28) | 23 | P1+ data obligation |
| spectrum/mask/profile payloads (G14/G35) | 11 | M2/M6, ASK-3 |
| sense=LOWER claims (A-3 discipline) | 12 | M1 |
| corner_monotone=False declarations | 5 | M1 (02 contract) |
| CoupledGroups (G22/G38) | 3 | M8 |
| tier competitions through ONE kind (G6) | 6 | M1/OPEN-6 (ASK-1) |
| 2-D/mixed forall coverage (G29/G43) | 5 | ASK-2 |
| flownet-consuming claims (G25/G39) | 14 | ASK-6/fluorite |
| config-domain kinematic fields (G36) | 6 | ASK-7 extension |
| hand-asserted routing givens (G42) | 3 | ASK-8 (new) |
| honesty-ladder items (G27/G37) | 7 | none -- by design |
| quantile-propagation customers (G17/G40) | 3 | 02 modes, post-v1 |
| claim-transform longhand pairs (G32/G41) | 3 | lithos sugar ask |

Reading of the roll-up: nothing in this vehicle requires a NEW
engine mechanism beyond what 09/10 already schedule -- the protocol
holds at vehicle scale. Every blocked claim is blocked on a
RECORDED ask or a SCHEDULED milestone, and each has an honest
degraded form today (worst-corner scalar, hand-asserted given, or
ladder item). That is the ecosystem claim, demonstrated: the
engineering content of a whole vehicle reduces to (a) declared,
cited, calibrated solvers, (b) routed evidence with budgets, and
(c) an explicit, finite list of language gaps -- nothing is
implicit, and nothing rests on an engineer's private judgment that
the tools cannot see.
