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

- [ ] **WO-12** payload ports (M2) -- the root of the forward graph.
- [ ] **WO-22** symbolic follow-ups (R4/R5, decided 2026-07-08) --
      independent of the M2 chain.
- [ ] **Lithos WO-27 conformance run** (lithos-side; expect asks to
      land here as small fixes, not new milestones).

Wave 2 -- after WO-12:

- [ ] **WO-14** regolith boundary v2 (M4) -- lithos WO-30 is DONE;
      this un-gates the contract's target state (kind re-key flip,
      structured coverage, payload channel, givens/regimes).
- [ ] **WO-13** budget-seeking + cost curves (M3).

Wave 3 -- after their named gates:

- [ ] **WO-16** structured ports + vibration tier (M6) -- after
      WO-12/14.
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

## Conventions (unchanged)

- Docs are the contract; code disagreement with a spec doc is a bug
  in one of them, fixed in both in the same change.
- Every guarantee lives in the FINV table
  (`docs/spec/toolchain/00-architecture.md`) with its mechanism.
- External contracts cited by home (`lithos:docs/...`), never
  copied (NO DUPLICATION).
- The dependency arrow stays one-way: feldspar depends on regolith
  (optionally); regolith never depends on feldspar.
