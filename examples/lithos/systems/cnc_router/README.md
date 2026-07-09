# Burin -- 3-axis CNC router, the D119 flagship stress project

A moving-gantry CNC router (620 x 520 x 120 mm work envelope in the
s600 variant, 920 x 520 x 120 in s900; 2.2 kW 24000 rpm ER20
spindle; 48 V steppers on ground ballscrews), written as a COMPLETE
lithos project: 17 checked source files across all three language
tracks plus one `.fluo` circuit, deliberately pushing every construct
family at once -- generics monomorphized under real load, five-stage
machining pipelines, weldments, variants, sealed brownfield imports,
the computer track's WCET ladder, and a machine-wide positioning
budget. Modeled on feldspar's `examples/lithos/dune_buggy` ledger
convention (per-file pressure column, candidate-findings ledger).

Every `.hema`/`.cupr` file is PARSE-CLEAN (`regolith check
examples/cnc_router` reports 0 diagnostics over 17 files); claim
forms the harness cannot yet lower are EXPECTED and land in the
deferral golden -- that is the honest gap inventory doing its job
(D119).

**The `.fluo` status** (updated cycle 27): `coolant.fluo` is
written against the RATIFIED fluorite spec (fluorite 02/03,
cycle 20 / D93); since WO-31 registered the extension, `regolith
check` discovers and checks it like every other source, and this
project's golden covers the whole directory. The original
invisible-until-WO-31 caveat is history.

## File map

| file | subsystem | pressure applied |
|---|---|---|
| `magnetite.toml` | manifest | evidence-ref pinning for FAI/survey docs |
| `contracts.hema` | shared mech contracts | parametric interfaces, promise slots (stiffness/thermal), `redundant` mating, effects routing |
| `contracts.cupr` | shared elec contracts | mixed-domain roles, couples-only matings, WO-34 harness prose at every run |
| `frame.hema` | welded base frame | `pieces:`/`joins=`, FilletWeld + GrooveWeld, forall-over-welds claim, machining across piece boundaries |
| `bed_plate.hema` | bed plate | bed-size VARIANTS (molded_clip precedent at plate scale), `when`-guarded hole grids (35 vs 54 taps), flip setup, zones over the deck |
| `spoilboard.hema` | spoilboard | second variant axis that must TRACK the bed's (CF-2), consumable-allowance claims, non-metal material |
| `gantry_beam.hema` | gantry beam | the sketch layer at its limit: long profile WALK, `hole` inner loops, `regions:`, extrusion stock from the profile, twist/sag budget members |
| `side_plate.hema` | gantry shoulders | DEEPEST pipeline (saw -> mill A -> flip B -> drill -> tap, 5 stages), mirrored `hand` variant, THE rung-7 waiver (basis + by test) |
| `axis_carriage.hema` | axis internals | parametric PARTS (width/nut-circle params), patterns framed off feature exports |
| `axis_module.hema` | generic linear axis | THE generic: 5-param assembly incl. PART-TYPED params (D54), assembly-level impls (F82), nested budget, exposing config var |
| `z_carriage.hema` | spindle mount | SUPPLIED G-CODE PLAN (gear_reducer precedent), rebind across a slit, clamped-state claims |
| `spindle.hema` | purchased spindle | SEALED brownfield import + retro-contracts over `src.` queries, thermal ZONES on measured geometry, catalog-evidence claims |
| `machine.hema` | the machine | 3 monomorphs / 4 instances of the axis, variant pass-through, POSITIONING-ERROR BUDGET (the E0432 shape), kinematic sweeps, locked/policy/model=/assume!/@hint ladder |
| `controller.cupr` | motion-controller board | locked pinmux (elec rung 2), impl aliases x4, image-typed board param (F83/D54) |
| `drives.cupr` | stepper drive bay | block orbit (4 x DriveChannel), `impl by circuit` power-stage nets, `arbitrate` wired-AND, board thermal sums |
| `power.cupr` | power cabinet | rail-droop budget with a locked member, inrush/brownout transients, e-stop loop master, ampacity harness prose |
| `vfd.cupr` | spindle VFD | vendor contract block, the DISSIPATION PROMISE CHAIN source, EOPEN-11 emissions posture, STO in the e-stop chain |
| `machine_elec.cupr` | control system | intents + flows at F79 altitude, motion-planner WORKLOADS (WCET/schedule/fit/stack), e-stop chain claims, ONE event ledger shared with the coolant circuit |
| `coolant.fluo` | flood coolant | fluorite v1: pump-curve imposer, filter/orifice records, flow-balance vs INV-4, valve-slam transient, leak + compliance-volume budgets (UNCHECKED until WO-31) |

## Expert-ladder inventory (the D117 lint fixtures in the wild)

- rung 2 `locked:`: `machine.hema` (clamp fit; two budget locks),
  `controller.cupr` (pinmux x4), `power.cupr` (bulk cap),
  `axis_module.hema` (bearing preload class)
- rung 3 `policy:`: `machine.hema` (prefer/forbid/minimize)
- rung 5 `model=`: `machine.hema` `Dynamics.first_mode`
  (`model=fea_modal`, justified: closed-form was within 12% of the
  limit)
- rung 7 `waive ... basis ... by test`: `side_plate.hema`
  (`dfm(corner_radius_vs_tool)`, FAI lot 2)
- `assume!` with named replacement evidence: `machine.hema`
  (duty-spectrum coverage)
- `@hint`: `machine.hema` `Kinematics.square_xy`
  (`@hint(symmetry=gantry_midplane)`)

## Candidate findings

