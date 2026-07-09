# WO-20: Phase 2 library wave -- thermal-fluids (incl. compressible networks)

Status: todo
Depends: WO-07 (library pattern + calibration harness), WO-12
(payload ports for `flownet`/`table`), WO-14 (regime channel --
the compressible tier is regime-routed)
Language: Rust formula homes (`feldspar-core` library modules) +
Python registration/table wrappers
Spec: 07 thermo/fluids/heat (the enumerated catalog IS the scope),
09 secs. 4/5, 03 (citations + calibration, every entry); lithos
D141 (compressible network delivery is a demanded discharge tier,
`lithos:docs/workflow/design-log/2026-07-08-cycle-27.md`) and the
`flownet` consumer contract
(`lithos:docs/spec/fluorite/03-lowering.md` secs. 2-3)

## Goal

The thermal-fluids catalog goes live: property tables, device
models, internal-flow + network solving over `flownet` payloads,
conduction/convection correlations -- including the compressible
tier lithos D141 now demands (Fanno-line network delivery), so
gas-subnet dp/pressure claims stop dead-ending at the
incompressible regime boundary.

## Deliverables

- `thermo`: property tables (steam/refrigerants/air via wrapped
  CoolProp per 03, interpolation eps + domain boxes declared);
  ideal/real-gas directions; device models (07 list).
- `fluids`: internal flow (Poiseuille, Colebrook/Haaland, minor-K
  tables), NETWORK tier consuming `flownet` payloads
  (series/parallel reduction + Hardy-Cross/Newton; imposers,
  pump curves, regulator droop per the payload's edge kinds);
  turbomachinery/NPSH entries backing `fluids.npsh_margin`;
  Joukowsky + MOC water hammer backing the transient claim forms.
- COMPRESSIBLE tier (D141): isentropic relations, normal shocks,
  Fanno-line network delivery registered under the SAME
  fluids claim kinds with `required_regimes` distinguishing it
  (incompressible entries carry the low-Mach regime; the mach/choked
  screening tags route) -- the fidelity-ladder proof for gas
  subnets; lithos's gn2_purge corpus fixture is the demand case.
- `heat`: 1-D resistance networks, transient lumped/one-term,
  forced/natural convection correlations with published Re/Pr
  domain boxes as Domains (07 list).
- Every entry: citations + calibration evidence at registration
  (03 floor); catalog cross-check that no entry duplicates a
  formula home.

## Acceptance

- Lithos's fluorite corpus claims (dp, npsh, reynolds-regime,
  hammer peak) discharge against hand-built flownet fixtures at
  the correct tiers; a beyond-regime gas case routes to the
  compressible entry via regime tags (proven both ways); every
  registration carries citations; `make check` green.
