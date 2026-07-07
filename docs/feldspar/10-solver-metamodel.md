# 10 -- The solver metamodel: what every solver shares

One sentence: every solver, from a one-line formula to a CAM
planner, is the same nine declarations plus one of eight authoring
patterns -- so solvers are data, packs are plug-and-play, tooling is
generated, and a new solver KIND is a new pattern over the same
metamodel, never a new protocol.

## 1. The nine-field anatomy

Distilled from the DX study (rungs 0-6) and the stress tests: every
solver is exactly

| field | question it answers |
|---|---|
| identity | who are you (id, namespace, version) |
| ports | what do you consume/produce (typed, ranked, payload kinds) |
| domain | where may you be trusted (box + tags + payload predicates) |
| cost | what do you charge (scalar now, cost(eps) curve at M3) |
| accuracy | how wrong can you be (declared ceiling; measured channel) |
| provenance | why should anyone believe you (citations + calibration) |
| settings | what tuning are you hiding (digested, always) |
| conservatism | which claim sense do you serve (upper/lower/both) |
| tier | how should reports describe you (dispatch-blind, FINV-8) |

Anything that cannot fill the nine fields is not a solver and must
not pretend to be one (the G27 rule: empirical stability ratings
stay on the assume!/waive ladder).

## 2. The eight authoring patterns

Every catalog entry is ONE of these; each has a builder that lowers
to the raw protocol (the one-protocol rule, digest-equal):

1. **Pure map** -- formula in, formula out (`@solver`,
   `make_direction`, `Relation`).
2. **Table** -- interpolated data with cited eps
   (`table_solver_1d/2d`).
3. **Correlation** -- published formula + published validity box +
   published band as one object (`Correlation`).
4. **Record edge** -- registry data (material, contact pair, pump
   curve) as a solver over its published range (G5/G15).
5. **Abstraction/envelope edge** -- payload in, idealized scalars
   out; idealization error as model error; execution-checked payload
   domain; sense-declared (09 sec. 4a).
6. **Tool wrapper** -- subprocess/external computation behind
   settings closures; failures as values (ccx, ngspice, CEA).
7. **Marching/reduction** -- distributed internal solve exposing
   extremal ports (09 sec. 4b interim; OPEN-14 residual).
8. **Coupled group** -- members + deterministic closure as one
   composite; unit-calibrated accuracy (09 sec. 4b).

A ninth arrives with manufacturability (sec. 5): the **planner
solver**. The pattern list is closed by review, not by accident: a
solver that fits no pattern triggers a metamodel discussion, not a
bespoke registration path.

## 3. Plug-and-play: solver packs (DECIDED 2026-07-07)

feldspar itself becomes a host, one level below regolith's pattern
(D-B verbatim, one arrow down):

```toml
[project.entry-points."feldspar.solver_packs"]
acme_bearings = "acme_bearings:register"
```

- `register(registry) -> None`; discovery sorted by name;
  `default_registry()` composes built-ins then packs; duplicate
  solver ids across packs are an Err naming both packs.
- Namespace etiquette: a pack registers under its OWN sub-namespace
  (`mech.acme_bearings.*`) unless it is upstreaming into a standard
  namespace through review; port declarations follow the same
  declare-first rule (F12) so packs cannot silently fork port
  meanings -- a port unit/rank conflict with the built-in table is a
  load error, never a shadow.
- **The conformance kit is the product**: `feldspar.testing`
  ships `assert_solverpack_conforms(register_fn)` -- runs the
  nine-field validation, citation floor, digest stability,
  twice-run determinism, domain honesty spot-checks (sampled
  in-domain evaluations return Ok; sampled out-of-domain inputs are
  rejected by the registry path), corner-monotonicity spot checks
  (sampled corners vs interior), and sugar-equivalence. A pack is
  "plug and play" exactly because the kit makes conformance a
  one-line test in the pack's own CI -- the same move regolith's
  `tests/packs/` made for model packs, one level down.
- Scheduled M9 (09 sec. 8).

## 4. Solvers are data: generated tooling

Because the nine fields are frozen declarations, all of this is
rendering, never new state:

- `feldspar list --namespace mech --tier closed_form` (capability
  queries), `feldspar graph --target mech.deflection.tip` (port-graph
  dot output), `feldspar doc <solver_id>` (docs straight from the
  metamodel + citations).
- Test scaffolding: property tests generated FROM SolverInfo
  (in-domain sampling stays Ok and finite; declared monotonicity
  spot-checked; accuracy ceiling vs calibration record). The
  conformance kit (sec. 3) is these generators, packaged.
- The justification report (04) and the pack's evidence mapping (06)
  read the same fields -- one metamodel, three renderings.

## 5. CAM and manufacturability (the ninth pattern: planner solvers)

Manufacturability is an ordinary obligation family (regolith/07
sec. 6: planner models, plans as evidence). The seam, drawn to avoid
duplication with regolith's WO-25/WO-28 territory:

- **regolith owns**: rule packs (eager DFM/DRC screens), the
  planning-as-evidence contract, plan serialization at L6 (G-code,
  etc.), and the `manufacturable(...)`/`mfg.unit_cost(...)` claim
  vocabulary.
- **feldspar owns**: the FORMULA tier the planners and screens call
  (cutting force/power, Taylor life, MRR, chip load, feed/speed
  tables, weld heat input, bend allowance -- 07 mfg catalog), and
  optionally hosts **planner solvers**: pattern-9 solvers whose
  inputs are a geometry payload + a process-capability record and
  whose outputs are scalar quantities (cycle time, unit cost,
  achievable tolerance) PLUS a `plan` payload (setups, ops, times)
  -- content-addressed evidence exactly like a mesh or a flownet.
- Planner solvers fill the nine fields like everyone else: cost is
  honest (search is expensive), accuracy bounds the ESTIMATE (a
  cycle-time model has an error band; cite it), conservatism is
  usually `upper` for time/cost, the plan payload rides the
  settings-digest discipline (tool library version, post version),
  and determinism holds (seeded, ordered search). A CAM engine that
  cannot be made deterministic is wrapped at tier=discretized with
  `deterministic=False` and honestly never cached.
- New payload kinds this section and calcite add to 09 sec. 4:
  `flownet` (calcite lowering) and `plan` (planner solvers).

## 6. What stays true across all of it

One protocol; sugar lowers to it. Dispatch reads cost/accuracy/
domain only. Every fallible edge returns values. Everything that can
change an answer is digested. Every number traces to a citation or a
calibration record. A pack you install behaves exactly like code in
this repo -- because the conformance kit will not let it differ.
