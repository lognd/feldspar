from __future__ import annotations

"""find_ngspice() and run_ngspice(): the external ngspice binary
boundary (WO-17), mirroring `feldspar.fea.ccx`'s shape exactly.

Every invocation writes the deck to a throwaway `tempfile.
TemporaryDirectory` and runs ngspice in batch mode (`-b`); stdout is
captured into memory before the tempdir is torn down, matching
`CcxRun.dat_text`'s "contents, not paths" convention. Version pin
recommendation (lithos benchmark memo sec. 4): ngspice 42 (2024
release) or newer; `tool_version` below is a best-effort scrape of
`ngspice --version`, advisory only, never used for behavior
decisions."""

import os
import shutil
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel, ConfigDict
from typani import Err, Ok
from typani.result import Result

from feldspar.logging_setup import get_logger
from feldspar.solve.errors import SolveError

__all__ = ["NgspiceRun", "find_ngspice", "run_ngspice", "probe_tools"]

_log = get_logger(__name__)

_LOG_TAIL_LINES = 20


# frob:doc docs/modules/elec.md#elec_ngspice
class NgspiceRun(BaseModel):
    """A completed ngspice batch run: the captured stdout+stderr TEXT
    (not a path -- the tempdir it was written under is gone by the
    time this is returned), wall time, and a best-effort tool version
    string."""

    model_config = ConfigDict(frozen=True)

    log_text: str
    elapsed_s: float
    tool_version: str


# The real kill-switch (T-0016, LINT004), mirroring `feldspar.fea.ccx`'s
# `_DISABLE_CCX_VAR` shape exactly: checked BEFORE any resolution
# attempt, so setting it disables subprocess spawning outright -- unlike
# pointing `FELDSPAR_NGSPICE` at a bogus path (which just falls through
# to a normal `ToolMissing`), this refuses even when a real `ngspice`
# sits on `PATH`. Any non-empty value other than "0"/"false"
# (case-insensitive) counts as set.
_DISABLE_NGSPICE_VAR = "FELDSPAR_DISABLE_NGSPICE"


def _exec_disabled() -> bool:
    """Reads `FELDSPAR_DISABLE_NGSPICE`; truthy values are any non-empty
    string except "0"/"false" (case-insensitive)."""
    raw = os.environ.get(_DISABLE_NGSPICE_VAR, "")
    return raw.strip().lower() not in ("", "0", "false")


# frob:doc docs/modules/elec.md#elec_ngspice
# frob:waive TEST005 reason="measured 47.8% branch on 2026-07-19; kill-switch + PATH-probe branches partly env-gated (real ngspice absent in CI); backfill T-0014"
def find_ngspice() -> Result[Path, SolveError]:
    """Locates the `ngspice` executable: `FELDSPAR_DISABLE_NGSPICE`
    kill-switch first (T-0016 -- if set, refuses immediately with
    `ToolMissing` without even attempting resolution), then
    `FELDSPAR_NGSPICE` env var (must point at an existing executable
    file), then `PATH` via `shutil.which`. `Err(SolveError.ToolMissing(...))`
    if the kill-switch is set or neither resolves -- never raises, so
    callers can degrade gracefully when ngspice is disabled or not
    installed."""
    if _exec_disabled():
        _log.warning(
            "find_ngspice: refusing, %s is set (exec kill-switch active)",
            _DISABLE_NGSPICE_VAR,
        )
        return Err(
            SolveError.ToolMissing(
                tool="ngspice",
                guidance=f"{_DISABLE_NGSPICE_VAR} is set -- unset it to allow ngspice exec",
            )
        )

    env_path = os.environ.get("FELDSPAR_NGSPICE")
    if env_path:
        candidate = Path(env_path)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            _log.info("find_ngspice: using FELDSPAR_NGSPICE=%s", candidate)
            return Ok(candidate)
        _log.warning(
            "find_ngspice: FELDSPAR_NGSPICE=%s does not point at an executable file",
            env_path,
        )

    which_path = shutil.which("ngspice")
    if which_path:
        _log.info("find_ngspice: found ngspice on PATH at %s", which_path)
        return Ok(Path(which_path))

    _log.warning("find_ngspice: ngspice not found via FELDSPAR_NGSPICE or PATH")
    return Err(
        SolveError.ToolMissing(
            tool="ngspice",
            guidance="install ngspice (42+ recommended), or set FELDSPAR_NGSPICE",
        )
    )


