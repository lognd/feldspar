from __future__ import annotations

"""CalculiX deck (.inp) generation from mesh + boundary conditions (WO-08).

PURE text generation: no IO, no gmsh/ccx import, no subprocess. Every
float written into the deck goes through `feldspar.core.format_f64` so
that two calls with identical `MeshData`/`Material`/load inputs produce
byte-identical strings (the "deck goldens (byte-stable)" requirement) --
no dict-iteration-order or float-repr-locale nondeterminism. `node_sets`
is a `Mapping`; we always look up its known keys explicitly ("FIXED",
"TIP", "BORE", "OUTER") rather than iterating it, for the same reason.

Load-application choices, documented here rather than buried in code:
- Cantilever *CLOAD: `tip_force` is split evenly across the TIP node
  set and applied as DOF 2 (transverse) point loads, matching the
  handbook bending-deflection convention `mech.py`'s closed-form
  cantilever direction is calibrated against.
- Cylinder pressure: the physically correct ccx mechanism is a
  `*DLOAD` face-pressure load, which needs element face/surface
  definitions this module does not have (`MeshData.node_sets` is a
  plain node-id list, not a face topology). Per the WO-08 contract's
  documented fallback, we instead apply an EQUIVALENT NODAL FORCE on
  the BORE set: total radial force = pressure * (2 * pi * r_avg) *
  (z_span of the BORE set), split evenly across BORE nodes. This is an
  approximation -- it ignores the non-uniform tributary area quadratic
  (corner vs. mid-side) elements actually carry -- traded for not
  needing face/surface data that MeshData does not expose.
- Cylinder *BOUNDARY: MeshData only carries "BORE"/"OUTER" node sets,
  with no separate top/bottom (z=0 / z=length) set to pin against rigid
  body motion along the axis. We therefore fix DOF 2 (axial, z) on
  EVERY node, which is the axisymmetric equivalent of a plane-strain /
  infinite-cylinder assumption (no net axial expansion) -- documented
  simplification given the available node sets."""

import math
from typing import Sequence, Tuple

from feldspar.core import format_f64
from feldspar.fea.geometry import Material
from feldspar.fea.mesh import MeshData
from feldspar.logging import get_logger

_log = get_logger(__name__)

__all__ = ["build_cantilever_deck", "build_cylinder_deck"]

_MAX_ITEMS_PER_LINE = 8  # ccx/Abaqus keyword-format line-length convention


def _chunk_line(items: Sequence[str]) -> str:
    """Join `items` into ccx continuation lines: at most
    `_MAX_ITEMS_PER_LINE` comma-separated entries per line, trailing
    comma on every line but the last to signal continuation."""

    lines = []
    for start in range(0, len(items), _MAX_ITEMS_PER_LINE):
        chunk = items[start : start + _MAX_ITEMS_PER_LINE]
        is_last = start + _MAX_ITEMS_PER_LINE >= len(items)
        suffix = "" if is_last else ","
        lines.append(",".join(chunk) + suffix)
    return "\n".join(lines)


def _node_block(nodes: Tuple[Tuple[float, float, float], ...]) -> str:
    """`*NODE` block: one line per node, id = index + 1 (ccx 1-indexed)."""

    lines = ["*NODE"]
    for index, (x, y, z) in enumerate(nodes):
        node_id = index + 1
        lines.append(
            f"{node_id},{format_f64(x)},{format_f64(y)},{format_f64(z)}"
        )
    return "\n".join(lines)


def _element_block(
    elements: Tuple[Tuple[int, ...], ...], element_type: str
) -> str:
    """`*ELEMENT` block: one continuation-wrapped record per element, id
    = index + 1, elset EALL (the single elset every element belongs
    to, used by *SOLID SECTION / *EL PRINT)."""

    lines = [f"*ELEMENT, TYPE={element_type}, ELSET=EALL"]
    for index, node_ids in enumerate(elements):
        elem_id = index + 1
        items = [str(elem_id)] + [str(n) for n in node_ids]
        lines.append(_chunk_line(items))
    return "\n".join(lines)


def _nset_block(name: str, node_ids: Tuple[int, ...]) -> str:
    """`*NSET` block for one named node set, continuation-wrapped."""

    lines = [f"*NSET, NSET={name}"]
    lines.append(_chunk_line([str(n) for n in node_ids]))
    return "\n".join(lines)


