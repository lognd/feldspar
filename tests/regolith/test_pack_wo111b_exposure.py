from __future__ import annotations

"""WO111b (lithos WO-110-F6/F4, D223 feldspar fatigue depth): regolith
`Model` wrappers for the S-N cycles-to-failure scalar direction and the
Miner's-rule cumulative-damage payload direction
(`feldspar.library.fatigue`). The scalar wrapper reuses the exact
hand-computed/analytic-self-check values `tests/unit/test_library_
fatigue.py` already proved (docs/benchmarks-memo.md sec. 20) -- a
mismatch here means the wrapper plumbing is wrong, not the physics.
The payload wrapper follows `tests/regolith/test_payload_resolver_
bridge.py`'s exact no-resolver / working-resolver shape for
`FeaStaticDeflectionFromGeometryModel` (NO DUPLICATION of that
reasoning, same D154 opt-in mechanism applied to a different payload
port). Regolith-marked (needs a lithos checkout; run from the real
checkout, not this worktree)."""

import json
import math

import pytest
from regolith._schema import SCHEMA_VERSION
from regolith._schema.models import PayloadRef as RegolithPayloadRef
from regolith.harness.model import DischargeRequest
from regolith.harness.quantity import Interval
from typani.result import Err, Ok, Result

from feldspar.pack.models import (
    DEFAULT_FATIGUE_CYCLES_TO_FAILURE_CLAIM_KIND,
    DEFAULT_FATIGUE_DAMAGE_CLAIM_KIND,
    FatigueMinerDamageModel,
    FatigueSnCyclesToFailureModel,
)

pytestmark = pytest.mark.regolith

_SPECTRUM_PORT = "mech.fatigue.miner.spectrum"
_DIGEST = "blake3:" + "b" * 64

# Same fixture constants as tests/unit/test_library_fatigue.py's
# ANALYTIC SELF-CHECK (docs/benchmarks-memo.md sec. 20).
_SN_SUT = 700.0e6
_SN_SE = 350.0e6
_SN_F = 0.9
_SN_KNEE = _SN_F * _SN_SUT


def _pinned(value: float) -> Interval:
    return Interval(lo=value, hi=value)


def test_sn_cycles_to_failure_at_knee_matches_1000() -> None:
    """sigma_a = f*Sut -> N = 1e3 exactly (the knee line's own defining
    boundary condition, memo sec. 20.1)."""
    model = FatigueSnCyclesToFailureModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_FATIGUE_CYCLES_TO_FAILURE_CLAIM_KIND,
        limit=0.0,
        inputs={
            "mech.fatigue.sn.sigma_a": _pinned(_SN_KNEE),
            "mech.fatigue.sn.sut": _pinned(_SN_SUT),
            "mech.fatigue.sn.se": _pinned(_SN_SE),
            "mech.fatigue.sn.f": _pinned(_SN_F),
        },
    )
    prediction = model.estimate(request).danger_ok
    assert prediction.value == pytest.approx(1.0e3, rel=1e-6)
    assert prediction.in_domain


def test_sn_cycles_to_failure_at_se_matches_1e6() -> None:
    """sigma_a = Se -> N = 1e6 exactly (the line's other defining
    point)."""
    model = FatigueSnCyclesToFailureModel()
    request = DischargeRequest(
        claim_kind=DEFAULT_FATIGUE_CYCLES_TO_FAILURE_CLAIM_KIND,
        limit=0.0,
        inputs={
            "mech.fatigue.sn.sigma_a": _pinned(_SN_SE),
            "mech.fatigue.sn.sut": _pinned(_SN_SUT),
            "mech.fatigue.sn.se": _pinned(_SN_SE),
            "mech.fatigue.sn.f": _pinned(_SN_F),
        },
    )
    prediction = model.estimate(request).danger_ok
    assert prediction.value == pytest.approx(1.0e6, rel=1e-6)
    assert prediction.in_domain


# --- FatigueMinerDamageModel (payload channel) ------------------------------


def _fake_lithos_resolver(responses: dict) -> "object":
    """Same stand-in shape `test_payload_resolver_bridge.py` uses for
    `Model.discharge`'s threaded lithos resolver callable."""

    def _resolve(digest: str) -> Result:
        if digest not in responses:
            return Err(f"no fixture bytes for digest {digest!r}")
        return Ok(responses[digest])

    return _resolve


