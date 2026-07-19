from __future__ import annotations

"""Civil/structural direct-stiffness solver direction (WO-21, 07
mech.struct Phase 6): consumes a `frame` payload (lithos
`regolith-oblig::frame::FramePayload`, calcite/03 sec. 4) and produces a
NEW `frame_result` payload carrying every joint displacement, support
reaction, and member end force from a 2D direct-stiffness solve
(`feldspar._feldspar.mech_frame2d_solve`, `crates/feldspar-library/src/
mech/frame.rs`).

SCOPE (honest, not the full 07 mech.struct Phase 6 wave -- see WO-21's
close-out for the complete cut list):

- 2D (planar) frame elements only. A member's GLOBAL geometry is
  derived from its `orientation` field (`"horizontal"` -> `dx=length,
  dy=0`; `"vertical"` -> `dx=0, dy=length`) since the payload carries a
  categorical orientation, not a resolved angle (calcite/03 sec. 4:
  `JointAt` names a grid/level DATUM, not a numeric coordinate).
  `"inclined"`/`"point"` members (true trusses, point-anchored
  footings) cannot be assembled from this payload alone -- a member
  with either orientation makes the whole solve
  `SolveError.OutOfDomain` (named cut: general 2D/3D geometry needs a
  resolved-coordinate channel that does not exist yet).
- Section/material PROPERTY resolution (a `RecordRef`'s digest ->
  numeric area/second-moment/modulus) has no channel in feldspar's
  current payload port surface (`PayloadResolver` resolves
  content-addressed PAYLOAD refs, not named REGISTRY records) -- a
  member whose section or material ref is unresolved (name-only,
  digest `""`, the AD-25 `"free"` placeholder) makes the solve honestly
  indeterminate rather than fabricating EA/EI (WO-21 close-out cut).
  This module's public entry point therefore takes ALREADY-RESOLVED
  `ea`/`ei` per member alongside the payload structure (a documented
  seam for whoever builds the missing registry-resolution channel).
- Member end releases (`Releases.a`/`.b`): EMPTY is the payload's
  "unresolved" state (calcite/03 sec. 4), not "nothing kept". This
  module applies a documented ENGINEERING-DEFAULT assumption when
  empty: rigid (fully moment-connected), the standard default for
  continuous framing absent an explicit release -- recorded in the
  result's `assumptions` list, never silent.
- Support fixity (`Support.fixity`): EMPTY is likewise "unresolved".
  UNLIKE member releases, there is no single safe default across a
  pin/fixed/roller vocabulary (the WO's own text: "if the payload's
  empty releases/fixity make a case indeterminate, that is the correct
  answer"), so an empty support fixity list makes the solve honestly
  `SolveError.OutOfDomain`, naming the unresolved support.
- Output claim kinds: `mech.deflection` (joint displacements), bare
  reactions/member-end-forces, `extract_member_demands`'s per-member
  axial/shear/moment envelope, and a SCOPED `civil.utilization`
  numeric half (`civil_utilization_h1`: AISC 360-16 eq. H1-1a/H1-1b
  combined axial-flexure interaction ONLY, over caller-supplied
  ALREADY-RESOLVED capacities -- same "out-of-band resolved numbers"
  seam as `ea`/`ei`) are produced this slice (WO-23). `story_drift`/
  `bearing_pressure`/`first_mode`, lateral-torsional/plate buckling
  curves, connection checks (bolt/weld/block-shear), geotech records,
  and classical indeterminate calibration tiers (slope-deflection/
  moment-distribution) are NOT built -- named cuts, WO-21/WO-23
  close-outs.
- Tributary load paths (WO-23 deliverable 1): `resolve_tributary_
  loads` turns a `Bearing(tributary=width|area)` transfer (calcite/02
  sec. 5-6 `std.civil` vocabulary -- NOT part of the `FramePayload`
  schema itself; a companion input the caller assembles from the
  `structure ... transfers:` declaration) into an ordinary
  `distributed`-kind `FrameLoad` merged into the existing load list;
  `solve_frame_payload`'s optional `transfers`/`source_intensities`
  parameters wire it in. A `Bearing` transfer with no declared
  `tributary` contributes NOTHING (the `frame_load_untargeted`
  posture, WO-48 close-out) -- deterministic from declared geometry
  only, never an inferred width/area."""

import json
from typing import Sequence

from typani import Err, Ok

from feldspar import _feldspar
from feldspar.core import Domain, PortDecl, Rank, UnitSystem
from feldspar.logging_setup import get_logger
from feldspar.solve import EXACT, Citation, SolverRegistry, make_direction
from feldspar.solve.errors import SolveError
from feldspar.solve.payload import PayloadResolver

