from __future__ import annotations

"""The ONE regolith<->feldspar `Interval` converter pair (06, FINV-3/10).

Both sides use the same closed `[lo, hi]` semantics (regolith
`harness.quantity.Interval`, feldspar `feldspar.core.Interval`, PyO3), so
conversion is a straight field copy -- but it is done in exactly one
place so no other module needs to know both types exist. Round-trip
tested both directions (`tests/regolith/test_pack_converters.py`)."""

from regolith.harness.quantity import Interval as RegolithInterval

from feldspar.core import Interval as FeldsparInterval

__all__ = ["to_feldspar_interval", "to_regolith_interval"]


def to_feldspar_interval(interval: RegolithInterval) -> FeldsparInterval:
    """A regolith `Interval` -> the equivalent feldspar `Interval`."""
    return FeldsparInterval(interval.lo, interval.hi)


def to_regolith_interval(interval: FeldsparInterval) -> RegolithInterval:
    """A feldspar `Interval` -> the equivalent regolith `Interval`."""
    return RegolithInterval(lo=interval.lo, hi=interval.hi)
