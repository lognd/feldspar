# 12 -- Solver organization (normative)

Decided with lithos cycle 35 (lithos D227/AD-37, owner directive
2026-07-13). This spec codifies where solver content GOES in this
repo, what it is NAMED, and the evidence bar it must meet. It is
the feldspar counterpart of lithos
`docs/spec/toolchain/39-stdlib-organization.md`; section 4 (the
boundary rule) is shared verbatim between the two documents and
must not drift.

## 1. Package taxonomy

1. One engineering domain per Python package under
   `python/feldspar/<domain>/` (`mech`, `elec`, `fea`, `thermo`,
   ...). Infrastructure packages (`plan`, `calib`, `testing`,
   `core`) are not domains and never register solvers themselves.
2. Within a domain, one MODULE per solver family
   (`mech/beams.py`, `mech/welds.py`, `mech/fatigue.py`) -- a
   family is one physical topic sharing inputs vocabulary and
   citations. External-engine adapters (ngspice, calculix) keep
   the established `<domain>/<engine>.py` + `deck.py`/`results.py`
   split.
3. A new domain is a new package plus a one-paragraph note in
   `07-capability-map.md`'s source; never a module squatting in an
   unrelated domain.

## 2. Naming

1. `solver_id` is the dotted lowercase path
   `<namespace>.<family>.<direction>` (spec 03), and `namespace`
   EQUALS the domain package name. The id is the routing key on
   both sides of the regolith seam; it never encodes tier, engine,
   or repo.
2. The lithos claim kind a solver serves uses the same
   `<domain>.<family>.<quantity>` shape; the pack manifest maps
   claim kind -> solver directions explicitly (spec 06/09), never
   by string coincidence.

## 3. Evidence bar (calibration-first law)

1. Every solver direction ships IN THE SAME CHANGE with a
   calibration test against a PUBLISHED worked example -- source,
   edition, and example/table number cited in the test -- with a
   stated tolerance. No citable worked example means the solver
   lands with a clearly-derived analytic self-check AND a recorded
   flag in its module docstring; fabricated reference values are
   refused.
2. `SolverInfo.citations` stays REQUIRED non-empty (spec 03);
   `accuracy` bounds are honest model-error statements, never
   aspirational.
3. Shared oracles live in `calib/`; a QA oracle that exists to
   check a solver independently must NOT import the solver's own
   implementation.

## 4. The boundary rule (shared verbatim with lithos charter 39)

A model belongs in lithos `harness/models/` iff ALL hold: closed
form from a citable source; deterministic with at most bounded
fixed iteration; inputs/outputs are scalars-with-units already in
the claim vocabulary; community tier suffices. Otherwise it belongs
in feldspar. A model moving across the boundary is a migration with
a design-log entry, never a copy -- the SAME physics must never be
resolvable from two homes (the duplication rule applied to models;
the router prefers the pack when both could answer, and the
built-in is retired in the same change).

## 5. Registration and growth discipline

1. Solvers register by decorator into the frozen deterministic
   registry (spec 03); the capability map (07) is REGENERATED from
   the registry and drift-checked -- never hand-edited.
2. Pack exposure to regolith goes through the one manifest (spec
   06); a solver not in the manifest does not exist to lithos, and
   the manifest row names the claim kind served plus the expected
   input names (the contract lithos WO briefs consume).
3. Determinism contracts (spec 02: corner monotonicity,
   `deterministic`, settings digests) are part of the direction's
   identity -- changing them is a version bump, not an edit.
4. Additive-only within a family module; renames/removals are
   migrations recorded in the workflow log with the lithos-side
   sweep coordinated in the same integration.

## 6. Reopen criteria

Section 4 moves only with per-model evidence (lithos charter 39
sec. 6 mirrors this). Engine-adapter structure (1.2) reopens only
when a second engine of the same class lands and the split
demonstrably fails it.
