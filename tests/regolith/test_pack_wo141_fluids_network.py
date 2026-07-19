from __future__ import annotations

"""WO-141 (feldspar fluids pack bridge): regolith `Model` wrappers
around the Hardy-Cross network solver (`feldspar.fluids.network`).
Follows `test_pack_wo111b_exposure.py`'s exact no-resolver / working-
resolver shape for the D154 payload channel (NO DUPLICATION of that
reasoning -- see either file's own docstrings).

Calibration anchor: the SAME asymmetric two-branch Hagen-Poiseuille
network `tests/unit/test_fluids_network_query.py`/`tests/unit/
test_library_fluids_network.py` use (White, Fluid Mechanics, 8th ed.,
sec. 6.4) -- an independent closed-form oracle, not the solver's own
code path."""

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
    DEFAULT_FLUIDS_MDOT_LO_CLAIM_KIND,
    FluidsDpModel,
    FluidsFlowImbalanceModel,
    FluidsMdotModel,
)

pytestmark = pytest.mark.regolith

_DIGEST = "blake3:" + "d" * 64


def _fake_lithos_resolver(responses: dict) -> object:
    def _resolve(digest: str) -> Result:
        if digest not in responses:
            return Err(f"no fixture bytes for digest {digest!r}")
        return Ok(responses[digest])

    return _resolve


def _pinned(value: float) -> Interval:
    return Interval(lo=value, hi=value)


# --- the asymmetric two-branch calibration network --------------------------

_LENGTH_A, _LENGTH_B = 1.0, 2.0
_DIAMETER = 0.02
_DENSITY, _VISCOSITY = 1000.0, 1e-3
_Q_TOTAL = 1e-5


def _scalar(value: float, unit: str = "m") -> dict:
    return {"lo": value, "hi": value, "unit": unit}


def _pipe(edge_id, a, b, length, diameter, roughness, density, viscosity) -> dict:
    return {
        "id": edge_id,
        "a": a,
        "b": b,
        "kind": "pipe",
        "params": {
            "source": "scalars",
            "values": {
                "length": _scalar(length),
                "diameter": _scalar(diameter),
                "roughness": _scalar(roughness),
                "density": _scalar(density, "kg/m^3"),
                "viscosity": _scalar(viscosity, "Pa s"),
            },
        },
    }


def _imposer(edge_id, a, b, flow_rate) -> dict:
    return {
        "id": edge_id,
        "a": a,
        "b": b,
        "kind": "imposer",
        "params": {
            "source": "scalars",
            "values": {"flow_rate": _scalar(flow_rate, "m^3/s")},
        },
    }


def _flownet_envelope() -> bytes:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "nodes": ["src", "n1", "n2", "sink"],
        "edges": [
            _imposer("imp_in", "src", "n1", _Q_TOTAL),
            _pipe("A", "n1", "n2", _LENGTH_A, _DIAMETER, 0.0, _DENSITY, _VISCOSITY),
            _pipe("B", "n1", "n2", _LENGTH_B, _DIAMETER, 0.0, _DENSITY, _VISCOSITY),
            _imposer("imp_out", "n2", "sink", _Q_TOTAL),
        ],
    }
    return json.dumps(payload, sort_keys=True).encode("ascii")


def _resistance(length: float) -> float:
    return 128.0 * _VISCOSITY * length / (math.pi * _DIAMETER**4)


_R_A, _R_B = _resistance(_LENGTH_A), _resistance(_LENGTH_B)
_EXPECTED_Q_A = _Q_TOTAL * _R_B / (_R_A + _R_B)
_EXPECTED_Q_B = _Q_TOTAL * _R_A / (_R_A + _R_B)


def _flownet_payload_ref() -> RegolithPayloadRef:
    return RegolithPayloadRef(kind="flownet", digest=_DIGEST, origin="fixture")


def _working_resolver():
    return _fake_lithos_resolver({_DIGEST: _flownet_envelope()})


# --- FluidsMdotModel ---------------------------------------------------------


def _mdot_request(edge_id: str, claim_kind: str) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=claim_kind,
        limit=0.0,
        inputs={edge_id: _pinned(1.0)},
        payloads={FLOWNET_PORT: _flownet_payload_ref()},
    )


# frob:tests python/feldspar/pack/models.py::FluidsMdotModel.estimate kind="unit"
def test_mdot_no_resolver_is_honest_indeterminate() -> None:
    model = FluidsMdotModel(
        claim_kind=DEFAULT_FLUIDS_MDOT_LO_CLAIM_KIND, sense=ClaimSense.lower_bound()
    )
    result = model.estimate(_mdot_request("A", DEFAULT_FLUIDS_MDOT_LO_CLAIM_KIND))
    assert result.is_err
    assert "regolith.orchestrator.payload_store" in result.danger_err.message


def test_mdot_working_resolver_matches_hand_computed_split() -> None:
    model = FluidsMdotModel(
        claim_kind=DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND, sense=ClaimSense.upper_bound()
    )
    result = model.estimate(
        _mdot_request("A", DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND),
        resolver=_working_resolver(),
    )
    assert result.is_ok, result
    assert result.danger_ok.value == pytest.approx(_EXPECTED_Q_A, rel=1e-3)
    assert result.danger_ok.eps == 0.0
    assert result.danger_ok.in_domain


