from __future__ import annotations

"""The calibration harness (01-interfaces ~261-275, 09 sec. 7, 03
"Citations and calibration", WO-07): `calibrate()` sweeps a candidate
solver against a reference solver over sampled in-domain points with a
deterministic seed and emits a content-addressed `CalibRecord`;
`check_ceilings()` verifies every non-EXACT declared accuracy ceiling in
a registry is backed by calibration evidence at least as tight as it
claims (FINV-6). Works against ANY `SolverRegistry`/`SolveFn` pair --
no dependency on any specific solver catalog."""

import random
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Tuple

from typani.result import Err, Ok, Result

from feldspar.calib._models import CalibRecord
from feldspar.calib.errors import CalibError
from feldspar.calib.store import read_record, write_record
from feldspar.logging_setup import get_logger
from feldspar.solve._models import EXACT, SolverInfo
from feldspar.solve.digest import canonical_digest
from feldspar.solve.solver import SolveFn

if TYPE_CHECKING:
    from feldspar.solve.registry import SolverRegistry

__all__ = [
    "calibrate",
    "check_ceilings",
    "resweep_derived",
    "resweep_all_derived",
]

_log = get_logger(__name__)


def _solver_map(registry: "SolverRegistry") -> Dict[str, Tuple[SolverInfo, SolveFn]]:
    """Build an id -> `(SolverInfo, SolveFn)` lookup by iterating
    `registry` locally (no `SolverRegistry.get` exists -- WO-03/06
    territory, out of scope here)."""
    return {info.solver_id: (info, fn) for info, fn in registry}


def _shared_input_box(a: SolverInfo, b: SolverInfo) -> Dict[str, Tuple[float, float]]:
    """Intersection box, over ports present in both solvers' `Domain.box`,
    restricted to ports either solver declares as an input. Empty dict
    (or any empty interval) signals no usable overlap."""
    box: Dict[str, Tuple[float, float]] = {}
    shared_ports = set(a.domain.box.keys()) & set(b.domain.box.keys())
    shared_ports &= set(a.inputs) | set(b.inputs)
    for port in sorted(shared_ports):
        iv_a = a.domain.box[port]
        iv_b = b.domain.box[port]
        lo = max(iv_a.lo, iv_b.lo)
        hi = min(iv_a.hi, iv_b.hi)
        if lo > hi:
            _log.info(
                "no overlap on shared port %s: [%s,%s] vs [%s,%s]",
                port,
                iv_a.lo,
                iv_a.hi,
                iv_b.lo,
                iv_b.hi,
            )
            return {}
        box[port] = (lo, hi)
    return box


