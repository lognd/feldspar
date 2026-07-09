from __future__ import annotations

"""D154 (lithos design-log `2026-07-08-cycle-28.md`): `Model.discharge`
now threads a real `PayloadStore`-backed resolver to any `estimate`
override that opts in by naming a keyword-only `resolver` parameter
(`regolith.harness.model._accepts_resolver`). This module proves the
feldspar-side half of that contract:

- `pack.payload_bridge.RegolithResolverAdapter` correctly wraps a
  lithos resolver callable into feldspar's own `PayloadResolver`
  protocol, honoring D154's wire-format rule (bytes ARE the schema-
  versioned JSON `regolith._schema` publishes) -- a major-version
  mismatch is an honest indeterminate naming both versions, never a
  silent parse.
- `FeaStaticDeflectionFromGeometryModel.estimate` opts in: with NO
  resolver threaded, its behavior is UNCHANGED (the pre-D154
  `NoStoreResolver` honest-ToolMissing path); with a WORKING resolver
  threaded, its payload path proceeds PAST resolution (a different,
  downstream failure reason -- proving the resolved bytes were
  actually consumed, not merely accepted).
"""

import json

import pytest
from regolith._schema import SCHEMA_VERSION
from regolith._schema.models import PayloadRef as RegolithPayloadRef
from regolith.harness.model import DischargeRequest
from regolith.harness.quantity import Interval
from typani.result import Err, Ok, Result

from feldspar.pack.models import FeaStaticDeflectionFromGeometryModel
from feldspar.pack.payload_bridge import RegolithResolverAdapter
from feldspar.solve.payload import PayloadRef as FeldsparPayloadRef

pytestmark = pytest.mark.regolith

_DIGEST = "blake3:" + "a" * 64
_GEOMETRY_PORT = "mech.geom.cantilever.parametric"


def _valid_geometry_envelope() -> bytes:
    """A `CantileverGeometry`-shaped envelope carrying the D154
    `schema_version` field (pydantic's default `extra="ignore"` on
    `CantileverGeometry` tolerates the extra key, so this is BOTH a
    valid schema-versioned envelope and valid geometry content)."""
    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "length": 0.1,
            "width": 0.01,
            "height": 0.01,
        },
        sort_keys=True,
    ).encode("ascii")


def _fake_lithos_resolver(
    responses: dict,
) -> "object":
    """A stand-in for the lithos `PayloadResolver` callable
    (`digest -> Result[bytes, object]`), the exact shape `Model.
    discharge` threads to an opted-in `estimate` override."""

    def _resolve(digest: str) -> Result:
        if digest not in responses:
            return Err(f"no fixture bytes for digest {digest!r}")
        return Ok(responses[digest])

    return _resolve


# --- RegolithResolverAdapter, in isolation ----------------------------------


def test_adapter_resolves_valid_schema_versioned_bytes() -> None:
    """Valid schema-JSON bytes at the right digest -> `Ok` with the
    exact bytes handed back unchanged."""
    payload = _valid_geometry_envelope()
    adapter = RegolithResolverAdapter(_fake_lithos_resolver({_DIGEST: payload}))
    ref = FeldsparPayloadRef(kind="geometry.parametric", digest=_DIGEST, origin="test")
    result = adapter.resolve(ref)
    assert result.is_ok
    assert result.danger_ok == payload


def test_adapter_honestly_indeterminates_on_schema_version_mismatch() -> None:
    """A payload declaring a different `schema_version` than this build
    understands is `Err(SolveError.ParseFailed)`, naming BOTH versions
    in the message -- never a silent parse of an unknown shape."""
    wrong_version = SCHEMA_VERSION + 1
    payload = json.dumps(
        {"schema_version": wrong_version, "length": 0.1, "width": 0.01, "height": 0.01}
    ).encode("ascii")
    adapter = RegolithResolverAdapter(_fake_lithos_resolver({_DIGEST: payload}))
    ref = FeldsparPayloadRef(kind="geometry.parametric", digest=_DIGEST, origin="test")
    result = adapter.resolve(ref)
    assert result.is_err
    err = result.danger_err
    assert err.kind == "ParseFailed"
    assert str(wrong_version) in err.context
    assert str(SCHEMA_VERSION) in err.context