def test_mdot_ambiguous_selection_is_honest_domain_error() -> None:
    """Two edge ids selected at once (both `A` and `B` present as
    input keys) cannot mean a single-edge flow query -- honest
    `DomainError`, never an arbitrary pick."""
    model = FluidsMdotModel(
        claim_kind=DEFAULT_FLUIDS_MDOT_LO_CLAIM_KIND, sense=ClaimSense.lower_bound()
    )
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_MDOT_LO_CLAIM_KIND,
        limit=0.0,
        inputs={"A": _pinned(1.0), "B": _pinned(1.0)},
        payloads={FLOWNET_PORT: _flownet_payload_ref()},
    )
    result = model.estimate(request, resolver=_working_resolver())
    assert result.is_err
    assert "exactly one selected edge" in result.danger_err.message


def test_mdot_no_selection_is_honest_domain_error() -> None:
    model = FluidsMdotModel(
        claim_kind=DEFAULT_FLUIDS_MDOT_LO_CLAIM_KIND, sense=ClaimSense.lower_bound()
    )
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_MDOT_LO_CLAIM_KIND,
        limit=0.0,
        inputs={"not_an_edge": _pinned(1.0)},
        payloads={FLOWNET_PORT: _flownet_payload_ref()},
    )
    result = model.estimate(request, resolver=_working_resolver())
    assert result.is_err
    assert "exactly one selected edge" in result.danger_err.message


# --- FluidsFlowImbalanceModel -------------------------------------------------


# frob:tests python/feldspar/pack/models.py::FluidsFlowImbalanceModel.estimate kind="unit"
def test_flow_imbalance_matches_hand_computed_split() -> None:
    model = FluidsFlowImbalanceModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_FLOW_IMBALANCE_CLAIM_KIND,
        limit=1.0,
        inputs={"A": _pinned(1.0), "B": _pinned(1.0)},
        payloads={FLOWNET_PORT: _flownet_payload_ref()},
    )
    result = model.estimate(request, resolver=_working_resolver())
    assert result.is_ok, result
    expected = (
        max(_EXPECTED_Q_A, _EXPECTED_Q_B) - min(_EXPECTED_Q_A, _EXPECTED_Q_B)
    ) / ((_EXPECTED_Q_A + _EXPECTED_Q_B) / 2.0)
    assert result.danger_ok.value == pytest.approx(expected, rel=1e-3)


def test_flow_imbalance_needs_at_least_two_edges() -> None:
    model = FluidsFlowImbalanceModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_FLOW_IMBALANCE_CLAIM_KIND,
        limit=1.0,
        inputs={"A": _pinned(1.0)},
        payloads={FLOWNET_PORT: _flownet_payload_ref()},
    )
    result = model.estimate(request, resolver=_working_resolver())
    assert result.is_err
    assert "at least two selected" in result.danger_err.message


# --- FluidsDpModel ------------------------------------------------------------


def test_dp_multipath_matches_hand_computed_path() -> None:
    """src->sink path dp is the single-branch converged dp (both
    branches share the same dp once converged) plus zero from both
    imposer legs."""
    model = FluidsDpModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_DP_CLAIM_KIND,
        limit=1.0e9,
        inputs={"src": _pinned(0.0), "sink": _pinned(1.0)},
        payloads={FLOWNET_PORT: _flownet_payload_ref()},
    )
    result = model.estimate(request, resolver=_working_resolver())
    assert result.is_ok, result
    # Independent oracle for branch A's dp at its converged flow:
    # Hagen-Poiseuille dP = Q * R.
    expected_dp = _EXPECTED_Q_A * _R_A
    assert result.danger_ok.value == pytest.approx(expected_dp, rel=1e-2)


# frob:tests python/feldspar/pack/models.py::FluidsDpModel.estimate kind="unit"
def test_dp_missing_endpoint_roles_is_honest_domain_error() -> None:
    model = FluidsDpModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_DP_CLAIM_KIND,
        limit=1.0e9,
        inputs={"src": _pinned(0.0)},
        payloads={FLOWNET_PORT: _flownet_payload_ref()},
    )
    result = model.estimate(request, resolver=_working_resolver())
    assert result.is_err
    assert "exactly one 'from' node" in result.danger_err.message


def test_dp_selection_matching_signature() -> None:
    """All three models are D96 payload-channel selections: absent the
    flownet payload, `registry.discharge` reports the honest
    `harness.no_model`/indeterminate (mirrors `test_pack_boundary_v2.
    py`'s own `FeaStaticDeflectionFromGeometryModel` no-payload test)."""
    from regolith.harness.registry import ModelRegistry

    registry = ModelRegistry()
    registry.register(FluidsDpModel())
    request = DischargeRequest(
        claim_kind=DEFAULT_FLUIDS_DP_CLAIM_KIND,
        limit=1.0e9,
        inputs={"src": _pinned(0.0), "sink": _pinned(1.0)},
    )
    evidence = registry.discharge(request)
    assert evidence.model_id == "harness.no_model"
    assert evidence.status.value == "indeterminate"