def calibrate(
    solver_id: str,
    reference_id: str,
    registry: "SolverRegistry",
    n_samples: int = 256,
    seed: int = 0,
) -> "Result[CalibRecord, CalibError]":
    """Sweep `solver_id` against `reference_id` over `n_samples`
    deterministic (`random.Random(seed)`) uniform samples of their
    shared-input-port intersection box, and record the worst observed
    absolute/relative error on their shared output port(s). If the
    reference value is exactly zero for a sample, that sample
    contributes only to `worst_abs_error` (rel error is undefined/skipped
    for that sample, documented interpretation of the NORMATIVE
    interface -- see WO-07 report)."""
    solvers = _solver_map(registry)
    if solver_id not in solvers:
        _log.warning("calibrate: unknown solver_id=%s", solver_id)
        return Err(CalibError.UnknownSolver(solver_id=solver_id))
    if reference_id not in solvers:
        _log.warning("calibrate: unknown reference_id=%s", reference_id)
        return Err(CalibError.UnknownSolver(solver_id=reference_id))

    cand_info, cand_fn = solvers[solver_id]
    ref_info, ref_fn = solvers[reference_id]

    shared_outputs = sorted(set(cand_info.outputs) & set(ref_info.outputs))
    if not shared_outputs:
        _log.warning(
            "calibrate: no shared output ports between %s and %s",
            solver_id,
            reference_id,
        )
        return Err(
            CalibError.DomainMismatch(solver_id=solver_id, reference_id=reference_id)
        )

    box = _shared_input_box(cand_info, ref_info)
    if not box:
        _log.warning(
            "calibrate: no overlapping input domain between %s and %s",
            solver_id,
            reference_id,
        )
        return Err(
            CalibError.DomainMismatch(solver_id=solver_id, reference_id=reference_id)
        )

    rng = random.Random(seed)
    ports = sorted(box.keys())

    worst_abs_error = 0.0
    worst_rel_error = 0.0
    n_valid = 0

    for _ in range(n_samples):
        point: Dict[str, float] = {}
        for port in ports:
            lo, hi = box[port]
            point[port] = rng.uniform(lo, hi)

        cand_point = {p: v for p, v in point.items() if p in cand_info.inputs}
        ref_point = {p: v for p, v in point.items() if p in ref_info.inputs}

        cand_result = cand_fn(cand_point)
        ref_result = ref_fn(ref_point)

        if cand_result.is_err or ref_result.is_err:
            _log.debug(
                "calibrate: skipping sample point (candidate_err=%s reference_err=%s)",
                cand_result.is_err,
                ref_result.is_err,
            )
            continue

        cand_out = cand_result.danger_ok
        ref_out = ref_result.danger_ok

        for out_port in shared_outputs:
            if out_port not in cand_out.values or out_port not in ref_out.values:
                continue
            cand_v = cand_out.values[out_port]
            ref_v = ref_out.values[out_port]
            abs_error = abs(cand_v - ref_v)
            worst_abs_error = max(worst_abs_error, abs_error)
            if ref_v != 0.0:
                rel_error = abs_error / abs(ref_v)
                worst_rel_error = max(worst_rel_error, rel_error)
        n_valid += 1

    if n_valid == 0:
        _log.warning(
            "calibrate: zero valid comparison points for %s vs %s (n_samples=%d)",
            solver_id,
            reference_id,
            n_samples,
        )
        return Err(
            CalibError.DomainMismatch(solver_id=solver_id, reference_id=reference_id)
        )

    payload = {
        "solver_id": solver_id,
        "reference_id": reference_id,
        "n_samples": n_samples,
        "seed": seed,
        "worst_abs_error": worst_abs_error,
        "worst_rel_error": worst_rel_error,
    }
    digest = canonical_digest(payload)
    record = CalibRecord(digest=digest, **payload)

    _log.info(
        "calibrate: solver_id=%s reference_id=%s n_samples=%d seed=%d "
        "worst_abs_error=%s worst_rel_error=%s digest=%s",
        solver_id,
        reference_id,
        n_samples,
        seed,
        worst_abs_error,
        worst_rel_error,
        digest,
    )
    return Ok(record)


def _is_derived(info: SolverInfo) -> bool:
    """A direction is DERIVED (11 sec. 1, WO-11) iff `Relation.law()`
    built it -- carried as `SolverInfo.solved_for` (non-`None` only on
    that path, `exclude=True` provenance)."""
    return info.solved_for is not None


