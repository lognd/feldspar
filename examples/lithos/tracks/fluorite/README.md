# examples/tracks/fluorite/

Single-file, teaching-scale fluid circuits (design-log cycle 23 /
D122, extended by WO-31 D5). Every construct is hand-validated against
`docs/spec/fluorite/02` (language) and cited to its section. As of WO-31 the
`.fluo` extension is registered (`crates/regolith-syntax`), so `regolith
check` parses these files and runs the fluid net discipline (fluorite/02
sec. 4) over them: every file here is `regolith check`-clean (it parses
losslessly and passes the E02xx fluid-discipline checks). Lowering to
obligations and solving remain WO-32.

## File map

| file | subsystem | pressure applied |
|---|---|---|
| `garden_irrigation.fluo` | drip irrigation | simplest shape: one `medium`, one `reference`, plain `Pipe` edges, a four-emitter `Orifice` orbit (named-list form), `dp` + `flow_imbalance` claims (02 sec. 6) |
| `aquarium_loop.fluo` | filtration loop | `Pump(curve=...)` record, `Filter(dp_curve=...)`, `CheckValve`, `npsh_margin` claim, edge-parameter state + `event ... commanded by`, a startup `settles` transient claim |
| `hydraulic_jack.fluo` | bottle jack | `Imposer(driven_by=...)` cross-track promise (mech handle force -> hydraulic pressure), `volume_consumed` compliance budget, `peak` claim on a release event |
| `shop_air.fluo` | compressed-air drop | gas medium (`ShopAir`) evaluated at temperature corners, `Regulator`, `Plenum` capacitance, `choked` regime screening, `forall` over a declared line-up state |
| `chilled_water_loop.fluo` | enclosure cooling | `HxSegment(zone=...)` mech-zone coupling, thermostat state sweep, `forall` line-up, `leak_total` circuit budget |
| `feed_system.fluo` | pressure-fed propellant leg | `Regulator` pressure imposer + `CheckValve` + metering `Orifice` (the WO-31 D5 feed shape), `dp`/`supply`/`reynolds` claims |
| `dual_brake_circuit.fluo` | dual-circuit hydraulic brake | `Imposer(driven_by=...)` master cylinder, dual-circuit `state` variables (`front_circuit`/`rear_circuit`), `forall` over declared state refs (the WO-31 D5 brake shape, fluorite/02 sec. 5 failure idiom) |
| `gn2_purge.fluo` | GN2 purge blowdown | (cycle 27, D141) the compressible-regime route: friction-dominated gas line, `fluids.mach` screening + `choked` metering, ordinary dp/pressure/mdot claims that the compressible TIER discharges -- honestly indeterminate until feldspar WO-20 registers it |
| `ullage_press.fluo` | pressurant-into-ullage tank | (cycle 27, D142) the `Mixer` declared-outlet medium boundary on FOPEN-1's expected first case: two single-medium subnets, one tank component in both, mixture properties as a RECORD |

## Conventions

- Comments cite the `fluorite/02` (or `/03` for lowering-visible
  behavior) section a construct exercises.
- Engineering numbers are realistic for the named subsystem (hose-bib
  pressure, ISO VG32 hydraulic oil, 60/40 ethylene-glycol/water, shop
  air at 620 kPa set pressure, etc.).
- Cross-track promise references (`handle.applied_force`,
  `handle_force`, `pump_stroke_displacement` in `hydraulic_jack.fluo`)
  are left unresolved on purpose, exactly like the `pedal_force`
  example in `fluorite/02` sec. 3 -- a single-file teaching fixture
  shows one side of a promise chain that a real multi-file project
  would close on the mech side.
- Reference nodes (`ambient(...)`) are never listed in a flownet's
  `nodes:` line, matching the worked example in `fluorite/02` sec. 4:
  the reference's own name is a synthesized node, not a declared one.

## Status (updated cycle 27)

`.fluo` is registered (WO-31: the extension registry, parse, and
the E020x fluid net discipline) and LOWERED (WO-32: elaboration,
the FlownetPayload, every claim form's obligation shape -- landed
cycle 24). Every pre-cycle-27 file here is check-clean and the two
enrolled goldens freeze the lowering output. Still pending:
the FOPEN-1 medium-binding ENFORCEMENT (WO-49) and the cycle-27
additions' machinery (WO-52: `Mixer` boundary treatment, and the
compressible discharge tier feldspar-side, WO-20 there) -- the two
new fixtures are spec pressure for exactly those.

## Candidate findings

- RESOLVED (D125a, cycle 23): flownet names follow the standard
  top-level declaration rule (package-scope uniqueness, INV-18) --
  `fluorite/02` sec. 4 states this.
- RESOLVED (D125b, cycle 23): the bracketed edge-list form for
  entity-set claim args (`fluids.flow_imbalance([e1, e2, e3, e4])`)
  is canonical alongside query and orbit refs -- `fluorite/02`
  sec. 6 states this.
- RESOLVED (D125c, cycle 23): `Plenum` is a two-terminal storage
  edge; both plumbing forms (in-line receiver, node-to-reference
  accumulator) are expressible -- `fluorite/02` sec. 3 states this.
- NEW (cycle 27, `ullage_press.fluo`): the cross-subnet identity of
  a mixer-shaped component (one physical tank with terminals in two
  flownets) is spelled here via component paths
  (`press_tank.ullage`/`press_tank.fuel_path`, the InjectorHead
  precedent) with the `Mixer` edge on the pressurant side. D142
  decides the SEMANTICS (declared outlet, mixture records, subnet
  boundary); WO-52 confirms or adjusts this SPELLING when it
  implements the boundary treatment -- if it changes, this fixture
  updates with it.
