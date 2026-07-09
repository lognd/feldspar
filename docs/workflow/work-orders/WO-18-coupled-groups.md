# WO-18: CoupledGroup (M8)

Status: todo
Depends: WO-12 (payload/field plumbing), WO-13 (eps machinery the
composite charges residuals into)
Language: Python (`feldspar/solve/coupled.py`) + Rust closure math
where hot
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
