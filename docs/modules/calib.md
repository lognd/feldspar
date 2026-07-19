# feldspar.calib

The calibration subpackage: content-addressed evidence records for
"how well does solver X track reference solver Y", the harness that
produces them, and the flat on-disk store that persists them (01-interfaces
~261-275, 09 sec. 7, WO-07).

## calib_models

<!-- frob:describes python/feldspar/calib/_models.py::CalibRecord -->

`CalibRecord` is the content-addressed calibration run record: one
calibration run's evidence -- `solver_id` swept against `reference_id`
over `n_samples` deterministic (`seed`) in-domain points, with the worst
observed absolute/relative error. `digest` is `canonical_digest` of every
other field (AD-5, AD-9: the digest IS the record's content-address; a
`Citation(kind="calibration", ref=digest)` points here). Frozen pydantic
model, same convention as `Citation`/`SolverInfo` (`feldspar.solve._models`).

## calib_errors

<!-- frob:describes python/feldspar/calib/errors.py::CalibError -->
<!-- frob:describes python/feldspar/calib/errors.py::CalibError.UnknownSolver -->
<!-- frob:describes python/feldspar/calib/errors.py::CalibError.DomainMismatch -->
<!-- frob:describes python/feldspar/calib/errors.py::CalibError.CeilingBusted -->
<!-- frob:describes python/feldspar/calib/errors.py::CalibError.NoRecord -->

`CalibError` is the total error union for the calibration harness, using
the same `_TaggedError` idiom as `feldspar.solve.errors.RegistryError`/
`SolveError` (one home for the kind/fields/eq/hash/repr machinery -- no
duplication). Its tagged constructors cover: an unknown solver id
(`UnknownSolver`), domains that don't overlap enough to sample
(`DomainMismatch`), a declared accuracy ceiling tighter than its backing
evidence (`CeilingBusted`), and a calibration citation with no matching
run record on disk (`NoRecord`).

## calib_store

<!-- frob:describes python/feldspar/calib/store.py::record_path -->
<!-- frob:describes python/feldspar/calib/store.py::write_record -->
<!-- frob:describes python/feldspar/calib/store.py::read_record -->

Flat content-addressed store for `CalibRecord` run files (AD-9, same
shape as `feldspar.plan.cache.SolveCache`): the filename IS the record's
own digest, so these are pure key-value operations with no index and no
eviction. `record_path` computes `records_dir / f"{digest}.json"` (the
one place this filename convention is spelled out); `write_record` dumps
a `CalibRecord` as sorted-key JSON at that path; `read_record` loads one
back.

## calib_harness

<!-- frob:describes python/feldspar/calib/harness.py::calibrate -->
<!-- frob:describes python/feldspar/calib/harness.py::check_ceilings -->

The calibration harness itself. `calibrate()` sweeps a candidate solver
against a reference solver over sampled in-domain points with a
deterministic seed and emits a content-addressed `CalibRecord`.
`check_ceilings()` verifies every non-EXACT declared accuracy ceiling in
a registry is backed by calibration evidence at least as tight as it
claims (FINV-6). Both work against any `SolverRegistry`/`SolveFn` pair --
no dependency on any specific solver catalog.
