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
  set and applied as DOF 3 (the z = height direction) point loads. The
  box is meshed x=length, y=width, z=height, so bending in z is bending
  about the width axis with `I = width*height^3/12` -- exactly the
  `mech.rect_second_moment(width, height)` the closed-form oracle uses.
  Loading DOF 2 (width) instead would bend about the height axis
  (`I = height*width^3/12`), deflecting by a factor `(height/width)^2`
  more than the oracle predicts.
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
from feldspar.logging_setup import get_logger

_log = get_logger(__name__)

__all__ = [
    "build_cantilever_deck",
    "build_cylinder_deck",
    "build_cantilever_modal_deck",
]

# ccx/Abaqus fixed-format data lines hold at most 16 comma-separated fields.
# A C3D20 record is 21 fields (id + 20 nodes); at 16/line that is exactly two
# lines (one continuation), which the ccx *ELEMENT reader's allocation pass
# expects. Splitting it across three lines (e.g. 8/line) makes stricter ccx
# builds miscount elements and abort with "*ERROR reading *ELEMENT: increase
# ne_".
_MAX_ITEMS_PER_LINE = 16


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
        lines.append(f"{node_id},{format_f64(x)},{format_f64(y)},{format_f64(z)}")
    return "\n".join(lines)


def _element_block(elements: Tuple[Tuple[int, ...], ...], element_type: str) -> str:
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


def _material_block_with_density(material: Material) -> str:
    """`*MATERIAL`/`*ELASTIC`/`*DENSITY` block (WO-16 modal tier):
    identical to `_material_block` plus the `*DENSITY` card ccx's
    `*FREQUENCY` eigenvalue solve needs for the mass matrix -- static
    decks never need mass, so the plain block stays density-free
    (NO DUPLICATION would otherwise mean either threading an unused
    density through every static deck, or this separate block; the
    latter keeps the static path's deck byte-identical to its pre-WO-16
    golden)."""

    return (
        "*MATERIAL, NAME=MAT1\n"
        "*ELASTIC\n"
        f"{format_f64(material.youngs_modulus)},{format_f64(material.poisson)}\n"
        "*DENSITY\n"
        f"{format_f64(material.density)}"
    )


def _modal_step_block(num_modes: int) -> str:
    """`*STEP`/`*FREQUENCY` block requesting the lowest `num_modes`
    eigenvalues; ccx prints the mode table (mode no, eigenvalue,
    freq rad/time, freq cycles/time) to the .dat file automatically for
    a `*FREQUENCY` step, no explicit `*NODE PRINT`/`*EL PRINT` needed."""

    return f"*STEP\n*FREQUENCY\n{num_modes}\n*END STEP"


# frob:doc docs/modules/fea.md#fea_deck
def build_cantilever_modal_deck(
    mesh: MeshData, material: Material, num_modes: int = 1
) -> str:
    """Render a full ccx .inp modal deck for one cantilever mesh
    (WO-16, 07 vibration Phase 3): fixed FIXED set (DOFs 1-3, matching
    the closed-form cantilever's fixed-free boundary condition), a
    `*DENSITY`-bearing material block, and a `*FREQUENCY` step
    requesting the lowest `num_modes` modes -- no load block (an
    eigenvalue extraction has no applied force)."""

    fixed_ids = mesh.node_sets["FIXED"]
    _log.info(
        "building cantilever modal deck: %d nodes, %d elements, FIXED=%d, num_modes=%d",
        len(mesh.nodes),
        len(mesh.elements),
        len(fixed_ids),
        num_modes,
    )

    all_node_ids = tuple(range(1, len(mesh.nodes) + 1))

    sections = [
        _node_block(mesh.nodes),
        _element_block(mesh.elements, mesh.element_type),
        _nset_block("NALL", all_node_ids),
        _nset_block("FIXED", fixed_ids),
        _material_block_with_density(material),
        _solid_section_block(),
        "*BOUNDARY\nFIXED,1,3",
        _modal_step_block(num_modes),
    ]
    return "\n".join(sections) + "\n"


def _solid_section_block() -> str:
    """`*SOLID SECTION` covering the single EALL elset, MAT1 material --
    shared by both C3D20 (solid) and CAX8 (axisymmetric-implied-by-
    element-type, no extra thickness line needed)."""

    return "*SOLID SECTION, ELSET=EALL, MATERIAL=MAT1"


def _static_step_block(cload_block: str, output_request: str) -> str:
    """`*STEP`/`*STATIC` block: the applied `*CLOAD` MUST live inside the
    step (ccx rejects a *CLOAD in the model-definition section), followed
    by exactly ONE result request (`output_request`). Each consumer reads
    a single .dat table, so a deck emits only the table it needs -- a
    cantilever prints displacements (U), a cylinder prints stresses (S);
    emitting both would put two differently-shaped tables in one .dat and
    break the single-table row parsers."""

    return f"*STEP\n*STATIC\n{cload_block}\n{output_request}\n*END STEP"


# frob:doc docs/modules/fea.md#fea_deck
def build_cantilever_deck(mesh: MeshData, material: Material, tip_force: float) -> str:
    """Render a full ccx .inp deck for one cantilever mesh: fixed FIXED
    set (DOFs 1-3), tip_force split evenly across TIP as DOF-3 (height)
    point loads (see the module load-application note), displacement
    result request."""

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
        _static_step_block(
            f"*CLOAD\nTIP,3,{format_f64(-force_per_node)}",
            "*NODE PRINT, NSET=NALL,\nU",
        ),
    ]
    return "\n".join(sections) + "\n"


# frob:doc docs/modules/fea.md#fea_deck
def build_cylinder_deck(mesh: MeshData, material: Material, pressure: float) -> str:
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
        _static_step_block(
            f"*CLOAD\nBORE,1,{format_f64(force_per_node)}",
            "*EL PRINT, ELSET=EALL,\nS",
        ),
    ]
    return "\n".join(sections) + "\n"
