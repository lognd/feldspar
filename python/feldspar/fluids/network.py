from __future__ import annotations

"""Hardy-Cross fluid-network solver (WO-20 residual): resolves a
`flownet` payload (D154: the bytes are the schema-versioned JSON
serialization of `regolith._schema.models.FlownetPayload`, sorted-key
serialized, digest-pinned) into a network topology and iterates the
classical Hardy-Cross loop-correction method (Cross, 1936) to a
converged flow distribution, storing the per-edge flow/dp solution
back through the resolver as a `table` payload.

This module never imports `regolith` (FINV-3/10: regolith imports stay
confined to `feldspar.pack`) -- `_FlownetPayload` below is a
feldspar-owned, FIELD-NAME-COMPATIBLE subset of the published schema
(D154's "bytes ARE the schema JSON" contract: parse the same field
names the schema publishes, never a second wire format).

Scope (this WO's honest coverage declaration -- named cuts, not silent
gaps, per the pack contract 03):

- Edge kinds: `pipe`, `imposer`, `orifice` (T-0022), and `hx_segment`
  (T-0023) are IN COVERAGE.
  * `pipe`: an ordinary loop/tree branch; its flow is a Hardy-Cross
    unknown.
  * `imposer`: a FIXED, externally-known flow rate (a metered/
    positive-displacement branch) -- not solved, just asserted.
  * `orifice` (T-0022): a sharp-edged orifice-plate flow restriction;
    its flow is a Hardy-Cross unknown, dp from the standard
    discharge-coefficient closed form (see `_orifice_dp_and_k`),
    domain-refused outside the beta/Cd validity band it cites.
  * `hx_segment` (T-0023): a fixed-hydraulic-resistance segment (e.g.
    a heat-exchanger coil's flow-side loss curve, curve-fit by the
    caller to one coefficient); its flow is a Hardy-Cross unknown, dp
    from a quadratic resistance law (see `_hx_segment_dp_and_k`).
    Models ONLY the hydraulic resistance -- NOT the thermal duty, NOT
    heat transfer or effectiveness; that stays a named cut (`thermo.py`
    is still unwired to this module, see the property-resolution
    paragraph below).
  Any other edge kind (`hose`, `valve`, `pump`, `regulator`, `filter`,
  `mixer`) reports an honest
  `SolveError.OutOfDomain(payload_feature_violation(...))` naming the
  unsupported kind, never a silent approximation or a fabricated
  convergence.
- Edge parameters: ONLY `EdgeParams1`-shaped literal scalar values
  (`source: "scalars"`) are read. Geometry-extract selectors
  (`EdgeParams2`, D131's `regolith-lower::extract` seam) and the
  mixer-outlet medium record (`EdgeParams3`) are CUT -- named above,
  needing the WO-32 extraction seam this pass does not wire in.
  T-0024 recon (this pass): the corpus's lowered `geom_extract` shape
  is `{"source": "geom_extract", "record": {"digest": <str>, "name":
  <str>}, "selector": <str>}` (see `examples/lithos/systems/
  small_office/.regolith/payloads/6d8d34...`, the hydronics.fluo
  `ret`/`supply` pipe edges) -- but the `digest` field is an EMPTY
  placeholder string in every corpus fixture that carries this shape
  today (the upstream WO-31 realized-CAD extraction has not landed a
  real digest yet). Wiring an actual resolver.resolve(digest) call
  here would therefore refuse on empty-digest anyway in every case
  the corpus currently exercises -- so this pass adds ONLY a more
  precise refusal (malformed-shape vs. well-formed-but-unresolvable
  are named distinctly, see `_Edge.__init__`) rather than a resolution
  hook whose wire contract (what a RESOLVED extraction payload look
  likes -- a scalar? a named table?) is not yet observable from this
  repo. Follow-up filed as T-0025 (report-only) for whoever holds the
  WO-32/lithos side of this seam.
- Fluid properties: `pipe`/`imposer` edges carry LITERAL
  `density`/`viscosity` values in their own `values` dict (a deviation
  from full `MediumRef` property-record resolution, which would need
  the thermo/CoolProp wrapper threaded through a resolver at THIS call
  site too -- named cut, not wired this pass. `thermo.py`, this WO's
  other residual, stands alone as a property-table catalog; the two
  residuals are not yet wired to each other).
- Topology: an arbitrary connected graph is accepted; independent
  loops come from a BFS spanning-tree/chord fundamental cycle basis
  (standard graph algorithm -- the "real algorithm work" the WO-20
  close-out named as missing). A DISCONNECTED graph (more than one
  component) is out of coverage (`OutOfDomain`, feature
  `"disconnected_network"`) -- multi-component solves are a
  CoupledGroup-shaped follow-up, not this direction's business.
- Loop-correction method: friction recomputed each iteration via the
  existing Rust `fluids_colebrook_friction_factor`/
  `fluids_laminar_friction_factor` homes (NO DUPLICATION -- the
  per-segment formula stays in ONE place, `incompressible.py`'s
  citations apply here too). Converges when every loop's |dQ| falls
  under `_HC_TOL`; `SolveError.NoConvergence` if `_HC_MAX_ITER` is
  exhausted -- honest indeterminate, never a fabricated result (same
  posture as WO-18's `CoupledGroup`, `SolveError.NoConvergence`)."""

