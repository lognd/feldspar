# WO-19: solver-pack plugin system + conformance kit (M9) + the AD-26 migration

Status: todo
Depends: WO-03 (registry), WO-14 (contract v2 -- packs must conform
to the current boundary); lithos WO-44 for the entry-point half
(see below; the kit half does not wait on it)
Language: Python (`feldspar/packs.py`, `feldspar/testing/`)
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

## Acceptance

- Toy pack passes the kit out-of-repo; kit failures are
  constructive (name the rule violated); discovery deterministic by
  test; post-migration (or recorded gate) the lithos conformance
  suite is green.
