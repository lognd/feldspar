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
    civil_utilization_h1,
    extract_member_demands,
    register,
    resolve_tributary_loads,
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


# frob:tests crates/feldspar-py/src/library/mech.rs::mech_frame2d_solve_py
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


# frob:tests python/feldspar/mech/struct.py::solve_frame_payload kind="unit"
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


def test_unmatched_point_load_target_is_honest_indeterminate():
    """M7 (cycle-28 audit): the joint point-load loop had the same
    silent-drop pattern as M2 -- a `"point"`-kind load whose target
    matches no joint id must be an honest `Err`, never silently
    dropped (contributing zero demand)."""
    payload = _propped_cantilever_payload(10e3, 6.0)
    payload["loads"].append(
        {
            "case": "dead",
            "target": "NoSuchJoint",
            "kind": "point",
            "value": _interval(5e3),
            "direction": "gravity",
        }
    )
    section_material = {"G1": {"ea": 1e12, "ei": 6.0e7}}
    result = solve_frame_payload(payload, section_material, "dead")
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
    assert "NoSuchJoint" in result.err.violation


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


# --- WO-23: tributary load paths + resolved-frame consumption -----------


def test_tributary_width_transfer_reproduces_benchmarks_memo_1_1():
    """WO-23 deliverable 1/4 calibration case: a `Bearing(tributary=
    width)` transfer from a source deck surface, at pressure=2 kPa
    over a tributary width=5 m (2000 Pa x 5 m = 10 kN/m), must
    reproduce benchmarks memo 1.1's own w=10 kN/m closed-form
    propped-cantilever result EXACTLY -- proof the tributary-derived
    load is arithmetically identical to a direct declaration, not a
    second, divergent load-application path."""
    length = 6.0
    w = 10e3  # N/m, the memo 1.1 anchor
    payload = _propped_cantilever_payload(0.0, length)  # no direct load
    payload["loads"] = []  # G1's demand arrives ONLY via the transfer
    section_material = {"G1": {"ea": 1e12, "ei": 6.0e7}}
    transfers = [
        {
            "id": "deck_g1",
            "kind": "Bearing",
            "from": "Deck",
            "to": "G1",
            "tributary": {"kind": "width", "value": _interval(5.0)},
        }
    ]
    source_intensities = {("Deck", "dead"): _interval(2000.0)}  # 2 kPa

    result = solve_frame_payload(
        payload,
        section_material,
        "dead",
        transfers=transfers,
        source_intensities=source_intensities,
    )
    assert result.is_ok, result.err
    solved = result.danger_ok

    assert _close(solved["reactions"]["A"][1], 5.0 * w * length / 8.0)
    assert _close(solved["reactions"]["B"][1], 3.0 * w * length / 8.0)
    assert _close(abs(solved["reactions"]["A"][2]), w * length * length / 8.0)
    assert len(solved["load_path"]) == 1
    evidence = solved["load_path"][0]
    assert evidence["transfer"] == "deck_g1"
    assert evidence["from"] == "Deck"
    assert evidence["to"] == "G1"
    assert _close(evidence["derived_udl_si"], w)


def test_tributary_area_transfer_spreads_resultant_over_member_length():
    """An `area` tributary yields a total resultant force that this
    module spreads over the RECEIVING member's own length (declared
    tributary geometry x source intensity -- no inferred width, per
    feldspar's standing law): pressure=1 kPa x area=30 m^2 = 30 kN
    total, over a 6 m receiving member -> w=5 kN/m."""
    length = 6.0
    payload = _propped_cantilever_payload(0.0, length)
    payload["loads"] = []
    section_material = {"G1": {"ea": 1e12, "ei": 6.0e7}}
    transfers = [
        {
            "id": "deck_g1",
            "kind": "Bearing",
            "from": "Deck",
            "to": "G1",
            "tributary": {"kind": "area", "value": _interval(30.0)},
        }
    ]
    source_intensities = {("Deck", "dead"): _interval(1000.0)}  # 1 kPa

    result = solve_frame_payload(
        payload,
        section_material,
        "dead",
        transfers=transfers,
        source_intensities=source_intensities,
    )
    assert result.is_ok, result.err
    w_expected = 1000.0 * 30.0 / length
    assert _close(result.danger_ok["load_path"][0]["derived_udl_si"], w_expected)
    assert _close(
        result.danger_ok["reactions"]["A"][1], 5.0 * w_expected * length / 8.0
    )