_log = get_logger(__name__)

__all__ = [
    "FRAME_PORT",
    "FRAME_RESULT_PORT",
    "civil_utilization_h1",
    "extract_member_demands",
    "register",
    "resolve_tributary_loads",
    "solve_frame_payload",
]

#: The `frame` payload input port (calcite/03 sec. 4, lithos WO-48).
# frob:doc docs/modules/mech.md#mech_struct
FRAME_PORT = "mech.struct.frame"
#: The result payload output port -- reuses the existing `"table"`
#: payload kind (09 sec. 4's generic tabular-content kind) rather than
#: minting a new one, since a new kind string would need a spec-table
#: change this WO does not own (docs are the contract, `test_payload.py`
#: pins the 09 sec. 4 list verbatim).
# frob:doc docs/modules/mech.md#mech_struct
FRAME_RESULT_PORT = "mech.struct.result"

_CITATION = Citation(
    kind="handbook",
    ref=(
        "Hibbeler, Structural Analysis, latest ed., ch. 16 (the "
        "direct-stiffness method: member stiffness assembly, "
        "fixed-end forces, reaction/end-force recovery)"
    ),
)

_ORIENTATION_TO_DXY = {
    "horizontal": (1.0, 0.0),
    "vertical": (0.0, 1.0),
}

#: Kept-DOF codes this module understands (2D: x, y, rz). Any other
#: code in a payload's `Releases`/`Support.fixity` is an honest
#: unsupported-vocabulary error, never silently ignored.
_DOF_CODES = ("x", "y", "rz")

#: The built-in SI unit table (`feldspar.core.UnitSystem`, 02-quantities
#: "Unit algebra"). `frame_lower::member_length` only *defaults* the
#: length unit to `"m"` -- it propagates whatever unit the source
#: grid/level datums carry (M4, cycle-28 audit) -- so every scalar this
#: module pulls off the payload is normalized through this table rather
#: than assumed SI.
_UNITS = UnitSystem.builtin()

#: Floating tolerance for the "length/geometry scalars carry a
#: degenerate (`lo == hi`) interval" payload-contract expectation
#: (`frame_lower::member_length` always emits `lo == hi`; M3/M4,
#: cycle-28 audit).
_DEGENERATE_TOL = 1e-9


def _scalar_to_si(interval: dict, corner: str, context: str):
    """Normalizes one payload `ScalarInterval`'s `corner` (`"lo"` or
    `"hi"`) value to SI through `_UNITS`, honestly `Err`ing rather than
    silently mixing units when the label isn't in the built-in table
    (M4, cycle-28 audit: a non-meter member length or an unregistered
    load-value unit must not be assumed SI)."""
    value = interval[corner]
    unit = interval["unit"]
    si_result = _UNITS.to_si(value, unit)
    if si_result.is_err:
        _log.warning(
            "struct.frame: %s: unit %r could not be normalized to SI (%s)",
            context,
            unit,
            si_result.err,
        )
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"{context}: unit {unit!r} has no SI conversion "
                    f"entry ({si_result.err}) -- cannot solve without "
                    "mixing units"
                )
            )
        )
    return Ok(si_result.danger_ok)


def _length_to_si_m(interval: dict, context: str):
    """Normalizes a `length`-shaped `ScalarInterval` to SI meters.

    `frame_lower::member_length` always emits a degenerate (`lo == hi`)
    interval -- a resolved length is a single scalar, not a genuine
    uncertainty range -- so a nondegenerate interval here means the
    producer-side invariant this module relies on has broken; that is
    an honest `OutOfDomain`, not a silent pick of one bound (M3/M4,
    cycle-28 audit)."""
    lo, hi = interval["lo"], interval["hi"]
    if abs(hi - lo) > _DEGENERATE_TOL * max(1.0, abs(lo), abs(hi)):
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"{context}: length interval [{lo}, {hi}] is not "
                    "degenerate (lo != hi) -- a resolved geometric length "
                    "is expected to be a single scalar, not a genuine "
                    "uncertainty range, this slice"
                )
            )
        )
    return _scalar_to_si(interval, "lo", context)