def _material_block(material: Material) -> str:
    """`*MATERIAL`/`*ELASTIC` block: E, nu only (linear-elastic
    isotropic; `yield_strength` is not a ccx *ELASTIC input)."""

    return (
        "*MATERIAL, NAME=MAT1\n"
        "*ELASTIC\n"
        f"{format_f64(material.youngs_modulus)},{format_f64(material.poisson)}"
    )


def _solid_section_block() -> str:
    """`*SOLID SECTION` covering the single EALL elset, MAT1 material --
    shared by both C3D20 (solid) and CAX8 (axisymmetric-implied-by-
    element-type, no extra thickness line needed)."""

    return "*SOLID SECTION, ELSET=EALL, MATERIAL=MAT1"


def _result_requests_block() -> str:
    """`*STEP`/`*STATIC` block requesting nodal displacements (U) and
    elemental PRINCIPAL stresses (S1, S2, S3 -- not the 6 tensor
    components, so results.py can call `mech_von_mises_principal`
    directly without reimplementing eigenvalue math)."""

    return (
        "*STEP\n"
        "*STATIC\n"
        "*NODE PRINT, NSET=NALL,\n"
        "U\n"
        "*EL PRINT, ELSET=EALL,\n"
        "S1, S2, S3\n"
        "*END STEP"
    )


def build_cantilever_deck(
    mesh: MeshData, material: Material, tip_force: float
) -> str:
    """Render a full ccx .inp deck for one cantilever mesh: fixed FIXED
    set (DOFs 1-3), tip_force split evenly across TIP as DOF-2 point
    loads, principal-stress + displacement result requests."""

    fixed_ids = mesh.node_sets["FIXED"]
    tip_ids = mesh.node_sets["TIP"]
    tip_count = len(tip_ids)
    force_per_node = tip_force / tip_count if tip_count else 0.0
    _log.info(
        "building cantilever deck: %d nodes, %d elements, FIXED=%d TIP=%d "
        "tip_force=%s -> force_per_node=%s",
        len(mesh.nodes),
        len(mesh.elements),
        len(fixed_ids),
        tip_count,
        tip_force,
        force_per_node,
    )

    all_node_ids = tuple(range(1, len(mesh.nodes) + 1))

    sections = [
        _node_block(mesh.nodes),
        _element_block(mesh.elements, mesh.element_type),
        _nset_block("NALL", all_node_ids),
        _nset_block("FIXED", fixed_ids),
        _nset_block("TIP", tip_ids),
        _material_block(material),
        _solid_section_block(),
        "*BOUNDARY\nFIXED,1,3",
        f"*CLOAD\nTIP,2,{format_f64(-force_per_node)}",
        _result_requests_block(),
    ]
    return "\n".join(sections) + "\n"


def build_cylinder_deck(
    mesh: MeshData, material: Material, pressure: float
) -> str:
    """Render a full ccx .inp deck for one cylinder mesh: axial (DOF 2)
    fixed on every node (documented plane-strain-style simplification,
    see module docstring), internal pressure applied as an equivalent
    evenly-split nodal radial force on BORE, principal-stress +
    displacement result requests."""

    bore_ids = mesh.node_sets["BORE"]
    outer_ids = mesh.node_sets["OUTER"]

    bore_coords = [mesh.nodes[node_id - 1] for node_id in bore_ids]
    if bore_coords:
        r_avg = sum(coord[0] for coord in bore_coords) / len(bore_coords)
        z_values = [coord[1] for coord in bore_coords]
        z_span = max(z_values) - min(z_values)
    else:
        r_avg = 0.0
        z_span = 0.0
    total_force = pressure * (2.0 * math.pi * r_avg) * z_span
    bore_count = len(bore_ids)
    force_per_node = total_force / bore_count if bore_count else 0.0
    _log.info(
        "building cylinder deck: %d nodes, %d elements, BORE=%d OUTER=%d "
        "pressure=%s r_avg=%s z_span=%s -> force_per_node=%s",
        len(mesh.nodes),
        len(mesh.elements),
        bore_count,
        len(outer_ids),
        pressure,
        r_avg,
        z_span,
        force_per_node,
    )

    all_node_ids = tuple(range(1, len(mesh.nodes) + 1))

    sections = [
        _node_block(mesh.nodes),
        _element_block(mesh.elements, mesh.element_type),
        _nset_block("NALL", all_node_ids),
        _nset_block("BORE", bore_ids),
        _nset_block("OUTER", outer_ids),
        _material_block(material),
        _solid_section_block(),
        "*BOUNDARY\nNALL,2,2",
        f"*CLOAD\nBORE,1,{format_f64(force_per_node)}",
        _result_requests_block(),
    ]
    return "\n".join(sections) + "\n"
