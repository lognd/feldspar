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

- **RESIDUAL UPDATE (2026-07-09, agent-wo20-residuals worktree,
  branch `wo20-residuals`):** both residuals below landed, at a
  narrower, explicitly-declared coverage -- neither residual line's
  original scope claim is fully met, and the gaps are named in their
  own paragraphs (this update does NOT flip WO-20's overall Status;
  the wave is still `partial`).
  - `thermo` property tables: DELIVERED as a CoolProp wrapper
    (`python/feldspar/library/thermo.py`, `props = ["CoolProp>=8.0"]`
    now populated in `pyproject.toml`/`uv.lock`, CoolProp 8.0.0
    installed and exercised). Registers 9 directions --
    `thermo.{water,air,nitrogen}_{density,specific_heat_cp,viscosity}`
    -- each a `PropsSI('D'|'C'|'V', 'T', T, 'P', P, fluid)` call with a
    declared `(T, P)` validity box and the benchmarks memo sec. 3.4
    tolerance as its `Accuracy` (+/-0.5% density/cp, +/-2% viscosity),
    verified against all 5 memo state points
    (`tests/unit/test_library_thermo.py`). CUT, still open: device
    models, cycles, combustion, psychrometrics, exergy, ideal/real-gas
    closed-form directions, two-phase/saturation-region lookups, and
    any CoolProp fluid beyond the three calibrated here -- the rest of
    the 07 `thermo` catalog remains a follow-up's worth of work.
  - Multi-branch NETWORK solving over resolved `flownet` payload
    BYTES: DELIVERED as a Hardy-Cross loop-balancing solver
    (`python/feldspar/library/fluids/network.py`,
    `fluids.network.hardy_cross`, registered in the pack registry
    exactly like `fea.payload_steps` -- declares its own payload ports
    (F12), takes the `PayloadResolver`, registers LAST). D154 (this
    cycle's escalation ruling, `lithos:docs/workflow/design-log/`
    `2026-07-08-cycle-28.md`) settled the missing wire-format
    question this WO's original close-out flagged: a payload
    reference resolves to the schema-versioned JSON serialization of
    the payload object, so this solver parses THAT shape (a
    feldspar-owned, field-name-compatible subset of
    `regolith._schema.models.FlownetPayload`, never importing
    `regolith` itself, FINV-3). Algorithm: BFS spanning-tree
    fundamental cycle basis (one loop per chord) plus a
    continuity-respecting initial-flow seed (tree edges' flows are
    DETERMINED by nodal balance given the chords' seeded guess, not
    assumed uniform -- a uniform seed was tried first and converges to
    a WRONG stationary point for asymmetric laminar networks; the
    fix and its derivation are in the module docstring), then
    classical Hardy-Cross loop correction with the per-iteration
    slope computed by NUMERICAL differencing of the Darcy-Weisbach
    `dp(Q)` (not an assumed fixed exponent -- a fixed quadratic
    exponent still converges but far more slowly in the laminar
    regime, verified during this pass). Calibration: the benchmarks
    memo sec. 3.2 symmetric two-branch case wired verbatim (Q_total =
    0.012 -> even 0.006/0.006 split); an independent Hagen-Poiseuille
    closed-form oracle for the asymmetric laminar case (not in the
    memo, derived and cross-checked in this WO's test file, since the
    memo does not include a two-different-length-branch worked
    number). Honest coverage (execution-time `OutOfDomain`, never
    fabricated convergence): edge kinds ONLY `pipe` and `imposer` (a
    fixed, externally-known flow) -- `hose`/`orifice`/`valve`/`pump`/
    `regulator`/`filter`/`hx_segment`/`mixer` are named-cut, reported
    as `edge_kind:<kind>`; edge params ONLY the literal-scalar
    `EdgeParams1` shape -- the `EdgeParams2` geometry-extract selector
    (D131's `regolith-lower::extract` seam) and the `EdgeParams3`
    mixer-outlet medium record are named-cut, reported as
    `edge_params:<source>`; fluid density/viscosity are read as
    LITERAL values on the edge itself, NOT resolved from the payload's
    `MediumRef` property records -- wiring the CoolProp wrapper above
    through a resolver at this call site is a follow-up, the two
    residuals landed this pass are NOT yet wired to each other;
    disconnected networks and over/under-constrained nodal demand are
    both named-cut (`disconnected_network`,
    `overconstrained_demand`/`unbalanced_demand`); non-convergence
    after 100 iterations reports `SolveError.NoConvergence` naming the
    residual, same posture as WO-18's `CoupledGroup`. Consequently the
    ORIGINAL acceptance line "lithos's fluorite corpus claims ...
    discharge against hand-built flownet fixtures" is now met ONLY for
    networks entirely inside this coverage (plain pipe/imposer
    incompressible loops with literal properties) -- valve/pump/
    regulator-bearing networks (pump-curve-driven systems, the
    Fanno-line compressible tier) still need their own follow-up;
    those per-segment formulas were already delivered by the ORIGINAL
    WO-20 pass and are unchanged.
  - Tests: `tests/unit/test_library_thermo.py` (11 cases) and
    `tests/unit/test_library_fluids_network.py` (7 cases), all new,
    all green. Full gate green in the `wo20-residuals` worktree:
    `make fmt-check lint import-lint typecheck test` (375 passed, up
    from the pre-existing 351) plus `cargo clippy --workspace
    --all-targets -- -D warnings` and `cargo test --workspace` (both
    clean, no Rust changes this pass -- both residuals are pure
    Python, composing the ALREADY-DELIVERED Rust friction-factor/
    Darcy-Weisbach homes rather than adding new ones).
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
