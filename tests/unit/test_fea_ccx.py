from __future__ import annotations

"""Direct unit tests for `feldspar.fea.ccx.find_ccx`/`run_ccx` (the
external CalculiX binary boundary, WO-08) -- a fake `ccx` shell script
stands in for the real tool via `FELDSPAR_CCX`, so these run without
requiring CalculiX installed, same shape as the ngspice/tool-boundary
tests elsewhere in this suite."""

import stat

from feldspar.fea import ccx


def _make_fake_ccx(tmp_path, script: str):
    path = tmp_path / "fake_ccx.sh"
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


# frob:tests python/feldspar/fea/ccx.py::find_ccx kind="unit"
def test_find_ccx_uses_feldspar_ccx_env_var_when_set(tmp_path, monkeypatch) -> None:
    """`FELDSPAR_CCX` pointing at an existing executable file wins over
    (and is checked before) any `PATH` lookup."""
    fake = _make_fake_ccx(tmp_path, "#!/bin/sh\nexit 0\n")
    monkeypatch.setenv("FELDSPAR_CCX", str(fake))
    result = ccx.find_ccx()
    assert result.is_ok
    assert result.danger_ok == fake


# frob:tests python/feldspar/fea/ccx.py::find_ccx kind="unit"
def test_find_ccx_reports_tool_missing_when_unresolvable(tmp_path, monkeypatch) -> None:
    """Neither `FELDSPAR_CCX` nor `PATH` resolves: honest
    `SolveError.ToolMissing`, never a raise."""
    monkeypatch.delenv("FELDSPAR_CCX", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))  # empty dir, ccx not on it
    result = ccx.find_ccx()
    assert result.is_err
    assert result.danger_err.kind == "ToolMissing"
    assert result.danger_err.tool == "ccx"


# frob:tests python/feldspar/fea/ccx.py::run_ccx kind="unit"
def test_run_ccx_reads_dat_and_frd_text_on_success(tmp_path, monkeypatch) -> None:
    """A successful run writes `job.dat`/`job.frd` next to `job.inp`
    (ccx's own jobname convention) -- `run_ccx` must read both contents
    into memory before its throwaway tempdir is torn down."""
    fake = _make_fake_ccx(
        tmp_path,
        "#!/bin/sh\n"
        "echo 'VERSION 2.20' \n"
        "echo 'dat contents' > job.dat\n"
        "echo 'frd contents' > job.frd\n"
        "exit 0\n",
    )
    monkeypatch.setenv("FELDSPAR_CCX", str(fake))
    result = ccx.run_ccx("*NODE\n1,0,0,0\n", timeout_s=10.0)
    assert result.is_ok
    run = result.danger_ok
    assert run.dat_text.strip() == "dat contents"
    assert run.frd_text is not None and run.frd_text.strip() == "frd contents"
    assert run.tool_version == "VERSION 2.20"


# frob:tests python/feldspar/fea/ccx.py::run_ccx kind="unit"
def test_run_ccx_reports_tool_failed_on_nonzero_exit(tmp_path, monkeypatch) -> None:
    """A nonzero ccx exit code maps to `SolveError.ToolFailed`, never a
    raise, with the tail of combined stdout/stderr attached."""
    fake = _make_fake_ccx(tmp_path, "#!/bin/sh\necho 'boom' >&2\nexit 1\n")
    monkeypatch.setenv("FELDSPAR_CCX", str(fake))
    result = ccx.run_ccx("*NODE\n1,0,0,0\n", timeout_s=10.0)
    assert result.is_err
    assert result.danger_err.kind == "ToolFailed"
    assert "boom" in result.danger_err.log_tail


# frob:tests python/feldspar/fea/ccx.py::find_ccx kind="unit"
def test_find_ccx_refuses_when_disable_var_set_even_with_real_binary(
    tmp_path, monkeypatch
) -> None:
    """T-0016: `FELDSPAR_DISABLE_CCX` is a REAL kill-switch -- it refuses
    exec even when `FELDSPAR_CCX` points at a perfectly resolvable
    binary, unlike pointing `FELDSPAR_CCX` at a bogus path (which merely
    falls through to a not-found `ToolMissing`)."""
    fake = _make_fake_ccx(tmp_path, "#!/bin/sh\nexit 0\n")
    monkeypatch.setenv("FELDSPAR_CCX", str(fake))
    monkeypatch.setenv("FELDSPAR_DISABLE_CCX", "1")
    result = ccx.find_ccx()
    assert result.is_err
    assert result.danger_err.kind == "ToolMissing"
    assert result.danger_err.tool == "ccx"
    assert "FELDSPAR_DISABLE_CCX" in result.danger_err.guidance


# frob:tests python/feldspar/fea/ccx.py::find_ccx kind="unit"
def test_find_ccx_treats_false_and_empty_disable_var_as_unset(
    tmp_path, monkeypatch
) -> None:
    """`FELDSPAR_DISABLE_CCX=0`/`"false"`/unset all resolve normally --
    only a genuinely truthy value trips the kill-switch."""
    fake = _make_fake_ccx(tmp_path, "#!/bin/sh\nexit 0\n")
    monkeypatch.setenv("FELDSPAR_CCX", str(fake))
    for falsy in ("0", "false", "False", ""):
        monkeypatch.setenv("FELDSPAR_DISABLE_CCX", falsy)
        result = ccx.find_ccx()
        assert result.is_ok, f"expected ok for FELDSPAR_DISABLE_CCX={falsy!r}"
        assert result.danger_ok == fake
    monkeypatch.delenv("FELDSPAR_DISABLE_CCX", raising=False)
    result = ccx.find_ccx()
    assert result.is_ok