def resweep_derived(
    info: SolverInfo,
    fn: SolveFn,
    n_samples: int = 256,
    seed: int = 0,
) -> "Result[CalibRecord, CalibError]":
    """The R5 automatic re-sweep (11 sec. 4, WO-22): for a DERIVED
    direction (`info.solved_for` set by `Relation.law()`, `info.law_lhs`/
    `info.law_rhs` carrying the ORIGINAL declared equation), samples
    `n_samples` deterministic (seeded) points over `info.domain.box`
    (the direction's own -- possibly nonlinearly mapped -- dispatch
    domain) and checks the algebraic identity `lhs == rhs` at each
    sampled point with the derived direction's OWN computed value
    substituted in. This is the "honest floor" the spec calls for: the
    inversion is exact by construction, but floating-point evaluation
    of a nonlinearly-mapped domain corner is not free, so the residual
    IS the calibration evidence (rather than comparing against a
    separate reference solver, which a freshly-derived direction may
    not have one of)."""
    if info.law_lhs is None or info.law_rhs is None:
        _log.warning(
            "resweep_derived: %s has no law_lhs/law_rhs (not a `.law()`-derived "
            "direction); nothing to re-sweep",
            info.solver_id,
        )
        return Err(CalibError.UnknownSolver(solver_id=info.solver_id))

    box = info.domain.box
    ports = sorted(box.keys())
    if not ports:
        _log.warning(
            "resweep_derived: %s has an empty domain box; nothing to sample",
            info.solver_id,
        )
        return Err(
            CalibError.DomainMismatch(
                solver_id=info.solver_id, reference_id=f"{info.solver_id}::law_residual"
            )
        )

    target = info.solved_for
    rng = random.Random(seed)
    worst_abs_error = 0.0
    worst_rel_error = 0.0
    n_valid = 0

    for _ in range(n_samples):
        point: Dict[str, float] = {}
        for port in ports:
            iv = box[port]
            point[port] = rng.uniform(iv.lo, iv.hi)

        cand_inputs = {p: v for p, v in point.items() if p in info.inputs}
        result = fn(cand_inputs)
        if result.is_err:
            _log.debug(
                "resweep_derived: %s skipping sample (solve err=%r)",
                info.solver_id,
                result.err,
            )
            continue
        out = result.danger_ok
        if target not in out.values:
            continue

        full_point = dict(cand_inputs)
        full_point[target] = out.values[target]
        try:
            lhs_v = info.law_lhs.eval(full_point)
            rhs_v = info.law_rhs.eval(full_point)
        except Exception:  # noqa: BLE001 -- eval's own errors are logged, sample skipped
            _log.debug(
                "resweep_derived: %s residual eval failed at %r",
                info.solver_id,
                full_point,
            )
            continue

        residual = abs(lhs_v - rhs_v)
        worst_abs_error = max(worst_abs_error, residual)
        scale = max(abs(lhs_v), abs(rhs_v))
        if scale != 0.0:
            worst_rel_error = max(worst_rel_error, residual / scale)
        n_valid += 1

    if n_valid == 0:
        _log.warning(
            "resweep_derived: %s produced zero valid residual samples (n_samples=%d)",
            info.solver_id,
            n_samples,
        )
        return Err(
            CalibError.DomainMismatch(
                solver_id=info.solver_id, reference_id=f"{info.solver_id}::law_residual"
            )
        )

    payload = {
        "solver_id": info.solver_id,
        "reference_id": f"{info.solver_id}::law_residual",
        "n_samples": n_samples,
        "seed": seed,
        "worst_abs_error": worst_abs_error,
        "worst_rel_error": worst_rel_error,
    }
    digest = canonical_digest(payload)
    record = CalibRecord(digest=digest, **payload)
    _log.info(
        "resweep_derived: solver_id=%s n_samples=%d worst_abs_error=%s "
        "worst_rel_error=%s digest=%s",
        info.solver_id,
        n_samples,
        worst_abs_error,
        worst_rel_error,
        digest,
    )
    return Ok(record)


def resweep_all_derived(
    registry: "SolverRegistry",
    records_dir: Path,
    n_samples: int = 256,
    seed: int = 0,
) -> "Result[List[CalibRecord], CalibError]":
    """Enqueues and runs the R5 automatic re-sweep (11 sec. 4, WO-22) for
    every DERIVED, non-EXACT direction in `registry` (`Accuracy(0,0)`
    laws are exempt, A-7: nothing to measure), writing each resulting
    `CalibRecord` to `records_dir` (AD-9). Iterates in the registry's
    natural sorted order (FINV-1); fails loudly on the first sweep that
    cannot produce evidence (an empty/degenerate domain), matching
    `calibrate`'s and `check_ceilings`'s existing fail-fast contract."""
    records: List[CalibRecord] = []
    for info, fn in registry:
        if not _is_derived(info):
            continue
        non_exact = any(acc != EXACT for acc in info.accuracy.values())
        if not non_exact:
            continue

        result = resweep_derived(info, fn, n_samples=n_samples, seed=seed)
        if result.is_err:
            return result.swap_ok(list)
        record = result.danger_ok
        write_record(records_dir, record)
        records.append(record)

    _log.info(
        "resweep_all_derived: wrote %d re-swept calibration record(s)", len(records)
    )
    return Ok(records)


