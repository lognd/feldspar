# WO-111b -- follow-up slice close-out (lithos WO-110-F6/F4 model gaps)

Status: done (scoped)
Language: Python (library/pack)
Branch: wo111b-followup

## Scope

Lithos WO-110's survey (WO110-F6) named three feldspar-shaped model
gaps for the fleet corpus: fatigue depth (`mech.fatigue.damage`),
FEA-pinned kind exposure (`fea_modal`/`fea_static_stress`/
`fea_contact`), and a waveform-statistics channel (WO110-F4). This
slice lands what is real closed-form/self-contained work and records
an honest disposition for what is not.

## Landed

1. **Fatigue depth** (`python/feldspar/library/fatigue.py`, docs/
   benchmarks-memo.md sec. 20):
   - `fatigue_sn_cycles_to_failure` -- Shigley 11e eqs. 6-13/6-14 S-N
     log-log knee-line cycles-to-failure.
   - `mech.fatigue.miner_damage` -- Shigley 11e sec. 6-16 eq. 6-58
     Miner's-rule cumulative damage over a declared load-block
     spectrum payload (`{"sigma_a": [...], "cycles": [...]}`, kind
     "spectrum", port `MINER_SPECTRUM_PORT`).
   - Both calibrated under the calibration-first law's SECOND path
     (analytic self-check against the closed form's own defining
     boundary conditions, docs/benchmarks-memo.md sec. 20 has the
     full derivation) -- no transcribed textbook number is used
     (fabrication-risk avoidance, WO111B-F2 below).
   - Regolith exposure: `feldspar.pack.models.
     FatigueSnCyclesToFailureModel` (claim kind
     `mech.fatigue.cycles_to_failure`, scalar) and `.
     FatigueMinerDamageModel` (claim kind `mech.fatigue.damage`, the
     D96/09 sec. 4 payload channel, same shape
     `FeaStaticDeflectionFromGeometryModel` uses).

## Surveyed, not attempted

2. **`fea_modal`/`fea_contact` pinned-model exposure** (WO111B-F1):
   `fea/modal.py`'s ccx modal direction is NOT registered in
   `pack.models._engine_registry()` today, and the port it targets
   (`mech.vibe.first_mode_freq`) already has TWO competing closed-form
   producers in `library/vibe.py` (`beam_cantilever_first_mode`,
   `sdof_first_mode`) with empty/trivially-satisfied tag requirements
   -- registering the ccx direction alongside them would not force the
   discretized route the `model=fea_modal` pin needs; the generic
   cost-ordered `solve()` planner would keep picking the cheaper
   closed form regardless of offered tags. Forcing the discretized
   route honestly requires either (a) a dedicated non-generic
   `estimate()` that calls the mesh/deck/ccx chain directly (bypassing
   `solve()`'s port-based routing entirely, mirroring the WO-08 scalar
   pair's self-meshing pattern but for modal), or (b) a routing-level
   discriminator this slice did not design. NOT ATTEMPTED this
   dispatch -- scoped out as a real, non-trivial routing-design
   question, not a quick wrapper. `fea_contact` (AGMA gear-contact
   stress, pinned in `examples/tracks/hematite/gear_reducer.hema`) has
   NO existing feldspar module at all (`grep -r AGMA` finds nothing);
   AGMA 2001-D04 basic contact stress needs geometry factors (I, J),
   load distribution/dynamic/size factors (Km, Kv, Ks, Ko) each with
   their own citation surface -- a full new solver family, out of this
   slice's time budget. NOT ATTEMPTED; reopen as its own WO.
3. **Waveform statistics channel** (WO110-F4/F6, jitter claims):
   surveyed `python/feldspar/elec/ngspice.py` + `elec/results.py` +
   `elec/deck.py`. The `.tran` deck support exists, but
   `elec/results.py`'s `parse_print_value` extracts a SINGLE scalar
   print value per run, not the full time-series voltage/current
   vector a caller needs to compute rms/percentile statistics over a
   transient waveform. The missing piece is exactly that: a
   vector-output parse path (ngspice `wrdata`/`.print` table dump
   parsing) plus a `rms`/`percentile` reduction direction consuming
   it. NOT ATTEMPTED this dispatch (real missing machinery, not a
   quick wrapper); lithos keeps its F131-style exclusion for the
   jitter corpus claims meanwhile.

## Escalations (placeholders, feldspar-side only -- no lithos D/F
numbers self-assigned)

- WO111B-F1: `fea_modal`/`fea_contact` pinned-model exposure needs a
  routing-forcing design (modal: bypass `solve()`'s port-based
  competition for a dedicated discretized-only estimate; contact:
  a net-new AGMA 2001-D04 module). Reopen with either design decided.
- WO111B-F2: the fatigue depth calibration used the ANALYTIC SELF-
  CHECK path (calibration-first law sec. 3.1, second path) rather
  than a transcribed published-example number, to avoid fabrication
  risk on a page/example citation this dispatch could not
  independently re-verify. If a maintainer has direct access to
  Shigley 11e's own worked cumulative-fatigue-damage example, swapping
  in that citation (keeping the same closed form) is a small
  follow-up, not a re-derivation.

## Verification

`make check` green in this worktree (fmt, lint, import-lint, ty
typecheck, `pytest tests/ -n auto -m "not regolith and not fea and not
spice"` -- 479 passed, cargo fmt/clippy/test). The new regolith-marked
suite (`tests/regolith/test_pack_wo111b_exposure.py`) needs a real
lithos checkout to run (`regolith` extra) -- not runnable from this
isolated worktree (`../lithos` path dependency does not resolve
inside `.worktrees/`); the coordinator runs `make regolith-test` from
the real checkout.
