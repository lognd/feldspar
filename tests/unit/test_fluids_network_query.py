from __future__ import annotations

"""WO-141 (feldspar fluids pack bridge) query-helper tests:
`feldspar.fluids.network.solve_flownet_bytes`/`find_path_edges`/
`edge_dp`, the pieces `feldspar.pack.models`'s `FluidsMdotModel`/
`FluidsFlowImbalanceModel`/`FluidsDpModel` build on. Regolith-free (no
`DischargeRequest`/`Model` involved) -- those wrappers are exercised in
`tests/regolith/test_pack_wo141_fluids_network.py`.

Calibration anchor: the SAME asymmetric two-branch Hagen-Poiseuille
oracle `tests/unit/test_library_fluids_network.py` uses (White, Fluid
Mechanics, 8th ed., sec. 6.4) -- an independent closed form, not the
solver's own code path, proving the query helpers read the converged
solve correctly rather than just re-deriving whatever the solver
already computed."""

import json
import math

import pytest

from feldspar.fluids.network import edge_dp, find_path_edges, solve_flownet_bytes
from feldspar.solve import SolveError


def _scalar(value: float, unit: str = "m") -> dict:
    return {"lo": value, "hi": value, "unit": unit}


def _pipe(edge_id, a, b, length, diameter, roughness, density, viscosity) -> dict:
    return {
        "id": edge_id,
        "a": a,
        "b": b,
        "kind": "pipe",
        "params": {
            "source": "scalars",
            "values": {
                "length": _scalar(length),
                "diameter": _scalar(diameter),
                "roughness": _scalar(roughness),
                "density": _scalar(density, "kg/m^3"),
                "viscosity": _scalar(viscosity, "Pa s"),
            },
        },
    }


def _imposer(edge_id, a, b, flow_rate) -> dict:
    return {
        "id": edge_id,
        "a": a,
        "b": b,
        "kind": "imposer",
        "params": {
            "source": "scalars",
            "values": {"flow_rate": _scalar(flow_rate, "m^3/s")},
        },
    }


_LENGTH_A, _LENGTH_B = 1.0, 2.0
_DIAMETER = 0.02
_DENSITY, _VISCOSITY = 1000.0, 1e-3
_Q_TOTAL = 1e-5


def _asymmetric_payload_bytes() -> bytes:
    payload = {
        "nodes": ["src", "n1", "n2", "sink"],
        "edges": [
            _imposer("imp_in", "src", "n1", _Q_TOTAL),
            _pipe("A", "n1", "n2", _LENGTH_A, _DIAMETER, 0.0, _DENSITY, _VISCOSITY),
            _pipe("B", "n1", "n2", _LENGTH_B, _DIAMETER, 0.0, _DENSITY, _VISCOSITY),
            _imposer("imp_out", "n2", "sink", _Q_TOTAL),
        ],
    }
    return json.dumps(payload).encode()


def _resistance(length: float) -> float:
    return 128.0 * _VISCOSITY * length / (math.pi * _DIAMETER**4)


def test_solve_flownet_bytes_matches_hagen_poiseuille_split() -> None:
    solved = solve_flownet_bytes(_asymmetric_payload_bytes())
    assert solved.is_ok
    network = solved.danger_ok

    r_a, r_b = _resistance(_LENGTH_A), _resistance(_LENGTH_B)
    expected_a = _Q_TOTAL * r_b / (r_a + r_b)
    expected_b = _Q_TOTAL * r_a / (r_a + r_b)
    assert network.by_id["A"].flow == pytest.approx(expected_a, rel=1e-3)
    assert network.by_id["B"].flow == pytest.approx(expected_b, rel=1e-3)


def test_edge_dp_matches_across_parallel_branches() -> None:
    """Two parallel branches between the same node pair must show the
    SAME converged head loss (that is what "parallel" means for a
    Hardy-Cross loop correction to have actually converged)."""
    network = solve_flownet_bytes(_asymmetric_payload_bytes()).danger_ok
    dp_a = edge_dp(network.by_id["A"])
    dp_b = edge_dp(network.by_id["B"])
    assert dp_a == pytest.approx(dp_b, rel=1e-3)


def test_edge_dp_is_zero_for_imposer_edges() -> None:
    """Named cut (module docstring): no head-loss model for a
    fixed-flow imposer branch -- `edge_dp` reports 0.0, never a guess."""
    network = solve_flownet_bytes(_asymmetric_payload_bytes()).danger_ok
    assert edge_dp(network.by_id["imp_in"]) == 0.0
    assert edge_dp(network.by_id["imp_out"]) == 0.0


def test_find_path_edges_end_to_end_dp_matches_single_branch_plus_imposers() -> None:
    """The src->sink path dp is the sum of the imposer legs (0.0 each)
    plus whichever single branch dp -- both branches carry the SAME dp
    once converged, so either path gives the same total."""
    network = solve_flownet_bytes(_asymmetric_payload_bytes()).danger_ok
    path = find_path_edges(network, "src", "sink")
    assert path.is_ok
    edges = path.danger_ok
    total = sum(sign * edge_dp(edge) for edge, sign in edges)
    assert total == pytest.approx(edge_dp(network.by_id["A"]), rel=1e-3)


def test_find_path_edges_same_node_is_the_empty_path() -> None:
    network = solve_flownet_bytes(_asymmetric_payload_bytes()).danger_ok
    path = find_path_edges(network, "n1", "n1")
    assert path.is_ok
    assert path.danger_ok == []


def test_find_path_edges_unknown_node_is_honest_out_of_domain() -> None:
    network = solve_flownet_bytes(_asymmetric_payload_bytes()).danger_ok
    path = find_path_edges(network, "src", "nowhere")
    assert path.is_err
    assert isinstance(path.err, SolveError)
    assert path.err.kind == "OutOfDomain"
    assert path.err.violation.tag == "unknown_node"


# frob:tests python/feldspar/solve/errors.py::SolveError.ParseFailed kind="unit"
def test_solve_flownet_bytes_rejects_malformed_json_honestly() -> None:
    result = solve_flownet_bytes(b"not json")
    assert result.is_err
    assert isinstance(result.err, SolveError)
    assert result.err.kind == "ParseFailed"
