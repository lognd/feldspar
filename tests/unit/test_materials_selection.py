from __future__ import annotations

"""T-0018 slice 5 tests: the materials-selection justification route
(`python/feldspar/materials/selection.py`), called THROUGH the
`SolverRegistry`/`SolveFn` protocol with an in-memory payload resolver
(same `DictResolver` fixture convention as
`tests/unit/test_library_fatigue.py`)."""

import hashlib
import json
from typing import Dict

import pytest
from typani import Err, Ok

from feldspar.materials.selection import (
    CANDIDATES_PORT,
    RANKED_CANDIDATES_PORT,
    register,
)
from feldspar.solve import PayloadRef, SolveError, SolverRegistry


class DictResolver:
    """In-memory orchestrator store stand-in; mirrors
    `tests/unit/test_library_fatigue.py`'s fixture verbatim."""

    def __init__(self) -> None:
        self._blobs: Dict[str, bytes] = {}

    def store(self, kind: str, content: bytes, origin: str) -> PayloadRef:
        digest = hashlib.sha256(content).hexdigest()
        self._blobs[digest] = content
        return PayloadRef(kind=kind, digest=digest, origin=origin)

    def resolve(self, ref: PayloadRef):
        blob = self._blobs.get(ref.digest)
        if blob is None:
            return Err(SolveError.DanglingDigest(digest=ref.digest))
        return Ok(blob)


def _registry(resolver=None):
    reg = SolverRegistry()
    resolver = resolver if resolver is not None else DictResolver()
    register(reg, resolver)
    return reg, resolver


def _solver(registry):
    for info, fn in registry:
        if info.solver_id == "materials.selection.rank_candidates_for_requirements":
            return info, fn
    raise AssertionError("selection direction not registered")


_CANDIDATES = [
    {
        "name": "AISI 4140",
        "achievable_hardness_hv": 550.0,
        "ideal_critical_diameter_m": 0.05,
        "cost_class": "low",
    },
    {
        "name": "AISI 4340",
        "achievable_hardness_hv": 600.0,
        "ideal_critical_diameter_m": 0.08,
        "cost_class": "medium",
    },
    {
        "name": "AISI 1045",
        "achievable_hardness_hv": 450.0,
        "ideal_critical_diameter_m": 0.02,
        "cost_class": "low",
    },
    {
        "name": "Maraging 300",
        "achievable_hardness_hv": 620.0,
        "ideal_critical_diameter_m": 0.10,
        "cost_class": "specialty",
    },
]


def _store_candidates(resolver, candidates=_CANDIDATES) -> PayloadRef:
    return resolver.store(
        kind="table",
        content=json.dumps(candidates).encode("utf-8"),
        origin="test",
    )


# frob:tests python/feldspar/materials/selection.py::register kind="unit"
def test_selection_ranks_eligible_candidates_by_hardness_margin():
    """1045 fails the hardness/diameter target; 4140/4340 both pass and
    stay within the medium cost ceiling; Maraging 300 passes hardness/
    diameter but exceeds the ceiling -- 4340 (larger margin) outranks
    4140."""
    registry, resolver = _registry()
    _info, fn = _solver(registry)
    candidates_ref = _store_candidates(resolver)
    result = fn(
        {
            "materials.selection.hardness_target_hv": 500.0,
            "materials.selection.required_diameter_m": 0.04,
            "materials.selection.cost_class_ceiling_rank": 1.0,
            CANDIDATES_PORT: candidates_ref,
        }
    )
    assert result.is_ok
    ranked_ref = result.danger_ok.payloads[RANKED_CANDIDATES_PORT]
    ranked = json.loads(resolver.resolve(ranked_ref).danger_ok)
    by_name = {c["name"]: c for c in ranked}

    assert by_name["AISI 4340"]["eligible"] is True
    assert by_name["AISI 4340"]["rank"] == 1
    assert by_name["AISI 4140"]["eligible"] is True
    assert by_name["AISI 4140"]["rank"] == 2

    assert by_name["AISI 1045"]["eligible"] is False
    assert by_name["AISI 1045"]["meets_hardness"] is False
    assert by_name["AISI 1045"]["meets_diameter"] is False
    assert by_name["AISI 1045"]["rank"] is None

    assert by_name["Maraging 300"]["eligible"] is False
    assert by_name["Maraging 300"]["meets_hardness"] is True
    assert by_name["Maraging 300"]["meets_diameter"] is True
    assert by_name["Maraging 300"]["meets_cost"] is False
    assert by_name["Maraging 300"]["rank"] is None


# frob:tests python/feldspar/materials/selection.py::register kind="unit"
def test_selection_reports_hardness_and_diameter_margins():
    registry, resolver = _registry()
    _info, fn = _solver(registry)
    candidates_ref = _store_candidates(resolver)
    result = fn(
        {
            "materials.selection.hardness_target_hv": 500.0,
            "materials.selection.required_diameter_m": 0.04,
            "materials.selection.cost_class_ceiling_rank": 3.0,
            CANDIDATES_PORT: candidates_ref,
        }
    )
    assert result.is_ok
    ranked_ref = result.danger_ok.payloads[RANKED_CANDIDATES_PORT]
    ranked = json.loads(resolver.resolve(ranked_ref).danger_ok)
    by_name = {c["name"]: c for c in ranked}
    assert by_name["AISI 4140"]["hardness_margin_hv"] == pytest.approx(50.0)
    assert by_name["AISI 4140"]["diameter_margin_m"] == pytest.approx(0.01)


# frob:tests python/feldspar/materials/selection.py::register kind="unit"
def test_selection_rejects_empty_candidate_pool():
    registry, resolver = _registry()
    _info, fn = _solver(registry)
    candidates_ref = _store_candidates(resolver, candidates=[])
    result = fn(
        {
            "materials.selection.hardness_target_hv": 500.0,
            "materials.selection.required_diameter_m": 0.04,
            "materials.selection.cost_class_ceiling_rank": 3.0,
            CANDIDATES_PORT: candidates_ref,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# frob:tests python/feldspar/materials/selection.py::register kind="unit"
def test_selection_rejects_unknown_cost_class():
    registry, resolver = _registry()
    _info, fn = _solver(registry)
    bad_candidates = [
        {
            "name": "Mystery Alloy",
            "achievable_hardness_hv": 600.0,
            "ideal_critical_diameter_m": 0.05,
            "cost_class": "unobtainium",
        }
    ]
    candidates_ref = _store_candidates(resolver, candidates=bad_candidates)
    result = fn(
        {
            "materials.selection.hardness_target_hv": 500.0,
            "materials.selection.required_diameter_m": 0.04,
            "materials.selection.cost_class_ceiling_rank": 3.0,
            CANDIDATES_PORT: candidates_ref,
        }
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


# frob:tests python/feldspar/materials/selection.py::register kind="unit"
# frob:tests python/feldspar/materials kind="integration"
def test_selection_registers_through_solver_registry():
    """Integration exercise: the selection route is discoverable
    through the standard SolverRegistry (the regolith-bridge-visible
    seam D270 ruling 3 asks for)."""
    registry, _resolver = _registry()
    ids = [info.solver_id for info, _fn in registry]
    assert "materials.selection.rank_candidates_for_requirements" in ids