import json
import math
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from feldspar.core import Domain, PortDecl, Rank
from feldspar.logging_setup import get_logger
from feldspar.solve import (
    EXACT,
    Citation,
    Err,
    Ok,
    SolveError,
    SolveOutput,
    SolverRegistry,
    make_direction,
)
from feldspar.solve.digest import canonical_digest
from feldspar.solve.payload import (
    PayloadResolver,
    payload_feature_violation,
    resolver_cache_identity,
)

if TYPE_CHECKING:
    from typani import Result

_log = get_logger(__name__)

__all__ = [
    "FLOWNET_PORT",
    "SOLUTION_PORT",
    "SolvedNetwork",
    "edge_dp",
    "find_path_edges",
    "register",
    "solve_flownet_bytes",
]

#: The flownet payload input port (kind `flownet`, D154).
# frob:doc docs/modules/fluids.md#fluids_network
FLOWNET_PORT = "fluids.network.flownet"

#: The solved per-edge flow/dp table payload output port (kind
#: `table`): downstream consumers (dp/npsh/hammer claims) read this
#: instead of re-running the loop solve.
# frob:doc docs/modules/fluids.md#fluids_network
SOLUTION_PORT = "fluids.network.solution"

_HC_TOL = 1e-6  # m^3/s -- the benchmarks memo sec. 3.2 convergence figure
_HC_MAX_ITER = 100
_LAMINAR_RE_CEILING = 2300.0

_HARDY_CROSS_CITATION = Citation(
    kind="paper",
    ref="Cross, H., Analysis of Flow in Networks of Conduits or "
    "Conductors, Univ. of Illinois Eng. Experiment Station Bulletin "
    "286, 1936.",
)
_WHITE_NETWORK_CITATION = Citation(
    kind="handbook",
    ref="White, Fluid Mechanics, 8th ed., sec. 6.8 (pipe networks)",
)
# frob:ticket T-0022
_ORIFICE_CITATION = Citation(
    kind="standard",
    ref="ISO 5167-2:2003, orifice-plate flow measurement "
    "(discharge-coefficient convention Q = Cd*A*sqrt(2*dp/rho)); "
    "White, Fluid Mechanics, 8th ed., sec. 6.11 (flow measurement) "
    "for the beta = d/D validity band [0.2, 0.75]",
)
# frob:ticket T-0023
_HX_SEGMENT_CITATION = Citation(
    kind="standard",
    ref="Crane Technical Paper 410, 'Flow of Fluids Through Valves, "
    "Fittings, and Pipe' (lumped-resistance/K-factor method), applied "
    "here as a caller-supplied fixed resistance coefficient standing "
    "in for a heat-exchanger segment's flow-side loss curve -- NOT a "
    "thermal/heat-transfer model",
)
_ORIFICE_BETA_MIN = 0.2
_ORIFICE_BETA_MAX = 0.75

# ---------------------------------------------------------------------------
# D154 wire-format subset (feldspar-owned, field-name-compatible with
# `regolith._schema.models.FlownetPayload`; never imports regolith)
# ---------------------------------------------------------------------------


