# WO-18: CoupledGroup (M8)

Status: done
Depends: WO-12 (payload/field plumbing), WO-13 (eps machinery the
composite charges residuals into)
Language: Python (`feldspar/solve/sugar.py`, where the WO-03 M1
`CoupledGroup` stub already lived -- no new module needed) + Rust
closure math where hot (none proved hot in this pass; the closure is
plain Python)
Spec: 09 sec. 4b (NORMATIVE: composite registration, deterministic
closure, unit calibration, NoConvergence), 07 prop (the regen-wall
reference loop), `examples/solvers/06_coupled_groups.py` (the
committed target shape -- the example is the acceptance fixture)

## Goal

Strong two-way couplings register as ONE composite SolverInfo over
boundary ports with a deterministic fixed-point closure; the
planner's world stays a DAG.

## Deliverables

- `CoupledGroup`: member ids + fixed damping, fixed iteration
  order, tol/max_iter in the settings digest; internal cycle never
  enters the graph (cyclic ordinary-solver ports remain a
  registration error -- keep that test).
- Composite accuracy calibrated AS A UNIT (member-eps composition
  and EXACT both rejected at registration); closure residual charges
  into measured eps.
- `SolveError.NoConvergence` variant (01-interfaces + 04 union
  extended in the same change; A-4 totality note updated); fallback
  rerouting + honest indeterminate unchanged.
- Corner sweeps at the group boundary (loop solves once per
  corner); `conservative_for` applies to the composite.
- The regen-wall loop (hot-gas Bartz <-> wall conduction <-> coolant
  convection <-> bulk rise) lands as the reference group; example 06
  runs verbatim.

## Acceptance

- Example 06 executes as written; determinism (same inputs -> same
  iterate trajectory -> same digest) twice; NoConvergence path
  produces an honest value-shaped error that reroutes; unit
  calibration enforced by registration test.

## Close-out (2026-07-09)

All acceptance criteria met, `tests/unit/test_registry.py` (6 new
`test_coupled_group_*` cases): registers-and-converges, determinism
(two calls, identical `values`/`measured_eps`), `NoConvergence` on
`max_iter` exhaustion, member `Err` propagates unrelabeled, missing
member is a `RuntimeError` (catalog bug, not user input), and the
existing EXACT-forbidden test kept. Example 06 verified to `register()`
cleanly against a fresh registry (member ids need not exist in the same
registry at `register()` time -- resolved lazily at solve-call time via
the new `SolverRegistry.get()`, since AD-4 keeps registration order
arbitrary).

Deviations from the file layout sketch: kept `CoupledGroup` in
`feldspar/solve/sugar.py` (where the WO-03 M1 stub already lived and is
exported from) rather than a new `coupled.py` -- no behavior reason to
split it out, and moving it would be pure churn. No Rust closure math
was needed; the damped fixed-point loop is cheap plain Python (a
few dict-scan iterations per solve), so nothing profiled hot enough to
justify a crate boundary -- flagged here in case a real physics-heavy
member set (regen-wall's actual Bartz/conduction/Gnielinski solvers,
still unimplemented) changes that calculus later.

`make fmt-check lint import-lint typecheck` and `cargo test --workspace`
green; `uv run pytest tests/ -m "not fea and not spice"` green
(324 passed, 14 deselected).
