from __future__ import annotations

"""Regression net for `examples/`: each target-API sketch is run as a
real subprocess and asserted to exit 0, so an API-drift break (like the
one this test file was added to catch, WO-mission "examples broken from
API drift") can never silently sit unrun again. 01/02 are plain closed-
form solves; 03 degrades gracefully without `gmsh` (asserted below, not
`fea`-marked, since it never needs to crash to prove the point); 04
needs a local lithos checkout with `regolith` installed, so it is
`regolith`-marked like the rest of `tests/regolith/`."""

import subprocess
import sys
from pathlib import Path

import pytest

_EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _run_example(name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_EXAMPLES_DIR / name)],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_01_register_and_solve_runs() -> None:
    """Minimal register/freeze/solve/explain happy path exits clean."""
    result = _run_example("01_register_and_solve.py")
    assert result.returncode == 0, result.stderr
    assert "explain" not in result.stderr  # no traceback leaked to stderr


def test_02_tier_competition_runs() -> None:
    """Loose budget picks the cheap chart tier, tight budget forces the
    exact closed form -- both routing outcomes exercised in one run."""
    result = _run_example("02_tier_competition.py")
    assert result.returncode == 0, result.stderr
    assert "loose budget picks: mech.lame_chart.chart" in result.stdout
    assert "tight budget picks: mech.lame_exact.exact" in result.stdout


def test_03_fea_cantilever_runs() -> None:
    """Runs to completion even without `gmsh`: either a real FEA solve
    (host has the `mesh` extra + gmsh) or the honest ToolMissing
    degrade-gracefully message -- never a crash."""
    result = _run_example("03_fea_cantilever.py")
    assert result.returncode == 0, result.stderr
    assert "Solution for target" in result.stdout or "needs 'gmsh'" in result.stdout


@pytest.mark.regolith
def test_04_pack_discharge_runs() -> None:
    """The regolith host-side seam: feldspar's pack loads through the
    real entry point and produces a (possibly indeterminate) Evidence
    without crashing."""
    result = _run_example("04_pack_discharge.py")
    assert result.returncode == 0, result.stderr
    assert "packs loaded: ['feldspar']" in result.stdout
    assert "status=" in result.stdout
