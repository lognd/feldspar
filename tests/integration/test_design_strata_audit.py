from __future__ import annotations

"""Integration check binding `design/feldspar.strata` (the T-0008 strata
model of feldspar's real topology) to the actual repo it claims to
model: runs `frob sys audit .` as a real subprocess and asserts it
reports zero UNWAIVED gaps (T-0009/T-0010's CWE-78 discharges, T-0016's
LINT004 kill-switch waivers, and T-0008's original SYS100/SYS101
scanner-false-positive waivers are all resolved or explicitly waived
with a reason and a tracking ticket) -- if the model or the code moves
and a NEW unwaived gap appears, this test breaks loudly instead of the
model quietly going stale.

History: T-0009/T-0010 originally tracked CWE-78 as an OPEN gap because
`regolith_consumer` was modeled `trusted`, so the discharging `assume`
claims could never satisfy THREAT003's src-is-foreign chokepoint
requirement (docs/strata/threat.md `_discharges_as_chokepoint`).
Re-modeling `regolith_consumer` as `foreign` (it genuinely is: a
sibling `../lithos` checkout feldspar does not control) let those SAME
claim bodies discharge for real -- see T-0009/T-0010's Done reports."""

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
    the committed strata model and report PROVED / zero unwaived gaps
    -- any new unwaived gap means the model or code drifted without a
    ticket."""
    result = subprocess.run(
        [shutil.which("frob"), "sys", "audit", "."],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert "Traceback" not in result.stderr, result.stderr
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert "PROVED" in combined, combined
    # No THREAT003 gap for CWE-78 at elec/fea (T-0009/T-0010): both
    # discharge for real now that regolith_consumer is modeled foreign.
    assert "GAP family=security" not in combined, combined
    assert "weakness:CWE-78:elec' does not prove" not in combined, combined
    assert "weakness:CWE-78:fea' does not prove" not in combined, combined
