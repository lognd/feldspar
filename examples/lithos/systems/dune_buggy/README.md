# Dune buggy -- the whole-vehicle stress test

A single-seat off-road buggy (450cc single, CVT primary + chain
final, double-wishbone front / trailing-arm rear, hydraulic discs,
tubular spaceframe, 12V EFI electrical), written as a COMPLETE
lithos project: 27 source files across all four language tracks
(.hema, .cupr, and -- deliberately, against the PROPOSED draft --
.fluo), every committed feldspar phase, and both toolchains' weakest
joints at once. It is the largest fixture in the corpus and is
INTENDED to be ridiculous: if the solver graph and the language
stack survive a vehicle, they survive a product.

Findings G34-G43 continue the log (the feldspar-fixtures ledger
G1-G12, ../reaction_wheel/ G13-G21, ../regen_engine/ G22-G33).
(The old SOLVER-TRACE.md companion -- per-claim route/gate mapping
-- was retired in cycle 27, owner directive: every milestone it
gated on is now a scheduled feldspar WO; git history keeps it.)

## File map

| file | subsystem | pressure applied |
|---|---|---|
| `frame.hema` | spaceframe weldment | pieces/welds, torsional stiffness (LOWER sense), collapse |
| `rollcage.hema` | roll cage | plastic collapse, proof transform (G41), assume!/test ladder (G37) |
| `suspension_front.hema` | double wishbone | kinematic config domains, camber/toe curves (G36) |
| `suspension_rear.hema` | trailing arm | terrain spectrum fatigue, bushing records |
| `coilover.hema` | spring/damper | Wahl spring, damper orifice hydraulics, ride freq (LOWER) |
| `steering.hema` | rack + tie rods | tie-rod buckling (LOWER), Ackermann, bump steer |
| `upright_hub_front.hema` | upright/hub | bearing L10, spindle fatigue, brake torque path |
| `hub_rear.hema` | rear hub/axle | sprocket carrier, axle bearing, impact torque |
| `wheel_tire.hema` | wheel + tire | tire records + vehicle namespace (G34), rim impact |
| `engine_bottom_end.hema` | crank/rod/cases | DIN 743, journal films, rod buckling, balance |
| `engine_top_end.hema` | head/valvetrain | cam Hertz contact, spring surge, port flow |
| `cvt_drive.hema` | CVT primary | belt traction, sheave Hertz, ratio coverage |
| `gearbox_final.hema` | reduction + chain | AGMA gears, chain capacity tables, sprocket wear |
| `halfshaft.hema` | halfshafts | CV joint angles, torsion fatigue under torque spectrum |
| `brake_corner.hema` | disc/caliper/pad | brake fade CoupledGroup (G38), pad mu(T) records |
| `pedal_box.hema` | pedals + masters | pedal stiffness (LOWER), bias bar, reserve travel |
| `fuel_tank.hema` | tank | slosh loads, baffle claims, strap fatigue |
| `exhaust_intake.hema` | exhaust + airbox | muffler Helmholtz (acoustics #2), header expansion |
| `bodywork.hema` | panels | bend allowance (mfg), panel modes, dust sealing |
| `seat_restraint.hema` | seat + harness | anchor proof loads, occupant ladder (G37) |
| `cooling.fluo` | coolant loop | fluorite customer #2 (G39): pump curve, HxSegment, thermostat |
| `fuel_system.fluo` | fuel feed | fluorite customer #3 (G39): vapor lock = pv(T) NPSH-analog |
| `brake_hydraulics.fluo` | brake circuit | fluorite customer #4 (G39): master-cylinder imposer, pedal transient |
| `electrical_power.cupr` | battery/charging | kill chain timing, ampacity, harness routing gap (G42) |
| `efi_ecu.cupr` | EFI controller | injector/VR/lambda loop (control ns), ADC budgets |
| `dash_instrumentation.cupr` | dash | sensor noise floors, warning latency |
| `vehicle.hema` | the assembly | mass/CG budgets, vehicle dynamics (G34), terrain spectra, coverage (G43) |

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
- **G39 (fixture, fluorite): three more circuits.** Brake hydraulics
  (master cylinder as pressure imposer; pedal-step transient peak),
  fuel feed (vapor lock at hot soak = the NPSH/pv(T) machinery),
  coolant loop (pump curve, thermostat state domain, HxSegment
  zone coupling). Originally written against the PROPOSED fluorite
  draft as reproduction demand for COPEN-1 ratification (sec. 7
  item 6). RESOLVED: fluorite ratified (D93) and implemented
  (lithos WO-31/32); these files carry ratified `.fluo` syntax
  today, and their claims await feldspar's fluids consumer wave
  (WO-20).
- **G40 (confirms G17): statistical stackups, customer #2.** Toe
  and camber build tolerance from pickup-point scatter is a
  quantile-propagation claim; worst-case corners condemn every
  buildable frame. Schedules with the mfg namespace, as before.
- **G41 (confirms G32): proof-claim transforms, customer #2.**
  Cage and anchor homologation proofs are the operating claims
  under scaled givens, written longhand here again -- the
  duplication smell is now two-for-two across big fixtures.
- **G42 (lithos ask, sec. 7 item 8): wiring routing has no
  home.** Voltage-drop and ampacity claims need conductor LENGTHS
  and bundle factors; hoses get hematite TubeRun geometry + fluorite
  extraction, but a wire run (routed path along the frame, bundle
  membership, connector environment) is inexpressible -- lengths
  are hand-asserted givens today. Recorded as the new sec. 7 ask.
  RESOLVED as a decision (D99, routed runs: the cuprite `harness:`
  block sharing the realized-geometry extraction seam); grammar
  landed (lithos WO-34 D1), the extraction slices are queued
  (WO-34 D2-D6).
- **G43 (folds into OPEN-8/sec. 7 item 2): discrete config axes in
  coverage.** `forall range_state in {low, high}` crossed with
  continuous payload/boundary domains needs coverage over MIXED
  discrete x continuous axes (fluorite COPEN-7 hits the same wall
  from line-ups); the per-axis encoding ask already recorded must
  carry discrete axes, not just grids. RESOLVED: D95's structured
  Coverage carries enumerated domains per axis; lithos WO-30
  landed; feldspar reports it via WO-14.

## What this project is FOR

- The end-state realism bar: WO-09's conformance suite grows into
  the manifold/boom fixtures first, the reaction wheel next, and
  THIS project last -- when a dune buggy's claim ledger discharges
  end to end, the ecosystem claim ("engineering as searchable,
  defensible routes over declared models") is demonstrated, not
  asserted.
- The catalog's coverage proof: every claim maps to a feldspar 07
  catalog entry with its unblocking milestone now a scheduled WO
  (feldspar WO-12..22); a claim with no catalog row is a finding by
  definition (G34 was caught exactly this way, via the retired
  SOLVER-TRACE mapping).
- The coverage/coupling pressure: G36/G38/G39/G42/G43 are the
  demand signal the regolith-side asks were waiting for.
