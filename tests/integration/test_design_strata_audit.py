from __future__ import annotations

"""Integration check binding `design/feldspar.strata` (the T-0008 strata
model of feldspar's real topology) to the actual repo it claims to
model: runs `frob sys audit .` as a real subprocess and asserts the
named-gap set matches the currently tracked, ticketed state (T-0009/
T-0010 CWE-78 discharges still queued) rather than silently drifting
-- if the model or the code moves and a NEW unticketed gap appears,
this test breaks loudly instead of the model quietly going stale."""

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    shutil.which("frob") is None, reason="frob CLI not on PATH"
)


# frob:tests design kind="integration"
def test_sys_audit_named_gaps_match_tracked_open_tickets() -> None:
    """`frob sys audit .` must run to completion (never crash) against
    the committed strata model, and its only THREAT003 gaps must be
    the two CWE-78 discharges already tracked as open tickets
    (T-0009 elec, T-0010 fea) -- any other/new THREAT003 gap means the
    model or code drifted without a ticket."""
    result = subprocess.run(
        [shutil.which("frob"), "sys", "audit", "."],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    # frob sys audit exits non-zero while named gaps remain open (T-0009/
    # T-0010); a crash (missing traceback-free failure) is still wrong.
    assert "Traceback" not in result.stderr, result.stderr
    combined = result.stdout + result.stderr
    assert "weakness:CWE-78:elec" in combined
    assert "weakness:CWE-78:fea" in combined