def test_bearing_without_declared_tributary_stays_honestly_deferred():
    """calcite/02 sec. 6: tributary assignment is declarative -- a
    `Bearing` transfer with no `tributary=` set must NOT contribute any
    inferred load (the WO-48 `frame_load_untargeted` posture: a member
    whose tributary is not declared stays deferred, never guessed).
    G1 ends up with zero applied load and a trivial (zero) solve."""
    length = 6.0
    payload = _propped_cantilever_payload(0.0, length)
    payload["loads"] = []
    section_material = {"G1": {"ea": 1e12, "ei": 6.0e7}}
    transfers = [
        {
            "id": "deck_g1",
            "kind": "Bearing",
            "from": "Deck",
            "to": "G1",
            "tributary": None,
        }
    ]
    source_intensities = {("Deck", "dead"): _interval(2000.0)}

    result = solve_frame_payload(
        payload,
        section_material,
        "dead",
        transfers=transfers,
        source_intensities=source_intensities,
    )
    assert result.is_ok, result.err
    assert result.danger_ok["load_path"] == []
    assert _close(result.danger_ok["reactions"]["A"][1], 0.0, tol=1.0)


# frob:tests python/feldspar/mech/struct.py::resolve_tributary_loads kind="unit"
def test_area_tributary_without_receiving_member_length_is_honest_indeterminate():
    """An `area` tributary needs the receiving member's length to
    spread the resultant into a UDL -- `resolve_tributary_loads` must
    refuse to guess one, never silently skip the spreading step."""
    transfers = [
        {
            "id": "deck_g1",
            "kind": "Bearing",
            "from": "Deck",
            "to": "Ghost",
            "tributary": {"kind": "area", "value": _interval(30.0)},
        }
    ]
    source_intensities = {("Deck", "dead"): _interval(1000.0)}
    result = resolve_tributary_loads(transfers, source_intensities, "dead", {})
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
    assert "Ghost" in result.err.violation


def test_extract_member_demands_reduces_end_forces_to_envelope():
    """WO-23 deliverable 2: `extract_member_demands` reduces the raw
    6-component local end-force vector to the worst-case abs(axial/
    shear/moment) envelope per member."""
    result = {
        "member_end_forces": {
            "G1": [1.0, -37.5e3, -45.0e3, -1.0, 22.5e3, 0.0],
        }
    }
    demands = extract_member_demands(result)
    assert demands == {"G1": {"axial": 1.0, "shear": 37.5e3, "moment": 45.0e3}}


def test_civil_utilization_h1_matches_hand_computed_interaction():
    """WO-23 deliverable 3: AISC 360-16 eq. H1-1a/b hand-computed
    check. Pr/Pc=0.5 (>=0.2, uses H1-1a): 0.5 + 8/9*(200/500)=0.5+
    0.3556=0.8556 -> Valid. Pr/Pc=0.1 (<0.2, uses H1-1b):
    0.1/2 + 100/500 = 0.05+0.2=0.25 -> Valid."""
    r1 = civil_utilization_h1(
        axial_demand=500e3,
        moment_demand=200e3,
        axial_capacity=1000e3,
        moment_capacity=500e3,
    )
    assert r1.is_ok
    ratio1, verdict1 = r1.danger_ok
    assert _close(ratio1, 0.5 + (8.0 / 9.0) * 0.4)
    assert verdict1 == "Valid"

    r2 = civil_utilization_h1(
        axial_demand=100e3,
        moment_demand=100e3,
        axial_capacity=1000e3,
        moment_capacity=500e3,
    )
    assert r2.is_ok
    ratio2, verdict2 = r2.danger_ok
    assert _close(ratio2, 0.05 + 0.2)
    assert verdict2 == "Valid"


def test_civil_utilization_h1_violated_over_unity():
    result = civil_utilization_h1(
        axial_demand=900e3,
        moment_demand=450e3,
        axial_capacity=1000e3,
        moment_capacity=500e3,
    )
    assert result.is_ok
    ratio, verdict = result.danger_ok
    assert ratio > 1.0
    assert verdict == "Violated"