def _member_geometry(orientation: str, length_m: float, member_id: str):
    """Derives `(dx, dy)` from a member's categorical `orientation` and
    scalar `length` (calcite/03 sec. 4 does not carry a resolved
    angle). `Err` for `"inclined"`/`"point"` -- honest, not a fabricated
    angle (module docstring "SCOPE")."""
    if orientation not in _ORIENTATION_TO_DXY:
        _log.info(
            "struct.frame: member %s has unsupported orientation %r "
            "(only horizontal/vertical derivable from this payload)",
            member_id,
            orientation,
        )
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"member {member_id!r}: orientation {orientation!r} is not "
                    "derivable to a 2D geometry vector from the frame payload "
                    "alone (no resolved joint coordinates) -- only "
                    "'horizontal'/'vertical' members are supported this slice"
                )
            )
        )
    ux, uy = _ORIENTATION_TO_DXY[orientation]
    return Ok((ux * length_m, uy * length_m))


def _release_kept_rz(codes: Sequence[str], member_id: str, end: str):
    """Interprets one end's `Releases` kept-DOF list: EMPTY -> the
    documented rigid-connection default (`rz` kept, an assumption
    recorded by the caller); non-empty -> `rz` kept iff `"rz"` is
    present. Any code outside `_DOF_CODES` is an honest unsupported-
    vocabulary error."""
    if not codes:
        return Ok((True, True))  # (rz_kept, was_default)
    for code in codes:
        if code not in _DOF_CODES:
            return Err(
                SolveError.OutOfDomain(
                    violation=(
                        f"member {member_id!r} {end}-end release code "
                        f"{code!r} is outside the supported 2D DOF "
                        f"vocabulary {_DOF_CODES}"
                    )
                )
            )
    return Ok(("rz" in codes, False))


def _support_fixed_dofs(fixity: Sequence[str], support_joint: str):
    """A support's `fixity` list -> which of `x, y, rz` are restrained.
    EMPTY is the payload's honest "unresolved" state (calcite/03 sec.
    4) -- unlike member releases there is no single safe default across
    pin/fixed/roller, so this is an `Err`, never a guess (module
    docstring "SCOPE")."""
    if not fixity:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"support at joint {support_joint!r} has unresolved "
                    "fixity (empty list) -- std.civil support-role "
                    "resolution has not landed for this structure; no "
                    "safe default exists across pin/fixed/roller, so this "
                    "solve honestly cannot proceed"
                )
            )
        )
    for code in fixity:
        if code not in _DOF_CODES:
            return Err(
                SolveError.OutOfDomain(
                    violation=(
                        f"support at joint {support_joint!r} fixity code "
                        f"{code!r} is outside the supported 2D DOF "
                        f"vocabulary {_DOF_CODES}"
                    )
                )
            )
    return Ok({code: (code in fixity) for code in _DOF_CODES})


def _udl_fef_local(w: float, length: float) -> list[float]:
    """Fixed-end forces for a uniformly distributed load `w` (positive
    = local -y, i.e. gravity-consistent with the payload's
    `direction: "gravity"` convention) over a fully rigid member of
    `length`: `[0, wL/2, wL^2/12, 0, wL/2, -wL^2/12]` (Hibbeler, ch.
    16 fixed-end force table), matching this module's Rust solver's
    moment-DOF sign convention (`crates/feldspar-library/src/mech/
    frame.rs` test suite derives/validates this exact sign against the
    benchmarks memo's propped-cantilever and two-span-continuous-beam
    cases)."""
    shear = w * length / 2.0
    moment = w * length**2 / 12.0
    return [0.0, shear, moment, 0.0, shear, -moment]