def check_ceilings(
    registry: "SolverRegistry", records_dir: Path
) -> "Result[None, CalibError]":
    """For every registry solver with any non-EXACT declared output
    accuracy, verify each of its `kind="calibration"` citations
    resolves to a `CalibRecord` file under `records_dir` (its `ref` IS
    the record's digest, AD-9), and that the declared ceiling is no
    tighter than that record's observed worst error. Iterates in the
    registry's natural sorted order (FINV-1) and fails loudly on the
    first violation.

    R5 (11 sec. 4, WO-22): a DERIVED direction (`info.solved_for` set)
    that has not yet had `resweep_all_derived` run for it carries no
    calibration citation at all (`Relation.law()` drops the parent's
    calibration evidence) -- that is reported as UNCALIBRATED (a log
    line, not a blocking `Err`), matching the decided policy: "a
    derived direction whose re-sweep has not run reports its ceiling
    as UNCALIBRATED (honest, blocks nothing at community tier)". A
    hand-written (non-derived) solver missing its record is still the
    pre-existing hard `NoRecord` error -- WO-07's contract is
    unchanged for that path."""
    for info, fn in registry:
        non_exact_ports = [port for port, acc in info.accuracy.items() if acc != EXACT]
        if not non_exact_ports:
            continue

        calib_citations = [c for c in info.citations if c.kind == "calibration"]
        if not calib_citations and _is_derived(info):
            # R5: no inherited calibration evidence (dropped by
            # `Relation.law()` on purpose) -- the automatic re-sweep IS
            # the evidence source for a derived direction, run live
            # here (cheap: the law is closed-form by construction) and
            # checked against the SAME ceiling rule as any other
            # evidence. A re-sweep that cannot even produce evidence
            # (e.g. an empty domain) reports UNCALIBRATED and does not
            # block -- the decided "honest, blocks nothing at
            # community tier" policy.
            resweep = resweep_derived(info, fn)
            if resweep.is_err:
                _log.warning(
                    "check_ceilings: solver_id=%s is UNCALIBRATED (derived "
                    "direction, re-sweep produced no evidence: %r); this does "
                    "not block registration or community-tier use",
                    info.solver_id,
                    resweep.err,
                )
                continue
            record = resweep.danger_ok
            for port in non_exact_ports:
                acc = info.accuracy[port]
                _log.info(
                    "check_ceilings (re-swept): solver_id=%s port=%s "
                    "declared_abs=%s declared_rel=%s observed_abs=%s observed_rel=%s",
                    info.solver_id,
                    port,
                    acc.eps_abs,
                    acc.eps_rel,
                    record.worst_abs_error,
                    record.worst_rel_error,
                )
                if acc.eps_abs < record.worst_abs_error:
                    return Err(
                        CalibError.CeilingBusted(
                            solver_id=info.solver_id,
                            declared=acc.eps_abs,
                            observed=record.worst_abs_error,
                        )
                    )
                if acc.eps_rel < record.worst_rel_error:
                    return Err(
                        CalibError.CeilingBusted(
                            solver_id=info.solver_id,
                            declared=acc.eps_rel,
                            observed=record.worst_rel_error,
                        )
                    )
            continue

        for citation in calib_citations:
            record = read_record(records_dir, citation.ref)
            if record is None:
                _log.error(
                    "check_ceilings: no calib record for %s (citation ref=%s)",
                    info.solver_id,
                    citation.ref,
                )
                return Err(CalibError.NoRecord(solver_id=info.solver_id))

            for port in non_exact_ports:
                acc = info.accuracy[port]
                _log.info(
                    "check_ceilings: solver_id=%s port=%s declared_abs=%s "
                    "declared_rel=%s observed_abs=%s observed_rel=%s",
                    info.solver_id,
                    port,
                    acc.eps_abs,
                    acc.eps_rel,
                    record.worst_abs_error,
                    record.worst_rel_error,
                )
                if acc.eps_abs < record.worst_abs_error:
                    _log.error(
                        "check_ceilings: CeilingBusted solver_id=%s "
                        "declared_abs=%s observed_abs=%s",
                        info.solver_id,
                        acc.eps_abs,
                        record.worst_abs_error,
                    )
                    return Err(
                        CalibError.CeilingBusted(
                            solver_id=info.solver_id,
                            declared=acc.eps_abs,
                            observed=record.worst_abs_error,
                        )
                    )
                if acc.eps_rel < record.worst_rel_error:
                    _log.error(
                        "check_ceilings: CeilingBusted solver_id=%s "
                        "declared_rel=%s observed_rel=%s",
                        info.solver_id,
                        acc.eps_rel,
                        record.worst_rel_error,
                    )
                    return Err(
                        CalibError.CeilingBusted(
                            solver_id=info.solver_id,
                            declared=acc.eps_rel,
                            observed=record.worst_rel_error,
                        )
                    )

    return Ok(None)