def test_civil_utilization_h1_nonpositive_capacity_is_honest_indeterminate():
    result = civil_utilization_h1(
        axial_demand=100e3,
        moment_demand=100e3,
        axial_capacity=0.0,
        moment_capacity=500e3,
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_small_office_g2_ab_girder_tributary_fixture_discharges_end_to_end():
    """WO-23 deliverable 5 (conformance-run readiness fixture): mirrors
    lithos calcite corpus member `small_office`'s second-floor girder
    `G2_AB` (`examples/lithos/systems/small_office/frame.calx`, `member
    G2_AB: beam ... from (A, 2, second) to (B, 2, second)`), whose
    entire "dead"-case demand this repo can resolve arrives ONLY
    through its declared transfer `d2_g2: Bearing(tributary=43.2m2)
    (Deck2 -> G2_AB)` -- exactly the WO-48 close-out's "girder-under-
    slab" architectural finding this WO exists to close. `section:
    free` (an L3 search variable) and the real ASCE7 `live:` load-case
    derivation are OUT of this fixture's scope (named residuals below);
    this fixture supplies an ALREADY-RESOLVED section (the
    `solve_frame_payload`/`civil_utilization_h1` out-of-band seam,
    matching every other test in this file) and a single "dead"-case
    intensity on `Deck2`, to prove the tributary-transfer path
    discharges Valid/Violated for real, then reverts to the honest
    `frame_load_untargeted`-shaped deferral when the tributary
    declaration is removed (Acceptance criterion 1)."""
    length = 8.0  # illustrative bay span -- calcite v1 carries no
    # resolved numeric grid coordinate (WO-21 close-out cut 2); the
    # corpus source only names the datum pair, not a distance.
    payload = {
        "joints": [{"id": "A2", "at": None}, {"id": "B2", "at": None}],
        "members": [
            {
                "id": "G2_AB",
                "role": "beam",
                "a": "A2",
                "b": "B2",
                "length": _interval(length),
                "orientation": "horizontal",
                "section": _resolved_ref("w410x60"),  # stand-in for L3 `free`
                "material": _resolved_ref("astm_a992"),
                "releases": _releases(),
            }
        ],
        "supports": [
            {"joint": "A2", "fixity": ["x", "y", "rz"]},
            {"joint": "B2", "fixity": ["y", "rz"]},
        ],
        "loads": [],  # G2_AB carries no direct literal load in the corpus
        "combinations": _unresolved_ref(),
    }
    section_material = {"G2_AB": {"ea": 1e12, "ei": 8.0e7}}
    transfers = [
        {
            "id": "d2_g2",
            "kind": "Bearing",
            "from": "Deck2",
            "to": "G2_AB",
            "tributary": {"kind": "area", "value": _interval(43.2)},
        }
    ]
    # Illustrative dead intensity (stand-in for the corpus's `derived`
    # self-weight case -- computing THAT from a resolved section is a
    # separate, already-cut concern, WO-21 close-out).
    source_intensities = {("Deck2", "dead"): _interval(2500.0)}  # 2.5 kPa

    resolved = solve_frame_payload(
        payload,
        section_material,
        "dead",
        transfers=transfers,
        source_intensities=source_intensities,
    )
    assert resolved.is_ok, resolved.err
    solved = resolved.danger_ok
    assert len(solved["load_path"]) == 1
    assert solved["load_path"][0]["from"] == "Deck2"
    assert solved["load_path"][0]["to"] == "G2_AB"

    demands = extract_member_demands(solved)["G2_AB"]
    # Stand-in resolved capacity (a real run needs the L3-resolved
    # section's Pn/Mn from std.civil capacity tables -- not built here,
    # WO-21 close-out cut 1/4; this proves the check ARITHMETIC given
    # resolved numbers, the WO-23 scope line).
    util = civil_utilization_h1(
        axial_demand=demands["axial"],
        moment_demand=demands["moment"],
        axial_capacity=1.0e6,
        moment_capacity=demands["moment"] * 1.5,
    )
    assert util.is_ok
    ratio, verdict = util.danger_ok
    assert verdict in ("Valid", "Violated")
    assert ratio > 0.0

    # Acceptance criterion 1's second half: removing the tributary
    # declaration reverts to the honest deferral (zero load applied,
    # no fabricated demand).
    transfers_no_trib = [
        {
            "id": "d2_g2",
            "kind": "Bearing",
            "from": "Deck2",
            "to": "G2_AB",
            "tributary": None,
        }
    ]
    deferred = solve_frame_payload(
        payload,
        section_material,
        "dead",
        transfers=transfers_no_trib,
        source_intensities=source_intensities,
    )
    assert deferred.is_ok, deferred.err
    assert deferred.danger_ok["load_path"] == []
    assert _close(deferred.danger_ok["reactions"]["A2"][1], 0.0)