# frob:doc docs/modules/mech.md#mech_struct
def solve_frame_payload(
    payload: dict,
    section_material: dict,
    load_case: str,
    transfers: Sequence[dict] = (),
    source_intensities: dict | None = None,
):
    """Solves one `frame` payload's `load_case` by 2D direct stiffness.

    `payload` is the parsed `FramePayload` JSON (calcite/03 sec. 4:
    `joints`, `members`, `supports`, `loads`, `combinations`).
    `section_material` maps each member id to an ALREADY-RESOLVED
    `{"ea": float, "ei": float}` pair (the missing registry-resolution
    channel this module's docstring names as a cut -- callers resolve
    section/material records themselves today). `load_case` selects
    which `loads[].case` entries apply (calcite/03's combination sweep
    is a discrete axis this function does not itself iterate -- one
    call per case/combination corner).

    `transfers`/`source_intensities` (WO-23 deliverable 1, both
    optional, default empty): fed straight to
    `resolve_tributary_loads` -- any `Bearing(tributary=...)` transfer
    resolves to an extra distributed load MERGED into `loads` before
    the existing load-application loop runs (no second load-path, the
    same list the direct `on [...]`-targeted loads already flow
    through). The result's `load_path` key carries the cited evidence
    (which transfers, which sources, per member) when any resolved.

    Returns `Ok(dict)` (the `frame_result` payload body: `displacements`,
    `reactions`, `member_end_forces`, `assumptions`, `load_path`) or
    `Err(SolveError)` naming the first honest gap encountered (unresolved
    support fixity, an unsupported orientation, a missing section/
    material entry, an unsupported load kind/direction, or an
    unresolvable tributary transfer)."""
    joints = payload["joints"]
    members = payload["members"]
    supports = payload["supports"]
    loads = list(payload["loads"])
    load_path_evidence: list[dict] = []

    if transfers:
        member_lengths_m: dict[str, float] = {}
        for m in members:
            length_si = _length_to_si_m(m["length"], f"member {m['id']!r} length")
            if length_si.is_err:
                return length_si
            member_lengths_m[m["id"]] = length_si.danger_ok
        trib_result = resolve_tributary_loads(
            transfers,
            source_intensities or {},
            load_case,
            member_lengths_m,
        )
        if trib_result.is_err:
            return trib_result
        derived_loads, load_path_evidence = trib_result.danger_ok
        loads.extend(derived_loads)

    joint_index = {j["id"]: idx for idx, j in enumerate(joints)}
    n_nodes = len(joints)

    # M2 (cycle-28 audit): `regolith-lower::frame_lower::on_target`
    # extracts the FIRST name in the source `on [<target>]` bracket,
    # which for civil designs is typically a level/region/deck name,
    # not a member declaration id. A distributed load whose target
    # matches no member honestly cannot be resolved (tributary/`on
    # [...]` target resolution is unbuilt this slice) -- refuse rather
    # than silently contribute zero to the assembled demand.
    member_ids = {m["id"] for m in payload["members"]}
    for load in loads:
        if load["case"] != load_case:
            continue
        if load["kind"] == "distributed" and load["target"] not in member_ids:
            _log.warning(
                "struct.frame: distributed load target %r (case %r) "
                "matches no member id",
                load["target"],
                load_case,
            )
            return Err(
                SolveError.OutOfDomain(
                    violation=(
                        f"distributed load target {load['target']!r} "
                        f"(case {load_case!r}) matches no member id -- "
                        "load-target-to-member resolution (tributary/"
                        "`on [...]`) is a named cut this slice; refusing "
                        "to silently drop this load"
                    )
                )
            )

    member_i: list[int] = []
    member_j: list[int] = []
    member_dx: list[float] = []
    member_dy: list[float] = []
    member_ea: list[float] = []
    member_ei: list[float] = []
    member_release_a: list[bool] = []
    member_release_b: list[bool] = []
    member_fef: list[list[float]] = []
    assumptions: list[str] = []
    hi_corner_recorded = False

    for m in members:
        mid = m["id"]
        if mid not in section_material:
            return Err(
                SolveError.OutOfDomain(
                    violation=(
                        f"member {mid!r}: no resolved section/material "
                        "properties supplied (section/material record "
                        "resolution is an unbuilt channel this slice)"
                    )
                )
            )
        props = section_material[mid]
        length_si = _length_to_si_m(m["length"], f"member {mid!r} length")
        if length_si.is_err:
            return length_si
        length_m = length_si.danger_ok
        geom = _member_geometry(m["orientation"], length_m, mid)
        if geom.is_err:
            return geom
        dx, dy = geom.danger_ok

        rel_a = _release_kept_rz(m["releases"]["a"], mid, "a")
        if rel_a.is_err:
            return rel_a
        rz_kept_a, defaulted_a = rel_a.danger_ok
        rel_b = _release_kept_rz(m["releases"]["b"], mid, "b")
        if rel_b.is_err:
            return rel_b
        rz_kept_b, defaulted_b = rel_b.danger_ok
        if defaulted_a or defaulted_b:
            assumptions.append(
                f"member {mid!r}: empty release list defaulted to rigid "
                "(fully moment-connected) -- calcite/03's "
                "std.civil transfer-class resolution has not landed"
            )

        fef = [0.0] * 6
        for load in loads:
            if load["case"] != load_case or load["target"] != mid:
                continue
            if load["direction"] != "gravity":
                return Err(
                    SolveError.OutOfDomain(
                        violation=(
                            f"member {mid!r} load direction "
                            f"{load['direction']!r} is unsupported (only "
                            "'gravity' this slice)"
                        )
                    )
                )
            if load["kind"] != "distributed":
                return Err(
                    SolveError.OutOfDomain(
                        violation=(
                            f"member {mid!r} load kind {load['kind']!r} is "
                            "unsupported (only 'distributed' UDL this slice "
                            "-- point/moment member loads are a named cut)"
                        )
                    )
                )
            w_si = _scalar_to_si(
                load["value"],
                "hi",
                f"member {mid!r} distributed load (case {load_case!r})",
            )
            if w_si.is_err:
                return w_si
            w = w_si.danger_ok
            if not hi_corner_recorded:
                assumptions.append(
                    "loads solved at the conservative .hi (upper-bound) "
                    "magnitude corner; lengths/geometry solved at their "
                    "(degenerate) nominal value"
                )
                hi_corner_recorded = True
            case_fef = _udl_fef_local(w, length_m)
            fef = [a + b for a, b in zip(fef, case_fef, strict=True)]

        for end_key in ("a", "b"):
            if m[end_key] not in joint_index:
                _log.warning(
                    "struct.frame: member %r endpoint %r=%r matches no joint id",
                    mid,
                    end_key,
                    m[end_key],
                )
                return Err(
                    SolveError.OutOfDomain(
                        violation=(
                            f"member {mid!r} endpoint {end_key!r}="
                            f"{m[end_key]!r} matches no joint id"
                        )
                    )
                )

        member_i.append(joint_index[m["a"]])
        member_j.append(joint_index[m["b"]])
        member_dx.append(dx)
        member_dy.append(dy)
        member_ea.append(props["ea"])
        member_ei.append(props["ei"])
        member_release_a.append(not rz_kept_a)
        member_release_b.append(not rz_kept_b)
        member_fef.append(fef)

    fixed = [False] * (n_nodes * 3)
    for s in supports:
        if s["joint"] not in joint_index:
            _log.warning(
                "struct.frame: support joint %r matches no joint id",
                s["joint"],
            )
            return Err(
                SolveError.OutOfDomain(
                    violation=(f"support joint {s['joint']!r} matches no joint id")
                )
            )
        node = joint_index[s["joint"]]
        fixed_result = _support_fixed_dofs(s["fixity"], s["joint"])
        if fixed_result.is_err:
            return fixed_result
        codes = fixed_result.danger_ok
        for local, code in enumerate(_DOF_CODES):
            fixed[node * 3 + local] = codes[code]

    joint_loads = [0.0] * (n_nodes * 3)
    for load in loads:
        if load["case"] != load_case:
            continue
        if load["kind"] != "point":
            continue
        if load["target"] not in joint_index:
            # M7 (cycle-28 audit): same silent-drop pattern as M2, but
            # for point loads -- a point load's target that matches no
            # joint id must be an honest OutOfDomain, never a silently
            # zero-contributing load.
            _log.warning(
                "struct.frame: point load target %r (case %r) matches no joint id",
                load["target"],
                load_case,
            )
            return Err(
                SolveError.OutOfDomain(
                    violation=(
                        f"point load target {load['target']!r} (case "
                        f"{load_case!r}) matches no joint id -- refusing "
                        "to silently drop this load"
                    )
                )
            )
        if load["direction"] != "gravity":
            return Err(
                SolveError.OutOfDomain(
                    violation=(
                        f"joint load at {load['target']!r} direction "
                        f"{load['direction']!r} is unsupported (only "
                        "'gravity' this slice)"
                    )
                )
            )
        node = joint_index[load["target"]]
        w_si = _scalar_to_si(
            load["value"],
            "hi",
            f"joint {load['target']!r} point load (case {load_case!r})",
        )
        if w_si.is_err:
            return w_si
        if not hi_corner_recorded:
            assumptions.append(
                "loads solved at the conservative .hi (upper-bound) "
                "magnitude corner; lengths/geometry solved at their "
                "(degenerate) nominal value"
            )
            hi_corner_recorded = True
        joint_loads[node * 3 + 1] -= w_si.danger_ok

    try:
        displacements, reactions, member_end_forces = _feldspar.mech_frame2d_solve(
            n_nodes,
            member_i,
            member_j,
            member_dx,
            member_dy,
            member_ea,
            member_ei,
            member_release_a,
            member_release_b,
            member_fef,
            fixed,
            joint_loads,
        )
    except ValueError as exc:
        _log.warning("struct.frame: direct-stiffness solve failed: %s", exc)
        return Err(SolveError.OutOfDomain(violation=str(exc)))

    joint_ids = [j["id"] for j in joints]
    member_ids = [m["id"] for m in members]
    return Ok(
        {
            "load_case": load_case,
            "joints": joint_ids,
            "displacements": {
                jid: displacements[idx * 3 : idx * 3 + 3]
                for idx, jid in enumerate(joint_ids)
            },
            "reactions": {
                jid: reactions[idx * 3 : idx * 3 + 3]
                for idx, jid in enumerate(joint_ids)
            },
            "member_end_forces": dict(zip(member_ids, member_end_forces, strict=True)),
            "assumptions": assumptions,
            "load_path": load_path_evidence,
        }
    )


