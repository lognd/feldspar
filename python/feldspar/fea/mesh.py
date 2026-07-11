from __future__ import annotations

"""Structured-mesh generation for the WO-08 FEA pipeline.

Wraps gmsh's transfinite (structured, non-adaptive) meshing to build the
two supported element topologies -- a hex C3D20 box for the cantilever
family and an axisymmetric CAX8 quad rectangle for the cylinder family
-- and flattens the result into plain, gmsh-free arrays (`MeshData`) so
that no other fea module needs gmsh installed (05's explicit
requirement). `import gmsh` is deferred into each build function's body
so this module stays importable without the optional `mesh` extra
(AD-6)."""

from typing import List, Mapping, Tuple

from pydantic import BaseModel, ConfigDict
from typani import Err, Ok, Result

from feldspar.fea.geometry import CantileverGeometry, CylinderGeometry
from feldspar.logging_setup import get_logger
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = [
    "MeshSettings",
    "MeshData",
    "build_cantilever_mesh",
    "build_cylinder_mesh",
]


class MeshSettings(BaseModel):
    """Fixed meshing knobs for one family: element type plus the single
    refinement parameter (char_length) the h/h/2 Richardson pair varies."""

    model_config = ConfigDict(frozen=True)

    family: str  # "cantilever" or "cylinder"
    element_type: str  # "C3D20" or "CAX8"
    char_length: float  # m -- the ONE refinement knob
    algorithm_id: int = 1  # fixed gmsh algorithm choice, constant
    seed: int = 0  # fixed seed, constant


class MeshData(BaseModel):
    """Plain, gmsh-free mesh arrays: 1-indexed ccx node ids (index i ->
    node id i+1), element connectivity in ccx's expected node order, and
    named node sets for boundary conditions and loads."""

    model_config = ConfigDict(frozen=True)

    element_type: str
    nodes: Tuple[Tuple[float, float, float], ...]
    elements: Tuple[Tuple[int, ...], ...]
    node_sets: Mapping[str, Tuple[int, ...]]


# gmsh numbers a 20-node hexahedron's twelve mid-edge nodes in a different
# edge order than Abaqus/ccx's C3D20, so the raw gmsh connectivity yields
# inverted elements (ccx: "nonpositive jacobian determinant"). This maps each
# ccx C3D20 slot to its gmsh index (corners 0-7 already agree; the mid-edge
# block 8-19 is the permutation, same as meshio's gmsh hexahedron20 mapping).
# gmsh's 8-node quad (CAX8) already matches ccx's mid-edge order, so it needs
# no reordering.
_GMSH_TO_CCX_C3D20 = (
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    11,
    13,
    9,
    16,
    18,
    19,
    17,
    10,
    12,
    14,
    15,
)


def _to_ccx_order(node_ids: Tuple[int, ...]) -> Tuple[int, ...]:
    """Reorder one element's gmsh node ids into ccx's expected order.
    Only the 20-node hexahedron (C3D20) differs; every other supported
    topology is passed through unchanged."""
    if len(node_ids) == len(_GMSH_TO_CCX_C3D20):
        return tuple(node_ids[i] for i in _GMSH_TO_CCX_C3D20)
    return node_ids


def _subdivisions(dimension: float, char_length: float) -> int:
    """Element count along one axis: dimension / char_length, rounded,
    floored at 1 so a coarse char_length never collapses an axis."""

    return max(1, round(dimension / char_length))