def _parse_tool_version(output: str) -> str:
    """Best-effort scrape of a version-looking token from ngspice's
    banner output; advisory only, never used for behavior decisions."""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("ngspice-"):
            return stripped
    return "unknown"


# frob:waive TEST005 reason="measured 12.5% branch cov on 2026-07-18; the external ngspice binary boundary (T-0014's documented external-tool floor, not installed in this sandbox). Backfill T-0014."
# frob:doc docs/modules/elec.md#elec_ngspice
def run_ngspice(deck: str, timeout_s: float) -> Result[NgspiceRun, SolveError]:
    """Writes `deck` to `job.cir` in a throwaway tempdir, runs
    `ngspice -b job.cir` (batch mode, no interactive prompt), and
    captures stdout+stderr into memory before the tempdir is torn
    down. Never raises: timeouts and nonzero exit codes are reported
    as `SolveError` values."""
    found = find_ngspice()
    if found.is_err:
        return Err(found.danger_err)
    ngspice_path = found.danger_ok

    with TemporaryDirectory(prefix="feldspar-ngspice-") as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        cir_path = tmpdir / "job.cir"
        cir_path.write_text(deck)
        _log.info("run_ngspice: wrote deck to %s (%d bytes)", cir_path, len(deck))

        start = time.monotonic()
        try:
            completed = subprocess.run(
                [str(ngspice_path), "-b", "job.cir"],
                cwd=str(tmpdir),
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            _log.warning(
                "run_ngspice: ngspice exceeded timeout_s=%s, tool=%s",
                timeout_s,
                ngspice_path,
            )
            return Err(SolveError.Timeout(tool="ngspice", seconds=timeout_s))
        elapsed_s = time.monotonic() - start

        combined_output = (completed.stdout or "") + (completed.stderr or "")
        for line in (completed.stderr or "").splitlines():
            if line.strip():
                _log.warning("ngspice stderr: %s", line)
        for line in (completed.stdout or "").splitlines():
            if line.strip():
                _log.info("ngspice stdout: %s", line)

        if completed.returncode != 0:
            tail_lines = combined_output.splitlines()[-_LOG_TAIL_LINES:]
            log_tail = "\n".join(tail_lines)
            _log.warning(
                "run_ngspice: ngspice exited with code %d, tool=%s",
                completed.returncode,
                ngspice_path,
            )
            return Err(SolveError.ToolFailed(tool="ngspice", log_tail=log_tail))

        tool_version = _parse_tool_version(combined_output)
        _log.info(
            "run_ngspice: completed in %.3fs, tool_version=%s, output=%d bytes",
            elapsed_s,
            tool_version,
            len(combined_output),
        )

        return Ok(
            NgspiceRun(
                log_text=combined_output,
                elapsed_s=elapsed_s,
                tool_version=tool_version,
            )
        )


# frob:doc docs/modules/elec.md#elec_ngspice
def probe_tools() -> Result[None, SolveError]:
    """Thin `find_ngspice()` wrapper dropping the `Ok` payload -- the
    `probe_tools` convention `plan/cache.py`'s `_tools_still_consistent`
    looks for via `getattr(fn, "probe_tools", None)` on a registered
    `SolveFn` (same convention `feldspar.fea.ccx.probe_tools` uses)."""
    return find_ngspice() | (lambda _path: None)