Recorded here per D119 (corpus authors never edit the design log;
promotion is the coordinating cycle's call). Honest and specific --
these ARE the deliverable.

- **CF-1. Generic DECLARATION headers cannot wrap.** A `<...>`
  parameter list split across physical lines in a declaration header
  is a parse error (E0191: the indentation lexer resets at the
  continuation line). A realistic module needs 5+ parameters --
  `axis_module.hema:18` is 150 columns because it has no choice.
  Instantiation-side argument lists DO wrap fine
  (`machine.hema:45-47`, the z-axis binding), which makes the
  asymmetry feel like a bug rather than a rule. Same lexer behavior
  family as CF-7.

- **CF-2. No cross-part variant tie.** `bed_plate.hema:15` and
  `spoilboard.hema:13` each declare `variant bed: {b600, b900}` and
  the machine passes its own `size` variant into both
  (`machine.hema` `bed: BedPlate(bed=size)`), but nothing states
  that the two parts' variant AXES are the same axis -- the tie is
  purely positional. A b600 spoilboard bound onto a b900 bed
  verifies fine part-by-part and is garbage as a machine. Want:
  either variant-axis identity declared at the contract level, or an
  equality constraint at binding (`spoil.bed = bed.bed`).

- **CF-3. Grouped orbit connections have no spelling.** Four trucks
  ride two rails, two per rail. `pairwise(a, b)` wants equal
  cardinality; there is no "zip in groups of k" form. Written as ONE
  `LinearGuide` mating with whole orbits on both sides
  (`axis_module.hema:40`), which type-checks as a single prismatic
  joint but erases the per-rail load split the truck L10 model
  wants. Same family as the dune buggy's G43 (mixed discrete
  structure in coverage), but on the connection side.

- **CF-4. Budget composition across assembly levels is implicit.**
  The axis-internal play budget (`axis_module.hema:99`) produces
  exactly the number the machine-level positioning budget
  (`machine.hema:129`) consumes via its `x_p`/`z_ax` members, but
  neither budget can NAME the other: the outer member is the whole
  sub-assembly and the inner budget's `require` is connected to the
  outer share only through the claim graph's plumbing. When the
  outer E0432 fires and names `z_ax` as the worst contributor, the
  user must know to go find the inner budget by hand. Want: budget
  members that are budget REFS, or at least an E0432 rendering that
  follows one level down.

- **CF-5. Integer role counts cannot be derived from length
  params.** The axis foot's hole count follows its travel
  (`n = travel/60mm + spares`), but `<...>` params and role counts
  only take literals or params -- there is no blessed integer
  arithmetic over quantity params. `axis_module.hema:61` uses an
  invented `hole_count(travel, spacing=60mm)` helper that parses but
  has no declared home anywhere. Adjacent to (not covered by) the
  G36 computed-fields ask: this is compile-time integer derivation,
  not a solver field.

- **CF-6. No mating for the consumable-on-grid joint.** The
  spoilboard bolts into the bed's tapped grid; the joint is real,
  load-bearing (clamp pull-out routes through it), and variant-sized
  -- and there is no contract for it (`machine.hema:95-97` carries
  it as a comment). The blocker is that the bed's grid orbit is
  variant-guarded (`bed_plate.hema:32-38`), so a `BedGrid<n>`
  interface would need variant-conditional role bindings. The
  spelling `holes = milled.grid_600.instances when bed = b600`
  PARSES today (probed during authoring) but no spec text blesses
  `when`-guarded impl bindings -- pin it or reject it.

- **CF-7. `realizes` must close on the workload's physical line.** A
  continuation line starting with `realizes` after the workload call
  is a parse error; long workloads must wrap INSIDE the call parens
  instead (`machine_elec.cupr:128-134`). Harmless once known, but it
  is the third distinct place the line-oriented lexer shapes the
  grammar (CF-1, CF-7, and the header-vs-instantiation asymmetry),
  and none of the three is written down in the spec.

- **CF-8. Duplicate part bindings under disjoint variant guards:
  blessed or accident?** `machine.hema:39-42` binds `x_p` TWICE,
  once per `size` value, to get variant-dependent generic arguments
  (620mm vs 920mm travel). It parses and checks clean, and it is the
  only discoverable spelling for "this instantiation parameter
  depends on the variant" -- but no spec text admits duplicate
  binding names even under provably disjoint guards. If this is the
  intended idiom, mech 02 sec. 7b should say so; if not, the parser
  is accepting a landmine (last-wins would silently build a 620mm
  s900 machine).

- **CF-9. Re-exporting a sub-part's contract has no delegation
  form.** The machine mates to `x_p.CarriageDeck`, so the axis
  assembly re-impls CarriageDeck by reaching into its own part's
  stage entities (`axis_module.hema:67`), duplicating the binding
  that `axis_carriage.hema:44` already made -- the same face is now
  permanently borrowed by two impls of the same interface at two
  levels, and no diagnostic fires. Want either delegation
  (`impl CarriageDeck for self = plate.CarriageDeck`) or a stated
  rule that nested impl addressing (`x_p.plate.CarriageDeck`) is the
  canonical path (kestrel's `bind` reaches `obc.u_mcu` this way, but
  matings have no stated equivalent).

## What this project is FOR

- The compiler-side stress signal F112 asked for: the golden +
  deferral entries freeze 168 obligations' worth of claim-form mix
  (positioning budget, WCET ladder, zone growth, weld forall, dual
  monomorph sharing) as drift-guarded data.
- The D117 lint fixtures in the wild: every expert-ladder rung used
  deliberately and justified in comments, ready to be linted against.
- The findings above are reproduction demand for the next design
  cycle, exactly as the dune buggy's G34-G43 were for feldspar's.
