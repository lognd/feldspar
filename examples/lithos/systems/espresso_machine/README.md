# Espresso machine -- dual-boiler E61-style, the fluorite-first D119 stress project

A dual-boiler home espresso machine (0.8L flooded brew boiler + 1.4L
steam/service boiler, E61-style thermosiphon group), written as a
COMPLETE lithos project: 14 checked source files across all three
language tracks -- the first stress project where the fluorite side
is the point rather than an add-on. Three `.fluo` circuits (brew
water path, steam/service circuit, group thermosiphon) exercise the
RATIFIED fluorite spec (docs/spec/fluorite/02, cycle 20 / D93) at three
very different corners: a pump-curve-imposed high-pressure loop, a
control-driven gas headspace, and a pump-free buoyancy loop three
orders of magnitude softer than the other two.

Every `.hema`/`.cupr` file is PARSE-CLEAN (`regolith check
examples/espresso_machine` reports 0 diagnostics over 10 files, 109
obligations). The three `.fluo` files are hand-validated against
docs/spec/fluorite/02 and, since WO-31 registered the extension,
CHECKED: `regolith check` discovers them and the directory golden
covers them (the original invisible-until-WO-31 caveat is history).

## File map

| file | subsystem | pressure applied |
|---|---|---|
| `magnetite.toml` | manifest | fluorite dependency pinned ahead of the extension landing |
| `contracts.cupr` | shared mixed-domain contracts | heater seat/flange conduction mating, thermowell/levelwell connector-role wells |
| `fittings.hema` | fluid-port + isolation contracts | FluidPort geometry hook every wetted part implements once, per-fitting leak promises, vibration isolation |
| `brew_boiler.hema` | 0.8L flooded brew vessel | welded vessel (`pieces:`), wall-temperature zones, computed-field DEMAND block, fluid-to-structural hoop pressure crossing |
| `steam_boiler.hema` | 1.4L headspace vessel | same weldment vocabulary at a different corner, waterline zone split, safety/anti-vacuum port set |
| `group_head.hema` | E61 billet group | 4-axis cross-drilled galleries, zones the thermosiphon flownet couples to BY NAME, LOWER-sense thermal-bank mass claim |
| `reservoir.hema` | 2.5L molded tank | molding vocabulary (Wall/Rib/Boss, free draft), the hot-inlet NPSH corner's geometry |
| `frame_panels.hema` | chassis + skins | sheet DFM pressure, one evidence-less prototype waiver, group-cantilever deflection through the interface envelope |
| `machine.hema` | the machine | vendor pump/heaters/probe, fluid-to-mech PRESSURE boundary crossing (peak promises entering ceilings as literals), cross-vessel mass/seal budgets |
| `control_board.cupr` | control PCB | mains-side triac switching, PT100 chains, inductive-kick claim windowed on the same event the water-hammer claim windows on |
| `controller.cupr` | control system | intents at F79 altitude, the cuprite side of the one event ledger (`commanded by`), mains power ceiling forall, sensing error budget |
| `brew_water.fluo` | brew water path | pump-curve imposer, declared net-level line-up variable, free-parameter gicleur, water-hammer peak feeding the mech boundary, NPSH, compliance + leak budgets (UNCHECKED until WO-31) |
| `steam_service.fluo` | steam/service circuit | control-driven Imposer (`driven_by=`), gas medium under v1 posture, `choked()` screening claim, LOWER-bound cooldown peak, dual single-fault sweep (UNCHECKED until WO-31) |
| `thermosiphon.fluo` | group thermosiphon | zero-imposer buoyancy-only loop, Pa/g-s unit-range stress, zone-coupled HxSegment edges, a physically dangling `from=` ref recorded as demand (UNCHECKED until WO-31) |

## Candidate findings

