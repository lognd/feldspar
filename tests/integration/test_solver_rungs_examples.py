from __future__ import annotations

"""Integration coverage for `examples/solvers/*.py` (the DX complexity-
rung ladder, see each rung's own module docstring and `examples/
solvers/README.md`). Each rung module defines `register(registry)`
against the real `feldspar.solve.SolverRegistry`/`@solver` decorator
protocol; importing the module AND calling `register` against a fresh
registry exercises the full path from decoration to a populated,
frozen-ready registry -- a real cross-module integration of the
example's public surface with `feldspar.solve`, not a syntax check."""

import importlib.util
import sys
from pathlib import Path

import pytest

from feldspar.solve import SolverRegistry

_SOLVERS_DIR = Path(__file__).resolve().parents[2] / "examples" / "solvers"

_RUNGS = [
    "00_raw_protocol",
    "01_sugar_coercions",
    "02_relations",
    "03_tables_correlations",
    "04_families",
    "05_expensive_and_abstraction",
    "06_coupled_groups",
]


def _load_rung(name: str):
    """Import a rung module from `examples/solvers/` by file path (that
    directory is not a package on `sys.path`)."""
    path = _SOLVERS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"rung_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# 05's `payload_domain=` kwarg is F17 (OPEN, M2 per README): a documented
# sketch of a not-yet-real declaration form, not a runnable direction --
# it is exercised as an import-only smoke check instead of a full
# register()+freeze() round trip.
_EXECUTABLE_RUNGS = [r for r in _RUNGS if r != "05_expensive_and_abstraction"]


def _assert_rung_registers(rung: str) -> None:
    """Shared body: `register()` populates a real `SolverRegistry`
    without error and the frozen registry produces a digest."""
    module = _load_rung(rung)
    registry = SolverRegistry()
    module.register(registry)
    registry.freeze()
    assert registry.is_frozen()
    assert registry.digest()


@pytest.mark.parametrize("rung", _EXECUTABLE_RUNGS)
def test_rung_registers_into_a_fresh_registry(rung: str) -> None:
    """Every complexity-rung example decorates at least one solver whose
    `register()` populates a real `SolverRegistry` without error."""
    _assert_rung_registers(rung)


# frob:tests examples/solvers/00_raw_protocol.py kind="integration"
def test_rung_00_raw_protocol_registers() -> None:
    """Binding anchor for rung 00 (body shared with the parametrized
    check above)."""
    _assert_rung_registers("00_raw_protocol")


# frob:tests examples/solvers/01_sugar_coercions.py kind="integration"
def test_rung_01_sugar_coercions_registers() -> None:
    """Binding anchor for rung 01."""
    _assert_rung_registers("01_sugar_coercions")


# frob:tests examples/solvers/02_relations.py kind="integration"
def test_rung_02_relations_registers() -> None:
    """Binding anchor for rung 02."""
    _assert_rung_registers("02_relations")


# frob:tests examples/solvers/03_tables_correlations.py kind="integration"
def test_rung_03_tables_correlations_registers() -> None:
    """Binding anchor for rung 03."""
    _assert_rung_registers("03_tables_correlations")


# frob:tests examples/solvers/04_families.py kind="integration"
def test_rung_04_families_registers() -> None:
    """Binding anchor for rung 04."""
    _assert_rung_registers("04_families")


# frob:tests examples/solvers/06_coupled_groups.py kind="integration"
def test_rung_06_coupled_groups_registers() -> None:
    """Binding anchor for rung 06."""
    _assert_rung_registers("06_coupled_groups")


# frob:tests examples/solvers/05_expensive_and_abstraction.py kind="integration"
# frob:tests examples/solvers/05_expensive_and_abstraction.py::flange_as_cantilever kind="unit"
def test_rung_05_second_solver_is_honestly_not_yet_registrable() -> None:
    """05's `flange_as_cantilever` abstraction-edge solver is explicitly
    "not registrable in M1" (its own comment; F17, README OPEN/M2): the
    `payload_domain=` kwarg is a sketch of a declaration form the real
    decorator does not accept yet. Importing the module must fail with
    exactly that `TypeError` -- not silently succeed (which would mean
    F17 shipped without this example, or this test, being updated) and
    not fail for some unrelated reason."""
    with pytest.raises(TypeError, match="payload_domain"):
        _load_rung("05_expensive_and_abstraction")