_TRANSFER_CITATION = Citation(
    kind="handbook",
    ref=(
        "Hibbeler, Structural Analysis, latest ed., ch. 2 (tributary "
        "area/width load distribution: a receiving member's UDL is the "
        "declared tributary measure x the source surface's load "
        "intensity, spread over the receiving member's own length)"
    ),
)

#: Transfer connection kinds this module treats as a real load-transfer
#: path for tributary resolution (calcite/02 sec. 5's `std.civil`
#: classes). `Pinned`/`Moment`/`Roller`/`BasePlate` transfer FORCES but
#: never carry a `tributary=` declaration in calcite's vocabulary (only
#: `Bearing` does, calcite/02 sec. 6) -- a transfer of any other kind
#: with a `tributary` field set would be a payload-contract violation,
#: not a silently-accepted alternate spelling.
_TRIBUTARY_TRANSFER_KIND = "Bearing"


# frob:doc docs/modules/mech.md#mech_struct
def resolve_tributary_loads(
    transfers: Sequence[dict],
    source_intensities: dict,
    load_case: str,
    member_lengths_m: dict,
):
    """WO-23 deliverable 1: turns declared `Bearing(tributary=...)`
    transfer records into member-distributed (`kind: "distributed"`)
    `FrameLoad`-shaped entries the existing `solve_frame_payload` load
    loop already understands -- no new load-application code path, only
    a load-list PRODUCER feeding the one that exists.

    `transfers` is a sequence of `{"id", "kind", "from", "to",
    "tributary": {"kind": "width"|"area", "value": ScalarInterval} |
    None}` records (calcite/02 sec. 5-6 `std.civil` transfer classes,
    lithos WO-48's `structure ... transfers:` block -- NOT part of the
    `FramePayload` schema itself, calcite/03 sec. 4, which carries no
    transfer list; a companion input the caller assembles from the
    `structure` declaration, matching the `section_material` seam's own
    "documented, out-of-band" shape).

    `source_intensities` maps `(from_member_id, load_case) ->
    ScalarInterval` -- the SOURCE surface/member's own already-resolved
    load intensity for `load_case` -- force/area (a pressure: roof
    snow/dead psf-shaped) in BOTH `tributary.kind` cases (calcite/03
    sec. 4 loads are area-sourced; a `width` tributary already yields a
    line load directly -- pressure x width = force/length -- while an
    `area` tributary yields a resultant total force this function then
    spreads over the receiving member's own length); a source
    with no intensity entry for this case is skipped, not zero-filled,
    since "no declared source load this case" is a different fact than
    "zero load").

    Deterministic, no inferred geometry (feldspar standing law): ONLY
    a `Bearing` transfer carrying an explicit `tributary` declaration
    resolves. Any other transfer kind, or a `Bearing` with no
    `tributary` set, is skipped -- its receiving member's demand stays
    the existing `frame_load_untargeted` honest deferral (WO-48
    close-out), never a guessed tributary width/area.

    Returns `Ok((derived_loads, evidence))`:
    - `derived_loads`: list of `FrameLoad`-shaped dicts (`case`,
      `target`, `kind="distributed"`, `value`, `direction="gravity"`)
      ready to merge into a `FramePayload["loads"]` list.
    - `evidence`: list of `{"transfer": id, "from": .., "to": ..,
      "tributary_kind": .., "tributary_value_si": .., "intensity_si":
      .., "derived_udl_si": ..}` -- the cited load-path walk (WO-23
      deliverable 1's "which transfers, which sources, per member").

    `Err(SolveError.OutOfDomain)` if a `Bearing(tributary=...)`
    transfer's `to` member has no `length` supplied via
    `member_lengths_m` -- the UDL-spreading arithmetic needs it and a
    receiving member with unknown length cannot honestly produce one
    (this module refuses to guess a length any more than it guesses a
    tributary width)."""
    derived_loads: list[dict] = []
    evidence: list[dict] = []
    for t in transfers:
        if t["kind"] != _TRIBUTARY_TRANSFER_KIND:
            continue
        trib = t.get("tributary")
        if trib is None:
            _log.info(
                "struct.frame: transfer %r (%s -> %s) carries no "
                "tributary declaration -- receiving member's demand "
                "stays the honest frame_load_untargeted deferral",
                t["id"],
                t["from"],
                t["to"],
            )
            continue
        src, dst = t["from"], t["to"]
        intensity_interval = source_intensities.get((src, load_case))
        if intensity_interval is None:
            continue
        intensity_si = _scalar_to_si(
            intensity_interval,
            "hi",
            f"transfer {t['id']!r} source {src!r} load intensity (case {load_case!r})",
        )
        if intensity_si.is_err:
            return intensity_si
        intensity = intensity_si.danger_ok

        trib_si = _scalar_to_si(
            trib["value"],
            "hi",
            f"transfer {t['id']!r} tributary {trib['kind']} value",
        )
        if trib_si.is_err:
            return trib_si
        trib_value = trib_si.danger_ok

        if trib["kind"] == "width":
            # force/length x length(width) is already a resultant
            # per-unit-length UDL on the receiving member -- no
            # spreading over the receiving member's own length.
            udl = intensity * trib_value
        elif trib["kind"] == "area":
            if dst not in member_lengths_m:
                return Err(
                    SolveError.OutOfDomain(
                        violation=(
                            f"transfer {t['id']!r}: receiving member "
                            f"{dst!r} has no resolved length to spread "
                            "an area-tributary resultant force into a "
                            "UDL -- refusing to guess"
                        )
                    )
                )
            total_force = intensity * trib_value
            udl = total_force / member_lengths_m[dst]
        else:
            return Err(
                SolveError.OutOfDomain(
                    violation=(
                        f"transfer {t['id']!r}: tributary kind "
                        f"{trib['kind']!r} is outside the supported "
                        "'width'/'area' vocabulary (calcite/02 sec. 6)"
                    )
                )
            )

        derived_loads.append(
            {
                "case": load_case,
                "target": dst,
                "kind": "distributed",
                "value": {"lo": udl, "hi": udl, "unit": "1"},
                "direction": "gravity",
            }
        )
        evidence.append(
            {
                "transfer": t["id"],
                "from": src,
                "to": dst,
                "tributary_kind": trib["kind"],
                "tributary_value_si": trib_value,
                "intensity_si": intensity,
                "derived_udl_si": udl,
                "citation": _TRANSFER_CITATION.ref,
            }
        )
        _log.info(
            "struct.frame: tributary transfer %r resolved %r -> %r: "
            "udl=%.6g N/m (%s tributary=%.6g, intensity=%.6g)",
            t["id"],
            src,
            dst,
            udl,
            trib["kind"],
            trib_value,
            intensity,
        )
    return Ok((derived_loads, evidence))