def build_cantilever_mesh(
    geometry: CantileverGeometry, settings: MeshSettings
) -> Result[MeshData, SolveError]:
    """Structured hex C3D20 box mesh over length x width x height, with
    "FIXED" (x=0 face) and "TIP" (x=length face) node sets for the
    *BOUNDARY / *CLOAD deck entries."""

    try:
        import gmsh
    except (ImportError, OSError):
        # OSError: gmsh is installed but a native dependency (e.g. libGLU)
        # failed to load -- still unusable, so degrade to ToolMissing.
        _log.warning("gmsh unavailable; cannot build cantilever mesh")
        return Err(
            SolveError.ToolMissing(
                tool="gmsh",
                guidance="install the 'mesh' extra: pip install feldspar[mesh]",
            )
        )

    n_x = _subdivisions(geometry.length, settings.char_length)
    n_y = _subdivisions(geometry.width, settings.char_length)
    n_z = _subdivisions(geometry.height, settings.char_length)
    _log.info(
        "building cantilever mesh: length=%s width=%s height=%s "
        "char_length=%s -> subdivisions (x,y,z)=(%d,%d,%d)",
        geometry.length,
        geometry.width,
        geometry.height,
        settings.char_length,
        n_x,
        n_y,
        n_z,
    )

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("cantilever")

        box = gmsh.model.occ.addBox(
            0.0, 0.0, 0.0, geometry.length, geometry.width, geometry.height
        )
        gmsh.model.occ.synchronize()

        # Structured (transfinite) meshing: pin subdivision counts PER AXIS
        # so gmsh produces a regular n_x by n_y by n_z hex grid. Each box edge
        # is axis-aligned; assign n_x/n_y/n_z by the edge's dominant extent.
        # (Applying n_x to every edge makes the mesh n_x^3, not n_x*n_y*n_z --
        # e.g. 50^3 = 125000 elements instead of 50*4*6 = 1200.)
        for dim, tag in gmsh.model.getEntities(1):
            xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(dim, tag)
            dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
            if dx >= dy and dx >= dz:
                divisions = n_x
            elif dy >= dz:
                divisions = n_y
            else:
                divisions = n_z
            gmsh.model.mesh.setTransfiniteCurve(tag, divisions + 1)
        for surface in gmsh.model.getEntities(2):
            gmsh.model.mesh.setTransfiniteSurface(surface[1])
            gmsh.model.mesh.setRecombine(2, surface[1])
        gmsh.model.mesh.setTransfiniteVolume(box)

        gmsh.option.setNumber("Mesh.Algorithm", settings.algorithm_id)
        gmsh.option.setNumber("Mesh.RandomSeed", settings.seed)
        gmsh.model.mesh.generate(3)
        # Serendipity (incomplete) second order: emit 20-node hexes (C3D20),
        # not the default 27-node hex (with face/body centre nodes) that ccx
        # would misread against a C3D20 declaration.
        gmsh.option.setNumber("Mesh.SecondOrderIncomplete", 1)
        gmsh.model.mesh.setOrder(2)  # quadratic -> C3D20

        node_ids, node_coords, _ = gmsh.model.mesh.getNodes()
        nodes_by_id = {
            int(node_ids[i]): (
                node_coords[3 * i],
                node_coords[3 * i + 1],
                node_coords[3 * i + 2],
            )
            for i in range(len(node_ids))
        }
        max_node_id = max(nodes_by_id)
        nodes: List[Tuple[float, float, float]] = [
            nodes_by_id.get(node_id, (0.0, 0.0, 0.0))
            for node_id in range(1, max_node_id + 1)
        ]

        elem_types, _, elem_node_tags = gmsh.model.mesh.getElements(3)
        elements: List[Tuple[int, ...]] = []
        for elem_type, node_tags in zip(elem_types, elem_node_tags, strict=True):
            _, _, _, nodes_per_elem, _, _ = gmsh.model.mesh.getElementProperties(
                elem_type
            )
            nodes_per_elem = int(nodes_per_elem)
            for i in range(0, len(node_tags), nodes_per_elem):
                elements.append(
                    _to_ccx_order(
                        tuple(int(t) for t in node_tags[i : i + nodes_per_elem])
                    )
                )

        fixed_ids = tuple(
            sorted(
                node_id
                for node_id, coord in nodes_by_id.items()
                if abs(coord[0]) < 1e-9
            )
        )
        tip_ids = tuple(
            sorted(
                node_id
                for node_id, coord in nodes_by_id.items()
                if abs(coord[0] - geometry.length) < 1e-9
            )
        )
        _log.info(
            "cantilever mesh built: %d nodes, %d elements, FIXED=%d TIP=%d",
            len(nodes),
            len(elements),
            len(fixed_ids),
            len(tip_ids),
        )

        return Ok(
            MeshData(
                element_type=settings.element_type,
                nodes=tuple(nodes),
                elements=tuple(elements),
                node_sets={"FIXED": fixed_ids, "TIP": tip_ids},
            )
        )
    finally:
        gmsh.finalize()


