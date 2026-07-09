# WO-19: solver-pack plugin system + conformance kit (M9) + the AD-26 migration

Status: done
Depends: WO-03 (registry), WO-14 (contract v2 -- packs must conform
to the current boundary); lithos WO-44 for the entry-point half
(see below; the kit half does not wait on it)
Language: Python (`feldspar/solve/packs.py` -- alongside `SolverRegistry`
rather than a top-level `feldspar/packs.py`, re-exported through
`feldspar.solve.__all__`, since every other registry-composition
symbol already lives in that package; `feldspar/testing/`)
Spec: 10 sec. 3 (pack protocol + conformance kit), 09 sec. 8 (M9);
lithos AD-26/D134 (the ONE `regolith.plugins` group) for the
regolith-facing entry point

## Goal

Out-of-repo solver packs are first-class: a `feldspar.solver_packs`
entry point with sorted composition, a conformance kit
(`feldspar.testing.assert_solverpack_conforms`), namespace
etiquette checks -- and feldspar's own regolith-facing entry point
migrates to the unified `regolith.plugins` group (kind=model_pack)
when lithos WO-44 lands.

## Deliverables

- `feldspar.solver_packs` discovery: sorted-by-name composition
  (deterministic), duplicate-id loud error, pack version folded
  into affected digests (the WO-20-precedent rule).
- `assert_solverpack_conforms`: registration validity (citations
  non-empty, domains well-formed, kind strings lint-clean per
  WO-14), determinism smoke (twice-run digest equality over the
  pack's declared fixtures), namespace etiquette (no squatting on
  `mech`/`elec`/... without matching claim kinds).
- A toy out-of-repo pack (fixture directory with its own
  pyproject) passing the kit from its own test session -- the M9
  acceptance.
- AD-26 migration (the TODO's standing queue item, folded here):
  `[project.entry-points."regolith.model_packs"]` ->
  `regolith.plugins` kind=model_pack, one release, conformance
  re-run against lithos `tests/packs/`; GATED on lithos WO-44 --
  if it has not landed at dispatch, deliver the kit half and
  record the migration as this WO's named remainder.

  DONE ALREADY at dispatch: lithos WO-44 had landed before this WO
  was picked up, and feldspar's own entry point (`pyproject.toml`
  `[project.entry-points."regolith.plugins"]`, target
  `feldspar.pack:MANIFEST`) was migrated to the unified seam in an
  earlier change (see `python/feldspar/pack/__init__.py`'s module
  docstring and `tests/regolith/test_pack_conformance.py`, both
  already referencing the `regolith.plugins`/`PluginManifest` shape
  before this WO started). This WO therefore delivered ONLY the kit
  half described below; no migration work remained to do.

## Acceptance

- Toy pack passes the kit out-of-repo; kit failures are
  constructive (name the rule violated); discovery deterministic by
  test; post-migration (or recorded gate) the lithos conformance
  suite is green.

## Close-out (kit half)

- `feldspar.solve.packs`: `load_solver_packs` discovers the
  `feldspar.solver_packs` entry-point group (or an
  `entry_points_override` of `FakeSolverPackEntryPoint`/any
  `SolverPackEntryPoint`), composes sorted-by-entry-point-name after
  the caller's built-ins, stages each pack onto a scratch
  `SolverRegistry` (seeded with the base port table) so a bad pack
  never partially lands, and replays a clean stage onto the real
  registry. Typed `SolverPackLoadError` variants each name the
  offending pack: `DuplicateSolverId` (names both the pack and the
  id's original owner, `"<builtin>"` or an earlier pack),
  `NamespaceViolation` (squatting on a bare standard namespace with
  no `reviewed_namespaces` opt-in), `MethodNamedSolverId` (the D94
  lint, one level down), `PackRegisterRaised`, `MalformedSolverPack`,
  `PortDeclarationFailed`, `RegistrationRejected`. `PackInfo`'s
  version comes from the entry point's own `dist.version`.
  `pack_composition_digest` folds a registry digest with every
  loaded pack's (name, version) pair -- the WO-20-precedent rule,
  since `SolverInfo` itself carries no pack identity.
- `feldspar.testing.assert_solverpack_conforms`: composes the pack
  via `load_solver_packs` (re-asserting a clean `skipped == ()`),
  then per registered solver checks a non-empty domain box, the
  method-named-kind lint, twice-run determinism (byte-identical
  `SolveOutput.values`), domain honesty (`Domain.admits` rejects a
  point well outside the box), and a corner-monotonicity spot check
  (`feldspar.core.corner_sweep` over the declared box, interior
  sample inside the corner hull within a loose tolerance). Every
  failure is a plain `AssertionError` naming the solver id and rule.
- `fixtures/toy_solver_pack/`: an out-of-repo-shaped pack
  (`toy_bearings`, own `pyproject.toml`, its own `feldspar.solver_packs`
  entry point, own `uv.lock`-free `uv sync`) whose
  `tests/test_conformance.py` calls `assert_solverpack_conforms`
  from its OWN `uv run pytest` session -- verified green in this
  close-out, independent of the parent repo's test config.
- Unit coverage: `tests/unit/test_solver_packs.py` (11 cases) --
  deterministic sorted composition, cross-pack duplicate-id naming
  both packs, namespace squatting rejected, `reviewed_namespaces`
  opt-in, a pack's own non-standard namespace always being its own
  turf, the method-named-kind lint, a malformed (non-callable) entry
  point, pack-version digest folding, and both the passing and
  failing paths of `assert_solverpack_conforms`.
- `make check`-equivalent gates all green: `ruff format --check`,
  `ruff check`, `lint-imports`, `ty check`, `cargo fmt --check`,
  `cargo test --workspace` (after `cargo build -p feldspar-library`
  per the `extern_c_smoke` dlopen note), `pytest tests/ -m "not fea
  and not spice"` (331 passed).
