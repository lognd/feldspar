from __future__ import annotations

"""WO-13 (09 sec. 5, 06 "margin-driven adaptive refinement"): the
pack-side margin translation -- `_FeaModel.estimate` converts the
claim's margin (`DischargeRequest.limit` vs the solved value) into an
eps budget and re-drives the engine's budget-seeking refinement,
deterministically; a refinement the engine cannot meet is an honest
indeterminate STATING eps achieved vs needed.

The engine seam (`feldspar.pack.models.solve`) is monkeypatched with a
scripted fake so the TRANSLATION LOGIC is exercised hermetically (no
gmsh/ccx); the engine-side ladder behavior itself is covered by
tests/unit/test_fea_ladder.py and test_fea_solver_seeking.py."""

from types import SimpleNamespace

import pytest
from regolith.harness.model import DischargeRequest
from regolith.harness.quantity import Interval
from typani import Err, Ok

import feldspar.pack.models as pack_models
from feldspar.pack.models import _EPS_BUDGET, FeaStaticDeflectionModel
from feldspar.solve.errors import SolveError

pytestmark = pytest.mark.regolith

_DEFLECTION_INPUTS = {
    "mech.geom.cantilever.length": Interval(lo=0.5, hi=0.5),
    "mech.geom.cantilever.width": Interval(lo=0.04, hi=0.04),
    "mech.geom.cantilever.height": Interval(lo=0.06, hi=0.06),
    "mech.material.youngs_modulus": Interval(lo=7e10, hi=7e10),
    "mech.material.poisson": Interval(lo=0.33, hi=0.33),
    "mech.load.tip_force": Interval(lo=1000.0, hi=1000.0),
}


def _request(limit: float) -> DischargeRequest:
    return DischargeRequest(
        claim_kind="mech.static_deflection",
        limit=limit,
        inputs=_DEFLECTION_INPUTS,
    )


def _solution(value: float, eps: float) -> SimpleNamespace:
    """The minimal Solution shape `estimate()` reads (value.hi/.lo, eps,
    settings_digest)."""
    return SimpleNamespace(
        value=SimpleNamespace(hi=value, lo=value),
        eps=eps,
        settings_digest="fake-digest",
    )


def _install_fake_solve(monkeypatch, script):
    """Replace the engine seam with a scripted fake: `script` is a list
    of Ok/Err results returned in order; every received eps_budget is
    recorded for assertion."""
    budgets: list = []
    remaining = list(script)

    def fake_solve(registry, known, tags, target, eps_budget, sense=None, **kwargs):
        budgets.append(eps_budget)
        return remaining.pop(0)

    monkeypatch.setattr(pack_models, "solve", fake_solve)
    return budgets


# frob:tests python/feldspar/pack/models.py::_FeaModel.estimate kind="unit"
def test_fat_margin_closes_on_the_first_loose_attempt(monkeypatch) -> None:
    """value + eps already within the limit: exactly ONE engine call at
    the loose first budget, no margin translation."""
    budgets = _install_fake_solve(monkeypatch, [Ok(_solution(value=5.0, eps=0.1))])
    result = FeaStaticDeflectionModel().estimate(_request(limit=10.0))
    assert result.is_ok
    prediction = result.danger_ok
    assert prediction.value == 5.0
    assert prediction.eps == 0.1
    assert budgets == [_EPS_BUDGET]


def test_thin_margin_translates_margin_into_eps_budget(monkeypatch) -> None:
    """First attempt's eps (1.0) busts the margin (limit 5.5 - value
    5.0 = 0.5): the model re-solves with eps_budget == the margin, and
    the refined answer closes."""
    budgets = _install_fake_solve(
        monkeypatch,
        [
            Ok(_solution(value=5.0, eps=1.0)),
            Ok(_solution(value=5.05, eps=0.4)),
        ],
    )
    result = FeaStaticDeflectionModel().estimate(_request(limit=5.5))
    assert result.is_ok
    prediction = result.danger_ok
    assert prediction.value == 5.05
    assert prediction.eps == 0.4  # value + eps = 5.45 <= 5.5: closed
    assert budgets == [_EPS_BUDGET, 0.5]  # margin translated verbatim


