from __future__ import annotations

"""WO-07 tests: calibration harness (calibrate/check_ceilings/CalibRecord).

Uses two locally-defined trivial solvers so the harness is exercised
against the registry protocol generically, not against the not-yet-
landed mech solvers (WO-07 mission scope)."""

from pathlib import Path

from typani import Ok

from feldspar.calib import CalibError, calibrate, check_ceilings
from feldspar.calib.store import write_record
from feldspar.core import Accuracy, Domain, Interval
from feldspar.solve import EXACT, Citation, SolverInfo, SolverRegistry


def _domain(lo: float, hi: float) -> Domain:
    return Domain(box={"x": Interval(lo, hi)})


def _make_info(
    solver_id: str,
    *,
    domain: Domain,
    accuracy: "Accuracy | None" = None,
    citations: tuple = (),
) -> SolverInfo:
    acc = accuracy if accuracy is not None else EXACT
    return SolverInfo(
        solver_id=solver_id,
        namespace="test",
        version="1",
        inputs=("x",),
        outputs=("y",),
        domain=domain,
        cost=1.0,
        accuracy={"y": acc},
        citations=citations or (Citation(kind="handbook", ref="test ref"),),
        tier="closed_form",
        settings_digest="none",
    )


def _exact_solver(registry: SolverRegistry) -> None:
    def fn(inputs):
        return Ok(_output(2.0 * inputs["x"]))

    info = _make_info("test.exact", domain=_domain(0.0, 10.0))
    assert registry.register(info, fn).is_ok


def _noisy_solver(registry: SolverRegistry, *, citations: tuple = ()) -> None:
    def fn(inputs):
        return Ok(_output(2.0 * inputs["x"] + 0.001))

    info = _make_info(
        "test.noisy",
        domain=_domain(0.0, 10.0),
        accuracy=Accuracy(0.01, 0.01),
        citations=citations,
    )
    assert registry.register(info, fn).is_ok


def _output(y: float):
    from feldspar.solve import SolveOutput

    return SolveOutput(values={"y": y})


def _build_registry(*, noisy_citations: tuple = ()) -> SolverRegistry:
    registry = SolverRegistry()
    _exact_solver(registry)
    _noisy_solver(registry, citations=noisy_citations)
    registry.freeze()
    return registry


def test_calibrate_happy_path() -> None:
    registry = _build_registry()
    result = calibrate("test.noisy", "test.exact", registry, n_samples=64, seed=0)
    assert result.is_ok
    record = result.danger_ok
    assert record.solver_id == "test.noisy"
    assert record.reference_id == "test.exact"
    assert record.n_samples == 64
    assert record.seed == 0
    assert 0.0 < record.worst_abs_error < 0.01
    assert record.worst_rel_error > 0.0
    assert record.digest


def test_calibrate_deterministic_digest() -> None:
    registry = _build_registry()
    r1 = calibrate("test.noisy", "test.exact", registry, n_samples=32, seed=7)
    r2 = calibrate("test.noisy", "test.exact", registry, n_samples=32, seed=7)
    assert r1.is_ok and r2.is_ok
    assert r1.danger_ok.digest == r2.danger_ok.digest


def test_calibrate_unknown_solver() -> None:
    registry = _build_registry()
    result = calibrate("test.missing", "test.exact", registry)
    assert result.is_err
    err = result.danger_err
    assert err.kind == "UnknownSolver"
    assert err.solver_id == "test.missing"


def test_calibrate_unknown_reference() -> None:
    registry = _build_registry()
    result = calibrate("test.noisy", "test.missing", registry)
    assert result.is_err
    assert result.danger_err == CalibError.UnknownSolver(solver_id="test.missing")


def test_calibrate_domain_mismatch() -> None:
    registry = SolverRegistry()

    def fn_a(inputs):
        return Ok(_output(2.0 * inputs["x"]))

    def fn_b(inputs):
        return Ok(_output(3.0 * inputs["x"]))

    info_a = _make_info("test.a", domain=_domain(0.0, 1.0))
    info_b = _make_info("test.b", domain=_domain(5.0, 6.0))
    assert registry.register(info_a, fn_a).is_ok
    assert registry.register(info_b, fn_b).is_ok
    registry.freeze()

    result = calibrate("test.b", "test.a", registry)
    assert result.is_err
    assert result.danger_err.kind == "DomainMismatch"


# frob:tests python/feldspar/calib/store.py::write_record kind="unit"
# frob:tests python/feldspar/calib/store.py::record_path kind="unit"
def test_check_ceilings_happy_path(tmp_path: Path) -> None:
    records_dir = tmp_path / "records"
    registry = _build_registry()
    calib_result = calibrate("test.noisy", "test.exact", registry, n_samples=64, seed=0)
    assert calib_result.is_ok
    record = calib_result.danger_ok
    write_record(records_dir, record)

    registry2 = SolverRegistry()
    _exact_solver(registry2)

    def fn(inputs):
        return Ok(_output(2.0 * inputs["x"] + 0.001))

    loose_info = _make_info(
        "test.noisy",
        domain=_domain(0.0, 10.0),
        accuracy=Accuracy(0.5, 0.5),
        citations=(
            Citation(kind="handbook", ref="test ref"),
            Citation(kind="calibration", ref=record.digest),
        ),
    )
    assert registry2.register(loose_info, fn).is_ok
    registry2.freeze()

    result = check_ceilings(registry2, records_dir)
    assert result.is_ok


# frob:tests python/feldspar/calib/errors.py::CalibError.CeilingBusted kind="unit"
def test_check_ceilings_busted(tmp_path: Path) -> None:
    records_dir = tmp_path / "records"
    registry = _build_registry()
    calib_result = calibrate("test.noisy", "test.exact", registry, n_samples=64, seed=0)
    assert calib_result.is_ok
    record = calib_result.danger_ok
    write_record(records_dir, record)

    registry2 = SolverRegistry()
    _exact_solver(registry2)

    def fn(inputs):
        return Ok(_output(2.0 * inputs["x"] + 0.001))

    tight_info = _make_info(
        "test.noisy",
        domain=_domain(0.0, 10.0),
        accuracy=Accuracy(1e-9, 1e-9),
        citations=(
            Citation(kind="handbook", ref="test ref"),
            Citation(kind="calibration", ref=record.digest),
        ),
    )
    assert registry2.register(tight_info, fn).is_ok
    registry2.freeze()

    result = check_ceilings(registry2, records_dir)
    assert result.is_err
    err = result.danger_err
    assert err.kind == "CeilingBusted"
    assert err.solver_id == "test.noisy"
    assert err.declared == 1e-9
    assert err.observed == record.worst_abs_error


def test_check_ceilings_no_record(tmp_path: Path) -> None:
    records_dir = tmp_path / "records"
    registry = SolverRegistry()
    _exact_solver(registry)
    _noisy_solver(
        registry,
        citations=(
            Citation(kind="handbook", ref="test ref"),
            Citation(kind="calibration", ref="deadbeef"),
        ),
    )
    registry.freeze()

    result = check_ceilings(registry, records_dir)
    assert result.is_err
    assert result.danger_err == CalibError.NoRecord(solver_id="test.noisy")
