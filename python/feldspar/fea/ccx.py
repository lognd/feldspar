from __future__ import annotations

"""find_ccx() and run_ccx(): the external CalculiX binary boundary (01). WO-08.

Every ccx invocation is isolated in a throwaway `tempfile.TemporaryDirectory`
so repeated solves never collide or leak job files; the `.dat`/`.frd`
contents are read into memory before the tempdir is torn down (their fields
are named `dat_text`/`frd_text`, not paths, precisely so callers never hold a
path that outlives the directory)."""

import os
import shutil
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from pydantic import BaseModel, ConfigDict
from typani import Err, Ok
from typani.result import Result

from feldspar.logging import get_logger
from feldspar.solve.errors import SolveError

__all__ = ["CcxRun", "find_ccx", "run_ccx", "probe_tools"]

_log = get_logger(__name__)

_LOG_TAIL_LINES = 20


class CcxRun(BaseModel):
    """A completed CalculiX run: the `.dat`/`.frd` output CONTENTS (not
    paths -- the tempdir they were written under is gone by the time this
    is returned), wall time, and a best-effort tool version string."""

    model_config = ConfigDict(frozen=True)

    dat_text: str
    frd_text: Optional[str]
    elapsed_s: float
    tool_version: str


def find_ccx() -> Result[Path, SolveError]:
    """Locates the `ccx` executable: `FELDSPAR_CCX` env var first (must
    point at an existing executable file), then `PATH` via `shutil.which`.
    `Err(SolveError.ToolMissing(...))` if neither resolves -- never raises,
    so callers can degrade gracefully when CalculiX is not installed."""
    env_path = os.environ.get("FELDSPAR_CCX")
    if env_path:
        candidate = Path(env_path)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            _log.info("find_ccx: using FELDSPAR_CCX=%s", candidate)
            return Ok(candidate)
        _log.warning(
            "find_ccx: FELDSPAR_CCX=%s does not point at an executable file",
            env_path,
        )

    which_path = shutil.which("ccx")
    if which_path:
        _log.info("find_ccx: found ccx on PATH at %s", which_path)
        return Ok(Path(which_path))

    _log.warning("find_ccx: ccx not found via FELDSPAR_CCX or PATH")
    return Err(
        SolveError.ToolMissing(
            tool="ccx",
            guidance="install CalculiX (ccx), or set FELDSPAR_CCX",
        )
    )


def _parse_tool_version(output: str) -> str:
    """Best-effort scrape of a version-looking token from ccx's banner
    output; ccx has no stable `--version` contract, so this is advisory
    only, never used for behavior decisions."""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("VERSION"):
            return stripped
    return "unknown"


def run_ccx(deck: str, timeout_s: float) -> Result[CcxRun, SolveError]:
    """Writes `deck` to `job.inp` in a throwaway tempdir, runs
    `ccx -i job` (ccx's own convention: jobname without extension) with
    `OMP_NUM_THREADS=1` (determinism -- thread count changes float
    summation order), and reads the resulting `.dat`/`.frd` contents into
    memory before the tempdir is torn down. Never raises: timeouts and
    nonzero exit codes are reported as `SolveError` values."""
    found = find_ccx()
    if found.is_err:
        return Err(found.danger_err)
    ccx_path = found.danger_ok

    with TemporaryDirectory(prefix="feldspar-ccx-") as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        inp_path = tmpdir / "job.inp"
        inp_path.write_text(deck)
        _log.info("run_ccx: wrote deck to %s (%d bytes)", inp_path, len(deck))

        run_env = dict(os.environ)
        run_env["OMP_NUM_THREADS"] = "1"

        start = time.monotonic()
        try:
            completed = subprocess.run(
                [str(ccx_path), "-i", "job"],
                cwd=str(tmpdir),
                env=run_env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            _log.warning(
                "run_ccx: ccx exceeded timeout_s=%s, tool=%s", timeout_s, ccx_path
            )
            return Err(SolveError.Timeout(tool="ccx", seconds=timeout_s))
        elapsed_s = time.monotonic() - start

        combined_output = (completed.stdout or "") + (completed.stderr or "")
        for line in (completed.stderr or "").splitlines():
            if line.strip():
                _log.warning("ccx stderr: %s", line)
        for line in (completed.stdout or "").splitlines():
            if line.strip():
                _log.info("ccx stdout: %s", line)

        if completed.returncode != 0:
            tail_lines = combined_output.splitlines()[-_LOG_TAIL_LINES:]
            log_tail = "\n".join(tail_lines)
            _log.warning(
                "run_ccx: ccx exited with code %d, tool=%s",
                completed.returncode,
                ccx_path,
            )
            return Err(SolveError.ToolFailed(tool="ccx", log_tail=log_tail))

        dat_path = tmpdir / "job.dat"
        frd_path = tmpdir / "job.frd"
        dat_text = dat_path.read_text() if dat_path.exists() else ""
        frd_text = frd_path.read_text() if frd_path.exists() else None

        tool_version = _parse_tool_version(combined_output)
        _log.info(
            "run_ccx: completed in %.3fs, tool_version=%s, dat=%d bytes, frd=%s",
            elapsed_s,
            tool_version,
            len(dat_text),
            "present" if frd_text is not None else "absent",
        )

        return Ok(
            CcxRun(
                dat_text=dat_text,
                frd_text=frd_text,
                elapsed_s=elapsed_s,
                tool_version=tool_version,
            )
        )


def probe_tools() -> Result[None, SolveError]:
    """Thin `find_ccx()` wrapper dropping the `Ok` payload -- the
    `probe_tools` convention `plan/cache.py`'s `_tools_still_consistent`
    looks for via `getattr(fn, "probe_tools", None)` on a registered
    `SolveFn`."""
    return find_ccx() | (lambda _path: None)
