# 07 -- Capability map

One sentence: the long-run solver library spans the analysis content
of accredited engineering curricula (mechanical, aerospace,
civil/structural, electrical, chemical), built as namespaced library
packs over the one engine protocol, in phases ordered by what the
lithos toolchain can consume -- and the method catalog below is the
enumerated scope.

Each capability is a `library/<namespace>` module registering
closed-form or table solvers (03), plus -- where warranted -- a
heavyweight numeric tier (05's pipeline pattern, integrated per 09).
Every formula has exactly one home here; FEA oracles, pack models,
and future regolith closed-form parity all import it (NO
DUPLICATION). Formula homes are Rust (03, Rust computation homes) so
any namespace subset is extractable for embedded targets (01).

**feldspar is the one backend; namespaces are the capabilities**
(DECIDED 2026-07-07, closes OPEN-7). New disciplines are new
namespaces in this repo, not sibling packs: one engine, one
registration protocol, one calibration harness, one pack entry point.
Namespacing prevents collision; cross-namespace bridges are ordinary
solver edges (03).

## Cross-phase infrastructure

- **Calibration harness** (03): ships with Phase 1; every phase's
  solvers must register with method citations and calibration
  evidence. No phase's solvers are exempt.
- **Numeric-tier pattern** (05, integrated per 09): mesh/deck/run/
  parse/eps-estimate as separate pure stages; modal analysis, SPICE,
  and future tiers instantiate the pattern rather than inventing
  their own pipeline shape.

## Method catalog

Derived from the analysis core of accredited BS/MS engineering
curricula and the canonical texts and handbooks those courses assign
(cited per area below; each entry's implementing solver must carry
its own precise citation, 03). Conventions:

- Every entry is solver-shaped: typed ports in, typed ports out, a
  validity domain (often the published applicability range -- the
  Domain concept earns its keep on correlations), declared accuracy.
- The catalog is committed SCOPE ("designed-for; the architecture
  must never make it harder"), not committed order: entries enter the
  library only through a scheduled phase WO, with citations and
  calibration.
- Tier tags: (t)=table, (r)=reduced numeric, (d)=discretized numeric;
  untagged = closed form.

### mech.statics -- Statics (Beer & Johnston; Hibbeler)

- Rigid-body equilibrium reductions, 2D/3D force/moment balance.
- Truss member forces: method of joints, method of sections.
- Frame/machine member loads; two-force/three-force reductions.
- Distributed-load resultants; centroids; first/second moments of
  area; parallel-axis composites; product of inertia, principal axes.
- Dry friction: slip/tip, wedges, screws, belt friction (capstan).
- Cables: parabolic and catenary sag-tension.

### mech.materials -- Mechanics of materials (Gere; Hibbeler; Roark's
Formulas for Stress and Strain; Peterson's charts)

- Axial members: stress/strain, thermal stress, statically
  indeterminate assemblies.
- Torsion: circular shafts, thin-walled closed sections (Bredt),
  open thin sections, shaft power relations.
- Beam bending: flexure formula, transverse shear and shear flow,
  built-up and composite (transformed-section) beams, unsymmetric
  bending.
- Beam deflection: superposition tables (t, Roark), singularity
  functions, indeterminate beams, three-moment equation.
- Stress state: plane-stress/strain transformation, Mohr's circle,
  principal stresses, octahedral/von Mises equivalent (the single
  `von_mises` home).
- Static failure theories: von Mises, Tresca, max-normal,
  Coulomb-Mohr and modified Mohr for brittle materials.
- Pressure vessels: thin-wall membrane, thick-wall Lame, compound
  cylinders, press/shrink fits, rotating disks.
- Columns and stability: Euler buckling with end-condition factors,
  secant formula, Johnson parabola, empirical column curves (t).
- Energy methods: Castigliano, unit-load/virtual work, impact
  factors.
- Stress concentrations: Kt charts (t, Peterson).
- Contact stress: Hertz sphere/cylinder pairs, subsurface shear.
- Plates and shells: Kirchhoff plate bending coefficient tables (t,
  Roark), membrane shell equations.

### mech.design -- Machine design (Shigley/Budynas; Norton; Juvinall;
VDI 2230; AGMA/ISO standards)

- Fatigue: Basquin S-N, endurance limit with Marin modification
  factors, mean-stress criteria (Goodman, Gerber, Soderberg, Morrow),
  Miner cumulative damage, rainflow counting (r), notch sensitivity
  (Neuber, Kf), strain-life (Coffin-Manson).
- Fracture: LEFM stress intensity K = Y*sigma*sqrt(pi*a) with
  geometry-factor tables (t), fracture-toughness screening, Paris-law
  crack growth life (r), leak-before-break.
- Shafts: combined static loading (DIN 743 / ASME shaft equations),
  deflection/slope limits, critical speed (Rayleigh, Dunkerley).
- Bolted joints: joint/bolt stiffness, preload and torque-preload,
  VDI 2230 joint diagram, separation and slip margins, thread shear,
  bolt-group load distribution.
- Welds: fillet throat stress, weld-group treated-as-line method
  (AWS/Shigley), fatigue categories (t, Eurocode 3 detail classes).
- Springs: helical compression/extension (Wahl factor), torsion
  springs, Belleville stacks.
- Bearings: rolling-element L10 life and static capacity (ISO 281),
  equivalent loads; journal bearings (Petroff, Raimondi-Boyd
  charts (t)).
- Gears: involute geometry/ratios, AGMA bending (Lewis + J factor)
  and contact (pitting) stresses, gear-train kinematics including
  planetary (Willis).
- Power transmission: belts and chains (t, capacity tables), clutch/
  brake torque and energy, power screws (efficiency,
  self-locking).

### mech.struct -- Structural analysis (Hibbeler Structural Analysis;
AISC Steel Construction Manual; Eurocode)

