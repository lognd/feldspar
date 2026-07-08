from __future__ import annotations

"""WO-08 deck goldens (byte-stable): `python/feldspar/fea/deck.py` is
PURE text generation, so the contract is exact -- calling
`build_cantilever_deck`/`build_cylinder_deck` twice on identical inputs
must produce byte-identical strings, every float must be routed through
`feldspar.core.format_f64`, and the expected CalculiX keyword sections
must be present."""

from feldspar.core import format_f64
from feldspar.fea.deck import build_cantilever_deck, build_cylinder_deck
from feldspar.fea.geometry import Material
from feldspar.fea.mesh import MeshData

_MATERIAL = Material(youngs_modulus=7.0e10, poisson=0.33, yield_strength=2.7e8)


def _tiny_cantilever_mesh() -> MeshData:
    """One hand-built C3D20 hex element (20 nodes, ccx's expected mid-
    edge-node order is not physically verified here -- deck.py treats
    connectivity as opaque ids, so any 20-tuple is a valid golden
    input): corner nodes 1-8, mid-edge nodes 9-20, all at nominal
    coordinates. Node 1-4 sit at x=0 (FIXED face), node 5-8 (and their
    mid-edge partners on that face) at x=1 (TIP face)."""

    nodes = (
        (0.0, 0.0, 0.0),  # 1
        (0.0, 1.0, 0.0),  # 2
        (0.0, 1.0, 1.0),  # 3
        (0.0, 0.0, 1.0),  # 4
        (1.0, 0.0, 0.0),  # 5
        (1.0, 1.0, 0.0),  # 6
        (1.0, 1.0, 1.0),  # 7
        (1.0, 0.0, 1.0),  # 8
        (0.0, 0.5, 0.0),  # 9
        (0.0, 1.0, 0.5),  # 10
        (0.0, 0.5, 1.0),  # 11
        (0.0, 0.0, 0.5),  # 12
        (1.0, 0.5, 0.0),  # 13
        (1.0, 1.0, 0.5),  # 14
        (1.0, 0.5, 1.0),  # 15
        (1.0, 0.0, 0.5),  # 16
        (0.5, 0.0, 0.0),  # 17
        (0.5, 1.0, 0.0),  # 18
        (0.5, 1.0, 1.0),  # 19
        (0.5, 0.0, 1.0),  # 20
    )
    elements = (tuple(range(1, 21)),)
    node_sets = {
        "FIXED": (1, 2, 3, 4, 9, 10, 11, 12),
        "TIP": (5, 6, 7, 8, 13, 14, 15, 16),
    }
    return MeshData(
        element_type="C3D20", nodes=nodes, elements=elements, node_sets=node_sets
    )


def _tiny_cylinder_mesh() -> MeshData:
    """One hand-built CAX8 quad element (8 nodes) on a thin r-z
    rectangle: inner radius 0.1 m, outer radius 0.2 m, axial length
    1.0 m."""

    nodes = (
        (0.1, 0.0, 0.0),  # 1 -- BORE, z=0
        (0.2, 0.0, 0.0),  # 2 -- OUTER, z=0
        (0.2, 1.0, 0.0),  # 3 -- OUTER, z=1
        (0.1, 1.0, 0.0),  # 4 -- BORE, z=1
        (0.15, 0.0, 0.0),  # 5 -- mid, bottom edge
        (0.2, 0.5, 0.0),  # 6 -- mid, OUTER edge
        (0.15, 1.0, 0.0),  # 7 -- mid, top edge
        (0.1, 0.5, 0.0),  # 8 -- mid, BORE edge
    )
    elements = (tuple(range(1, 9)),)
    node_sets = {
        "BORE": (1, 4, 8),
        "OUTER": (2, 3, 6),
    }
    return MeshData(
        element_type="CAX8", nodes=nodes, elements=elements, node_sets=node_sets
    )


def test_cantilever_deck_is_byte_stable():
    """Two calls with identical MeshData/Material/tip_force inputs must
    produce byte-identical deck text (no dict-iteration or float-repr
    nondeterminism)."""

    mesh = _tiny_cantilever_mesh()
    tip_force = 1000.0

    deck_a = build_cantilever_deck(mesh, _MATERIAL, tip_force)
    deck_b = build_cantilever_deck(mesh, _MATERIAL, tip_force)

    assert deck_a == deck_b


def test_cantilever_deck_has_expected_sections():
    mesh = _tiny_cantilever_mesh()
    deck = build_cantilever_deck(mesh, _MATERIAL, 1000.0)

    for keyword in (
        "*NODE",
        "*ELEMENT",
        "*MATERIAL",
        "*ELASTIC",
        "*SOLID SECTION",
        "*BOUNDARY",
        "*CLOAD",
        "*STATIC",
        "*END STEP",
    ):
        assert keyword in deck


def test_cantilever_deck_formats_tip_force_via_format_f64():
    """The per-node share of tip_force must appear in the deck rendered
    through `format_f64`, not Python's default float repr."""

    mesh = _tiny_cantilever_mesh()
    tip_force = 1000.0
    tip_count = len(mesh.node_sets["TIP"])
    force_per_node = tip_force / tip_count

    deck = build_cantilever_deck(mesh, _MATERIAL, tip_force)

    assert format_f64(-force_per_node) in deck
    assert format_f64(_MATERIAL.youngs_modulus) in deck
    assert format_f64(_MATERIAL.poisson) in deck


def test_cylinder_deck_is_byte_stable():
    """Two calls with identical MeshData/Material/pressure inputs must
    produce byte-identical deck text."""

    mesh = _tiny_cylinder_mesh()
    pressure = 5.0e6

    deck_a = build_cylinder_deck(mesh, _MATERIAL, pressure)
    deck_b = build_cylinder_deck(mesh, _MATERIAL, pressure)

    assert deck_a == deck_b


def test_cylinder_deck_has_expected_sections():
    mesh = _tiny_cylinder_mesh()
    deck = build_cylinder_deck(mesh, _MATERIAL, 5.0e6)

    for keyword in (
        "*NODE",
        "*ELEMENT",
        "*MATERIAL",
        "*ELASTIC",
        "*SOLID SECTION",
        "*BOUNDARY",
        "*CLOAD",
        "*STATIC",
        "*END STEP",
    ):
        assert keyword in deck


def test_cylinder_deck_formats_material_via_format_f64():
    mesh = _tiny_cylinder_mesh()
    pressure = 5.0e6

    deck = build_cylinder_deck(mesh, _MATERIAL, pressure)

    assert format_f64(_MATERIAL.youngs_modulus) in deck
    assert format_f64(_MATERIAL.poisson) in deck
