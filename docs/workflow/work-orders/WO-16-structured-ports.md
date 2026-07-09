# WO-16: structured ports + the vibration tier (M6)

Status: done (2026-07-08 completion cycle)
Depends: WO-12 (payload machinery), WO-14 (boundary channel for
spectrum/profile/mask refs)
Language: Python (+ `feldspar-core` for rank-native port model)
Spec: 02 (non-scalar quantities -- OPEN-12's rank-native model;
OPEN-11's payload adoption incl. the D102 temporal split), 09
secs. 4/8 (M6), 07 vibration (the consuming tier)

## Goal

Spectrum/profile/mask payloads and ranked (vector/complex/tensor)
ports go live, unblocking the vibration tier (07 Phase 3): Miles'
equation, PSD/GRMS arithmetic, SDOF/MDOF entries, ccx modal reusing
the WO-12 mesh step.

## Deliverables

- Ranked ports registered beyond scalar (per-component
  uncertainty; scalar reductions -- magnitude, von Mises -- are
  ordinary edges, never implicit casts; rank mismatch = registration
  error). v1's scalar-only registration restriction lifts.
- `spectrum`/`profile`/`mask` payload kinds consumed by real
  solvers: Miles (spectrum -> GRMS), rainflow/Miner with
  mech.design, mask containment checks. Claim-form reductions
  follow the D102 split: `peak`/`rms(band)`/`overshoot` are edges
  to ranked ports with EXTERNAL comparators;
  `settles`/`stays_within` are verdict-shaped containments.
- Modal tier: ccx modal/harmonic instantiating the 05 pipeline
  pattern over the M2 mesh step (frequencies + mode shapes; the 07
  vibration (d) row); closed-form SDOF/beam-table entries as its
  cheap competitors and calibration partners.
- 02-edge-cases rows: rank mismatch, band outside spectrum domain,
  mask/profile domain misalignment (honest errors, never clipping).

## Acceptance

- A `mech.first_mode`-shaped claim discharges at closed-form tier
  on a clean beam and escalates to ccx modal when the margin
  demands (fea-marked); a random-vibe GRMS claim consumes a
  spectrum payload end to end; planner tier-blind; determinism
  suite green.

## Close-out (2026-07-08 completion cycle)

Delivered:

- Ranked ports (`Rank::Vector`/`Complex`/`Tensor`) were ALREADY live
  end to end at the core/registry level (`feldspar-core::rank`,
  `feldspar-py::rank::PyRank`, `SolverRegistry.declare_ports`'s
  generic rank-conflict check) as of WO-02/WO-12 -- no v1
  scalar-only guard existed to lift. Verified (not re-implemented)
  with a new registration-error test
  (`tests/unit/test_library_vibe.py::
  test_rank_mismatch_at_connection_is_a_registration_error`) proving
  the WO-03 rank-mismatch row against a REAL WO-16 payload port.
- `mech.vibe.first_mode_freq`: closed-form cantilever-beam direction
  (Blevins Table 8-1) and a closed-form SDOF competitor (Rao),
  `crates/feldspar-library/src/mech.rs`'s `beam_cantilever_first_mode`/
  `sdof_first_mode`, wired through `python/feldspar/library/vibe.py`.
- ccx modal direction `fea.modal.cantilever_from_mesh`
  (`python/feldspar/fea/modal.py`): a `*FREQUENCY` deck
  (`build_cantilever_modal_deck`, `deck.py`) reusing the WO-12
  `fea.mesh.cantilever` mesh payload, a `.dat` mode-table parser
  (`parse_dat_frequencies`/`first_mode_frequency`, `results.py`).
  Planner routing verified directly (both routes -- closed-form when
  in-domain, mesh+modal when the beam direction's density box is
  exceeded -- land exactly as designed, `tests/integration/
  test_vibration_modal_tier.py`); ccx/gmsh EXECUTION is unverified in
  this sandbox (no gmsh wheel, no ccx binary) -- the SAME standing
  caveat `TODO.md` already records for every other `fea`-marked suite
  (WO-08/09/10/12).
- Miles' equation GRMS (`mech.vibe.miles_grms`): spectrum payload
  (JSON `{freq_hz, asd_g2_per_hz}`) resolved via `PayloadResolver`,
  linear-interpolated ASD lookup at the claim's `first_mode_freq`,
  `crates/feldspar-library/src/mech.rs`'s `miles_grms`. Consumed end
  to end in `tests/unit/test_library_vibe.py` (no ccx/gmsh needed --
  a pure payload+scalar direction).
- `mech.vibe.mask_containment`: profile/mask payload comparison
  (the `stays_within` claim form's edge, D102 split), domain
  misalignment (mismatched sample grids) as an honest
  `SolveError.OutOfDomain`, never an implicit resample.
- 02-edge-cases: new "Structured ports + vibration tier (WO-16)"
  section, 8 rows, all covered by `tests/unit/test_library_vibe.py`
  and `tests/integration/test_vibration_modal_tier.py`.

Escalated / cut, named explicitly (none silently dropped):

- **Rainflow/Miner with `mech.design`** (named in Deliverables) is
  CUT from this pass: it is not required by the Acceptance list
  (which only names `first_mode`/GRMS), and a real cycle-counting +
  S-N/Miner's-rule implementation is a standalone-sized effort in its
  own right (a new fatigue-curve data model, not just a formula).
  Flagging for a follow-up WO/ticket rather than a rushed stub.
- **Mode SHAPES** (the eigenvector, not just the eigenvalue) from the
  ccx modal direction are NOT produced. `fea.modal.cantilever_from_mesh`
  reports only the frequency scalar; a mode-shape payload output (a
  natural `Payload("mode_shape")` extension of `MeshData`-shaped
  node-displacement arrays) is deferred. Reopen when a consumer
  claim actually needs mode-shape data (07 vibration's (d) row is
  satisfied by frequency alone for M6; harmonic response reading mode
  shapes is a natural WO-16 follow-on, not required by this WO's
  stated Acceptance).
  Mode SHAPES are a genuinely separate rank-native-vs-payload design
  question (a mode shape has real componentwise spread across mesh
  refinement, so it is arguably a RANKED port, not payload -- 02's own
  dividing rule is ambiguous here) and is left OPEN rather than
  guessed at.
- A componentwise Richardson/eps-seeking ladder for the modal
  direction (mirroring WO-13's static-solve ladder) is not wired;
  the modal direction uses a single-mesh declared ceiling, exactly
  the same posture `fea/payload_steps.py`'s static-from-mesh twin
  already ships with. Natural M3 extension, not required here.
- The cross-module port-table composition tension already documented
  in `fea/payload_steps.py`'s docstring (declaring the SAME port
  twice across two catalog modules is `RegistryError.DuplicatePortDecl`,
  not a tolerated no-op) surfaced again for `mech.material.
  youngs_modulus`/`mech.geom.cantilever.length`/`mech.section.
  second_moment` (shared between `library/mech.py` and this WO's
  `library/vibe.py`). Resolved the same way payload_steps.py already
  does: `vibe.py` does NOT declare those three, documented in its
  `register()` docstring as a composing-catalog responsibility (its
  own unit tests declare them locally). Full port-table unification
  across ALL library modules remains out of this WO's scope (it was
  already out of WO-14's despite that WO's name suggesting otherwise).
