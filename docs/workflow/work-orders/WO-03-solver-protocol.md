# WO-03: Solver protocol and registry

Status: todo
Depends: WO-02
Language: Python (`feldspar/solve/`), thin
Spec: 03 (all sections), FINV-4/5/6, AD-4/7

## Goal

`SolverInfo`, `Citation`, the `@solver` decorator, and
`SolverRegistry` -- the registration surface everything downstream
populates.

## Deliverables

- `SolverInfo` frozen model per 03 incl. `tier` (09 sec. 1),
  `citations` (Citation model per 03), `deterministic`,
  `corner_monotone`; `eps_seeking`/cost-curve fields RESERVED
  (documented, not implemented -- M3).
- `@solver(...)` decorator building `(SolverInfo, SolveFn)` with NO
  global state (AD-4); module-level `register(registry)` convention
  documented in the module docstring.
- The DX-settled sugar layer (`feldspar/solve/sugar.py`), per 03
  "Registration ergonomics" and 01-interfaces: coercions,
  `make_direction`, `Relation`, `table_solver_1d/2d`, `Correlation`,
  `SolveOutput`/`EXACT`, `declare_ports` + UnknownPort. Everything
  lowers at decoration time to the raw protocol; ship the
  digest-equivalence test (sugar twin == hand-built) and keep
  `examples/solvers/*.py` importable as written.
- `SolverRegistry`: `register` (Err on duplicate id, port unit/rank
  conflict, empty method citations -- FINV-6), `freeze`,
  sorted-by-id iteration, registry digest (folds every SolverInfo;
  feeds FINV-7).
- Error types: `RegistryError` ErrorSet, `SolveError` ErrorSet
  (ToolMissing/ToolFailed/Timeout/ParseFailed/OutOfDomain/...) --
  the TOTAL unions of 03/04 (FINV-5).
- Logging: every registration, rejection, and freeze logged with ids.
- Tests: each error variant exercised; import-order permutation test
  proving AD-4; citation floor test.

## Acceptance

- A toy `thermo.ideal_gas` solver registers, freezes, iterates
  sorted; all RegistryError variants reachable in tests; `make
  check` green.
