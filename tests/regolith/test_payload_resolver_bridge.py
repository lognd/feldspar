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
import math

import pytest
from regolith._schema import SCHEMA_VERSION
from regolith._schema.models import PayloadRef as RegolithPayloadRef
from regolith.harness.model import DischargeRequest
from regolith.harness.quantity import Interval
from regolith.harness.signature import ClaimSense
from typani.result import Err, Ok, Result

from feldspar.fluids.network import FLOWNET_PORT
from feldspar.pack.models import (
    DEFAULT_FLUIDS_DP_CLAIM_KIND,
    DEFAULT_FLUIDS_FLOW_IMBALANCE_CLAIM_KIND,
    DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND,
    FeaStaticDeflectionFromGeometryModel,
    FluidsDpModel,
    FluidsFlowImbalanceModel,
    FluidsMdotModel,
)
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


# frob:tests python/feldspar/pack/models.py::FeaStaticDeflectionFromGeometryModel.estimate kind="unit"
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


# --- T-0019: FlownetPayload.claim_target, both directions -------------------
#
# SCHEMA_VERSION 31 added `FlownetPayload.claim_target` (D272 passenger,
# WO-141 escalation): the fluids pack models in `feldspar.pack.models`
# now PREFER it over the legacy `DischargeRequest.inputs` 0.0/1.0
# presence-flag convention (`test_pack_wo141_fluids_network.py`'s own
# fixtures exercise the legacy fallback path; this file adds the
# claim_target-carrying cases both ways -- present and absent -- using
# the SAME asymmetric two-branch Hagen-Poiseuille calibration network,
# NOT reproduced field-by-field here, just enough of it to answer one
# mdot/flow_imbalance/dp claim each).

_FLUIDS_DIGEST_CT = "blake3:" + "e" * 64
_FLUIDS_DIGEST_LEGACY = "blake3:" + "f" * 64

_CT_LENGTH_A, _CT_LENGTH_B = 1.0, 2.0
_CT_DIAMETER = 0.02
_CT_DENSITY, _CT_VISCOSITY = 1000.0, 1e-3
_CT_Q_TOTAL = 1e-5


def _ct_scalar(value: float, unit: str = "m") -> dict:
    return {"lo": value, "hi": value, "unit": unit}


def _ct_pipe(edge_id, a, b, length) -> dict:
    return {
        "id": edge_id,
        "a": a,
        "b": b,
        "kind": "pipe",
        "params": {
            "source": "scalars",
            "values": {
                "length": _ct_scalar(length),
                "diameter": _ct_scalar(_CT_DIAMETER),
                "roughness": _ct_scalar(0.0),
                "density": _ct_scalar(_CT_DENSITY, "kg/m^3"),
                "viscosity": _ct_scalar(_CT_VISCOSITY, "Pa s"),
            },
        },
    }


def _ct_imposer(edge_id, a, b, flow_rate) -> dict:
    return {
        "id": edge_id,
        "a": a,
        "b": b,
        "kind": "imposer",
        "params": {
            "source": "scalars",
            "values": {"flow_rate": _ct_scalar(flow_rate, "m^3/s")},
        },
    }


def _ct_flownet_envelope(claim_target: dict | None) -> bytes:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "nodes": ["src", "n1", "n2", "sink"],
        "edges": [
            _ct_imposer("imp_in", "src", "n1", _CT_Q_TOTAL),
            _ct_pipe("A", "n1", "n2", _CT_LENGTH_A),
            _ct_pipe("B", "n1", "n2", _CT_LENGTH_B),
            _ct_imposer("imp_out", "n2", "sink", _CT_Q_TOTAL),
        ],
    }
    if claim_target is not None:
        payload["claim_target"] = claim_target
    return json.dumps(payload, sort_keys=True).encode("ascii")


def _ct_resistance(length: float) -> float:
    return 128.0 * _CT_VISCOSITY * length / (math.pi * _CT_DIAMETER**4)


_CT_R_A, _CT_R_B = _ct_resistance(_CT_LENGTH_A), _ct_resistance(_CT_LENGTH_B)
_CT_EXPECTED_Q_A = _CT_Q_TOTAL * _CT_R_B / (_CT_R_A + _CT_R_B)
_CT_EXPECTED_Q_B = _CT_Q_TOTAL * _CT_R_A / (_CT_R_A + _CT_R_B)


def _ct_pinned(value: float) -> Interval:
    return Interval(lo=value, hi=value)


def _ct_resolver(digest: str, envelope: bytes) -> object:
    def _resolve(d: str) -> Result:
        if d != digest:
            return Err(f"no fixture bytes for digest {d!r}")
        return Ok(envelope)

    return _resolve


