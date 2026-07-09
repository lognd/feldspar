from __future__ import annotations

"""WO-21 tests: `python/feldspar/library/struct.py`'s `mech.struct`
direct-stiffness frame consumer. `solve_frame_payload` is exercised
directly against synthetic `FramePayload`-shaped dicts (calcite/03
sec. 4 field list) for the benchmarks memo's compatible (horizontal-
member) cases; the registered `SolverRegistry` direction is exercised
separately for its honest-indeterminate behavior on unresolved
section/material refs (the WO-21 close-out's named cut)."""

import hashlib
import json
from typing import Dict

from typani import Err, Ok

from feldspar.library.struct import (
    FRAME_PORT,
    register,
    solve_frame_payload,
)
from feldspar.solve import PayloadRef, SolveError, SolverRegistry

_TOL = 1e-3


def _close(a: float, b: float, tol: float = _TOL) -> bool:
    if abs(b) < 1e-9:
        return abs(a - b) < 1e-6
    return abs((a - b) / b) < tol


def _interval(value: float) -> dict:
    return {"lo": value, "hi": value, "unit": "1"}


def _resolved_ref(name: str) -> dict:
    return {"digest": f"blake3:{name}", "name": name}


def _unresolved_ref() -> dict:
    return {"digest": "", "name": "free"}


def _releases(a: list[str] | None = None, b: list[str] | None = None) -> dict:
    return {"a": a or [], "b": b or []}


class DictResolver:
    """In-memory orchestrator store stand-in (D96/OPEN-2 handle);
    mirrors `tests/unit/test_library_vibe.py`'s fixture verbatim."""

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


def _propped_cantilever_payload(w: float, length: float) -> dict:
    """Benchmarks memo 1.1: fixed at A, roller at B, UDL w over L."""
    return {
        "joints": [
            {"id": "A", "at": None},
            {"id": "B", "at": None},
        ],
        "members": [
            {
                "id": "G1",
                "role": "beam",
                "a": "A",
                "b": "B",
                "length": _interval(length),
                "orientation": "horizontal",
                "section": _resolved_ref("wshape"),
                "material": _resolved_ref("astm_a992"),
                "releases": _releases(),
            }
        ],
        "supports": [
            {"joint": "A", "fixity": ["x", "y", "rz"]},
            {"joint": "B", "fixity": ["y"]},
        ],
        "loads": [
            {
                "case": "dead",
                "target": "G1",
                "kind": "distributed",
                "value": _interval(w),
                "direction": "gravity",
            }
        ],
        "combinations": _unresolved_ref(),
    }


def test_propped_cantilever_udl_matches_closed_form():
    """Benchmarks memo 1.1 numeric anchor: w=10 kN/m, L=6 m,
    EI=6.0e7 N m^2 -> R_A=37.5 kN, R_B=22.5 kN, |M_A|=45.0 kN m."""
    w, length = 10e3, 6.0
    payload = _propped_cantilever_payload(w, length)
    section_material = {"G1": {"ea": 1e12, "ei": 6.0e7}}

    result = solve_frame_payload(payload, section_material, "dead")
    assert result.is_ok, result.err
    solved = result.danger_ok

    r_a_y = solved["reactions"]["A"][1]
    r_b_y = solved["reactions"]["B"][1]
    m_a = solved["reactions"]["A"][2]

    assert _close(r_a_y, 5.0 * w * length / 8.0)
    assert _close(r_b_y, 3.0 * w * length / 8.0)
    assert _close(abs(m_a), w * length * length / 8.0)
    # Fixture's member release list is empty (unresolved) -> the
    # documented rigid default applies and is recorded, never silent
    # (see test_empty_member_release_defaults_to_rigid_and_is_recorded).
    # The load-value ".hi" corner choice is likewise recorded (M3,
    # cycle-28 audit).
    assert len(solved["assumptions"]) == 2
    assert any("rigid" in a for a in solved["assumptions"])
    assert any(".hi" in a for a in solved["assumptions"])


def test_empty_member_release_defaults_to_rigid_and_is_recorded():
    """calcite/03 sec. 4: an empty `Releases` list is the payload's
    "unresolved" state; this module's documented engineering default
    (rigid) must both apply AND be named in `assumptions` (never
    silent)."""
    payload = _propped_cantilever_payload(10e3, 6.0)
    section_material = {"G1": {"ea": 1e12, "ei": 6.0e7}}
    result = solve_frame_payload(payload, section_material, "dead")
    assert result.is_ok
    assert any("rigid" in a for a in result.danger_ok["assumptions"])


def test_unresolved_support_fixity_is_honest_indeterminate():
    """An empty support `fixity` list has no safe engineering default
    (unlike member releases) -- must be `Err`, never a guessed pin/
    fixed/roller assumption."""
    payload = _propped_cantilever_payload(10e3, 6.0)
    payload["supports"][1]["fixity"] = []  # roller support unresolved
    section_material = {"G1": {"ea": 1e12, "ei": 6.0e7}}
    result = solve_frame_payload(payload, section_material, "dead")
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
    assert "unresolved fixity" in result.err.violation


def test_inclined_member_orientation_is_honest_indeterminate():
    """An `"inclined"`/`"point"` member has no derivable (dx, dy)
    from this payload alone (no resolved joint coordinates) -- must be
    `Err`, never a fabricated angle."""
    payload = _propped_cantilever_payload(10e3, 6.0)
    payload["members"][0]["orientation"] = "inclined"
    section_material = {"G1": {"ea": 1e12, "ei": 6.0e7}}
    result = solve_frame_payload(payload, section_material, "dead")
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
    assert "orientation" in result.err.violation