Recorded here per D119 (corpus authors never edit the design log;
promotion is the coordinating cycle's call). Honest and specific --
these ARE the deliverable. Numbered independently of `cnc_router`'s
CF ledger; several are fluorite-specific and would not have surfaced
from a mech/elec-only project.

- **CF-1. No spelling for a complementary two-position solenoid.**
  The three-way brew valve is physically ONE solenoid: sup open
  implies vent closed and vice versa. `brew_water.fluo` declares a
  net-level line-up variable (`state v3 in {brew, release}`) but the
  binding of that variable to the two `Valve` edges' `.position`
  states is prose-only (`brew_water.fluo:57-64`) -- 02 sec. 4 has no
  construct that ties two edge states together as one controlled
  degree of freedom. Every claim that reads `given v3 = brew` is
  trusting a comment.

- **CF-2. No routed-tube construct on either track.** The brew/
  thermosiphon/steam copper lines are real load-bearing parts (they
  carry the water-hammer pressure and the thermosiphon's entire
  elevation head) and neither hematite nor fluorite can name them:
  `machine.hema:80-84` records the mech-side gap (no tube-run source
  form to extract elevation/routing from), and
  `thermosiphon.fluo:50-58` hits the fluid-side consequence head-on
  -- `ThermoLines.riser_run`/`return_run` are `from=` refs to a part
  that does not exist. A record-bound `Hose` stand-in (used
  elsewhere in this project for the braided supply line) would carry
  compliance but NOT elevation, and in a buoyancy-driven loop
  elevation IS the physics, so the usual stand-in is dishonest here
  specifically. One gap, two tracks, two symptoms.

- **CF-3. Fluorite has no sensing crossing.** The flowmeter
  (`brew_water.fluo:34-39`) is hydraulically just a datasheet dp
  curve, but its real job is producing the pulse train
  `controller.cupr`'s `sense_flow` intent consumes. Fluorite 02 sec.
  5 gives ONE cross-track form, `commanded by` (actuation only,
  fluid effect driven by a cuprite/mech event). There is no dual
  form for "this edge's flow state is a sensing intent's physical
  origin." The link exists only as parallel prose comments in the
  two files.

- **CF-4. Reference-node multiplicity has no syntax past one.**
  `brew_water.fluo:16-19`: three physically distinct atmospheric
  terminations (tank surface, drip tray, cup) collapse onto ONE
  `reference:` node because 02 sec. 4 admits ">= 1 reference per
  subnet" but names no syntax for declaring a second, distinguished
  one. Harmless while all three really are just "atmosphere," but it
  means the language cannot currently express "vents to two
  different atmospheric points that might see different transients."

- **CF-5. Cross-flownet promise has one demonstrated shape, not a
  general one.** The autofill line's back-pressure comes from the
  STEAM net's shell pressure (`svc_bp: Imposer(...,
  driven_by=SteamService.shell_p)`, `brew_water.fluo:76-82`,
  mirrored in `steam_service.fluo:15-16`). Fluorite 03 sec. 4 only
  demonstrates the cross-TRACK promise chain (fluid value driving a
  mech/elec claim, or vice versa); a fluid-to-fluid promise across
  two DIFFERENT flownets in the same project is being used here on
  the strength of `driven_by=`'s general shape, but no spec text
  states that a flownet reference may itself be a promise source for
  another flownet's Imposer.

- **CF-6. Boundary domains cannot be per-shot free parameters.**
  The coffee puck (`brew_water.fluo:65-69`) is hand-pinned at one
  nominal grind (`dia=0.35mm`), but its resistance genuinely varies
  shot to shot -- it is a BOUNDARY condition in spirit, not a fixed
  geometry. Fluorite's `boundary:` block (mirroring hematite/
  cuprite) only takes intervals over quantities that already have a
  physical home in the net; there is no parameter KIND for "this
  edge's resolved value is itself a per-instance boundary domain."
  The corpus pins one nominal value and moves on; a real product
  claim (basket size vs. grind vs. shot time) cannot be written yet.

- **CF-7. Manual actuation has no event source.** The steam wand's
  close transition is the one `recover` (`steam_service.fluo:79`)
  windows its milk-recovery claim on, but 02's only event-declaration
  form is `commanded by <cuprite ref>` and the wand is a hand-turned
  manual valve with no controller behind it
  (`steam_service.fluo:44,66-69`). The event is left dangling as
  recorded demand rather than invented around: either a manual/
  observed event source, or an explicit statement that manual
  transitions cannot be windowed on (which would make `recover`
  itself unwritable honestly).

- **CF-8. No cross-file medium import.** `BrewWater` is declared
  verbatim, twice, in `brew_water.fluo` and `thermosiphon.fluo`
  (`thermosiphon.fluo:19-22`) because 02 gives media file-local scope
  and no import form. Two spellings of one fluid (density/viscosity
  registry, same `water_iapws_liquid` reference) is exactly the NO
  DUPLICATION failure mode the project's own engineering principles
  flag -- if one file's registry reference is ever bumped and the
  other is not, the two nets silently disagree about what water is.

- **CF-9. One physical vessel, two flownet representations, no tie.**
  The brew boiler is BOTH the `reference:` node of
  `GroupThermosiphon` (pressure+temperature anchor,
  `thermosiphon.fluo:26-30`) AND the `boiler` `Plenum` edge of
  `BrewPath` (`brew_water.fluo`) -- the same 0.8L volume, same wall,
  same wetted mass, appearing as two unrelated fluorite entities
  across two flownets with nothing in the language stating they are
  the same physical object. A conjugate solve (shared thermal mass,
  shared pressure state during a shot) is legitimately pack
  territory, but today there is not even a NAMED coupling for a
  future pack to hang off of -- rename either representation and the
  two nets drift apart with zero diagnostic.

- **CF-10. No sweep form over an assembly's interface impls.** A
  realistic service claim -- "every `FittingPort` on this machine
  opens with hand tools after 2 years of scale buildup" -- wants a
  `forall` over the INTERFACE IMPLS of an assembly's parts
  (`machine.hema:107-116`), something like `forall f in
  <part>.FittingPort.all`. `forall` today covers config domains,
  boundary intervals, declared state sets, and feature orbits
  (`welded.welds.all`), but not "every impl of interface X across
  every part in this assembly." The per-fitting leak PROMISES in
  `fittings.hema` carry the serviceable-joint intent as a proxy
  instead; the sweep form itself is recorded as demand, not invented.

## What this project is FOR

- The fluorite spec's first real load test against the ratified
  text (docs/spec/fluorite/02, D93): three flownets at three physical
  regimes (forced high-pressure, control-driven gas, buoyancy-only)
  stress the same handful of constructs (`Imposer`, `Plenum`,
  `Orifice`, `CheckValve`, declared states, the one-event-ledger
  cuprite crossing) hard enough to surface CF-1 through CF-9 above.
- The mech/elec sides carry their own share of the D119 stress
  program too: weldment vessels with zones, molded tanks, sheet DFM,
  a mixed-domain contract pack, and one written-out analog escape
  hatch on the control board.
- The findings above are reproduction demand for the next design
  cycle, in the same spirit as `cnc_router`'s CF-1..CF-9 and
  feldspar's dune-buggy ledger.
