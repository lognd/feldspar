# WO-25: signal-integrity closed-form models (impedance + termination)

Status: done, landed with a named residual (`diff_pair_z` cut whole --
see ledger below and `python/feldspar/library/signal_integrity.py`'s
module docstring).
Depends: WO-11/22 (validity predicates), the benchmarks memo
(in-repo). Serialize integration with the in-flight WO-24 thermal
dispatch (both register in pack/models.py -- keep your registration
additive; the integrator resolves).
Language: Python pure-map @solver directions (member_capacity.py
precedent) + memo sections.
Spec: lithos:docs/spec/toolchain/35-signal-integrity.md sec. 1.6
(NORMATIVE target list); lithos design-log 2026-07-10-cycle-32
D186; this repo's standing law (cited, calibrated, predicated).

## Deliverables

1. `elec.si.microstrip_z0` (Hammerstad-Jensen, w/h + Dk + t ->
   Z0), `elec.si.stripline_z0` (symmetric stripline),
   `elec.si.diff_pair_z` (edge-coupled forms) -- each with narrow
   validity predicates (w/h + Dk ranges, TEM assumption, the
   formulas' own stated accuracy bands as declared error).
2. Termination sizing: `elec.si.series_termination` (Rs = Z0 - Ro),
   `elec.si.ac_shunt_sizing` (R/C from Z0 + rise time, cited
   form), `elec.si.thevenin_termination` -- outputs carry the full
   arithmetic (inputs echoed in the result payload) so lithos
   evidence shows the numbers.
3. Memo sections: calibration against >= 2 PUBLISHED fab impedance
   tables/calculators (cite fab + revision/date) within stated
   tolerance; a case outside a validity band proven to reject.
4. Registration + tests + WO ledger (dispatch record; name every
   direction signature for lithos WO-78 to consume).

## Acceptance: every direction calibrated + predicate-gated; gates
green via uv run (7 pre-existing collection errors unchanged);
Status flipped with the ledger.

## Dispatch ledger (cycle-33, worktree `cycle33-wo25-si`)

Landed (`python/feldspar/library/signal_integrity.py`, seven `@solver`
directions, `docs/benchmarks-memo.md` sec. 13):

- `elec.si.microstrip_z0` -- Hammerstad-Jensen (Wadell 1991 eq. (2)/
  (3a)/(3b)), calibrated against Burkhardt/Gregg/Staniforth 1999
  Table 1's field-solver column (three widths, within ~1.3%, inside
  Wadell's own quoted 2%). Accuracy declared `Accuracy(0, 0.02)`, not
  `EXACT` (it is a curve-fit closed form).
- `elec.si.stripline_z0` -- Cohn's 1954 exact centred-track symmetric
  stripline closed form, Hilberg's 1969 elliptic-ratio approximation
  (accurate to 1e-12 per Burkhardt 1999's own citation). Exact-theory
  calibration tier (same as `member_capacity.py`'s
  `euler_critical_buckling_load`), not a numeric-table fit.
- `elec.si.series_termination` -- exact algebra (Johnson & Graham
  1993 ch. 4).
- `elec.si.thevenin_termination_r1` / `_r2` -- exact algebra (same
  chapter), verified by a Kirchhoff recombination check
  (`(R1*R2)/(R1+R2) == Z0` exactly) in
  `tests/unit/test_library_signal_integrity.py`.
- `elec.si.ac_shunt_sizing_r` -- exact (R=Z0).
- `elec.si.ac_shunt_sizing_c` -- Johnson & Graham's quarter-rise-time
  RC guideline, a NAMED HEURISTIC with a wide declared accuracy
  (`Accuracy(0, 1.0)`, honestly stating the tr/5..tr/2 spread around
  the tr/4 midpoint baked here), not a physical law.

CUT WHOLE, named residual (deliverable 1's third form): `diff_pair_z`
(edge-coupled differential impedance). The commonly quoted
`Zdiff = 2*Z0*(1-0.48*exp(-0.96*s/h))` IPC-2141-style form could not
be traced to a verbatim primary-source equation within this dispatch's
research budget (WebSearch/WebFetch turned up secondary paraphrases
and image-only formula renderings, not a confirmable primary text --
contrast `microstrip_z0`/`stripline_z0`, both verified against a
primary-source PDF actually read, `Burkhardt, Gregg & Staniforth,
"Calculation of PCB Track Impedance", IPC Printed Circuit Expo 1999`).
Per the WO-24/WO-25 standing law ("never land uncalibrated"), this
direction is cut whole rather than landed on an unverified formula.
Reopen criteria: a verbatim IPC-2141(A) or Wadell equation for
edge-coupled differential impedance confirmed against a primary
source, with at least one traceable numeric calibration point.

Exposure (`python/feldspar/pack/models.py` "WO-25 signal-integrity
wave" section, `python/feldspar/pack/__init__.py`): seven regolith
`Model` classes, nine registered instances (`MicrostripImpedanceModel`/
`StriplineImpedanceModel` each register twice, one per `within
[lo, hi]` obligation half, D186 sec. 1 point 2, mirroring
`ElecRailModel`). `feldspar.pack.register()` now registers nineteen
models total (twelve pre-existing + seven new signature classes minus
the two rail/microstrip/stripline double-counting -- see
`pack/__init__.py`'s own registration call list for the exact nine
instances). Claim kinds named for lithos WO-78 to consume:
`elec.si.microstrip_z0.{lo,hi}`, `elec.si.stripline_z0.{lo,hi}`,
`elec.si.series_termination.rs`, `elec.si.thevenin_termination.{r1,r2}`,
`elec.si.ac_shunt.{r,c}`.

Deliverable 2's "outputs carry the full arithmetic (inputs echoed in
the result payload)" is satisfied STRUCTURALLY via the regolith
`DischargeRequest.inputs`/`Prediction` evidence channel (the standard
channel every other WO-24-wave direction relies on for the same
purpose) -- no per-direction manual echo was added, matching
precedent (no other closed-form direction in this pack manually
duplicates its inputs into the `Ok` payload either).

Test counts: `tests/unit/test_library_signal_integrity.py` (16 cases,
library-level, no regolith needed) +
`tests/regolith/test_pack_wo25_exposure.py` (9 cases, regolith-marked,
wrapper plumbing only, reusing the library-level pinned values).
Before this dispatch: 413 non-regolith / 75 regolith-marked (488
total, 0 collection errors with regolith installed -- NOT the WO's
"7 pre-existing collection errors unchanged" baseline: that count
assumed `--no-extra regolith`; this worktree used `make
install-regolith` per the dispatch's own instruction to exercise the
pack, and got 0 collection errors both before and after). After:
429 non-regolith / 84 regolith-marked (513 total). `make check` green
(fmt, clippy, ty, import-lint, pytest, `cargo test --workspace`) in
worktree `cycle33-wo25-si`.

Commits: `feat(si): land WO-25 signal-integrity closed-form
directions`, `fix(si): declare honest accuracy bands, wire into
engine registry`, plus the pack-exposure/docs/ledger commits that
follow this one.