def test_missing_section_material_is_honest_indeterminate():
    """No out-of-band resolved EA/EI supplied for a member -> `Err`,
    never a fabricated property."""
    payload = _propped_cantilever_payload(10e3, 6.0)
    result = solve_frame_payload(payload, {}, "dead")
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
    assert "no resolved section/material" in result.err.violation


def test_unmatched_distributed_load_target_is_honest_indeterminate():
    """M2 (cycle-28 audit): `regolith-lower::frame_lower::on_target`
    extracts a level/region/deck name for civil designs, not a member
    id -- a distributed load whose target matches no member must be an
    honest `Err`, never silently dropped (contributing zero demand)."""
    payload = _propped_cantilever_payload(10e3, 6.0)
    payload["loads"][0]["target"] = "Deck"  # not a member id
    section_material = {"G1": {"ea": 1e12, "ei": 6.0e7}}
    result = solve_frame_payload(payload, section_material, "dead")
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
    assert "Deck" in result.err.violation


def test_member_length_in_millimeters_is_normalized_to_si():
    """M4 (cycle-28 audit): `frame_lower::member_length` only
    *defaults* the length unit to `"m"` -- it propagates whatever unit
    the source grid/level datums carry. A `mm`-unit length must be
    normalized to SI meters (not treated as if it were already
    meters), so a `[lo=6000, hi=6000, unit="mm"]` length reproduces the
    same closed-form result as `length=6.0` meters."""
    w = 10e3
    payload = _propped_cantilever_payload(w, 6.0)
    payload["members"][0]["length"] = {"lo": 6000.0, "hi": 6000.0, "unit": "mm"}
    section_material = {"G1": {"ea": 1e12, "ei": 6.0e7}}

    result = solve_frame_payload(payload, section_material, "dead")
    assert result.is_ok, result.err
    solved = result.danger_ok
    length = 6.0
    assert _close(solved["reactions"]["A"][1], 5.0 * w * length / 8.0)
    assert _close(solved["reactions"]["B"][1], 3.0 * w * length / 8.0)
    assert _close(abs(solved["reactions"]["A"][2]), w * length * length / 8.0)


def test_member_length_nondegenerate_interval_is_honest_indeterminate():
    """M4 (cycle-28 audit): a resolved member length is expected to be
    a degenerate (`lo == hi`) interval (`frame_lower::member_length`
    always emits one) -- a genuine `lo != hi` range here means the
    producer-side invariant broke; that must be an honest `Err`, never
    a silent pick of one bound."""
    payload = _propped_cantilever_payload(10e3, 6.0)
    payload["members"][0]["length"] = {"lo": 5.0, "hi": 7.0, "unit": "m"}
    section_material = {"G1": {"ea": 1e12, "ei": 6.0e7}}
    result = solve_frame_payload(payload, section_material, "dead")
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_registry_direction_honestly_indeterminates_on_unresolved_refs():
    """The registered `mech.struct.frame2d` direction has no
    registry-resolution channel (WO-21 close-out cut): ANY frame
    payload -- even with resolved digests -- must indeterminate today,
    never silently skip or fabricate."""
    resolver = DictResolver()
    registry = SolverRegistry()
    register(registry, resolver)

    payload = _propped_cantilever_payload(10e3, 6.0)
    ref = resolver.store("frame", json.dumps(payload).encode(), origin="test")

    solvers = {info.solver_id: fn for info, fn in registry}
    result = solvers["mech.struct.frame2d"]({FRAME_PORT: ref})
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_two_span_continuous_beam_udl_matches_closed_form():
    """Benchmarks memo 1.3: two equal spans L, uniform w, simple
    supports at A (pinned), B (center), C -- w=12 kN/m, L=5 m ->
    R_A=R_C=22.5 kN, R_B=75.0 kN."""
    w, length = 12e3, 5.0
    payload = {
        "joints": [{"id": n, "at": None} for n in ("A", "B", "C")],
        "members": [
            {
                "id": "G1",
                "role": "beam",
                "a": "A",
                "b": "B",
                "length": _interval(length),
                "orientation": "horizontal",
                "section": _resolved_ref("wshape"),
                "material": _resolved_ref("astm_a992"),
                "releases": _releases(),
            },
            {
                "id": "G2",
                "role": "beam",
                "a": "B",
                "b": "C",
                "length": _interval(length),
                "orientation": "horizontal",
                "section": _resolved_ref("wshape"),
                "material": _resolved_ref("astm_a992"),
                "releases": _releases(),
            },
        ],
        "supports": [
            {"joint": "A", "fixity": ["x", "y"]},
            {"joint": "B", "fixity": ["y"]},
            {"joint": "C", "fixity": ["y"]},
        ],
        "loads": [
            {
                "case": "dead",
                "target": mid,
                "kind": "distributed",
                "value": _interval(w),
                "direction": "gravity",
            }
            for mid in ("G1", "G2")
        ],
        "combinations": _unresolved_ref(),
    }
    section_material = {
        "G1": {"ea": 1e12, "ei": 6.0e7},
        "G2": {"ea": 1e12, "ei": 6.0e7},
    }
    result = solve_frame_payload(payload, section_material, "dead")
    assert result.is_ok, result.err
    solved = result.danger_ok
    assert _close(solved["reactions"]["A"][1], 0.375 * w * length)
    assert _close(solved["reactions"]["C"][1], 0.375 * w * length)
    assert _close(solved["reactions"]["B"][1], 1.25 * w * length)