# frob:doc docs/modules/mech.md#mech_struct
def extract_member_demands(result: dict) -> dict:
    """WO-23 deliverable 2: reduces `solve_frame_payload`'s
    `member_end_forces` (local `[n1, v1, m1, n2, v2, m2]` per member,
    `crates/feldspar-library/src/mech/frame.rs`'s documented local DOF
    order) to the per-member envelope `civil.utilization`/
    `mech.deflection` checks need: worst-case absolute axial, shear,
    and moment demand across both member ends (a single load case's
    envelope -- sweeping combinations is the caller's discrete axis,
    same posture as `solve_frame_payload` itself, 09 sec. 4 "structured
    Coverage")."""
    demands: dict[str, dict[str, float]] = {}
    for mid, ef in result["member_end_forces"].items():
        n1, v1, m1, n2, v2, m2 = ef
        demands[mid] = {
            "axial": max(abs(n1), abs(n2)),
            "shear": max(abs(v1), abs(v2)),
            "moment": max(abs(m1), abs(m2)),
        }
    return demands


#: AISC 360-16 Chapter H interaction-check citation (deliverable 3:
#: combined axial-flexure `civil.utilization`).
_H1_CITATION = Citation(
    kind="handbook",
    ref=(
        "AISC 360-16 Specification for Structural Steel Buildings, "
        "Ch. H sec. H1.1, eq. H1-1a/H1-1b (combined axial and flexural "
        "interaction, doubly/singly symmetric members)"
    ),
)


