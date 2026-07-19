from __future__ import annotations

"""The ONE feldspar-error -> regolith-`DomainError` mapping (06
"Failures"): every `SolveError`/`PlanError` variant maps honestly, with
the original message embedded, never an exception."""

import pytest
from regolith.harness.errors import DomainError

from feldspar.pack.errors import map_engine_error
from feldspar.plan.errors import PlanError
from feldspar.solve.errors import SolveError

pytestmark = pytest.mark.regolith


@pytest.mark.parametrize(
    "error",
    [
        SolveError.ToolMissing(tool="gmsh", guidance="install the mesh extra"),
        SolveError.ToolFailed(tool="ccx", log_tail="segfault"),
        SolveError.Timeout(tool="ccx", seconds=30.0),
        SolveError.ParseFailed(context="results.dat"),
        SolveError.OutOfDomain(violation="radius too small"),
        SolveError.NonFinite(port="mech.stress.von_mises"),
        SolveError.MissingOutput(port="mech.deflection.tip"),
        SolveError.InvalidMeasurement(reason="negative eps"),
        SolveError.BudgetExceeded(realized=1.0, budget=0.5),
        SolveError.NoRouteRemaining(attempts=()),
        PlanError.InvalidBudget(),
        PlanError.UnknownTarget(target="mech.stress.von_mises"),
        PlanError.NoApplicableSolver(),
        PlanError.BudgetUnreachable(best_eps=0.2),
        PlanError.CyclicPortEquivalence(),
    ],
)
# frob:tests python/feldspar/pack/errors.py::map_engine_error kind="unit"
def test_every_variant_maps_to_domain_error(error: object) -> None:
    """Every `SolveError`/`PlanError` variant -> a `DomainError` embedding
    the original kind/fields in its message -- never an exception, never
    silently dropped."""
    mapped = map_engine_error("fea_static_stress@1", error)
    assert isinstance(mapped, DomainError)
    assert mapped.model_id == "fea_static_stress@1"
    assert error.kind in mapped.message  # type: ignore[attr-defined]
