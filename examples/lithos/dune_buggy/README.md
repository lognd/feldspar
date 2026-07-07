# Dune buggy -- the whole-vehicle stress test

A single-seat off-road buggy (450cc single, CVT primary + chain
final, double-wishbone front / trailing-arm rear, hydraulic discs,
tubular spaceframe, 12V EFI electrical), written as a COMPLETE
lithos project: 27 source files across all four language tracks
(.hem, .cupr, and -- deliberately, against the PROPOSED draft --
.calc), every committed feldspar phase, and both toolchains' weakest
joints at once. It is the largest fixture in the corpus and is
INTENDED to be ridiculous: if the solver graph and the language
stack survive a vehicle, they survive a product.

Findings G34-G43 continue the log (../README.md G1-G12,
../reaction_wheel/ G13-G21, ../regen_engine/ G22-G33).
`SOLVER-TRACE.md` is the companion deliverable: for every claim
group in the project, the exact route the feldspar planner must
find -- tier, ports, eps behavior, payloads, milestone gates.

## File map

| file | subsystem | pressure applied |
|---|---|---|
| `frame.hem` | spaceframe weldment | pieces/welds, torsional stiffness (LOWER sense), collapse |
| `rollcage.hem` | roll cage | plastic collapse, proof transform (G41), assume!/test ladder (G37) |
| `suspension_front.hem` | double wishbone | kinematic config domains, camber/toe curves (G36) |
| `suspension_rear.hem` | trailing arm | terrain spectrum fatigue, bushing records |
| `coilover.hem` | spring/damper | Wahl spring, damper orifice hydraulics, ride freq (LOWER) |
| `steering.hem` | rack + tie rods | tie-rod buckling (LOWER), Ackermann, bump steer |
| `upright_hub_front.hem` | upright/hub | bearing L10, spindle fatigue, brake torque path |
| `hub_rear.hem` | rear hub/axle | sprocket carrier, axle bearing, impact torque |
| `wheel_tire.hem` | wheel + tire | tire records + vehicle namespace (G34), rim impact |
| `engine_bottom_end.hem` | crank/rod/cases | DIN 743, journal films, rod buckling, balance |
| `engine_top_end.hem` | head/valvetrain | cam Hertz contact, spring surge, port flow |
| `cvt_drive.hem` | CVT primary | belt traction, sheave Hertz, ratio coverage |
| `gearbox_final.hem` | reduction + chain | AGMA gears, chain capacity tables, sprocket wear |
| `halfshaft.hem` | halfshafts | CV joint angles, torsion fatigue under torque spectrum |
| `brake_corner.hem` | disc/caliper/pad | brake fade CoupledGroup (G38), pad mu(T) records |
| `pedal_box.hem` | pedals + masters | pedal stiffness (LOWER), bias bar, reserve travel |
| `fuel_tank.hem` | tank | slosh loads, baffle claims, strap fatigue |
| `exhaust_intake.hem` | exhaust + airbox | muffler Helmholtz (acoustics #2), header expansion |
| `bodywork.hem` | panels | bend allowance (mfg), panel modes, dust sealing |
| `seat_restraint.hem` | seat + harness | anchor proof loads, occupant ladder (G37) |
| `cooling.calc` | coolant loop | calcite customer #2 (G39): pump curve, HxSegment, thermostat |
| `fuel_system.calc` | fuel feed | calcite customer #3 (G39): vapor lock = pv(T) NPSH-analog |
| `brake_hydraulics.calc` | brake circuit | calcite customer #4 (G39): master-cylinder imposer, pedal transient |
| `electrical_power.cupr` | battery/charging | kill chain timing, ampacity, harness routing gap (G42) |
| `efi_ecu.cupr` | EFI controller | injector/VR/lambda loop (control ns), ADC budgets |
| `dash_instrumentation.cupr` | dash | sensor noise floors, warning latency |
| `vehicle.hem` | the assembly | mass/CG budgets, vehicle dynamics (G34), terrain spectra, coverage (G43) |

## Findings G34-G43

- **G34 (FIXED, 07 catalog): no vehicle-dynamics namespace
  existed.** Tire mechanics (cornering stiffness, friction ellipse,
  Magic Formula as a `Correlation` with its published fit band),
  terramechanics (Bekker-Wong pressure-sinkage and drawbar pull --
  a dune buggy lives on SAND, and no catalog area could say what
  sand does to traction or flotation), quasi-static vehicle
  dynamics (longitudinal/lateral load transfer, static stability
  factor / rollover threshold, ride frequencies, quarter-car (r)),
  and adhesion-limited braking. Added as the `vehicle` namespace;
  tire/soil data are G5-style records (published range = domain).
- **G35 (confirms 09 sec. 4): payload -> payload transform edges.**
  The terrain PSD at the wheel depends on speed: `spectrum` in,
  speed port in, rescaled `spectrum` out -- a deterministic,
  content-addressed transform, exactly the mesh-from-geometry
  precedent. Any tier reads and WRITES payloads; no spec change.
- **G36 (sharpens regolith ask, sec. 7 item 7): computed fields
  over CONFIG domains.** camber(travel), toe(travel), motion
  ratio(travel) are 1-D curves over a kinematic config variable,
  computed by four-bar solvers and consumed by sibling claims (roll
  stiffness needs the motion ratio CURVE, bump steer needs the toe
  SLOPE). Today each degenerates to worst-point scalar claims.
  Same shape as zone fields (G23) with the index axis a config
  variable instead of space -- the sec. 7 item 7 ask is extended
  rather than a new item invented. Engine-side interim is OPEN-14's
  extremal-port reduction, unchanged.
- **G37 (confirms G27): occupant injury metrics stay on the
  ladder.** Harness-anchor and cage proofs are solver territory;
  "the occupant survives the 2m drop" is not -- `assume!` with
  SAE-heritage basis, replaced `by test(...)`. The fixture pins the
  pattern outside propulsion.
- **G38 (fixture, M8): brake fade is CoupledGroup customer #2.**
  Pad mu(T) record <-> friction heat generation <-> disc
  convection/soak: two-way, and the fade claim is thin-margin on
  long descents. Proves the M8 composite mechanism generalizes
  beyond the regen wall with zero new design.
- **G39 (fixture, calcite): three more circuits.** Brake hydraulics
  (master cylinder as pressure imposer; pedal-step transient peak),
  fuel feed (vapor lock at hot soak = the NPSH/pv(T) machinery),
  coolant loop (pump curve, thermostat state domain, HxSegment
  zone coupling). Written against the PROPOSED calcite draft; they
  are reproduction demand for COPEN-1 ratification, recorded at
  sec. 7 item 6.
- **G40 (confirms G17): statistical stackups, customer #2.** Toe
  and camber build tolerance from pickup-point scatter is a
  quantile-propagation claim; worst-case corners condemn every
  buildable frame. Schedules with the mfg namespace, as before.
- **G41 (confirms G32): proof-claim transforms, customer #2.**
  Cage and anchor homologation proofs are the operating claims
  under scaled givens, written longhand here again -- the
  duplication smell is now two-for-two across big fixtures.
- **G42 (OPEN, lithos ask, sec. 7 item 8): wiring routing has no
  home.** Voltage-drop and ampacity claims need conductor LENGTHS
  and bundle factors; hoses get hematite TubeRun geometry + calcite
  extraction, but a wire run (routed path along the frame, bundle
  membership, connector environment) is inexpressible -- lengths
  are hand-asserted givens today. Recorded as the new sec. 7 ask.
- **G43 (folds into OPEN-8/sec. 7 item 2): discrete config axes in
  coverage.** `forall range_state in {low, high}` crossed with
  continuous payload/boundary domains needs coverage over MIXED
  discrete x continuous axes (calcite COPEN-7 hits the same wall
  from line-ups); the per-axis encoding ask already recorded must
  carry discrete axes, not just grids.

## What this project is FOR

- The end-state realism bar: WO-09's conformance suite grows into
  the manifold/boom fixtures first, the reaction wheel next, and
  THIS project last -- when a dune buggy's claim ledger discharges
  end to end, the ecosystem claim ("engineering as searchable,
  defensible routes over declared models") is demonstrated, not
  asserted.
- The catalog's coverage proof: SOLVER-TRACE.md maps every claim to
  a 07 catalog entry and flags the exact milestone that unblocks
  it; a claim with no catalog row is a finding by definition (G34
  was caught exactly this way).
- The coverage/coupling pressure: G36/G38/G39/G42/G43 are the
  demand signal the regolith-side asks were waiting for.
