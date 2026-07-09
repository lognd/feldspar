from __future__ import annotations

"""WO-20 residual conformance tests: the Hardy-Cross `flownet`-payload
solver (`feldspar/library/fluids/network.py`), called THROUGH the
`SolverRegistry`/`SolveFn` protocol against hand-built D154-shaped
payload fixtures.

Calibration anchors:

- The SYMMETRIC two-branch case is the benchmarks memo sec. 3.2
  parallel-network worked case, wired verbatim: two identical branches
  passing Q_total = 0.012 m^3/s split evenly (Q1 = Q2 = 0.006 m^3/s at
  delta-h = 4.0 m) -- an oracle independent of the exact resistance
  formula (symmetric branches split evenly by construction, regardless
  of whether the loss law is linear or quadratic in Q).
- The ASYMMETRIC two-branch case is an independent Hagen-Poiseuille
  closed-form oracle (White, Fluid Mechanics, 8th ed., sec. 6.4): two
  laminar branches of different length split flow inversely
  proportional to their resistance, `Q_A / Q_B = R_B / R_A` where
  `R = 128 mu L / (pi D^4)`; this WO's `_pipe_dp_and_k` composes the
  SAME Darcy-Weisbach/friction-factor Rust homes `incompressible.py`
  wraps, so this checks the loop solve's CONVERGENCE and CONTINUITY
  bookkeeping against a textbook formula computed independently in
  this test file, not the solver's own code path.
- The non-convergent/unsupported-feature cases prove the honest-
  indeterminate posture (WO-20's "never fake convergence" mandate):
  an out-of-coverage edge kind, unresolvable params source, and a
  disconnected network each report `SolveError.OutOfDomain` naming the
  offending feature, never a fabricated result."""

import hashlib
import json
import math
from typing import Dict

import pytest
from typani import Err, Ok

from feldspar.library.fluids.network import FLOWNET_PORT, SOLUTION_PORT, register
from feldspar.solve import PayloadRef, SolveError, SolverRegistry


class _DictResolver:
    """In-memory orchestrator-store stand-in (D96/OPEN-2 handle), same
    shape as `tests/integration/test_fea_payload_steps.py`'s."""

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


def _scalar(value: float, unit: str = "m") -> dict:
    return {"lo": value, "hi": value, "unit": unit}


def _pipe(
    edge_id: str,
    a: str,
    b: str,
    length: float,
    diameter: float,
    roughness: float,
    density: float,
    viscosity: float,
) -> dict:
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


def _imposer(edge_id: str, a: str, b: str, flow_rate: float) -> dict:
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


def _setup():
    resolver = _DictResolver()
    registry = SolverRegistry()
    register(registry, resolver)
    registry.freeze()
    info, fn = next(iter(registry))
    return resolver, fn


def _solve(resolver, fn, payload: dict):
    ref = resolver.store("flownet", json.dumps(payload).encode(), "test-fixture")
    result = fn({FLOWNET_PORT: ref})
    return result


def _solution_rows(resolver, result) -> dict:
    ref = result.danger_ok.payloads[SOLUTION_PORT]
    solved = json.loads(resolver.resolve(ref).danger_ok)
    return {row["edge_id"]: row for row in solved["edges"]}


def test_symmetric_parallel_network_splits_evenly():
    """Benchmarks memo sec. 3.2 verbatim: Q_total=0.012 m^3/s into two
    identical branches splits evenly, Q1=Q2=0.006 m^3/s."""
    resolver, fn = _setup()
    q_total = 0.012
    payload = {
        "nodes": ["src", "n1", "n2", "sink"],
        "edges": [
            _imposer("imp_in", "src", "n1", q_total),
            _pipe("A", "n1", "n2", 10.0, 0.1, 4.5e-5, 1000.0, 1e-3),
            _pipe("B", "n1", "n2", 10.0, 0.1, 4.5e-5, 1000.0, 1e-3),
            _imposer("imp_out", "n2", "sink", q_total),
        ],
    }
    result = _solve(resolver, fn, payload)
    assert result.is_ok
    rows = _solution_rows(resolver, result)
    assert rows["A"]["flow_rate"] == pytest.approx(0.006, rel=1e-3)
    assert rows["B"]["flow_rate"] == pytest.approx(0.006, rel=1e-3)
    assert rows["A"]["dp"] == pytest.approx(rows["B"]["dp"], rel=1e-3)


def test_asymmetric_laminar_network_matches_hagen_poiseuille_oracle():
    """Independent Hagen-Poiseuille oracle: R = 128 mu L / (pi D^4);
    parallel branches split inversely proportional to resistance."""
    resolver, fn = _setup()
    length_a, length_b = 1.0, 2.0
    diameter = 0.02
    density, viscosity = 1000.0, 1e-3
    q_total = 1e-5
    payload = {
        "nodes": ["src", "n1", "n2", "sink"],
        "edges": [
            _imposer("imp_in", "src", "n1", q_total),
            _pipe("A", "n1", "n2", length_a, diameter, 0.0, density, viscosity),
            _pipe("B", "n1", "n2", length_b, diameter, 0.0, density, viscosity),
            _imposer("imp_out", "n2", "sink", q_total),
        ],
    }
    result = _solve(resolver, fn, payload)
    assert result.is_ok
    rows = _solution_rows(resolver, result)

    def resistance(length: float) -> float:
        return 128.0 * viscosity * length / (math.pi * diameter**4)

    r_a, r_b = resistance(length_a), resistance(length_b)
    expected_q_a = q_total * r_b / (r_a + r_b)
    expected_q_b = q_total * r_a / (r_a + r_b)
    assert rows["A"]["flow_rate"] == pytest.approx(expected_q_a, rel=1e-3)
    assert rows["B"]["flow_rate"] == pytest.approx(expected_q_b, rel=1e-3)
    # Conservation: the two branches must sum to the imposed total.
    assert rows["A"]["flow_rate"] + rows["B"]["flow_rate"] == pytest.approx(
        q_total, rel=1e-6
    )