- Influence lines and moving loads.
- Classical indeterminate methods: slope-deflection, moment
  distribution.
- Matrix direct stiffness: truss/beam/frame/grid (r) -- the first
  reduced tier, and the bridge to FEA proper.
- Plastic analysis: plastic hinges, collapse mechanisms, shape
  factors.
- Member design checks (t/closed: AISC/Eurocode curves): flexural
  members, lateral-torsional buckling, plate buckling, combined
  axial+bending interaction.
- Connections: bolt groups (elastic + instantaneous center), weld
  groups, block shear.

### dynamics -- Dynamics and machines (Hibbeler/Meriam dynamics;
Norton/Uicker theory of machines)

- Particle/rigid-body kinematics and kinetics; relative motion;
  rotating frames.
- Work-energy and impulse-momentum; impact with restitution.
- Mechanisms: four-bar and slider-crank position/velocity/
  acceleration, transmission angle, cam-follower kinematics and
  dynamic loading.
- Flywheel sizing from torque fluctuation; rotating and
  reciprocating balance; gyroscopic moments.

### vibration -- Vibrations (Rao; Den Hartog; Steinberg for
electronics)

- SDOF: natural frequency, damping/log decrement, forced response,
  transmissibility and isolation, base excitation, rotating
  unbalance.
- MDOF lumped: eigenvalue natural frequencies and mode shapes (r),
  Rayleigh quotient, Dunkerley bound, tuned absorbers.
- Continuous members: beam/plate modal coefficient tables (t).
- Random vibration: Miles' equation, PSD-to-GRMS arithmetic, fatigue
  under random loading (with mech.design).
- Shock: shock response spectra (r); drop/half-sine survival checks.
- Rotor dynamics: critical speeds, whirl screening.
- Numeric tier (d): ccx modal / harmonic / transient reusing the 05
  pipeline (09 M6).

### materials -- Materials engineering (Callister; Ashby; Dowling;
composite texts: Jones)

Property RECORDS are table solvers (friction G5): an
environment-dependent record (`E: f(T) interval`) registers as an
edge `thermo.temperature -> mech.material.youngs_modulus`, so the
ordinary corner discipline evaluates the T_env worst corner and
material ports are outputs, never free givens. regolith's property
registries (regolith/02 sec. 6) are the data source; feldspar wraps,
never copies.

- Property estimation: rule of mixtures, Halpin-Tsai; classical
  laminate theory ABD matrices (r); first-ply failure (Tsai-Wu,
  Tsai-Hill, max-stress).
- Hardness scale conversions and UTS-hardness correlations (t).
- Creep: Larson-Miller parameter (t), Norton power law, stress
  relaxation.
- Environmental life: Arrhenius acceleration, galvanic-series
  compatibility screening (t).
- Thermal-expansion mismatch stress (bimetal, constrained joints).

### thermo -- Thermodynamics (Moran; Cengel & Boles; NIST/CoolProp
property data)

- Ideal gas directions; real gas via compressibility charts (t) and
  cubic EOS (van der Waals, Redlich-Kwong, Peng-Robinson).
- Property tables (t): steam, refrigerants, air -- interpolated with
  declared interpolation eps and table-domain boxes (CoolProp as a
  wrapped in-process source, 03).
- Device models: turbines, compressors, pumps, nozzles, throttles,
  mixing chambers, heat exchangers -- first/second law with
  isentropic efficiencies.
