# Solver-authoring DX study

Six files, one per complexity rung, each written raw-first and then
with candidate sugar; losers are recorded so they stay rejected. The
governing rule for ALL sugar: it lowers AT DECORATION TIME to the one
raw protocol (a sugar-built direction is digest-equal to its
hand-built twin) -- there is never a second registration path.

| rung | file | pattern (winner) |
|---|---|---|
| 0 | `00_raw_protocol.py` | the floor; ground truth every sugar lowers to |
| 1 | `01_sugar_coercions.py` | coercions + `declare_ports` typo safety |
| 2 | `02_relations.py` | `Relation` builder for multi-direction laws |
| 3 | `03_tables_correlations.py` | `table_solver_1d/2d`, `Correlation` bundle |
| 4 | `04_families.py` | plain factories + `make_direction` |
| 5 | `05_expensive_and_abstraction.py` | settings closure; abstraction edge |
| 6 | `06_coupled_groups.py` | CoupledGroup: strong two-way coupling as ONE composite solver (09 sec. 4b, M8) |

## Decisions (F7-F17; FIXED items folded into 03 / 01-interfaces /
02-edge-cases in this change)

- **F7 (FIXED): multi-direction = `Relation`.** Shared metadata once,
  explicit per-direction numerics, auto-suffixed ids. REJECTED: N
  independent decorators (metadata drift = desync bug); symbolic
  auto-inversion (magic; hides division guards; fails non-invertible
  forms).
- **F8 (FIXED): `table_solver_1d/2d` + `Correlation`.** Table domain
  auto = data extent; interpolation eps EXPLICIT AND CITED, never
  auto-derived (a derived bound claims knowledge of unsampled data).
  Correlation packages formula + published validity box + published
  accuracy + citation as one object because the literature ships
  them together and splitting them invites transcription bugs.
- **F9 (FIXED): families = plain factories.** `make_direction` (the
  decorator's function-call twin, same coercions) + a sorted loop.
  REJECTED: a SolverFamily class -- no new concept earns its keep.
- **F10 (FIXED): citations coerce from `"kind: ref -- note"` strings.**
- **F11 (FIXED): domain coercions.** Box values accept `(lo, hi)`
  tuples; a bare dict is a tagless Domain; tags accept any iterable.
- **F12 (FIXED): `registry.declare_ports(*PORTS)` and unknown-port
  rejection.** Namespace modules declare their port table once;
  a typo'd port in any solver is `RegistryError.UnknownPort` at
  registration -- the single best guard for agent-written catalog
  code, where silent never-routable edges are otherwise invisible.
- **F13/F14 (FIXED): return normalization.** SolveFn may return
  `Result`, a plain Mapping (auto-`Ok`), or -- with exactly one
  output -- a bare float. Raising remains a programmer bug.
- **F15 (FIXED): `EXACT` constant; scalar `accuracy=` applies to all
  outputs.**
- **F16 (FIXED): measured-eps channel.** A measuring solver (FEA,
  Richardson; anything with an internal error estimator) returns
  `SolveOutput(values, measured_eps=...)` inside its Ok; plain
  mappings mean "no measurement, use the declared accuracy". This
  was UNDEFINED before this study -- the SolveFn signature had no
  way to carry the realized eps that 03/05 promised would replace
  the ceiling.
- **F17 (OPEN, M2): payload-domain declaration form.** 05's
  `payload_domain=` string is a sketch; the real declaration object
  (feature predicates: clearance bands, aspect boxes, hole
  exclusions) is an M2 design item under 09 sec. 4a. The EXECUTION
  semantics are already settled (out-of-domain payload -> SolveError
  -> reroute); only the declaration syntax is deferred.

## Style guide (what an implementer/catalog agent picks)

1. One-off formula -> `@solver` with rung-1 coercions.
2. Invertible law -> `Relation`.
3. Published table -> `table_solver_1d/2d`; published correlation ->
   `Correlation`.
4. N-alike -> factory + `make_direction`, sorted registration loop.
5. Tool-backed / measuring -> `@solver(settings=..., tier=...)` +
   `SolveOutput` with measured eps; every failure a SolveError value.
6. Geometry idealization -> abstraction edge with `conservative_for`
   and (M2) payload domain.

Always: declare ports first; cite before you register; the domain is
the published range, not your optimism.
