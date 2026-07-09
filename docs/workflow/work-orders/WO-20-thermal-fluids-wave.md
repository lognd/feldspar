# WO-20: Phase 2 library wave -- thermal-fluids (incl. compressible networks)

Status: partial (2026-07-08 close-out; see "Close-out" section below --
core `fluids`/`heat` catalog + D141 compressible closed-form tier
landed with conformance tests and citations, `make check` green;
`thermo` property tables and full `flownet`-payload network solving
are NOT delivered and remain open, named explicitly, not silently
dropped)
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

## Close-out (2026-07-08, agent-wo20-thermal-fluids worktree)

DELIVERED (Rust homes in `crates/feldspar-library/src/{fluids,heat}.rs`
+ PyO3 wrappers + Python solver directions in
`python/feldspar/library/{fluids,heat}.py`, wired into
`feldspar.pack.models._engine_registry`):

- `fluids`: Reynolds number, Hagen-Poiseuille laminar friction factor,
  Colebrook-White (Newton/fixed-point root) and Haaland friction
  factors, Darcy-Weisbach dp, Crane minor-K loss, series/parallel
  network dp/Q reduction, pump/system operating point (`Relation`),
  NPSH available, Joukowsky water hammer.
- COMPRESSIBLE tier (D141): isentropic stagnation temp/pressure
  ratios, normal-shock Mach2/pressure ratio, the Fanno function (the
  per-segment building block for Fanno-line delivery). Registered
  under the same `fluids` namespace with `Domain.tags`
  `{"incompressible", ...}` vs `{"compressible", ...}` distinguishing
  the regime (regime-tag routing proven both ways,
  `tests/unit/test_library_fluids.py::test_compressible_and_incompressible_entries_carry_distinct_regime_tags`).
- `heat`: plane-wall/cylindrical-wall/convection resistances, series
  combination, rate-from-resistance, Dittus-Boelter Nusselt
  correlation (published Re/Pr validity box as its `Domain`),
  Nusselt-to-h conversion.
- Every registration cites its method source (03 floor); all
  `accuracy=EXACT` (A-7 convention, same as `mech.py`'s Lame
  equations: each solver evaluates ITS OWN declared model exactly,
  even where that model -- Haaland, Fanno, Dittus-Boelter -- is
  itself a textbook approximation).
- 23 new conformance tests (`tests/unit/test_library_fluids.py`,
  `tests/unit/test_library_heat.py`) turning the benchmarks memo's
  fluid-network cases (friction factor, series/parallel network,
  pump operating point, NPSH, Joukowsky, isentropic/shock) into
  known-answer pytest checks with cited tolerances, plus 14 new Rust
  unit tests. `make fmt-check lint import-lint typecheck` and
  `cargo test --workspace` and `pytest tests/ -m "not fea"` (274
  passed) are all green.
- DEVIATION (flagged, not silently absorbed): the benchmarks memo
  sec. 3.1 quotes the Colebrook root for the D=0.1m/eps=0.045mm/
  Re=1e5 case as 0.0195; both this WO's Newton/fixed-point solver and
  an independent bisection on the defining residual converge to
  0.02012 instead. The memo is explicitly advisory/non-normative; the
  analytically-verified root is used in the conformance test instead
  of the memo's rounded figure (see the test's docstring and the Rust
  unit test's comment).

CUT / ESCALATED (named, not silently dropped):

- `thermo` property tables (CoolProp wrapper) are NOT implemented.
  A `cp312-abi3-manylinux2014_aarch64` CoolProp 8.0.0 wheel does
  exist for this platform/Python (verified via `pip download`), so
  the path is open, but wrapping it (interpolation eps, domain boxes,
  device models, cycles, combustion, psychrometrics, exergy -- the
  rest of the 07 `thermo` catalog) is a full sub-WO's worth of work
  on its own and did not fit this pass. `pyproject.toml`'s existing
  `props = []` extra is the anchor point for that follow-up; it was
  NOT populated with `CoolProp` since nothing depends on it yet (an
  unused pinned dependency would be its own smell).
- Full multi-branch NETWORK solving over resolved `flownet` payload
  BYTES (Hardy-Cross for incompressible loops, the analogous
  Fanno-line reduction lithos's gn2_purge/ullage_press fixtures
  ultimately need) is NOT implemented. `PayloadRef` is exact-by-
  reference (09 sec. 4): interpreting resolved bytes into a network
  topology and iterating a loop-correction solver is real algorithm
  work, not a registration exercise, and needs its own design pass
  (what wire format does a `flownet` payload's bytes carry?  that
  question is NOT decided anywhere in the docs read for this WO).
  What IS delivered is every per-segment/per-branch formula the
  network tier would call (friction factors, dp, series/parallel
  two-branch reduction, the Fanno function) plus the pump-curve and
  water-hammer formulas -- the building blocks, not the graph solver.
  Consequently the acceptance line "lithos's fluorite corpus claims
  ... discharge against hand-built flownet fixtures" is NOT met by
  this close-out; it needs the network-solver follow-up above.
- Hydrostatics, external flow (drag/lift, boundary layer), open
  channel (Manning), flow measurement (ISO 5167), oblique shocks and
  CD-nozzle operation, and turbomachinery similarity/affinity laws
  are cut from `fluids`.
- Transient lumped/Heisler, natural convection, boiling/condensation,
  radiation networks, and LMTD/effectiveness-NTU heat exchangers are
  cut from `heat`.
- No collisions observed with WO-16 (structured ports/vibration) or
  WO-17 (ngspice) during this pass -- neither touches `fluids.rs`/
  `heat.rs`/`fluids.py`/`heat.py`. One shared-file touch to flag
  loudly: `python/feldspar/pack/models.py::_engine_registry` was
  edited to add `register_fluids`/`register_heat` calls (same
  ordering constraint as `register_mech`: declaration-free modules
  before `payload_steps`). If WO-16/17/18 also add `register_*` calls
  there in parallel, expect a merge conflict in that one function,
  not a semantic collision -- the fix is a straight list-merge of the
  import/register lines.
