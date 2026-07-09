# feldspar -- the live queue

M1 is COMPLETE: WO-01..WO-10 (scaffold, quantity core, solver
protocol/registry, propagation, planner, solve facade, mech library
+ calibration, FEA pipeline, regolith pack, explain/close-out) and
WO-11 (the symbolic core, M10 phase 1) are all done -- per-WO
close-out reports live in `docs/workflow/work-orders/`, and the
detailed done-ledger this file used to carry is in git history
(deleted per lithos D137: git history is the archive). The FINV
audit checklist is `docs/workflow/FINV-audit.md`.

## Queue

- [ ] **Entry-point migration (lithos WO-44 follow-up, same
      release):** move `pyproject.toml`'s
      `[project.entry-points."regolith.model_packs"]` to the
      unified `regolith.plugins` group (`kind=model_pack`) when
      lithos WO-44 lands (AD-26/D134). One-line change + conformance
      re-run against the lithos `tests/packs/` suite.
- [ ] **Lithos WO-27 conformance run:** the lithos-side reference
      conformance for this pack is dispatchable now (lithos queue,
      wave 1); expect asks to land here as small fixes, not new
      milestones.
- [ ] **Frame IR consumption (lithos WO-48 follow-up):** when the
      calcite civil track's realized frame IR lands (lithos
      D133/WO-48, kind string per `docs/spec/09-model-integration.md`
      sec. 4's table), add the frame/FEA consumer solvers here --
      the pack side of `std.civil`'s structural claims. Not
      scheduled until lithos WO-48 exists in the wild.
- [ ] **M-milestones beyond M1** (`docs/spec/09-model-integration.md`
      sec. 8): M2 calibration ceilings at scale, M4/M6 payload-port
      milestones (unblocked by lithos WO-30, done), the phased
      capability roadmap in `docs/spec/07-capability-map.md`
      (thermal/fluids -> vibration -> electrical -> controls).
      Schedule by demand from real lithos claims, not speculatively.
- [ ] **FEA-marked tests in a tooled environment:** `fea`-marked
      tests were written per spec but never executed where gmsh/ccx
      exist (WO-08/09/10 close-out note); run and green them the
      first time the environment has the tools (check with
      `find_ccx()` before assuming).

## Conventions (unchanged)

- Docs are the contract; code disagreement with a spec doc is a bug
  in one of them, fixed in both in the same change.
- Every guarantee lives in the FINV table
  (`docs/spec/toolchain/00-architecture.md`) with its mechanism.
- External contracts cited by home (`lithos:docs/...`), never
  copied (NO DUPLICATION).
- The dependency arrow stays one-way: feldspar depends on regolith
  (optionally); regolith never depends on feldspar.
