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
    except ImportError:
        _log.warning("gmsh not importable; cannot build cantilever mesh")
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

        # Structured (transfinite) meshing: pin subdivision counts on
        # every edge of the box so gmsh produces a regular hex grid
        # instead of a free/adaptive tetrahedral mesh.
        for curve in gmsh.model.getEntities(1):
            gmsh.model.mesh.setTransfiniteCurve(curve[1], n_x + 1)
        for surface in gmsh.model.getEntities(2):
            gmsh.model.mesh.setTransfiniteSurface(surface[1])
            gmsh.model.mesh.setRecombine(2, surface[1])
        gmsh.model.mesh.setTransfiniteVolume(box)

        gmsh.option.setNumber("Mesh.Algorithm", settings.algorithm_id)
        gmsh.option.setNumber("Mesh.RandomSeed", settings.seed)
        gmsh.model.mesh.generate(3)
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
                    tuple(int(t) for t in node_tags[i : i + nodes_per_elem])
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
    except ImportError:
        _log.warning("gmsh not importable; cannot build cylinder mesh")
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

        for curve in gmsh.model.getEntities(1):
            gmsh.model.mesh.setTransfiniteCurve(curve[1], n_r + 1)
        gmsh.model.mesh.setTransfiniteSurface(rectangle)
        gmsh.model.mesh.setRecombine(2, rectangle)

        gmsh.option.setNumber("Mesh.Algorithm", settings.algorithm_id)
        gmsh.option.setNumber("Mesh.RandomSeed", settings.seed)
        gmsh.model.mesh.generate(2)
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
                    tuple(int(t) for t in node_tags[i : i + nodes_per_elem])
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