# frob:doc docs/modules/mech.md#mech_struct
def civil_utilization_h1(
    axial_demand: float,
    moment_demand: float,
    axial_capacity: float,
    moment_capacity: float,
):
    """Deliverable 3 (scoped): the AISC 360-16 H1-1 combined axial-
    flexure interaction ratio for one member -- NOT the full
    `civil.utilization` code-pack surface (buckling curves, LTB,
    connection checks are named residuals below, not guessed).

    `axial_capacity`/`moment_capacity` are the member's ALREADY-
    RESOLVED design capacities (`phi*Pn`, `phi*Mn` -- LRFD, or the
    ASD-equivalent the caller normalizes to; this function does not
    itself apply a phi/omega factor, matching `solve_frame_payload`'s
    "caller supplies resolved numbers" seam). Both must be strictly
    positive (a zero/negative capacity is a resolution bug upstream,
    not a solvable case here).

    Returns `Ok((ratio, "Valid"|"Violated"))` per AISC 360-16 eq.
    H1-1a (`Pr/Pc >= 0.2`) or H1-1b (`Pr/Pc < 0.2`); `ratio <= 1.0` is
    `Valid`. `Err(SolveError.OutOfDomain)` for a non-positive
    capacity -- refuses to divide into a fabricated verdict."""
    if axial_capacity <= 0.0 or moment_capacity <= 0.0:
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    "civil.utilization H1: non-positive capacity "
                    f"(axial={axial_capacity!r}, moment={moment_capacity!r}) "
                    "-- cannot form an interaction ratio"
                )
            )
        )
    pr_pc = abs(axial_demand) / axial_capacity
    mr_mc = abs(moment_demand) / moment_capacity
    if pr_pc >= 0.2:
        ratio = pr_pc + (8.0 / 9.0) * mr_mc  # eq. H1-1a
    else:
        ratio = pr_pc / 2.0 + mr_mc  # eq. H1-1b
    verdict = "Valid" if ratio <= 1.0 else "Violated"
    return Ok((ratio, verdict))


