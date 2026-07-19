from __future__ import annotations

"""Direct unit test for `feldspar.fluids.register_network` (WO-20
residual, F12 payload-port declaration path) -- the pack-level and
query-helper tests exercise the Hardy-Cross solver body itself
(`tests/regolith/test_pack_wo141_fluids_network.py`,
`tests/unit/test_fluids_network_query.py`) but never the thin
`register_network` wrapper directly, so it had no binding of its own."""

from feldspar.fluids import register_network
from feldspar.fluids.network import FLOWNET_PORT
from feldspar.pack.payload_bridge import NoStoreResolver
from feldspar.solve import SolverRegistry


# frob:tests python/feldspar/fluids/__init__.py::register_network kind="unit"
def test_register_network_declares_the_flownet_solver_direction() -> None:
    """`register_network` must add exactly one solver direction that
    consumes the `FLOWNET_PORT` payload port (module docstring's F12
    ordering contract), regardless of which resolver it is threaded."""
    registry = SolverRegistry()
    register_network(registry, NoStoreResolver())
    solver_ids = [info.solver_id for info, _fn in registry]
    assert len(solver_ids) == 1
    (info, _fn) = next(iter(registry))
    assert FLOWNET_PORT in info.inputs
