# WO-15: parallel execution (M5)

Status: done (2026-07-09 completion cycle)
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

## Close-out (2026-07-09)

**Architectural finding that reshaped scope**: real solver evaluation
crosses the PyO3 boundary as a GIL-bound Python `SolveFn` callback
(`corner_sweep_py`); no pure-Rust eval path exists for real solvers
today (the only `feldspar-library` consumer of `corner_sweep` is
`search.rs`'s sum-surrogate ESTIMATE, which never calls back into
Python). A GIL-bound callback cannot run concurrently across rayon
worker threads with any real parallelism benefit -- rayon-based
Rust-side threading was therefore not the right mechanism for the
NAMED parallelism sites (corner solves, calibration sweeps); the
actual "uses available cores" win is Python-side concurrent dispatch
of the callback (which DOES help wall-clock whenever the callback
itself releases the GIL -- subprocess FEA/spice calls, or PyO3 calls
back into Rust).

**Delivered**:
- `feldspar_core::propagation::hull_from_results` (+ its PyO3 wrapper
  `hull_from_results`, alongside a newly-exposed `enumerate_corners`):
  splits `corner_sweep` into enumerate/fold halves so a caller can
  evaluate corners OFF the hot fold path -- in particular, in
  parallel -- and fold through the ONE core hull routine (FINV-4
  preserved: still one hull implementation). Rust unit test proves
  the fold is order-independent (shuffled vs. corner-order inputs
  produce byte-identical hulls) -- the determinism argument FINV-9
  rests on.
- `feldspar.plan.parallel.parallel_corner_sweep`: the Python-side
  parallel corner dispatch, `thread_count=1` (default) being the
  always-present serial fallthrough (byte-identical code path to
  `corner_sweep`, not just byte-identical output). `thread_count>1`
  dispatches via `concurrent.futures.ThreadPoolExecutor`, whose `map`
  preserves input (corner) order regardless of completion order, so
  the fold is always over the same ordered results (FINV-9). Serial
  path short-circuits on the first corner's `Err`, exactly matching
  `corner_sweep`; the parallel path cannot short-circuit mid-flight
  (dispatch is eager) but still surfaces the same FIRST-in-order
  `Err`.
- `feldspar.calib.harness.calibrate` gained a `thread_count` parameter
  ("calibration sweeps parallelize (03) -- the dev-loop win that
  motivates the milestone", verbatim from this WO's Deliverables):
  sample points are generated sequentially from the seeded rng (the
  point SEQUENCE never depends on `thread_count`), evaluated across a
  thread pool when `thread_count>1`, then folded in original point
  order via the existing max-reduction (commutative/associative, so
  byte-identical at any `thread_count`).
- Determinism suite: `tests/unit/test_parallel_determinism.py`
  (`parallel_corner_sweep` vs. serial `corner_sweep` at thread counts
  1/2/4/8; `calibrate` digest at thread_count 1 vs. 4) plus the Rust
  `hull_from_results_matches_corner_sweep_regardless_of_result_order`
  test. No platform-specific APIs (`std`/`concurrent.futures` only;
  grep-clean of any OS-conditional code).
- FINV-9's mechanism cell (00-architecture.md) updated to cite the
  actual implementation.

**Cut, and why (recorded rather than silently dropped)**:
- **`execute()`'s per-step corner sweep is UNCHANGED.** `_make_corner_fn`
  (execute.py) closes over shared mutable state (`measured: List[float]`,
  `produced: Dict[str, List[PayloadRef]]`) that every corner call
  appends to as a side effect -- parallelizing that call site safely
  requires restructuring the corner callback to return its
  measurement/payload-production data instead of mutating shared
  state, which is bigger than "wire in the new primitive" and sits
  exactly in the executor/route territory WO-18 (CoupledGroup,
  parallel in this same cycle) is also touching. Flagged per this
  WO's dispatch instructions rather than risking a collision;
  `parallel_corner_sweep` is ready to be wired in there once that
  restructuring happens (a natural WO-18 or follow-up task).
- **Route-step-level parallelism** (independent route steps running
  concurrently) is not implemented: `Route.steps` is a flat ordered
  list with no independence/dependency metadata in the current model
  (WO-06), so "which steps are independent" is not yet answerable
  without new structure -- another reason this sits close to WO-18's
  scope and was left alone.
- **`resweep_derived`'s sample loop** was not threaded (unlike
  `calibrate`'s): it is documented as "cheap: the law is closed-form
  by construction" and is called synchronously from `check_ceilings`'s
  hot path; threading it would add real complexity (its own
  `thread_count` plumbing through `resweep_all_derived`/
  `check_ceilings`) for a site the codebase's own comments say is
  already fast. Left as a candidate follow-up, not required by this
  WO's acceptance.
- **Refinement-ladder rungs** (`fea/ladder.py`'s
  `climb_richardson_ladder`) are NOT parallelized: the ladder is
  intentionally adaptive/sequential (climb until budget met, stop
  early) -- eagerly running all rungs in parallel would defeat the
  WO-13 budget-seeking design's entire cost-saving purpose. Not
  cut for lack of a mechanism; ruled out on the merits.

`make check`-equivalent gates all green: `fmt-check`, `lint`,
`import-lint`, `typecheck` (ty), `cargo test --workspace` (63 tests,
incl. the new determinism proof), `pytest tests/ -m "not fea and not
spice"` (328 passed, 0 failed).