def _make_frame_direction(resolver: PayloadResolver):
    """The one registered `mech.struct` direction: resolves the `frame`
    payload, solves every load case named in its `loads` list (one
    direct-stiffness solve per case -- the calcite/03 combination sweep
    itself stays the CALLER's discrete axis, per 09 sec. 4 "structured
    Coverage"), and stores one `frame_result` payload with every case's
    output keyed by case name.

    NOTE (named cut): section/material property resolution has no
    channel here (module docstring) -- this direction currently
    honestly indeterminates on ANY member whose section/material ref
    is name-only (the AD-25 `"free"`/empty-digest placeholder every
    corpus fixture carries until std.civil resolution lands
    upstream), since it has no numeric EA/EI source of its own. A
    caller with an out-of-band property source can call
    `solve_frame_payload` directly (see this module's docstring)."""

    def frame_fn(x):
        payload_result = resolver.resolve(x[FRAME_PORT])
        if payload_result.is_err:
            _log.warning(
                "struct.frame: frame payload unresolvable: %r", payload_result.err
            )
            return payload_result
        payload = json.loads(payload_result.danger_ok)

        unresolved = [
            m["id"]
            for m in payload["members"]
            if not m["section"]["digest"] or not m["material"]["digest"]
        ]
        if unresolved:
            _log.info(
                "struct.frame: %d member(s) carry unresolved section/"
                "material refs (name-only, empty digest): %s",
                len(unresolved),
                unresolved,
            )
            return Err(
                SolveError.OutOfDomain(
                    violation=(
                        "frame payload has unresolved section/material "
                        f"record refs for member(s) {unresolved!r} -- "
                        "std.civil property resolution has not landed "
                        "(named cut, WO-21 close-out); this direction "
                        "cannot fabricate EA/EI"
                    )
                )
            )

        return Err(
            SolveError.OutOfDomain(
                violation=(
                    "struct.frame: every member's section/material ref "
                    "carries a digest, but this direction still has no "
                    "registry-resolution channel to turn a digest into "
                    "numeric EA/EI (named cut, WO-21 close-out) -- use "
                    "`feldspar.library.struct.solve_frame_payload` "
                    "directly with out-of-band resolved properties"
                )
            )
        )

    info, fn = make_direction(
        solver_id="mech.struct.frame2d",
        namespace="mech.struct",
        inputs=(FRAME_PORT,),
        outputs=(FRAME_RESULT_PORT,),
        domain=Domain({}, set()),
        cost=1e-4,
        accuracy=EXACT,
        citations=(_CITATION,),
        version="1",
        tier="reduced",
        fn=frame_fn,
    )
    return info, fn


# frob:doc docs/modules/mech.md#mech_struct
def register(registry: SolverRegistry, resolver: PayloadResolver) -> None:
    """Declares the `frame`/`frame_result` payload ports and registers
    the one `mech.struct` direction (WO-21). See this module's
    docstring for the full, honestly-scoped cut list against the WO-21
    Acceptance criteria."""
    ports_result = registry.declare_ports(
        PortDecl(FRAME_PORT, "", Rank.payload("frame")),
        PortDecl(FRAME_RESULT_PORT, "", Rank.payload("table")),
    )
    _ = ports_result.danger_ok
    info, fn = _make_frame_direction(resolver)
    result = registry.register(info, fn)
    _ = result.danger_ok
    _log.info("library.struct: registered 1 solver direction")