- Cycles: Rankine (+ reheat/regenerative), Brayton (+ regeneration,
  intercool/reheat), Otto, Diesel, dual, vapor-compression
  refrigeration and heat pumps, combined cycles.
- Combustion: stoichiometry, air-fuel ratio, heating values,
  adiabatic flame temperature.
- Psychrometrics: humid-air properties, HVAC process lines.
- Exergy: dead-state availability, second-law efficiencies.

### fluids -- Fluid mechanics (White; Fox & McDonald; Crane TP-410;
Idelchik)

- Hydrostatics: pressure fields, forces on plane/curved surfaces,
  buoyancy and stability (metacentric height).
- Energy equation with losses; EGL/HGL bookkeeping.
- Internal flow: Poiseuille laminar exact, turbulent friction factors
  (Colebrook implicit, Haaland/Swamee-Jain explicit; Moody as
  table (t)), minor-loss K tables (t, Crane/Idelchik), pipe networks
  (Hardy Cross (r)).
- External flow: drag/lift correlations (flat plate, cylinder,
  sphere), boundary-layer estimates (Blasius, 1/7th-power).
- Compressible flow: isentropic relations, normal and oblique
  shocks, Fanno and Rayleigh lines, converging-diverging nozzle
  operation.
- Open channel: Manning, normal/critical depth, hydraulic jump.
- Turbomachinery: similarity/affinity laws, specific speed, NPSH and
  cavitation margins, pump-system curve matching.
- Flow measurement: orifice/venturi/nozzle per ISO 5167 (published
  uncertainty IS the declared accuracy).
- CFD (d): named as the far-future full tier; determinism cost is
  acknowledged up front, not assumed away.

### heat -- Heat transfer (Incropera; Cengel)

- Conduction: 1-D resistance networks (plane/cylindrical/spherical,
  contact resistance), critical insulation radius, 2-D conduction
  shape factors (t), extended surfaces (fin efficiency/
  effectiveness).
- Transient conduction: lumped capacitance, one-term Heisler/Grober
  solutions (t), semi-infinite solids.
- Forced convection correlations, each with its published Re/Pr
  validity box as its Domain: Dittus-Boelter, Gnielinski,
  Sieder-Tate (internal); flat plate, Churchill-Bernstein cylinder,
  Whitaker sphere, Zukauskas tube banks (external).
- Natural convection: Churchill-Chu, vertical/horizontal plates,
  enclosures.
- Boiling/condensation: Rohsenow pool boiling, critical heat flux,
  Nusselt film condensation.
- Radiation: view-factor algebra + tables (t), gray-diffuse network
  exchange, shields.
- Heat exchangers: LMTD with F-correction charts (t),
  effectiveness-NTU, fouling allowances.
- Numeric tier (d): FD/FE conduction via ccx thermal, reusing the 05
  pipeline and the M2 mesh step (09).

### elec -- Circuits, electronics, power (Nilsson; Sedra-Smith;
Razavi; Erickson & Maksimovic; Mohan; IPC standards)

- DC/AC steady state: nodal/mesh reduction, Thevenin/Norton, phasor
  impedance, resonance, three-phase power, power-factor correction.
- Transients: first/second-order RC/RL/RLC step and switching
  responses.
- Power systems: transformer equivalent circuits, per-unit
  arithmetic, symmetrical-component fault currents, AC power flow
  (r); machine steady-state models (DC, induction, synchronous).
- Electronics: diode/BJT/MOSFET operating points, small-signal gain/
  bandwidth (Miller effect), op-amp non-idealities (GBW, slew,
  offset, noise), active-filter tables (Butterworth/Chebyshev) (t),
  Sallen-Key/MFB synthesis, oscillator criteria (Barkhausen).
- Power electronics: buck/boost/buck-boost/flyback steady state,
  ripple, CCM/DCM boundary, switching + conduction losses, magnetics
  sizing (area product, Steinmetz core loss), semiconductor thermal
  derating.
- Interconnect: IPC-2221 trace current capacity, IPC-2141 microstrip/
  stripline impedance, voltage-drop budgets, fusing current.
- Energy storage: battery capacity/derating, Peukert, cell series/
  parallel arithmetic.
- Signal integrity (reduced): reflection/termination arithmetic,
  crosstalk estimates, eye/jitter budgets.
- Numeric tier (d): ngspice op/dc/ac/tran inside `elec` (09 M7).

### elec.em -- Electromagnetics and RF (Pozar; Balanis; Paul EMC)

