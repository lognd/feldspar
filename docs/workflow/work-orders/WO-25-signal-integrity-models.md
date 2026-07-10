# WO-25: signal-integrity closed-form models (impedance + termination)

Status: todo
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