# frob:tests python/feldspar/pack/models.py::FluidsMdotModel.estimate kind="unit"
def test_mdot_prefers_claim_target_role_over_legacy_inputs() -> None:
    """A resolved payload carrying `claim_target = {claim_kind, role="A"}`
    is honored even though the request's `inputs` presence-flag key
    names a DIFFERENT edge (`B`) -- proving `claim_target` wins, not
    merely that it is consulted when the legacy path is silent."""
    model = FluidsMdotModel(
        claim_kind=DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND, sense=ClaimSense.upper_bound()
    )
    envelope = _ct_flownet_envelope(
        {"claim_kind": DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND, "role": "A"}
    )
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND,
        limit=0.0,
        inputs={"B": _ct_pinned(1.0)},
        payloads={
            FLOWNET_PORT: RegolithPayloadRef(
                kind="flownet", digest=_FLUIDS_DIGEST_CT, origin="fixture"
            )
        },
    )
    result = model.estimate(request, resolver=_ct_resolver(_FLUIDS_DIGEST_CT, envelope))
    assert result.is_ok, result
    assert result.danger_ok.value == pytest.approx(_CT_EXPECTED_Q_A, rel=1e-3)


# frob:tests python/feldspar/pack/models.py::FluidsMdotModel.estimate kind="unit"
def test_mdot_falls_back_to_legacy_inputs_when_no_claim_target() -> None:
    """A pre-SCHEMA_VERSION-31-shaped payload (no `claim_target` key at
    all) still resolves via the legacy `inputs` presence-flag
    convention, unchanged."""
    model = FluidsMdotModel(
        claim_kind=DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND, sense=ClaimSense.upper_bound()
    )
    envelope = _ct_flownet_envelope(None)
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND,
        limit=0.0,
        inputs={"A": _ct_pinned(1.0)},
        payloads={
            FLOWNET_PORT: RegolithPayloadRef(
                kind="flownet", digest=_FLUIDS_DIGEST_LEGACY, origin="fixture"
            )
        },
    )
    result = model.estimate(
        request, resolver=_ct_resolver(_FLUIDS_DIGEST_LEGACY, envelope)
    )
    assert result.is_ok, result
    assert result.danger_ok.value == pytest.approx(_CT_EXPECTED_Q_A, rel=1e-3)


def test_mdot_claim_target_role_naming_absent_edge_is_honest_domain_error() -> None:
    """`claim_target.role` naming an id that is not one of this
    network's edges is an honest `DomainError`, never a silent
    fallback to the (also-present) legacy `inputs` selection."""
    model = FluidsMdotModel(
        claim_kind=DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND, sense=ClaimSense.upper_bound()
    )
    envelope = _ct_flownet_envelope(
        {"claim_kind": DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND, "role": "not_an_edge"}
    )
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND,
        limit=0.0,
        inputs={"A": _ct_pinned(1.0)},
        payloads={
            FLOWNET_PORT: RegolithPayloadRef(
                kind="flownet", digest=_FLUIDS_DIGEST_CT, origin="fixture"
            )
        },
    )
    result = model.estimate(request, resolver=_ct_resolver(_FLUIDS_DIGEST_CT, envelope))
    assert result.is_err
    assert "claim_target.role" in result.danger_err.message


# frob:tests python/feldspar/pack/models.py::FluidsFlowImbalanceModel.estimate kind="unit"
def test_flow_imbalance_prefers_claim_target_role_edge_set() -> None:
    """`claim_target.role = "A,B"` (T-0019's comma-joined role
    convention) selects the sibling edge set even though `inputs`
    carries no matching keys at all."""
    model = FluidsFlowImbalanceModel()
    envelope = _ct_flownet_envelope(
        {"claim_kind": DEFAULT_FLUIDS_FLOW_IMBALANCE_CLAIM_KIND, "role": "A,B"}
    )
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_FLOW_IMBALANCE_CLAIM_KIND,
        limit=1.0,
        inputs={},
        payloads={
            FLOWNET_PORT: RegolithPayloadRef(
                kind="flownet", digest=_FLUIDS_DIGEST_CT, origin="fixture"
            )
        },
    )
    result = model.estimate(request, resolver=_ct_resolver(_FLUIDS_DIGEST_CT, envelope))
    assert result.is_ok, result
    expected = (
        max(_CT_EXPECTED_Q_A, _CT_EXPECTED_Q_B)
        - min(_CT_EXPECTED_Q_A, _CT_EXPECTED_Q_B)
    ) / ((_CT_EXPECTED_Q_A + _CT_EXPECTED_Q_B) / 2.0)
    assert result.danger_ok.value == pytest.approx(expected, rel=1e-3)