def build_cylinder_mesh(
    geometry: CylinderGeometry, settings: MeshSettings
) -> Result[MeshData, SolveError]:
    """Structured axisymmetric CAX8 quad mesh on the r-z rectangle
    (inner_radius..outer_radius x 0..length), with "BORE" (r=inner) and
    "OUTER" (r=outer) node sets for the pressure load / support."""

    try:
        import gmsh
    except (ImportError, OSError):
        # OSError: gmsh installed but a native dependency failed to load.
        _log.warning("gmsh unavailable; cannot build cylinder mesh")
        return Err(
            SolveError.ToolMissing(
                tool="gmsh",
                guidance="install the 'mesh' extra: pip install feldspar[mesh]",
            )
        )

    wall_thickness = geometry.outer_radius - geometry.inner_radius
    n_r = _subdivisions(wall_thickness, settings.char_length)
    n_z = _subdivisions(geometry.length, settings.char_length)
    _log.info(
        "building cylinder mesh: inner_radius=%s outer_radius=%s length=%s "
        "char_length=%s -> subdivisions (r,z)=(%d,%d)",
        geometry.inner_radius,
        geometry.outer_radius,
        geometry.length,
        settings.char_length,
        n_r,
        n_z,
    )

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("cylinder")

        # r-z rectangle: x axis represents r, y axis represents z, per
        # the axisymmetric CAX8 convention (revolve about x=0/r=0).
        rectangle = gmsh.model.occ.addRectangle(
            geometry.inner_radius, 0.0, 0.0, wall_thickness, geometry.length
        )
        gmsh.model.occ.synchronize()

        # Per-axis subdivision (see the cantilever note): the r-z rectangle's
        # x-edges span r (n_r), its y-edges span z (n_z). Applying n_r to every
        # edge would make the mesh n_r by n_r instead of n_r by n_z.
        for dim, tag in gmsh.model.getEntities(1):
            xmin, ymin, _zmin, xmax, ymax, _zmax = gmsh.model.getBoundingBox(dim, tag)
            divisions = n_r if (xmax - xmin) >= (ymax - ymin) else n_z
            gmsh.model.mesh.setTransfiniteCurve(tag, divisions + 1)
        gmsh.model.mesh.setTransfiniteSurface(rectangle)
        gmsh.model.mesh.setRecombine(2, rectangle)

        gmsh.option.setNumber("Mesh.Algorithm", settings.algorithm_id)
        gmsh.option.setNumber("Mesh.RandomSeed", settings.seed)
        gmsh.model.mesh.generate(2)
        # Serendipity (incomplete) second order: emit 8-node quads (CAX8),
        # not the default 9-node quad (with a centre node) that ccx would
        # misread against a CAX8 declaration.
        gmsh.option.setNumber("Mesh.SecondOrderIncomplete", 1)
        gmsh.model.mesh.setOrder(2)  # quadratic -> CAX8

        node_ids, node_coords, _ = gmsh.model.mesh.getNodes()
        nodes_by_id = {
            int(node_ids[i]): (
                node_coords[3 * i],
                node_coords[3 * i + 1],
                node_coords[3 * i + 2],
            )
            for i in range(len(node_ids))
        }
        max_node_id = max(nodes_by_id)
        nodes: List[Tuple[float, float, float]] = [
            nodes_by_id.get(node_id, (0.0, 0.0, 0.0))
            for node_id in range(1, max_node_id + 1)
        ]

        elem_types, _, elem_node_tags = gmsh.model.mesh.getElements(2)
        elements: List[Tuple[int, ...]] = []
        for elem_type, node_tags in zip(elem_types, elem_node_tags, strict=True):
            _, _, _, nodes_per_elem, _, _ = gmsh.model.mesh.getElementProperties(
                elem_type
            )
            nodes_per_elem = int(nodes_per_elem)
            for i in range(0, len(node_tags), nodes_per_elem):
                elements.append(
                    _to_ccx_order(
                        tuple(int(t) for t in node_tags[i : i + nodes_per_elem])
                    )
                )

        bore_ids = tuple(
            sorted(
                node_id
                for node_id, coord in nodes_by_id.items()
                if abs(coord[0] - geometry.inner_radius) < 1e-9
            )
        )
        outer_ids = tuple(
            sorted(
                node_id
                for node_id, coord in nodes_by_id.items()
                if abs(coord[0] - geometry.outer_radius) < 1e-9
            )
        )
        _log.info(
            "cylinder mesh built: %d nodes, %d elements, BORE=%d OUTER=%d",
            len(nodes),
            len(elements),
            len(bore_ids),
            len(outer_ids),
        )

        return Ok(
            MeshData(
                element_type=settings.element_type,
                nodes=tuple(nodes),
                elements=tuple(elements),
                node_sets={"BORE": bore_ids, "OUTER": outer_ids},
            )
        )
    finally:
        gmsh.finalize()