def _valid_spectrum_envelope() -> bytes:
    """A Miner-spectrum-shaped envelope carrying the D154
    `schema_version` field: one block at its own S-N life (D=1.0 by
    construction, same identity `tests/unit/test_library_fatigue.py`
    checks)."""
    a = (_SN_KNEE**2) / _SN_SE
    b = -(1.0 / 3.0) * math.log10(_SN_KNEE / _SN_SE)
    sigma_a = (_SN_KNEE + _SN_SE) / 2.0
    n_life = (sigma_a / a) ** (1.0 / b)
    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "sigma_a": [sigma_a],
            "cycles": [n_life],
        },
        sort_keys=True,
    ).encode("ascii")


def _damage_request(digest: str = _DIGEST) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=DEFAULT_FATIGUE_DAMAGE_CLAIM_KIND,
        limit=1.0,
        inputs={
            "mech.fatigue.miner.sut": _pinned(_SN_SUT),
            "mech.fatigue.miner.se": _pinned(_SN_SE),
            "mech.fatigue.miner.f": _pinned(_SN_F),
        },
        payloads={
            _SPECTRUM_PORT: RegolithPayloadRef(
                kind="spectrum", digest=digest, origin="fixture"
            )
        },
    )


# frob:tests python/feldspar/pack/models.py::FatigueMinerDamageModel.estimate kind="unit"
def test_miner_damage_no_resolver_is_honest_indeterminate() -> None:
    """No `resolver` threaded: the pre-D154 `NoStoreResolver` honest
    path, same as `FeaStaticDeflectionFromGeometryModel`'s no-resolver
    case (`test_payload_resolver_bridge.py`)."""
    model = FatigueMinerDamageModel()
    result = model.estimate(_damage_request())
    assert result.is_err
    assert "regolith.orchestrator.payload_store" in result.danger_err.message


def test_miner_damage_no_resolver_stays_honest_after_a_resolver_run_cached(
    tmp_path,
) -> None:
    """Regression (integration failure at WO-118 close, found via
    `SolveCache`'s key not folding resolver participation): run the
    SAME request first WITH a working resolver (a real `Ok` populates
    `.feldspar/cache`), then WITHOUT one -- the no-resolver call must
    still honestly indeterminate, never a stale cache hit replaying the
    resolver-run's `Ok`. The `_isolate_feldspar_cache` autouse fixture
    already chdirs into a fresh `tmp_path`; this test additionally
    asserts a cache entry actually exists there after the first call,
    so a future change that silently disables caching cannot make this
    test pass for the wrong reason."""
    model = FatigueMinerDamageModel()
    resolver = _fake_lithos_resolver({_DIGEST: _valid_spectrum_envelope()})

    with_resolver = model.estimate(_damage_request(), resolver=resolver)
    assert with_resolver.is_ok, (
        f"expected the priming resolver-run to succeed: {with_resolver}"
    )

    cache_dir = tmp_path / ".feldspar" / "cache"
    assert list(cache_dir.glob("*.json")), (
        "expected the resolver-run to have populated the on-disk solve "
        "cache -- otherwise this test cannot exercise the leak it guards "
        "against"
    )

    without_resolver = model.estimate(_damage_request())
    assert without_resolver.is_err, (
        f"a stale cache entry from the resolver-run leaked into the "
        f"no-resolver call: {without_resolver}"
    )
    assert "regolith.orchestrator.payload_store" in without_resolver.danger_err.message


def test_miner_damage_working_resolver_matches_hand_computed() -> None:
    """A WORKING lithos resolver threaded: the spectrum resolves and
    the accumulated damage matches the D=1.0 construction (block
    cycles == block life, docs/benchmarks-memo.md sec. 20.2)."""
    model = FatigueMinerDamageModel()
    resolver = _fake_lithos_resolver({_DIGEST: _valid_spectrum_envelope()})
    result = model.estimate(_damage_request(), resolver=resolver)
    assert result.is_ok, (
        f"expected the spectrum to resolve and the closed-form Miner "
        f"sum to run to completion: {result}"
    )
    assert result.danger_ok.value == pytest.approx(1.0, rel=1e-6)
    assert result.danger_ok.in_domain