def test_unsupported_edge_kind_is_honest_indeterminate():
    """A `valve` edge (out of this pass's coverage) reports
    `OutOfDomain` naming the unsupported kind -- never a silent
    approximation."""
    resolver, fn = _setup()
    payload = {
        "nodes": ["n1", "n2"],
        "edges": [
            {
                "id": "V",
                "a": "n1",
                "b": "n2",
                "kind": "valve",
                "params": {"source": "scalars", "values": {}},
            }
        ],
    }
    result = _solve(resolver, fn, payload)
    assert result.is_err
    assert isinstance(result.err, SolveError)
    assert result.err.kind == "OutOfDomain"
    assert result.err.violation.tag == "edge_kind:valve"


def test_geometry_extract_params_are_cut_honestly():
    """`EdgeParams2` (geometry-extract selector, `source: geom_extract`)
    is a named cut this pass -- reported as OutOfDomain, never silently
    treated as scalars."""
    resolver, fn = _setup()
    payload = {
        "nodes": ["n1", "n2"],
        "edges": [
            {
                "id": "A",
                "a": "n1",
                "b": "n2",
                "kind": "pipe",
                "params": {
                    "source": "geom_extract",
                    "record": "somehash",
                    "selector": "wetted",
                },
            }
        ],
    }
    result = _solve(resolver, fn, payload)
    assert result.is_err
    assert result.err.violation.tag == "edge_params:geom_extract"


def test_disconnected_network_is_honest_indeterminate():
    """Two disjoint components: out of coverage, named explicitly."""
    resolver, fn = _setup()
    payload = {
        "nodes": ["n1", "n2", "n3", "n4"],
        "edges": [
            _pipe("A", "n1", "n2", 1.0, 0.02, 0.0, 1000.0, 1e-3),
            _pipe("B", "n3", "n4", 1.0, 0.02, 0.0, 1000.0, 1e-3),
        ],
    }
    result = _solve(resolver, fn, payload)
    assert result.is_err
    assert result.err.violation.tag == "disconnected_network"


def test_overconstrained_demand_is_honest_indeterminate():
    """Two fixed imposers at a single junction whose flows cannot both
    be satisfied (no pipe/chord free to absorb the mismatch) is
    reported, never silently dropped or averaged away."""
    resolver, fn = _setup()
    payload = {
        "nodes": ["src", "n1", "sink1", "sink2"],
        "edges": [
            _imposer("imp_in", "src", "n1", 1.0e-4),
            _imposer("imp_out1", "n1", "sink1", 1.0e-4),
            _imposer("imp_out2", "n1", "sink2", 1.0e-4),
        ],
    }
    result = _solve(resolver, fn, payload)
    assert result.is_err
    assert result.err.violation.tag in (
        "overconstrained_demand",
        "unbalanced_demand",
    )


def test_all_imposer_cycle_loop_is_honest_indeterminate():
    """L3 (cycle-28 audit): two parallel fixed-flow imposer edges
    between the same node pair form a cycle-basis loop with NO pipe
    unknown (denominator stays 0 every iteration) and no head-loss
    model for imposer edges (module docstring's named cut) to verify
    it against. Continuity is fully satisfied here (0.6e-4 + 0.4e-4 =
    1e-4 splits and recombines exactly) -- this is not an
    over/under-constrained demand case -- yet the loop's head balance
    is structurally unverifiable by Hardy-Cross, so the solve must
    report `OutOfDomain`, never a fabricated "converged"."""
    resolver, fn = _setup()
    payload = {
        "nodes": ["src", "a", "b", "sink"],
        "edges": [
            _imposer("imp_in", "src", "a", 1.0e-4),
            _imposer("imp1", "a", "b", 0.6e-4),
            _imposer("imp2", "a", "b", 0.4e-4),
            _imposer("imp_out", "b", "sink", 1.0e-4),
        ],
    }
    result = _solve(resolver, fn, payload)
    assert result.is_err
    assert result.err.kind == "OutOfDomain"
    assert result.err.violation.tag == "all_imposer_loop"


def test_dead_end_pipe_forced_to_zero_flow():
    """A pipe leading to a degree-1 node with no imposer is a physical
    dead end: continuity forces it to zero flow, not an arbitrary
    guess."""
    resolver, fn = _setup()
    payload = {
        "nodes": ["src", "n1", "deadend", "sink"],
        "edges": [
            _imposer("imp_in", "src", "n1", 5e-5),
            _pipe("dead", "n1", "deadend", 1.0, 0.02, 0.0, 1000.0, 1e-3),
            _imposer("imp_out", "n1", "sink", 5e-5),
        ],
    }
    result = _solve(resolver, fn, payload)
    assert result.is_ok
    rows = _solution_rows(resolver, result)
    assert rows["dead"]["flow_rate"] == pytest.approx(0.0, abs=1e-12)
