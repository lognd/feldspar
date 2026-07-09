from __future__ import annotations

"""WO-14 (M4 -- regolith boundary v2): structured coverage (D95), the
regime channel (D97/A-10), and the D96 payload-ref channel, exercised
against `feldspar.pack`'s own models (not the generic lithos fixture
pack -- these prove the CHANNEL as feldspar wires it, complementing
`lithos:tests/packs/test_pack_contract_v2.py`'s generic-fixture
coverage)."""

import pytest
from regolith._schema.models import CoverageMethod1, PayloadRef
from regolith.harness.model import DischargeRequest
from regolith.harness.quantity import Interval
from regolith.harness.registry import ModelRegistry

from feldspar.pack.models import (
    DEFAULT_STRESS_CLAIM_KIND,
    FeaStaticDeflectionFromGeometryModel,
    FeaStaticStressModel,
)

pytestmark = pytest.mark.regolith

_STRESS_INPUTS = {
    "mech.load.internal_pressure": Interval(lo=5e6, hi=5e6),
    "mech.geom.cylinder.inner_radius": Interval(lo=0.02, hi=0.021),
    "mech.geom.cylinder.outer_radius": Interval(lo=0.03, hi=0.03),
    "mech.material.youngs_modulus": Interval(lo=2e11, hi=2e11),
    "mech.material.poisson": Interval(lo=0.3, hi=0.3),
}


# -- D95: structured coverage -------------------------------------------------


def test_swept_axis_reports_a_corners_coverage_axis() -> None:
    """A request with ONE non-degenerate input (`inner_radius`, an
    interval) reports exactly one structured `CoverageAxis`, method
    `corners` (06 "estimate(request)"); every pinned (`lo == hi`) input
    contributes none."""
    registry = ModelRegistry()
    registry.register(FeaStaticStressModel())
    request = DischargeRequest(
        claim_kind=DEFAULT_STRESS_CLAIM_KIND, limit=1.0e9, inputs=_STRESS_INPUTS
    )
    evidence = registry.discharge(request)
    axes = evidence.coverage.axes
    assert [a.axis for a in axes] == ["mech.geom.cylinder.inner_radius"]
    assert axes[0].method == CoverageMethod1.corners


def test_all_pinned_inputs_report_no_coverage_axes() -> None:
    """Every input pinned (`lo == hi`): the conservative-collapse
    `fraction` alone stands, no axes (nothing was swept)."""
    registry = ModelRegistry()
    registry.register(FeaStaticStressModel())
    pinned = {
        "mech.load.internal_pressure": Interval(lo=5e6, hi=5e6),
        "mech.geom.cylinder.inner_radius": Interval(lo=0.02, hi=0.02),
        "mech.geom.cylinder.outer_radius": Interval(lo=0.03, hi=0.03),
        "mech.material.youngs_modulus": Interval(lo=2e11, hi=2e11),
        "mech.material.poisson": Interval(lo=0.3, hi=0.3),
    }
    request = DischargeRequest(
        claim_kind=DEFAULT_STRESS_CLAIM_KIND, limit=1.0e9, inputs=pinned
    )
    evidence = registry.discharge(request)
    assert len(evidence.coverage.axes) == 0


# -- D97/A-10: regime channel --------------------------------------------------


def test_regime_channel_dispatches_both_ways() -> None:
    """A model constructed with a `required_regimes` override no-matches
    a request lacking the tag (honest `no_model`) and matches (reaches
    `estimate`) once the request carries it -- proven both ways without
    disturbing the v1 degenerate default (`required_regimes=()`) every
    OTHER test in this suite relies on."""
    registry = ModelRegistry()
    registry.register(FeaStaticStressModel(required_regimes=("mech.demo_regime",)))

    without_regime = DischargeRequest(
        claim_kind=DEFAULT_STRESS_CLAIM_KIND, limit=1.0e9, inputs=_STRESS_INPUTS
    )
    evidence_without = registry.discharge(without_regime)
    assert evidence_without.model_id == "harness.no_model"

    with_regime = DischargeRequest(
        claim_kind=DEFAULT_STRESS_CLAIM_KIND,
        limit=1.0e9,
        inputs=_STRESS_INPUTS,
        regimes=("mech.demo_regime",),
    )
    evidence_with = registry.discharge(with_regime)
    assert evidence_with.model_id.startswith("fea_static_stress")


def test_default_required_regimes_is_the_v1_degenerate_case() -> None:
    """No override (`required_regimes=()`, every OTHER model in `pack.
    register`): the model matches regardless of what `regimes` a request
    carries, including none at all -- the WO-27 conformance suite's own
    requests (which never set `regimes`) keep matching unchanged."""
    registry = ModelRegistry()
    registry.register(FeaStaticStressModel())
    request = DischargeRequest(
        claim_kind=DEFAULT_STRESS_CLAIM_KIND, limit=1.0e9, inputs=_STRESS_INPUTS
    )
    evidence = registry.discharge(request)
    assert evidence.model_id.startswith("fea_static_stress")


# -- D96: the payload-ref channel ----------------------------------------------


def _tip_force_inputs() -> dict:
    return {
        "mech.material.youngs_modulus": Interval(lo=7.0e10, hi=7.0e10),
        "mech.material.poisson": Interval(lo=0.33, hi=0.33),
        "mech.load.tip_force": Interval(lo=1.0e3, hi=1.0e3),
    }


def test_payload_needing_model_no_matches_honestly_without_the_payload() -> None:
    """`FeaStaticDeflectionFromGeometryModel` declares `payload_kinds`
    for the geometry ref: a request that never carries
    `mech.geom.cantilever.parametric` is an honest non-match (06
    "DischargeRequest.payloads consumed ... honest no_model")."""
    registry = ModelRegistry()
    registry.register(FeaStaticDeflectionFromGeometryModel())
    request = DischargeRequest(
        claim_kind="mech.static_deflection", limit=1.0, inputs=_tip_force_inputs()
    )
    evidence = registry.discharge(request)
    assert evidence.model_id == "harness.no_model"
    assert evidence.status.value == "indeterminate"


def test_payload_needing_model_matches_with_the_payload_present() -> None:
    """The SAME model, given the geometry payload ref, is SELECTED (the
    signature matches): resolution itself honestly indeterminates today
    (`pack.payload_bridge.NoStoreResolver` -- the escalated WO-14
    residual, no orchestrator store handle reaches `Model.estimate`
    yet), but selection -- the D96 deliverable this WO owns -- is
    proven."""
    registry = ModelRegistry()
    registry.register(FeaStaticDeflectionFromGeometryModel())
    request = DischargeRequest(
        claim_kind="mech.static_deflection",
        limit=1.0,
        inputs=_tip_force_inputs(),
        payloads={
            "mech.geom.cantilever.parametric": PayloadRef(
                kind="geometry.parametric",
                digest="blake3:" + "c" * 64,
                origin="test",
            )
        },
    )
    selected = registry.select(request)
    assert selected.is_ok
    assert selected.danger_ok.model_id.startswith("fea_static_deflection_from_geometry")

    evidence = registry.discharge(request)
    assert evidence.status.value == "indeterminate"
    assert evidence.model_id.startswith("fea_static_deflection_from_geometry")