# frob:tests python/feldspar/pack/models.py::FluidsFlowImbalanceModel.estimate kind="unit"
def test_flow_imbalance_falls_back_to_legacy_inputs_when_no_claim_target() -> None:
    model = FluidsFlowImbalanceModel()
    envelope = _ct_flownet_envelope(None)
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_FLOW_IMBALANCE_CLAIM_KIND,
        limit=1.0,
        inputs={"A": _ct_pinned(1.0), "B": _ct_pinned(1.0)},
        payloads={
            FLOWNET_PORT: RegolithPayloadRef(
                kind="flownet", digest=_FLUIDS_DIGEST_LEGACY, origin="fixture"
            )
        },
    )
    result = model.estimate(
        request, resolver=_ct_resolver(_FLUIDS_DIGEST_LEGACY, envelope)
    )
    assert result.is_ok, result
    expected = (
        max(_CT_EXPECTED_Q_A, _CT_EXPECTED_Q_B)
        - min(_CT_EXPECTED_Q_A, _CT_EXPECTED_Q_B)
    ) / ((_CT_EXPECTED_Q_A + _CT_EXPECTED_Q_B) / 2.0)
    assert result.danger_ok.value == pytest.approx(expected, rel=1e-3)


# frob:tests python/feldspar/pack/models.py::FluidsDpModel.estimate kind="unit"
def test_dp_prefers_claim_target_role_arrow_pair() -> None:
    """`claim_target.role = "src->sink"` (T-0019's arrow-pair role
    convention) selects the path endpoints with no `inputs` role
    values at all."""
    model = FluidsDpModel()
    envelope = _ct_flownet_envelope(
        {"claim_kind": DEFAULT_FLUIDS_DP_CLAIM_KIND, "role": "src->sink"}
    )
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_DP_CLAIM_KIND,
        limit=1.0e9,
        inputs={},
        payloads={
            FLOWNET_PORT: RegolithPayloadRef(
                kind="flownet", digest=_FLUIDS_DIGEST_CT, origin="fixture"
            )
        },
    )
    result = model.estimate(request, resolver=_ct_resolver(_FLUIDS_DIGEST_CT, envelope))
    assert result.is_ok, result
    expected_dp = _CT_EXPECTED_Q_A * _CT_R_A
    assert result.danger_ok.value == pytest.approx(expected_dp, rel=1e-2)


# frob:tests python/feldspar/pack/models.py::FluidsDpModel.estimate kind="unit"
def test_dp_falls_back_to_legacy_inputs_when_no_claim_target() -> None:
    model = FluidsDpModel()
    envelope = _ct_flownet_envelope(None)
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_DP_CLAIM_KIND,
        limit=1.0e9,
        inputs={"src": _ct_pinned(0.0), "sink": _ct_pinned(1.0)},
        payloads={
            FLOWNET_PORT: RegolithPayloadRef(
                kind="flownet", digest=_FLUIDS_DIGEST_LEGACY, origin="fixture"
            )
        },
    )
    result = model.estimate(
        request, resolver=_ct_resolver(_FLUIDS_DIGEST_LEGACY, envelope)
    )
    assert result.is_ok, result
    expected_dp = _CT_EXPECTED_Q_A * _CT_R_A
    assert result.danger_ok.value == pytest.approx(expected_dp, rel=1e-2)


def test_dp_claim_target_role_malformed_is_honest_domain_error() -> None:
    """A `claim_target.role` that does not parse as `"<from>-><to>"`
    (missing the arrow separator) is an honest `DomainError`, never a
    silent fallback to the legacy `inputs` convention."""
    model = FluidsDpModel()
    envelope = _ct_flownet_envelope(
        {"claim_kind": DEFAULT_FLUIDS_DP_CLAIM_KIND, "role": "src_only"}
    )
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_DP_CLAIM_KIND,
        limit=1.0e9,
        inputs={"src": _ct_pinned(0.0), "sink": _ct_pinned(1.0)},
        payloads={
            FLOWNET_PORT: RegolithPayloadRef(
                kind="flownet", digest=_FLUIDS_DIGEST_CT, origin="fixture"
            )
        },
    )
    result = model.estimate(request, resolver=_ct_resolver(_FLUIDS_DIGEST_CT, envelope))
    assert result.is_err
    assert "claim_target.role" in result.danger_err.message
