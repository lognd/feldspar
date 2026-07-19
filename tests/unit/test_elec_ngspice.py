from __future__ import annotations

"""WO-17 ngspice-tier unit tests, mocked at the documented subprocess
seam (`feldspar.elec.ngspice.run_ngspice`/`find_ngspice`) -- same
posture as the `fea`/`ccx` precedent. Covers: absent-tool honesty
(`ToolMissing`, no fake pass), deck-text determinism, `results.py`
parsing (happy path + fail-closed), the FINV-2 settings_digest fold
enumeration for both registered directions, and a mocked twice-run
digest-equality check that does not require a real `ngspice` binary."""

from unittest import mock

import pytest
from typani import Ok

from feldspar.core import Interval
from feldspar.elec import deck, ngspice, results
from feldspar.elec.ngspice import NgspiceRun
from feldspar.elec.solver import (
    ToolVersion,
    _fold_divider_settings_digest,
    _fold_rc_step_settings_digest,
)
from feldspar.elec.solver import (
    register as register_elec_ngspice,
)
from feldspar.plan import solve
from feldspar.solve import SolverRegistry

_TOOL_VERSION = ToolVersion(ngspice_version="unknown", feldspar_version="0.1.0")

# ---------------------------------------------------------------------------
# find_ngspice: absent-tool honesty.
# ---------------------------------------------------------------------------


def test_find_ngspice_missing_returns_tool_missing(monkeypatch):
    monkeypatch.delenv("FELDSPAR_NGSPICE", raising=False)
    with mock.patch("shutil.which", return_value=None):
        result = ngspice.find_ngspice()
    assert result.is_err
    assert result.err.kind == "ToolMissing"
    assert result.err.tool == "ngspice"


def test_find_ngspice_env_var_must_be_executable(monkeypatch, tmp_path):
    non_executable = tmp_path / "not_ngspice"
    non_executable.write_text("not a real binary")
    monkeypatch.setenv("FELDSPAR_NGSPICE", str(non_executable))
    with mock.patch("shutil.which", return_value=None):
        result = ngspice.find_ngspice()
    assert result.is_err
    assert result.err.kind == "ToolMissing"


def test_find_ngspice_env_var_wins_over_path(monkeypatch, tmp_path):
    fake = tmp_path / "ngspice"
    fake.write_text("#!/bin/sh\necho fake\n")
    fake.chmod(0o755)
    monkeypatch.setenv("FELDSPAR_NGSPICE", str(fake))
    result = ngspice.find_ngspice()
    assert result.is_ok
    assert str(result.danger_ok) == str(fake)


def test_probe_tools_missing_is_tool_missing(monkeypatch):
    monkeypatch.delenv("FELDSPAR_NGSPICE", raising=False)
    with mock.patch("shutil.which", return_value=None):
        result = ngspice.probe_tools()
    assert result.is_err
    assert result.err.kind == "ToolMissing"


# ---------------------------------------------------------------------------
# deck.py: pure text, deterministic.
# ---------------------------------------------------------------------------


# frob:tests python/feldspar/elec/deck.py::build_divider_deck kind="unit"
def test_divider_deck_is_deterministic():
    first = deck.build_divider_deck(10.0, 10e3, 10e3, 100e3)
    second = deck.build_divider_deck(10.0, 10e3, 10e3, 100e3)
    assert first == second
    assert "op" in first
    assert "print v(out)" in first


# frob:tests python/feldspar/elec/deck.py::build_rc_step_deck kind="unit"
def test_rc_step_deck_is_deterministic():
    first = deck.build_rc_step_deck(5.0, 1000.0, 1e-6, 1e-3, 5e-6)
    second = deck.build_rc_step_deck(5.0, 1000.0, 1e-6, 1e-3, 5e-6)
    assert first == second
    assert "tran" in first


# ---------------------------------------------------------------------------
# results.py: parse happy path + fail-closed.
# ---------------------------------------------------------------------------


def test_parse_print_value_happy_path():
    result = results.parse_print_value("v(out) = 4.761905e+00\n", "v(out)")
    assert result.is_ok
    assert result.danger_ok == pytest.approx(4.761905)


def test_parse_print_value_case_insensitive_name():
    result = results.parse_print_value("V(OUT) = 1.0\n", "v(out)")
    assert result.is_ok
    assert result.danger_ok == pytest.approx(1.0)


