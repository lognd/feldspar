# WO-15: parallel execution (M5)

Status: todo
Depends: WO-06 (executor), WO-13 (rungs are a parallelism site)
Language: Rust (`feldspar-core` threading) + Python (executor
orchestration)
Spec: 09 sec. 6 (NORMATIVE, closes OPEN-9: determinism >
portability > fallthrough), 00-architecture FINV table (extend with
the parallel-determinism guarantee + mechanism in the same change)

## Goal

Independent work (corner solves, refinement rungs, independent
route steps, calibration sweeps) uses available cores with
bit-identical results to the serial path.

## Deliverables

- Pure-Rust threading (std/rayon) in `feldspar-core` hot paths;
  Python-side concurrent dispatch of independent route
  steps/corners; thread count 1 is a configuration (the always-
  present serial fallthrough).
- Order-deterministic assembly: sorted corner order, sorted digest
  folds -- never arrival order; external-tool guards unchanged
  (`OMP_NUM_THREADS=1` for ccx stays; parallelism is ACROSS runs).
- The determinism suite runs serial AND parallel paths and diffs
  bytes (the 09 sec. 6 constraint made a standing test).
- Calibration harness sweeps parallelize (03) -- the dev-loop win
  that motivates the milestone.

## Acceptance

- Serial and parallel solves of the corpus produce byte-identical
  Solutions/digests on >= 2 thread counts; no platform-specific
  APIs (grep-proven); `make check` green single- and multi-thread.