class _FlowEdge(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    a: str
    b: str
    kind: str
    params: dict[str, Any]


# frob:ticket T-0019
class _ClaimTarget(BaseModel):
    """Field-name-compatible subset of `regolith._schema.models.
    ClaimTarget` (SCHEMA_VERSION 31, T-0019): which claim/role a
    discharge over this payload answers. `role` is untyped free text
    here -- `feldspar.pack.models` owns the per-claim-kind convention
    for what a role string MEANS (a bare edge id, a comma-joined edge
    set, an `a->b` node pair), this module only parses the wire
    shape."""

    model_config = ConfigDict(extra="ignore")
    claim_kind: str
    role: str | None = None


# frob:ticket T-0019
class _FlownetPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    nodes: list[str]
    edges: list[_FlowEdge]
    #: `None` for pre-31 payloads and whole-network solves (T-0019):
    #: absence is NOT an error, it just means the caller (`feldspar.
    #: pack.models`) falls back to the legacy `DischargeRequest.inputs`
    #: presence-flag convention this field replaces.
    claim_target: _ClaimTarget | None = None


def _scalar_value(interval: dict[str, Any]) -> float:
    """Collapses a `ScalarInterval`-shaped `{lo, hi, unit}` dict (or a
    bare number, for callers building fixtures by hand) to its midpoint
    -- Hardy-Cross needs a point value per edge parameter; interval
    propagation through the loop-correction iteration is POST-V1 (same
    ruling as WO-22's note on `Normal` propagation not yet routing
    through `execute()`)."""
    if isinstance(interval, (int, float)):
        return float(interval)
    return (float(interval["lo"]) + float(interval["hi"])) / 2.0


#: Edge kinds whose flow is a Hardy-Cross unknown (contrasted with
#: `imposer`, the only fixed-flow kind this module supports) -- pipe,
#: orifice (T-0022), and hx_segment (T-0023) all participate in loop
#: correction the same way, they differ only in their dp(Q) law.
_UNKNOWN_FLOW_KINDS = frozenset({"pipe", "orifice", "hx_segment"})


def _require_keys(edge_id: str, values: dict[str, Any], keys: tuple[str, ...]) -> None:
    """Validates that every key in `keys` is present in `values` before
    `_Edge.__init__` subscripts it -- a missing key (e.g. an `imposer`
    edge with no `flow_rate`) is a malformed payload, not a programmer
    bug: it must surface as the module's typed `_UnsupportedFeature` ->
    `SolveError.OutOfDomain(...)` path (caught in `_hardy_cross_solve`),
    never a bare `KeyError` crash (INV-24-class totality; T-0021)."""
    for key in keys:
        if key not in values:
            raise _UnsupportedFeature(edge_id, f"missing_param:{key}")


class _Edge:
    """One in-coverage network edge: a pipe (unknown flow) or an
    imposer (fixed flow), with the literal scalar params Hardy-Cross
    needs."""

    __slots__ = (
        "id",
        "a",
        "b",
        "kind",
        "length",
        "diameter",
        "roughness",
        "density",
        "viscosity",
        "flow",
        "cd",
        "bore_diameter",
        "resistance",
    )

    def __init__(self, edge: _FlowEdge):
        params = edge.params
        source = params.get("source")
        if source == "geom_extract":
            # T-0024 recon (see module docstring): validate the
            # LOWERED shape's own required keys first (a malformed
            # geom_extract record is a distinct, more actionable
            # refusal than "unsupported at all") before refusing --
            # this repo has no seam to actually RESOLVE `record.digest`
            # into a scalar (the wire contract of a resolved payload is
            # not observable from feldspar alone), so every geom_extract
            # edge is refused either way, just with a sharper reason.
            _require_keys(edge.id, params, ("record", "selector"))
            record = params.get("record")
            if not isinstance(record, dict) or not record.get("digest"):
                raise _UnsupportedFeature(
                    edge.id, "edge_params:geom_extract:unresolved_digest"
                )
            raise _UnsupportedFeature(edge.id, "edge_params:geom_extract")
        if source != "scalars":
            raise _UnsupportedFeature(edge.id, f"edge_params:{source or 'unknown'}")
        values = params.get("values", {})
        self.id = edge.id
        self.a = edge.a
        self.b = edge.b
        self.kind = edge.kind
        self.cd = self.bore_diameter = self.resistance = 0.0
        if edge.kind == "pipe":
            _require_keys(
                edge.id, values, ("length", "diameter", "density", "viscosity")
            )
            self.length = _scalar_value(values["length"])
            self.diameter = _scalar_value(values["diameter"])
            self.roughness = _scalar_value(values.get("roughness", 0.0))
            self.density = _scalar_value(values["density"])
            self.viscosity = _scalar_value(values["viscosity"])
            self.flow = 0.0  # Hardy-Cross unknown, seeded below
        elif edge.kind == "imposer":
            _require_keys(edge.id, values, ("flow_rate",))
            self.length = self.diameter = self.roughness = 0.0
            self.density = self.viscosity = 0.0
            self.flow = _scalar_value(values["flow_rate"])
        elif edge.kind == "orifice":
            # T-0022: sharp-edged orifice plate. `pipe_diameter` (D,
            # the approach run) is used ONLY to check the beta = d/D
            # validity band the discharge-coefficient closed form (ISO
            # 5167-2, `_ORIFICE_CITATION`) is honestly cited for --
            # outside it, this is not a silently-wrong number, it is a
            # refusal.
            _require_keys(
                edge.id,
                values,
                ("cd", "bore_diameter", "pipe_diameter", "density"),
            )
            cd = _scalar_value(values["cd"])
            bore_diameter = _scalar_value(values["bore_diameter"])
            pipe_diameter = _scalar_value(values["pipe_diameter"])
            if not (0.0 < cd <= 1.0):
                raise _UnsupportedFeature(edge.id, "orifice_cd_out_of_range")
            beta = bore_diameter / pipe_diameter if pipe_diameter else math.inf
            if not (_ORIFICE_BETA_MIN <= beta <= _ORIFICE_BETA_MAX):
                raise _UnsupportedFeature(edge.id, "orifice_beta_out_of_range")
            self.length = self.roughness = 0.0
            self.diameter = pipe_diameter
            self.density = _scalar_value(values["density"])
            self.viscosity = 0.0
            self.cd = cd
            self.bore_diameter = bore_diameter
            self.flow = 0.0  # Hardy-Cross unknown, seeded below
        elif edge.kind == "hx_segment":
            # T-0023: a K-factor-only minor-loss model (White sec.
            # 6.10 / Crane TP-410, `_HX_SEGMENT_CITATION`) for the
            # segment's flow-side resistance -- NOT a thermal model.
            # `density` is read as a LITERAL value on the edge itself,
            # same deviation from full `MediumRef` resolution the pipe
            # kind already carries (module docstring's property-
            # resolution named cut; thermo.py's CoolProp wrapper is
            # NOT wired into this call site this pass either).
            _require_keys(edge.id, values, ("k_factor", "diameter", "density"))
            resistance = _scalar_value(values["k_factor"])
            diameter = _scalar_value(values["diameter"])
            if resistance < 0.0:
                raise _UnsupportedFeature(edge.id, "hx_segment_negative_resistance")
            if diameter <= 0.0:
                raise _UnsupportedFeature(edge.id, "hx_segment_nonpositive_diameter")
            self.length = self.roughness = 0.0
            self.diameter = diameter
            self.density = _scalar_value(values["density"])
            self.viscosity = 0.0
            self.resistance = resistance
            self.flow = 0.0  # Hardy-Cross unknown, seeded below
        else:
            raise _UnsupportedFeature(edge.id, f"edge_kind:{edge.kind}")


class _UnsupportedFeature(Exception):
    """Internal signal: an edge kind/params combination outside this
    direction's declared coverage. Caught at the call boundary and
    turned into `SolveError.OutOfDomain` -- never propagated raw."""

    def __init__(self, edge_id: str, feature: str):
        self.edge_id = edge_id
        self.feature = feature
        super().__init__(f"{edge_id}: {feature}")


def _pipe_dp_and_k(edge: _Edge, flow: float) -> tuple[float, float]:
    """`(dp, dh/dQ)` for one pipe edge at the given signed flow, via the
    existing Rust friction-factor/Darcy-Weisbach homes (NO DUPLICATION
    -- same formula `incompressible.py`'s `darcy_dp`/friction directions
    wrap). `dp` carries the sign of `flow`; the loop-correction
    coefficient uses `abs`."""

    def _dp_mag(m: float) -> float:
        """`|dp|` at flow magnitude `m` (Darcy-Weisbach, friction factor
        recomputed at this `m`'s Reynolds number)."""
        from feldspar import _feldspar

        if m <= 0.0:
            return 0.0
        area = math.pi * (edge.diameter / 2.0) ** 2
        speed = m / area if area > 0 else 0.0
        reynolds = _feldspar.fluids_reynolds_number(
            edge.density, speed, edge.diameter, edge.viscosity
        )
        if reynolds < _LAMINAR_RE_CEILING:
            f = _feldspar.fluids_laminar_friction_factor(max(reynolds, 1.0))
        else:
            rel_rough = edge.roughness / edge.diameter if edge.diameter else 0.0
            f = _feldspar.fluids_colebrook_friction_factor(reynolds, rel_rough)
        return _feldspar.fluids_darcy_dp(
            f, edge.length, edge.diameter, edge.density, speed
        )

    m = abs(flow)
    dp_mag = _dp_mag(m)
    dp = math.copysign(dp_mag, flow) if flow != 0.0 else 0.0
    # dh/dQ via a numerical forward difference of |dp| at |Q| -- correct
    # across BOTH the laminar (dp ~ Q, slope = dp/Q) and turbulent
    # (dp ~ Q^2, slope = 2 dp/Q) regimes, and at the transition between
    # them, instead of assuming one fixed exponent (a fixed-exponent
    # slope halves the effective Newton step in the laminar regime,
    # which still converges but far more slowly -- verified against the
    # Hagen-Poiseuille closed form during this WO's calibration pass).
    if m == 0.0:
        k = 0.0
    else:
        h = max(m * 1e-6, 1e-12)
        k = (_dp_mag(m + h) - dp_mag) / h
    return dp, k


def _orifice_dp_and_k(edge: _Edge, flow: float) -> tuple[float, float]:
    """`(dp, dh/dQ)` for one orifice edge (T-0022) at the given signed
    flow, via the Rust `fluids_orifice_dp` home (NO DUPLICATION -- the
    ISO 5167 discharge-coefficient closed form `Q = Cd*A*sqrt(2*dp/
    rho)` solved for dp lives ONE place, `feldspar-library`'s
    `incompressible.rs`, `_ORIFICE_CITATION`). Exactly quadratic in Q
    (unlike the pipe case, no laminar/turbulent transition applies
    here), so the slope is the exact analytic derivative, not a
    numerical difference."""
    from feldspar import _feldspar

    area = math.pi * (edge.bore_diameter / 2.0) ** 2

    def _dp_mag(m: float) -> float:
        return _feldspar.fluids_orifice_dp(edge.cd, area, edge.density, m)

    m = abs(flow)
    dp_mag = _dp_mag(m)
    dp = math.copysign(dp_mag, flow) if flow != 0.0 else 0.0
    coeff = edge.density / (2.0 * (edge.cd * area) ** 2) if area > 0 else 0.0
    k = 2.0 * coeff * m
    return dp, k


def _hx_segment_dp_and_k(edge: _Edge, flow: float) -> tuple[float, float]:
    """`(dp, dh/dQ)` for one hx_segment edge (T-0023) at the given
    signed flow, via the SAME Rust `fluids_minor_loss_dp` home
    `incompressible.py`'s own K-factor minor-loss direction wraps (NO
    DUPLICATION -- `_HX_SEGMENT_CITATION`, Crane TP-410): `dp = K * rho
    * v^2 / 2` with `v = Q/A`. Models ONLY the flow-side hydraulic
    resistance -- NOT heat transfer/effectiveness (module docstring's
    named cut)."""
    from feldspar import _feldspar

    area = math.pi * (edge.diameter / 2.0) ** 2

    def _dp_mag(m: float) -> float:
        velocity = m / area if area > 0 else 0.0
        return _feldspar.fluids_minor_loss_dp(edge.resistance, edge.density, velocity)

    m = abs(flow)
    dp_mag = _dp_mag(m)
    dp = math.copysign(dp_mag, flow) if flow != 0.0 else 0.0
    coeff = edge.resistance * edge.density / (2.0 * area * area) if area > 0 else 0.0
    k = 2.0 * coeff * m
    return dp, k


def _edge_dp_and_k(edge: _Edge, flow: float) -> tuple[float, float]:
    """Dispatches to the right dp(Q) law for any `_UNKNOWN_FLOW_KINDS`
    edge kind (pipe/orifice/hx_segment) -- the ONE place that maps edge
    kind to head-loss model, so `_hardy_cross_solve`, `edge_dp`, and
    `hardy_cross_fn`'s row-building all agree (NO DUPLICATION)."""
    if edge.kind == "pipe":
        return _pipe_dp_and_k(edge, flow)
    if edge.kind == "orifice":
        return _orifice_dp_and_k(edge, flow)
    if edge.kind == "hx_segment":
        return _hx_segment_dp_and_k(edge, flow)
    return 0.0, 0.0


class _SpanningTree:
    """A BFS spanning tree over the full edge set (pipe + imposer): the
    shared structure both the fundamental cycle basis and the
    continuity-respecting initial-flow seed are built from (ONE
    traversal, two consumers, NO DUPLICATION)."""

    __slots__ = ("order", "parent_node", "parent_edge", "tree_edges")

    def __init__(self, order, parent_node, parent_edge, tree_edges):
        self.order = order
        self.parent_node = parent_node
        self.parent_edge = parent_edge
        self.tree_edges = tree_edges


def _spanning_tree(
    nodes: list[str], edges: list[_Edge]
) -> "Result[_SpanningTree, SolveError]":
    """BFS spanning tree; `Err` on a disconnected graph (out of
    coverage -- multi-component solves are a `CoupledGroup`-shaped
    follow-up, not this direction's business)."""
    adjacency: dict[str, list[tuple[str, int]]] = {n: [] for n in nodes}
    for idx, e in enumerate(edges):
        adjacency[e.a].append((e.b, idx))
        adjacency[e.b].append((e.a, idx))

    visited = {nodes[0]}
    parent_edge: dict[str, int] = {}
    parent_node: dict[str, str] = {}
    order = [nodes[0]]
    queue = [nodes[0]]
    tree_edges: set[int] = set()
    while queue:
        node = queue.pop(0)
        for neighbor, edge_idx in adjacency[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                parent_edge[neighbor] = edge_idx
                parent_node[neighbor] = node
                tree_edges.add(edge_idx)
                order.append(neighbor)
                queue.append(neighbor)

    if len(visited) != len(nodes):
        _log.warning(
            "hardy_cross: disconnected network (%d/%d nodes reached)",
            len(visited),
            len(nodes),
        )
        return Err(
            SolveError.OutOfDomain(
                payload_feature_violation(FLOWNET_PORT, "disconnected_network")
            )
        )
    return Ok(_SpanningTree(order, parent_node, parent_edge, tree_edges))


def _build_cycle_basis(
    nodes: list[str], edges: list[_Edge], tree: _SpanningTree
) -> list[list[tuple[int, int]]]:
    """Fundamental cycle basis from `tree`: each non-tree ("chord")
    edge closes exactly one independent loop with the tree path between
    its endpoints. Returns loops as lists of `(edge_index, sign)` where
    `sign` is +1 if the edge is traversed a->b in the loop's positive
    sense, -1 otherwise."""

    def _path_to_root(n: str) -> list[tuple[int, int]]:
        path = []
        while n in tree.parent_node:
            e_idx = tree.parent_edge[n]
            e = edges[e_idx]
            sign = 1 if e.b == n else -1
            path.append((e_idx, sign))
            n = tree.parent_node[n]
        return path

    depth_path = {n: _path_to_root(n) for n in nodes}

    loops: list[list[tuple[int, int]]] = []
    for idx, e in enumerate(edges):
        if idx in tree.tree_edges:
            continue
        # Chord e.a -> e.b closes a loop with the tree paths from each
        # endpoint back to their common ancestor; the ROOT is common
        # ancestor here since the tree is a simple BFS tree -- correct
        # for any tree, just not shortest, which does not affect
        # Hardy-Cross correctness (only the number of loops ==
        # cyclomatic number is what has to be right, and it is: one
        # loop per chord).
        loop = [(idx, 1)]
        a_path = depth_path[e.a]
        b_path = depth_path[e.b]
        a_edges = {i for i, _ in a_path}
        b_edges = {i for i, _ in b_path}
        common = a_edges & b_edges
        for i, s in a_path:
            if i not in common:
                loop.append((i, s))
        for i, s in b_path:
            if i not in common:
                loop.append((i, -s))
        loops.append(loop)
    return loops


#: Global/nodal conservation tolerance (m^3/s) -- tight, since this is
#: an exact bookkeeping check (continuity), not a converging iterate.
_CONSERVATION_TOL = 1e-9


def _seed_continuity_respecting_flows(
    nodes: list[str], edges: list[_Edge], tree: _SpanningTree
) -> "Result[None, SolveError]":
    """Assigns every PIPE edge an initial flow that satisfies node
    continuity EXACTLY (imposer edges keep their fixed, given flow):
    chord pipe edges get an arbitrary small nonzero seed (Hardy-Cross
    loop correction refines it either way -- the seed's exactness only
    affects iteration count, never correctness); tree pipe edges are
    then DETERMINED, leaf-to-root, by the continuity balance at each
    node. This is the initial-assignment half of Hardy-Cross the WO-20
    close-out flagged as missing "real algorithm work" -- corrected
    loop flows alone never fabricate continuity, they only preserve
    whatever the seed started with."""
    for idx, e in enumerate(edges):
        if e.kind in _UNKNOWN_FLOW_KINDS and idx not in tree.tree_edges:
            e.flow = 1e-4  # arbitrary nonzero chord seed

    incident: dict[str, list[tuple[int, int]]] = {n: [] for n in nodes}
    for idx, e in enumerate(edges):
        incident[e.a].append((idx, -1))  # e.flow > 0 means outflow from a
        incident[e.b].append((idx, 1))  # and inflow to b

    # Degree-1 nodes are boundary nodes (a source/sink imposer, or a
    # dead-end pipe), not junctions -- continuity is enforced ONLY at
    # interior nodes (degree >= 2). A dead-end pipe (no imposer at a
    # degree-1 node) is forced to zero flow (nothing else there to
    # source/sink it); a degree-1 imposer keeps its given, trusted
    # value with no consistency check (it IS the boundary condition).
    root = tree.order[0]
    for node in reversed(tree.order):
        if node == root:
            continue
        parent_e_idx = tree.parent_edge[node]
        parent_e = edges[parent_e_idx]
        if len(incident[node]) == 1:
            if parent_e.kind in _UNKNOWN_FLOW_KINDS:
                _log.info(
                    "hardy_cross: dead-end %s edge %s forced to zero flow",
                    parent_e.kind,
                    parent_e.id,
                )
                parent_e.flow = 0.0
            continue
        balance = sum(
            sign * edges[idx].flow
            for idx, sign in incident[node]
            if idx != parent_e_idx
        )
        sign_here = -1 if parent_e.a == node else 1
        required = -balance * sign_here
        if parent_e.kind in _UNKNOWN_FLOW_KINDS:
            parent_e.flow = required
        elif abs(required - parent_e.flow) > _CONSERVATION_TOL:
            _log.warning(
                "hardy_cross: node %s over-constrained by fixed imposer flows "
                "(needs %.6g, imposer gives %.6g)",
                node,
                required,
                parent_e.flow,
            )
            return Err(
                SolveError.OutOfDomain(
                    payload_feature_violation(FLOWNET_PORT, "overconstrained_demand")
                )
            )

    if len(incident[root]) > 1:
        root_balance = sum(sign * edges[idx].flow for idx, sign in incident[root])
        if abs(root_balance) > _CONSERVATION_TOL:
            _log.warning(
                "hardy_cross: network demand does not globally balance "
                "(residual %.6g m^3/s at root %s)",
                root_balance,
                root,
            )
            return Err(
                SolveError.OutOfDomain(
                    payload_feature_violation(FLOWNET_PORT, "unbalanced_demand")
                )
            )
    return Ok(None)


def _hardy_cross_solve(
    payload: _FlownetPayload,
) -> "Result[list[_Edge], SolveError]":
    try:
        edges = [_Edge(e) for e in payload.edges]
    except _UnsupportedFeature as exc:
        _log.info("hardy_cross: unsupported feature %s (%s)", exc.feature, exc.edge_id)
        return Err(
            SolveError.OutOfDomain(payload_feature_violation(FLOWNET_PORT, exc.feature))
        )

    tree_result = _spanning_tree(payload.nodes, edges)
    if tree_result.is_err:
        return Err(tree_result.danger_err)
    tree = tree_result.danger_ok
    loops = _build_cycle_basis(payload.nodes, edges, tree)

    seed_result = _seed_continuity_respecting_flows(payload.nodes, edges, tree)
    if seed_result.is_err:
        return Err(seed_result.danger_err)

    for iteration in range(1, _HC_MAX_ITER + 1):
        max_dq = 0.0
        for loop in loops:
            numerator = 0.0
            denominator = 0.0
            for edge_idx, sign in loop:
                edge = edges[edge_idx]
                if edge.kind not in _UNKNOWN_FLOW_KINDS:
                    numerator += sign * 0.0  # imposer contributes no loop head term
                    continue
                signed_flow = sign * edge.flow
                dp, k = _edge_dp_and_k(edge, signed_flow)
                numerator += dp
                denominator += k
            if denominator == 0.0:
                # L3 (cycle-28 audit): a cycle-basis loop of ONLY
                # fixed-flow imposer edges has no pipe unknown to
                # correct with (denominator stays 0 every iteration)
                # AND no head-loss model for imposer edges (module
                # docstring's named cut) to verify its head balance
                # against. Silently `continue`-ing here let such a
                # loop's imbalance go forever unverified while
                # `max_dq` (driven only by OTHER loops) still reached
                # `_HC_TOL`, so the overall solve reported "converged"
                # for a loop this method structurally cannot certify.
                # Honest: refuse rather than fabricate a convergence
                # claim for a loop this algorithm has no information
                # about.
                loop_edge_ids = [edges[edge_idx].id for edge_idx, _sign in loop]
                _log.warning(
                    "hardy_cross: all-imposer cycle-basis loop %s has no "
                    "flow unknown and no head-loss model to verify its "
                    "balance -- cannot certify convergence",
                    loop_edge_ids,
                )
                return Err(
                    SolveError.OutOfDomain(
                        payload_feature_violation(FLOWNET_PORT, "all_imposer_loop")
                    )
                )
            dq = -numerator / denominator
            max_dq = max(max_dq, abs(dq))
            for edge_idx, sign in loop:
                edge = edges[edge_idx]
                if edge.kind in _UNKNOWN_FLOW_KINDS:
                    edge.flow += sign * dq
        _log.debug("hardy_cross: iteration %d max|dQ|=%s", iteration, max_dq)
        if max_dq < _HC_TOL:
            _log.info(
                "hardy_cross: converged in %d iterations (max|dQ|=%s)",
                iteration,
                max_dq,
            )
            return Ok(edges)

    _log.warning(
        "hardy_cross: non-convergent after %d iterations (max|dQ|=%s)",
        _HC_MAX_ITER,
        max_dq,
    )
    return Err(SolveError.NoConvergence(iterations=_HC_MAX_ITER, residual=max_dq))


# frob:doc docs/modules/fluids.md#fluids_network
class SolvedNetwork:
    """The parsed + Hardy-Cross-converged network (WO-141 pack bridge):
    wraps the SAME solved `_Edge` list `hardy_cross_fn` serializes to
    its `table` output (NO DUPLICATION -- re-solving per query model
    would be a second copy of the loop-correction call), plus by-id
    and by-node indexes the query models in `feldspar.pack.models`
    (`FluidsMdotModel`/`FluidsFlowImbalanceModel`/`FluidsDpModel`) use
    to answer a single-edge flow, a sibling-edge-set imbalance, or a
    multi-segment path pressure drop without re-parsing the payload."""

    __slots__ = ("payload", "edges", "by_id", "incidence")

    def __init__(self, payload: _FlownetPayload, edges: list[_Edge]) -> None:
        self.payload = payload
        self.edges = edges
        self.by_id: dict[str, _Edge] = {e.id: e for e in edges}
        incidence: dict[str, list[tuple[_Edge, int]]] = {n: [] for n in payload.nodes}
        for e in edges:
            incidence[e.a].append((e, -1))  # e.flow > 0 = outflow from a
            incidence[e.b].append((e, 1))  # and inflow to b
        self.incidence = incidence


# frob:doc docs/modules/fluids.md#fluids_network
def solve_flownet_bytes(data: bytes) -> "Result[SolvedNetwork, SolveError]":
    """Parses `data` as a `_FlownetPayload` (D154 wire subset, this
    module's own field-name-compatible schema) and runs the Hardy-Cross
    solve (`_hardy_cross_solve`, NO DUPLICATION -- the exact function
    `hardy_cross_fn` itself calls), returning a `SolvedNetwork` the
    pack query models index by edge id / node id. Never imports
    regolith (FINV-3/10): this takes raw bytes, already resolved by the
    caller (`feldspar.pack.models`, under the FINV-3 boundary) through
    whatever `PayloadResolver` it has -- the parse boundary here is the
    same one `hardy_cross_fn` uses, just exposed as a standalone
    function instead of inlined in a solver-direction closure.

    Any bytes that do not validate against the `_FlownetPayload` shape
    are an honest `SolveError.ParseFailed`, never a silent partial
    parse; a solve failure (unsupported edge kind, disconnected net,
    unbalanced/overconstrained demand, non-convergence) is whatever
    `_hardy_cross_solve` itself reports, unchanged."""
    try:
        payload = _FlownetPayload.model_validate_json(data)
    except Exception as exc:  # noqa: BLE001 -- any parse failure is an honest ParseFailed
        _log.info("solve_flownet_bytes: flownet payload parse failed: %s", exc)
        return Err(SolveError.ParseFailed(context=f"flownet payload: {exc}"))
    solved = _hardy_cross_solve(payload)
    if solved.is_err:
        return Err(solved.danger_err)
    return Ok(SolvedNetwork(payload, solved.danger_ok))


# frob:doc docs/modules/fluids.md#fluids_network
def edge_dp(edge: "_Edge") -> float:
    """The converged signed pressure drop across one solved edge (a->b
    positive sense): pipe/orifice/hx_segment via `_edge_dp_and_k` (NO
    DUPLICATION -- the same dispatcher `hardy_cross_fn`'s own
    row-building loop calls); imposer edges report `0.0` -- the
    module's own named cut (no head-loss model for a fixed-flow
    branch, see `_hardy_cross_solve`'s all-imposer-loop refusal for the
    same admission stated as a hard error there; here, on an edge that
    is merely PART of a longer queried path rather than the whole loop,
    a zero contribution is the honest "this branch's head loss is not
    modeled" statement, not a fabricated number)."""
    if edge.kind not in _UNKNOWN_FLOW_KINDS:
        return 0.0
    dp, _k = _edge_dp_and_k(edge, edge.flow)
    return dp


# frob:doc docs/modules/fluids.md#fluids_network
def find_path_edges(
    solved: SolvedNetwork, node_a: str, node_b: str
) -> "Result[list[tuple[_Edge, int]], SolveError]":
    """BFS shortest path (by edge count) from `node_a` to `node_b` over
    the FULL solved edge set (pipe + imposer), returned as `(edge,
    sign)` pairs where `sign=+1` means the path traverses the edge in
    its own `a->b` sense, `-1` the reverse.

    Once Hardy-Cross has converged, the network's node heads form a
    consistent potential field (White, Fluid Mechanics, 8th ed., sec.
    6.8): the total head difference between any two nodes is the same
    regardless of which connecting path sums it, so BFS-shortest is
    just the cheapest path to compute, never a physically-privileged
    one. `Err(SolveError.OutOfDomain(...))` names an unknown node id or
    a genuinely disconnected pair (unreachable in practice once the
    overall solve already refused a disconnected graph, but checked
    honestly rather than assumed)."""
    if node_a not in solved.incidence or node_b not in solved.incidence:
        return Err(
            SolveError.OutOfDomain(
                payload_feature_violation(FLOWNET_PORT, "unknown_node")
            )
        )
    if node_a == node_b:
        return Ok([])
    adjacency: dict[str, list[tuple[str, _Edge, int]]] = {
        n: [] for n in solved.payload.nodes
    }
    for e in solved.edges:
        adjacency[e.a].append((e.b, e, 1))
        adjacency[e.b].append((e.a, e, -1))

    visited = {node_a}
    parent: dict[str, tuple[str, _Edge, int]] = {}
    queue = [node_a]
    while queue:
        node = queue.pop(0)
        if node == node_b:
            break
        for neighbor, e, sign in adjacency[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                parent[neighbor] = (node, e, sign)
                queue.append(neighbor)

    if node_b not in visited:
        return Err(
            SolveError.OutOfDomain(
                payload_feature_violation(FLOWNET_PORT, "disconnected_query_path")
            )
        )
    path: list[tuple[_Edge, int]] = []
    cur = node_b
    while cur != node_a:
        prev, e, sign = parent[cur]
        path.append((e, sign))
        cur = prev
    path.reverse()
    return Ok(path)


def _make_hardy_cross_direction(resolver: PayloadResolver):
    def hardy_cross_fn(x):
        flownet_result = resolver.resolve(x[FLOWNET_PORT])
        if flownet_result.is_err:
            _log.warning(
                "fluids.network.hardy_cross: flownet payload unresolvable: %r",
                flownet_result.err,
            )
            return flownet_result
        payload = _FlownetPayload.model_validate_json(flownet_result.danger_ok)
        solved_result = _hardy_cross_solve(payload)
        if solved_result.is_err:
            return solved_result
        edges = solved_result.danger_ok
        rows = []
        for edge in edges:
            dp = 0.0
            if edge.kind in _UNKNOWN_FLOW_KINDS:
                dp, _k = _edge_dp_and_k(edge, edge.flow)
            rows.append({"edge_id": edge.id, "flow_rate": edge.flow, "dp": dp})
        content = json.dumps({"edges": rows}, sort_keys=True).encode()
        ref = resolver.store("table", content, "fluids.network.hardy_cross")
        _log.info(
            "fluids.network.hardy_cross: solved %d edges -> payload %s",
            len(rows),
            ref.digest,
        )
        return Ok(SolveOutput(values={}, payloads={SOLUTION_PORT: ref}))

    info, fn = make_direction(
        solver_id="fluids.network.hardy_cross",
        namespace="fluids.network",
        inputs=(FLOWNET_PORT,),
        outputs=(SOLUTION_PORT,),
        # No scalar box: the network enters as a payload; coverage
        # (edge kinds/params/connectivity) is an execution-time payload-
        # feature check (09 sec. 4a), not a scalar domain.
        domain=Domain({}, {"incompressible", "network"}),
        cost=3.0,
        accuracy=EXACT,
        citations=(_HARDY_CROSS_CITATION, _WHITE_NETWORK_CITATION),
        version="1",
        tier="discretized",
        # Bug fix (cycle-35 WO-118 integration): fold the resolver's own
        # kind into the settings digest -- see
        # `feldspar.solve.payload.resolver_cache_identity`'s docstring.
        settings=canonical_digest({"resolver": resolver_cache_identity(resolver)}),
        fn=hardy_cross_fn,
    )
    return info, fn


# frob:doc docs/modules/fluids.md#fluids_network
def register(registry: SolverRegistry, resolver: PayloadResolver) -> None:
    """Declares this module's port table (payload ports need declared
    kinds, F12) and registers the Hardy-Cross direction, closed over
    the caller's resolver. Must be called after every declaration-free
    module (`mech`, `fluids` incompressible/compressible, `heat`,
    `thermo`) has registered, same F12 ordering constraint
    `fea.payload_steps` documents."""
    ports_result = registry.declare_ports(
        PortDecl(FLOWNET_PORT, "", Rank.payload("flownet")),
        PortDecl(SOLUTION_PORT, "", Rank.payload("table")),
    )
    _ = ports_result.danger_ok
    info, fn = _make_hardy_cross_direction(resolver)
    result = registry.register(info, fn)
    _ = result.danger_ok
    _log.info("fluids.network: registered 1 payload direction (hardy_cross)")