def test_refinement_exhaustion_states_eps_achieved_vs_needed(monkeypatch) -> None:
    """The engine cannot meet the translated budget (ladder top-out):
    honest indeterminate whose message states eps achieved vs needed
    (regolith's what-would-resolve-it family, 09 sec. 5)."""
    budgets = _install_fake_solve(
        monkeypatch,
        [
            Ok(_solution(value=5.0, eps=1.0)),
            Err(SolveError.LadderExhausted(best_eps=0.8, budget=0.5, rungs_tried=4)),
        ],
    )
    result = FeaStaticDeflectionModel().estimate(_request(limit=5.5))
    assert result.is_err
    error = result.danger_err
    assert "eps achieved 1.0" in error.message
    assert "needed 0.5" in error.message
    assert "LadderExhausted" in error.message
    assert budgets == [_EPS_BUDGET, 0.5]


def test_value_busting_the_limit_returns_honest_prediction(monkeypatch) -> None:
    """No positive margin exists (value alone exceeds the upper limit):
    refinement cannot close the claim, so the honest prediction returns
    after exactly one engine call -- never a doomed refinement spiral."""
    budgets = _install_fake_solve(monkeypatch, [Ok(_solution(value=6.0, eps=0.3))])
    result = FeaStaticDeflectionModel().estimate(_request(limit=5.5))
    assert result.is_ok
    prediction = result.danger_ok
    assert prediction.value == 6.0
    assert prediction.eps == 0.3
    assert budgets == [_EPS_BUDGET]


def test_first_attempt_engine_failure_maps_plainly(monkeypatch) -> None:
    """A failure BEFORE any successful answer has no margin story: the
    plain engine-error mapping applies (06 "Failures"), not the
    margin-exhausted rendering."""
    _install_fake_solve(
        monkeypatch,
        [Err(SolveError.ToolMissing(tool="gmsh", guidance="install it"))],
    )
    result = FeaStaticDeflectionModel().estimate(_request(limit=5.5))
    assert result.is_err
    assert "feldspar engine failure" in result.danger_err.message
    assert "eps achieved" not in result.danger_err.message


def test_margin_seeking_is_deterministic_twice(monkeypatch) -> None:
    """Same request, same scripted engine -> identical budget sequence
    and identical prediction, run twice (09 sec. 5: driven by the
    margin, deterministically)."""
    script = [
        Ok(_solution(value=5.0, eps=1.0)),
        Ok(_solution(value=5.05, eps=0.4)),
    ]
    budgets_1 = _install_fake_solve(monkeypatch, list(script))
    result_1 = FeaStaticDeflectionModel().estimate(_request(limit=5.5))
    budgets_2 = _install_fake_solve(monkeypatch, list(script))
    result_2 = FeaStaticDeflectionModel().estimate(_request(limit=5.5))

    assert budgets_1 == budgets_2
    assert result_1.danger_ok.value == result_2.danger_ok.value
    assert result_1.danger_ok.eps == result_2.danger_ok.eps


def test_attempt_bound_returns_best_achieved(monkeypatch) -> None:
    """A pathological value drifting toward the limit: the loop stops at
    the attempt bound and returns the best achieved prediction rather
    than spiraling (each re-solve still used a strictly tighter
    budget)."""
    script = [
        Ok(_solution(value=5.0, eps=1.0)),  # needed 0.5
        Ok(_solution(value=5.2, eps=0.45)),  # needed 0.3
        Ok(_solution(value=5.3, eps=0.25)),  # needed 0.2
        Ok(_solution(value=5.4, eps=0.15)),  # needed 0.1 -- bound hit
    ]
    budgets = _install_fake_solve(monkeypatch, script)
    result = FeaStaticDeflectionModel().estimate(_request(limit=5.5))
    assert result.is_ok
    prediction = result.danger_ok
    assert prediction.value == 5.4
    assert prediction.eps == 0.15
    assert budgets == [_EPS_BUDGET, 0.5, pytest.approx(0.3), pytest.approx(0.2)]
