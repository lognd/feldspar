# WO-07: library/mech Phase 1 + calibration harness

Status: done
Depends: WO-06
Language: Rust formulas (`feldspar-library::mech`) + Python
registration (`feldspar/library/mech.py`) + Python harness
(`feldspar/calib/`)
Spec: 07 Phase 1, 03 (citations, Rust homes), FINV-6, 09 sec. 7

## Goal

The Phase 1 formula homes (the FEA oracles) and the calibration
harness that makes every declared ceiling defensible.

## Deliverables

- `feldspar-library::mech` (Rust, extern "C" exported, AD-3):
  `rect_second_moment`, Euler-Bernoulli cantilever tip deflection,
  Lame thick-wall hoop/radial stress, bore `von_mises` (THE single
  von Mises home). Unit-consistent, documented, each with its
  citation constants alongside. Transcendentals via AD-13's
  deterministic libm only (sqrt is exempt).
- `feldspar/library/mech.py`: `register(registry)` wiring each
  formula as solver directions with ports (02 naming), domains
  (linear_elastic etc. tags), costs, exact-or-cited accuracies, and
  method citations (FINV-6). Multi-direction where meaningful
  (e.g. deflection -> required E).
- Calibration harness v1 (`feldspar/calib/`): sweep a solver vs a
  reference solver (or cited dataset) over sampled in-domain points
  (deterministic seed), record worst observed error, emit a
  content-addressed run record; `calibrate(solver_id, reference_id,
  registry) -> Result[CalibRecord, CalibError]`; a check that every
  declared ceiling <= its newest CalibRecord's observed bound fails
  loudly. Records land under `tests/calib/records/` (committed).
- Known-answer unit tests against textbook values (cited in test
  docstrings).

## Acceptance

- All Phase 1 solvers registered with citations; `extern "C"` symbol
  presence asserted (nm/dlopen smoke test); calibration records
  exist for every declared ceiling and the ceiling-vs-record check
  is in `make check`.
