from __future__ import annotations

"""The ONE `Interval` converter pair, round-trip tested both directions
(06 "Conversion at the boundary only ... one converter pair, round-trip
tested")."""

import pytest
from regolith._schema.models import PayloadRef as RegolithPayloadRef
from regolith.harness.quantity import Interval as RegolithInterval

from feldspar.core import Interval as FeldsparInterval
from feldspar.pack.converters import (
    to_feldspar_interval,
    to_feldspar_payload_ref,
    to_regolith_interval,
    to_regolith_payload_ref,
)
from feldspar.solve.payload import PayloadRef as FeldsparPayloadRef

pytestmark = pytest.mark.regolith


# frob:tests python/feldspar/pack/converters.py::to_feldspar_interval kind="unit"
# frob:tests python/feldspar/pack/converters.py::to_regolith_interval kind="unit"
def test_regolith_to_feldspar_round_trip() -> None:
    """regolith -> feldspar -> regolith preserves lo/hi exactly."""
    original = RegolithInterval(lo=1.5, hi=3.25)
    feldspar_iv = to_feldspar_interval(original)
    assert (feldspar_iv.lo, feldspar_iv.hi) == (1.5, 3.25)
    back = to_regolith_interval(feldspar_iv)
    assert back == original


def test_feldspar_to_regolith_round_trip() -> None:
    """feldspar -> regolith -> feldspar preserves lo/hi exactly."""
    original = FeldsparInterval(-2.0, 4.0)
    regolith_iv = to_regolith_interval(original)
    assert (regolith_iv.lo, regolith_iv.hi) == (-2.0, 4.0)
    back = to_feldspar_interval(regolith_iv)
    assert (back.lo, back.hi) == (original.lo, original.hi)


def test_degenerate_point_round_trips() -> None:
    """A pinned (lo == hi) value survives both directions."""
    original = RegolithInterval(lo=7.0, hi=7.0)
    back = to_regolith_interval(to_feldspar_interval(original))
    assert back == original


# -- WO-14: the `PayloadRef` converter pair (06 "Planned (09 M4)") ----------


def test_regolith_to_feldspar_payload_ref_round_trip() -> None:
    """regolith `PayloadRef` -> feldspar -> regolith preserves every field."""
    original = RegolithPayloadRef(
        kind="geometry.parametric", digest="blake3:" + "a" * 64, origin="test"
    )
    feldspar_ref = to_feldspar_payload_ref(original)
    assert (feldspar_ref.kind, feldspar_ref.digest, feldspar_ref.origin) == (
        original.kind,
        original.digest,
        original.origin,
    )
    back = to_regolith_payload_ref(feldspar_ref)
    assert back == original


def test_feldspar_to_regolith_payload_ref_round_trip() -> None:
    """feldspar `PayloadRef` -> regolith -> feldspar preserves every field."""
    original = FeldsparPayloadRef(
        kind="mesh", digest="blake3:" + "b" * 64, origin="fea.mesh.cantilever"
    )
    regolith_ref = to_regolith_payload_ref(original)
    assert (regolith_ref.kind, regolith_ref.digest, regolith_ref.origin) == (
        original.kind,
        original.digest,
        original.origin,
    )
    back = to_feldspar_payload_ref(regolith_ref)
    assert back == original