- Transmission lines: Z0, reflection coefficient, VSWR, input
  impedance, quarter-wave and stub matching (Smith-chart
  arithmetic).
- Link budgets: Friis transmission, EIRP, path-loss models, cascade
  noise figure (Friis noise), G/T, link margin (coordinated with
  regolith's existing link-budget model -- share, never duplicate).
- EMC: shielding-effectiveness estimates, filter insertion loss,
  emissions-mask arithmetic (CISPR masks as `mask` payloads, 09
  sec. 4).

### signal -- Signals and communication (Oppenheim & Willsky;
Proakis)

- Sampling: Nyquist, aliasing checks, quantization SNR, ADC/DAC
  error budgets (ENOB arithmetic).
- Spectral estimates (r): FFT-based PSD, in-band RMS -- the numeric
  backends for regolith's `rms(x, band=...)` claim form.
- Noise: thermal/shot/flicker budgets, SNR cascades, AWGN BER
  waterfalls (t/closed), Shannon capacity bounds.

### control -- Control systems (Ogata; Nise; Franklin Powell)

- Transfer-function and block-diagram algebra.
- Stability: Routh-Hurwitz, gain/phase margins from frequency
  response (r evaluation), Nyquist criterion (r).
- Time response: second-order metrics (overshoot, settling, rise),
  steady-state error constants; these back regolith's `settles(...)`
  and `overshoot(...)` claim forms.
- Design rules: PID tuning (Ziegler-Nichols, lambda/IMC), lead-lag
  placement, root-locus evaluation (r).
- State space: controllability/observability, pole placement, LQR
  (r), ZOH discretization, discrete stability (Jury).

### mfg -- Manufacturing analysis (Kalpakjian; Groover; Machinery's
Handbook)

Coordinated with regolith's planner-model territory (regolith/07
sec. 6): feldspar owns the FORMULAS (cheap conservative tier);
plan-shaped decisions stay regolith planner models.

- Machining: cutting force/power via specific cutting energy, Taylor
  tool life, MRR, surface-finish estimates (t).
- Tolerance analysis: worst-case and RSS stackups -- a direct client
  of the interval and normal propagation modes (02); process
  capability Cp/Cpk.
- Forming: bend allowance/K-factor, springback estimates,
  deep-drawing limits (the WO-22 cut 3 reopen path).
- Joining/casting/molding: welding heat input and cooling,
  Chvorinov solidification time, injection cooling-time estimates.

### aero -- Aerospace (Anderson; Sutton & Biblarz) [catalog only;
no lithos demand yet]

- Standard atmosphere (t); airfoil/wing lift-curve and induced-drag
  corrections; Breguet range/endurance.
- Orbits: two-body elements, Hohmann transfers, plane-change costs.

### prop -- Propulsion (Sutton & Biblarz; Huzel & Huang; NASA
SP-8087/8124; found by the regen-engine stress test, G26/G30)

- Ideal rocket relations: c*, thrust coefficient Cf, Isp (g0-
  referenced unit view), expansion-ratio/pressure relations,
  throat sizing.
- Combustion equilibrium: CEA-class equilibrium chemistry as a
  wrapped external tool tier (d) producing gas properties
  (gamma, M_w, T_c, transport) with cited fidelity.
- Heat load: Bartz hot-gas convection correlation (its published
  band IS its accuracy), film/curtain cooling effectiveness
  correlations, radiation from combustion gases (t).
- Regen cooling: channel hydraulics + the coupled wall loop
  (CoupledGroup, 09 sec. 4b -- the reference coupled fixture).
- Feed: injector element hydraulics (orifice/swirl), injector
  stiffness (chugging margin), water hammer (Joukowsky + method of
  characteristics (r)).

### acoustics -- Acoustics (Kinsler & Frey; NASA SP-194) [added by
finding G26 -- the catalog had NO acoustics home]

- Cavity mode frequencies: cylindrical/annular chamber transverse
  and longitudinal modes (closed form), duct/room modes.
- Resonator sizing: Helmholtz and quarter-wave damper tuning,
  absorption estimates.
- Screening: mode-separation checks (injector response vs chamber
  modes); full combustion-stability rating stays EMPIRICAL
  (assume!/waive-by-test ladder, fixture G27) -- deliberately NOT a
  solver.

### vehicle -- Ground-vehicle dynamics and terramechanics
(Gillespie; Milliken; Pacejka; Wong Theory of Ground Vehicles)
[added by finding G34 -- the dune-buggy stress test: the catalog
had NO home for what a vehicle does on a surface]

