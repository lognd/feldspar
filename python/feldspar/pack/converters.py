from __future__ import annotations

"""The ONE regolith<->feldspar `Interval` converter pair (06, FINV-3/10).

Both sides use the same closed `[lo, hi]` semantics (regolith
`harness.quantity.Interval`, feldspar `feldspar.core.Interval`, PyO3), so
conversion is a straight field copy -- but it is done in exactly one
place so no other module needs to know both types exist. Round-trip
tested both directions (`tests/regolith/test_pack_converters.py`)."""

from regolith._schema.models import PayloadRef as RegolithPayloadRef
from regolith.harness.quantity import Interval as RegolithInterval

from feldspar.core import Interval as FeldsparInterval
from feldspar.solve.payload import PayloadRef as FeldsparPayloadRef

__all__ = [
    "to_feldspar_interval",
    "to_regolith_interval",
    "to_feldspar_payload_ref",
    "to_regolith_payload_ref",
]


# frob:waive TEST005 reason="measured 50.0% branch cov on 2026-07-18; straight-line field-copy body (coverage.py branch-pair artifact) genuinely covered by test_regolith_to_feldspar_round_trip in tests/regolith/test_pack_converters.py -- excluded from THIS coverage run by the -m the regolith-exclusion filter (tests pass; regolith-marked suites need a local lithos checkout, which this sandbox has, but the stamped coverage command deliberately excludes them, matching the rest of the fleet). Backfill T-0014."
# frob:doc docs/modules/pack.md#pack_converters
def to_feldspar_interval(interval: RegolithInterval) -> FeldsparInterval:
    """A regolith `Interval` -> the equivalent feldspar `Interval`."""
    return FeldsparInterval(interval.lo, interval.hi)


# frob:waive TEST005 reason="measured 50.0% branch cov on 2026-07-18; straight-line field-copy body (coverage.py branch-pair artifact) genuinely covered by test_regolith_to_feldspar_round_trip / test_feldspar_to_regolith_round_trip in tests/regolith/test_pack_converters.py -- excluded from THIS coverage run by the -m the regolith-exclusion filter (tests pass; regolith-marked suites need a local lithos checkout, which this sandbox has, but the stamped coverage command deliberately excludes them, matching the rest of the fleet). Backfill T-0014."
# frob:doc docs/modules/pack.md#pack_converters
def to_regolith_interval(interval: FeldsparInterval) -> RegolithInterval:
    """A feldspar `Interval` -> the equivalent regolith `Interval`."""
    return RegolithInterval(lo=interval.lo, hi=interval.hi)


# frob:waive TEST005 reason="measured 50.0% branch cov on 2026-07-18; straight-line field-copy body (coverage.py branch-pair artifact) genuinely covered by test_regolith_to_feldspar_payload_ref_round_trip in tests/regolith/test_pack_converters.py -- excluded from THIS coverage run by the -m the regolith-exclusion filter (tests pass; regolith-marked suites need a local lithos checkout, which this sandbox has, but the stamped coverage command deliberately excludes them, matching the rest of the fleet). Backfill T-0014."
# frob:doc docs/modules/pack.md#pack_converters
def to_feldspar_payload_ref(ref: RegolithPayloadRef) -> FeldsparPayloadRef:
    """A regolith `PayloadRef` (D96, sec. 8.3) -> the equivalent feldspar
    `PayloadRef` (09 sec. 4). Both are `{kind, digest, origin}`, exact by
    reference (WO-14 boundary v2, 06 "Planned (09 M4)"): a straight field
    copy, done in exactly this one place, mirroring the `Interval` pair
    above -- the pack adapter stays a converter, never a second dispatch
    path."""
    return FeldsparPayloadRef(kind=ref.kind, digest=ref.digest, origin=ref.origin)


# frob:waive TEST005 reason="measured 50.0% branch cov on 2026-07-18; straight-line field-copy body (coverage.py branch-pair artifact) genuinely covered by test_regolith_to_feldspar_payload_ref_round_trip / test_feldspar_to_regolith_payload_ref_round_trip in tests/regolith/test_pack_converters.py -- excluded from THIS coverage run by the -m the regolith-exclusion filter (tests pass; regolith-marked suites need a local lithos checkout, which this sandbox has, but the stamped coverage command deliberately excludes them, matching the rest of the fleet). Backfill T-0014."
# frob:doc docs/modules/pack.md#pack_converters
def to_regolith_payload_ref(ref: FeldsparPayloadRef) -> RegolithPayloadRef:
    """A feldspar `PayloadRef` -> the equivalent regolith `PayloadRef`."""
    return RegolithPayloadRef(kind=ref.kind, digest=ref.digest, origin=ref.origin)
