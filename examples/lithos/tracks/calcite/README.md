# examples/tracks/calcite/

Single-file, teaching-scale civil designs (charter sec. 8, written
by the cycle-27 elaboration / D139). Every construct is
hand-validated against `docs/spec/calcite/02` (language) and cited to
its section. Like every track's corpus, these files PRECEDE their
parser: they are the spec's pressure tests first (`.calx` registers
in `regolith-syntax` at WO-47), and the WO-47 golden corpus after.

`std.civil` names (occupancy records, transfer classes, load-case
models, combination sets, section tables) are WO-48 content --
phantom until the pack lands, exactly like the fluorite corpus's
`std.fluorite` imports before WO-32; each file's header notes it.

## File map

| file | design | pressure applied |
|---|---|---|
| `bus_shelter.calx` | transit shelter | simplest shape: one space, four members, one envelope assembly, one circulation edge; `structure` net + `forall combo` strength sweep (02 secs. 2-7) |
| `pole_barn.calx` | timber pole barn | snow governs: site truth -> pack load model (`roof_snow`), timber records, tributary partition ledger, frost-depth footing (02 secs. 1, 6, 7) |
| `footbridge.calx` | pedestrian footbridge | steel, serviceability: deflection span/360 and the `mech.first_mode` vibration claim; no spaces at all (structure-only file) |
| `retaining_wall.calx` | cantilever retaining wall | record-driven geotech consumption: `by test` soil records, `equilibrium(...): stable` overturning, sliding utilization, bearing pressure (02 sec. 1; 03 sec. 5) |

The fifth charter design -- the cross-track flagship -- is
`examples/systems/small_office/` (`.calx` + `.fluo` + `.cupr`).

## Conventions

- Comments cite the `calcite/02` (or `/03` for lowering-visible
  behavior) section a construct exercises.
- Engineering numbers are realistic for the named design (ASCE
  7-style loads, real section families, plausible occupancies).
- Every charter claim family appears at least once across the five
  designs (WO-46 acceptance): occupancy/egress (bus_shelter,
  small_office), area budgets (small_office), strength/deflection/
  drift (all), bearing (pole_barn, retaining_wall), envelope
  ratings (bus_shelter, small_office).