- Tire mechanics: cornering stiffness, friction ellipse /
  combined-slip envelopes, Magic Formula fits as `Correlation`s
  (the published fit range IS the domain), load/pressure
  sensitivity, rolling resistance -- tire data are G5-style vendor
  RECORDS, wrapped never copied.
- Terramechanics: Bekker-Wong pressure-sinkage, drawbar pull vs
  compaction/bulldozing resistance, flotation/sinkage on deformable
  terrain (t/cf) -- soil parameter records with cited test
  conditions.
- Quasi-static vehicle dynamics: longitudinal/lateral load
  transfer, static stability factor / rollover threshold,
  gradeability, Ackermann/steering geometry errors, ride
  frequencies and flat-ratio rules, quarter-car response (r).
- Braking performance: adhesion-limited deceleration, brake bias/
  proportioning, stopping distance envelopes.
- Driveline load cases: traction-limited torque, shock/application
  factors (t) -- the honest upstream givens for mech.design shafts,
  gears, and chains.

### chem -- Chemical/process engineering (Fogler; McCabe Smith
Harriott) [catalog only; no lithos demand yet]

- Reaction: Arrhenius kinetics, ideal reactor sizing (batch, CSTR,
  PFR), conversion/selectivity.
- Separations: flash/VLE (Raoult + activity models), McCabe-Thiele
  staging, absorption/stripping.
- Mass-transfer correlations (film coefficients, packed columns),
  with heat/fluids sharing the dimensionless-group homes.

## Phases (committed sequencing over the catalog)

Phases follow lithos demand, not curriculum order; each phase is a
work order appended to `implementation/` when scheduled. Only Phase 1
is committed scope now (WO-05).

- **Phase 1 -- solid mechanics (v1, ships with WO-27)**: the
  `mech.materials` entries needed as FEA oracles (rect section
  properties, cantilever deflection, Lame thick-wall, von Mises) plus
  the FEA reduced tier (05). The catalog's remaining `mech.*` waves
  in behind it.
- **Phase 2 -- thermal-fluids**: `thermo` property tables + device
  models, `fluids` internal flow, `heat` conduction/convection
  correlations (the README's motivating example).
- **Phase 3 -- dynamics and vibration**: `dynamics`, `vibration`
  including the ccx modal tier; gated on structured ports (09 M6,
  OPEN-11 residual).
- **Phase 4 -- electrical**: `elec` closed forms coordinated with
  regolith's built-ins (shared claim kinds, never duplicated);
  ngspice numeric tier INSIDE feldspar's `elec` namespace (DECIDED
  2026-07-07, closes OPEN-7; regolith/11's `spice.ngspice` naming is
  illustrative -- ask recorded regolith-side,
  `lithos:docs/spec/toolchain/20-solver-abstraction.md` sec. 7).
- **Phase 5 -- controls and signals**: `control` + `signal`;
  deliberately last among the original phases, lithos-side demand
  speculative until cuprite's behavioral layer stabilizes.
- **Phase 6 -- civil/structural (ADDED 2026-07-08, pulled forward
  by lithos calcite, D133/D139/D146 -- exactly this map's rule:
  phases follow lithos demand)**: `mech.struct` (direct stiffness
  frame tier, member design checks, connections) consuming the
  `frame` payload (09 sec. 4), the `civil.utilization` /
  `mech.deflection` / drift / modal claim kinds calcite lowers, and
  the geotech-record consumers its retaining-wall corpus names.
  Gated on lithos WO-48 producing frames in the wild; WO-21 here.
- **Unphased catalog** (`materials`, `mfg`, `aero`, `chem`,
  `vehicle`; `mech.struct` graduated to Phase 6): committed scope,
  scheduled when a lithos consumer or an owner decision pulls them
  forward. The dune-buggy fixture (examples/lithos/dune_buggy/)
  remains the standing demand signal for `vehicle` (its
  SOLVER-TRACE names every blocked claim). STANDING DEMAND (lithos
  D144, cycle 27): the pattern/mechanism libraries
  (`std.mech.mechanisms` etc.) consume `dynamics` (four-bar/cam
  kinematics) and `mech.design` (screws, belts, gears) entries as
  their model halves -- schedule those catalog areas with or right
  after the phase that first needs them.

## Ordering rationale

hematite's mechanical claims (stress, deflection) are live today ->
Phase 1; thermal/fluids claims are the next spec pressure; electrical
overlaps regolith built-ins and must be coordinated, not raced;
controls/signals wait on cuprite. The catalog exists so that no
phase's design decisions (port vocabulary, payload kinds, namespace
layout) can accidentally foreclose a later area -- scope reviews
check new mechanisms against the whole catalog, not the current
phase.
