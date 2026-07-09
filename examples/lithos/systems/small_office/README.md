# small_office -- the cross-track flagship (charter sec. 8, D139)

A two-story office building as ONE project: architectural program +
egress (`program.calx`), structural frame (`frame.calx`), a fluorite
hydronic heating loop (`hydronics.fluo`), and a cuprite panel
feeder (`power.cupr`) -- the fourth `systems/` flagship and the
proof that MEP is composition, not calcite surface (charter sec. 6;
regolith/10 sec. 3 import machinery).

| file | track | pressure applied |
|---|---|---|
| `site.calx` | calcite | one `site` per project root; grids/levels shared by every file (calcite/02 sec. 1) |
| `program.calx` | calcite | spaces, occupancy records, circulation net with a stair, egress claims, envelope assemblies + ratings, the `area` budget, `offers:` contracts for MEP |
| `frame.calx` | calcite | two-story steel frame, moment + braced bays, drift claim, the full load-case set, tributary ledger |
| `hydronics.fluo` | fluorite | heating loop with a vendor boiler binding `MechRoom.offers` (pad, drain); HxSegment coupling to the building's zones; the operating-mass promise `frame.calx` consumes |
| `power.cupr` | cuprite | panel + feeder implementing `MechRoom.offers.power`; pump/boiler circuits consuming fluorite electrical-demand promises; the cross-track energy budget; the BOM cost claim (D147) |
| `magnetite.toml` | -- | the project manifest: dependency set + COST PROFILES (D147: prototype/construction estimating axes) |

Cross-track claims exercised: the mech room's boundary subsumption
(the boiler's proven envelope must contain the room's), the energy
budget spanning tracks (D49 members-span-domains), the equipment
electrical demand flowing cuprite<-fluorite and the operating mass
flowing calcite<-fluorite through one promise chain, and the
whole-project + BOM cost claims over declared cost profiles (D147 --
the estimating pressure test).

`std.civil` / `std.fluid` / `std.elec` names are stdlib content
(WO-45/48) -- phantom until the packs land, per corpus convention.