def test_adapter_maps_an_unresolvable_digest_to_dangling_digest() -> None:
    """A digest the wrapped lithos callable cannot resolve maps to
    `SolveError.DanglingDigest`, never propagating the lithos-side
    error type across the FINV-3 boundary."""
    adapter = RegolithResolverAdapter(_fake_lithos_resolver({}))
    ref = FeldsparPayloadRef(kind="geometry.parametric", digest=_DIGEST, origin="test")
    result = adapter.resolve(ref)
    assert result.is_err
    assert result.danger_err.kind == "DanglingDigest"
    assert result.danger_err.digest == _DIGEST


def test_adapter_store_is_never_called() -> None:
    """The pack boundary never performs its own payload storage IO --
    a call to `store()` on this adapter is a programmer bug."""
    adapter = RegolithResolverAdapter(_fake_lithos_resolver({}))
    with pytest.raises(AssertionError):
        adapter.store("mesh", b"{}", "test")


# --- FeaStaticDeflectionFromGeometryModel.estimate --------------------------


def _tip_force_inputs() -> dict:
    return {
        "mech.material.youngs_modulus": Interval(lo=7.0e10, hi=7.0e10),
        "mech.material.poisson": Interval(lo=0.33, hi=0.33),
        "mech.load.tip_force": Interval(lo=1.0e3, hi=1.0e3),
    }


def _geometry_request(digest: str = _DIGEST) -> DischargeRequest:
    return DischargeRequest(
        claim_kind="mech.static_deflection",
        limit=1.0,
        inputs=_tip_force_inputs(),
        payloads={
            _GEOMETRY_PORT: RegolithPayloadRef(
                kind="geometry.parametric", digest=digest, origin="fixture"
            )
        },
    )


def test_no_resolver_keeps_the_pre_d154_no_store_resolver_behavior() -> None:
    """No `resolver` argument at all: `estimate` behaves exactly as it
    did before D154, honestly indeterminating via `NoStoreResolver`
    (the missing-channel `ToolMissing`)."""
    model = FeaStaticDeflectionFromGeometryModel()
    result = model.estimate(_geometry_request())
    assert result.is_err
    assert "regolith.orchestrator.payload_store" in result.danger_err.message


def test_resolver_none_is_identical_to_omitting_it() -> None:
    """Explicitly passing `resolver=None` (what `Model.discharge` does
    when no `PayloadStore` is configured) is indistinguishable from the
    pre-D154 call shape."""
    model = FeaStaticDeflectionFromGeometryModel()
    result = model.estimate(_geometry_request(), resolver=None)
    assert result.is_err
    assert "regolith.orchestrator.payload_store" in result.danger_err.message


def test_a_working_resolver_lets_the_payload_path_proceed_past_resolution() -> None:
    """With a WORKING lithos resolver threaded, the model's payload path
    proceeds PAST the resolver channel entirely: the failure this build
    reports is no longer the resolver-channel `ToolMissing` -- proving
    the geometry payload was actually resolved and handed to the
    engine's mesh-building direction (whatever it fails on next, e.g.
    gmsh being unavailable in this environment, is a DIFFERENT, honest
    reason than 'no resolver reached me')."""
    model = FeaStaticDeflectionFromGeometryModel()
    resolver = _fake_lithos_resolver({_DIGEST: _valid_geometry_envelope()})
    result = model.estimate(_geometry_request(), resolver=resolver)
    assert result.is_err, (
        "gmsh/ccx are not installed in this environment, so the solve "
        "cannot fully complete -- but it must not fail for the "
        "resolver-channel reason"
    )
    assert "regolith.orchestrator.payload_store" not in result.danger_err.message


def test_a_version_mismatched_resolver_honestly_indeterminates_naming_both_versions() -> (
    None
):
    """A resolver whose bytes declare a schema version this build does
    not understand: the model still fails honestly, and the message
    names both the version the payload declared and the version this
    build understands (D154's naming-both-versions rule), reaching the
    caller through `pack.errors.map_engine_error`'s one shared
    mapping."""
    wrong_version = SCHEMA_VERSION + 1
    bad_payload = json.dumps(
        {
            "schema_version": wrong_version,
            "length": 0.1,
            "width": 0.01,
            "height": 0.01,
        }
    ).encode("ascii")
    model = FeaStaticDeflectionFromGeometryModel()
    resolver = _fake_lithos_resolver({_DIGEST: bad_payload})
    result = model.estimate(_geometry_request(), resolver=resolver)
    assert result.is_err
    message = result.danger_err.message
    assert str(wrong_version) in message
    assert str(SCHEMA_VERSION) in message