def test_parse_print_value_missing_line_fails_closed():
    result = results.parse_print_value("nothing useful here\n", "v(out)")
    assert result.is_err
    assert result.err.kind == "ParseFailed"


# frob:tests python/feldspar/solve/digest.py::settings_digest kind="unit"
def test_parse_print_value_malformed_value_fails_closed():
    result = results.parse_print_value("v(out) = notafloat\n", "v(out)")
    assert result.is_err
    assert result.err.kind == "ParseFailed"


# ---------------------------------------------------------------------------
# FINV-2: settings_digest fold enumerates every field.
# ---------------------------------------------------------------------------


def test_divider_fold_changes_when_analysis_changes():
    base = _fold_divider_settings_digest("op", _TOOL_VERSION)
    other = _fold_divider_settings_digest("dc", _TOOL_VERSION)
    assert base != other


def test_divider_fold_changes_when_tool_version_changes():
    base = _fold_divider_settings_digest("op", _TOOL_VERSION)
    other = _fold_divider_settings_digest(
        "op", ToolVersion(ngspice_version="42.0", feldspar_version="0.1.0")
    )
    assert base != other


def test_rc_step_fold_changes_when_analysis_changes():
    base = _fold_rc_step_settings_digest("tran", 200.0, _TOOL_VERSION)
    other = _fold_rc_step_settings_digest("dc", 200.0, _TOOL_VERSION)
    assert base != other


def test_rc_step_fold_changes_when_coarse_divisor_changes():
    base = _fold_rc_step_settings_digest("tran", 200.0, _TOOL_VERSION)
    other = _fold_rc_step_settings_digest("tran", 400.0, _TOOL_VERSION)
    assert base != other


def test_rc_step_fold_changes_when_tool_version_changes():
    base = _fold_rc_step_settings_digest("tran", 200.0, _TOOL_VERSION)
    other = _fold_rc_step_settings_digest(
        "tran", 200.0, ToolVersion(ngspice_version="42.0", feldspar_version="0.1.0")
    )
    assert base != other


# ---------------------------------------------------------------------------
# Everything imports and returns ToolMissing without a real ngspice
# (WO-17 acceptance: "without ngspice installed everything imports and
# returns ToolMissing values").
# ---------------------------------------------------------------------------


def _registry() -> SolverRegistry:
    registry = SolverRegistry()
    register_elec_ngspice(registry)
    registry.freeze()
    return registry


def test_divider_direction_returns_tool_missing_without_ngspice(monkeypatch):
    monkeypatch.delenv("FELDSPAR_NGSPICE", raising=False)
    with mock.patch("shutil.which", return_value=None):
        result = solve(
            _registry(),
            known={
                "elec.source.vin": Interval(10.0, 10.0),
                "elec.divider.r1": Interval(10e3, 10e3),
                "elec.divider.r2": Interval(10e3, 10e3),
                "elec.divider.rl": Interval(100e3, 100e3),
            },
            tags={"linear", "small_signal"},
            target="elec.divider.vout",
            eps_budget=1e10,
        )
    assert result.is_err


# ---------------------------------------------------------------------------
# Mocked twice-run digest equality (no real ngspice needed: mocks the
# subprocess seam with a deterministic canned response so this runs in
# every environment, complementing the real spice-marked equivalent in
# tests/integration/test_elec_ngspice.py).
# ---------------------------------------------------------------------------


# frob:tests python/feldspar/elec/ngspice.py::run_ngspice kind="unit"
def test_divider_solve_digest_is_deterministic_across_two_runs_mocked():
    canned = Ok(
        NgspiceRun(
            log_text="v(out) = 4.761905e+00\n",
            elapsed_s=0.01,
            tool_version="ngspice-42",
        )
    )
    known = {
        "elec.source.vin": Interval(10.0, 10.0),
        "elec.divider.r1": Interval(10e3, 10e3),
        "elec.divider.r2": Interval(10e3, 10e3),
        "elec.divider.rl": Interval(100e3, 100e3),
    }
    with mock.patch("feldspar.elec.ngspice.run_ngspice", return_value=canned):
        first = solve(
            _registry(),
            known=known,
            tags={"linear", "small_signal"},
            target="elec.divider.vout",
            eps_budget=1e10,
        ).danger_ok
        second = solve(
            _registry(),
            known=known,
            tags={"linear", "small_signal"},
            target="elec.divider.vout",
            eps_budget=1e10,
        ).danger_ok

    assert first.settings_digest == second.settings_digest
    assert first.value.lo == pytest.approx(second.value.lo)
