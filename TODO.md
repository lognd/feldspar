# feldspar -- the live queue

M1 is COMPLETE: WO-01..WO-10 (scaffold, quantity core, solver
protocol/registry, propagation, planner, solve facade, mech library
+ calibration, FEA pipeline, regolith pack, explain/close-out) and
WO-11 (the symbolic core, M10 phase 1) are all done -- per-WO
close-out reports live in `docs/workflow/work-orders/`, and the
detailed done-ledger this file used to carry is in git history
(deleted per lithos D137: git history is the archive). The FINV
audit checklist is `docs/workflow/FINV-audit.md`.

FORWARD PLAN SCHEDULED 2026-07-08 (owner closure directive; lithos
cycle 27, D146): every remaining milestone and library phase is now
a zero-shot WO (WO-12..WO-22, dependency graph in
`docs/workflow/README.md`); the open-questions ledger (spec 08) has
NOTHING open -- every residual is decided or named-gate deferred.

## Queue

Wave 1 -- dispatchable NOW:

- [x] **WO-12** DONE (2026-07-08 completion cycle): payload ports
      through plan/execute/solve, PayloadStepCache, FINV-12
      payload-hash-in-digest; 15-row edge matrix tested. Deferred
      (recorded in the WO): F12 declaration-ordering seam -> WO-14;
      payload-port targets -> M4.
- [x] **WO-22** DONE (2026-07-08 completion cycle): differentiate +
      Normal delta-propagation + R5 re-swept calibration; digests
      CANON_VERSION-sensitive. NOTE (coordinator ruling): wiring
      `Normal` propagation into execute()/plan() route selection
      stays POST-V1 per doc 02's own "Planned, not v1" -- reopen
      when a consumer needs calibration-grade uncertainty routing,
      not before.
- [x] **Lithos WO-27 conformance run** DONE lithos-side (its WO
      file has the close-out): real-pack discharge signed+verified,
      uninstall reverts, evidence hash byte-identical. The one ask
      that landed here: the `regolith.plugins` seam migration +
      the stderr logging fix (2026-07-08).
      KNOWN LATENT (flagged by WO-12's agent, fix with WO-14): the
      WO-08 `fea`-marked tests pin `eps_budget=1e-2`, which the M1
      sum-surrogate would refuse as BudgetUnreachable if ever run
      with real gmsh/ccx present.

Wave 2 -- after WO-12:

- [ ] **WO-14** regolith boundary v2 (M4) -- lithos WO-30 is DONE;
      this un-gates the contract's target state (kind re-key flip,
      structured coverage, payload channel, givens/regimes).
- [ ] **WO-13** budget-seeking + cost curves (M3).

Wave 3 -- after their named gates:

- [x] **WO-16** DONE (2026-07-08 completion cycle): structured ports
      (verified already rank-native since WO-02/12, no scalar-only
      guard existed) + vibration tier -- closed-form
      beam/SDOF first_mode, Miles GRMS over a spectrum payload, mask
      containment, ccx modal direction reusing the WO-12 mesh step
      (routing verified, ccx/gmsh execution unverified in this
      sandbox per the standing fea-marked caveat). Cut (recorded in
      the WO): rainflow/Miner with mech.design (not required by
      Acceptance, standalone-sized); modal mode SHAPES (frequency
      only, left OPEN as a rank-vs-payload design question).
- [ ] **WO-20** Phase 2 thermal-fluids wave (incl. the lithos-D141
      compressible tier) -- after WO-12/14; lithos's gn2_purge
      fixture is the demand case.
- [ ] **WO-15** parallel execution (M5) -- after WO-13.
- [ ] **WO-17** ngspice elec tier (M7) -- after WO-13/14.
- [ ] **WO-18** CoupledGroup (M8) -- after WO-12/13; example 06 is
      the acceptance fixture.
- [ ] **WO-19** solver-pack kit (M9) -- kit half after WO-14; the
      AD-26 entry-point migration half is GATED on lithos WO-44.
- [ ] **WO-21** Phase 6 civil/structural wave (`frame` consumer,
      `mech.struct`) -- HARD-gated on lithos WO-48 producing frame
      payloads in the wild.

Standing:

- [ ] **FEA-marked tests in a tooled environment**: `fea`-marked
      tests were written per spec but never executed where gmsh/ccx
      exist (WO-08/09/10 close-out note); run and green them the
      first time the environment has the tools (check with
      `find_ccx()` before assuming). WO-17 adds the same posture
      for `spice`-marked tests.

## Conventions

- `examples/lithos/` is a MIRROR of `lithos:examples/` (lithos
  D148): never edit it here; land fixture changes in lithos, then
  `make sync-examples` and review the diff.

## Conventions (unchanged)

- Docs are the contract; code disagreement with a spec doc is a bug
  in one of them, fixed in both in the same change.
- Every guarantee lives in the FINV table
  (`docs/spec/toolchain/00-architecture.md`) with its mechanism.
- External contracts cited by home (`lithos:docs/...`), never
  copied (NO DUPLICATION).
- The dependency arrow stays one-way: feldspar depends on regolith
  (optionally); regolith never depends on feldspar.
