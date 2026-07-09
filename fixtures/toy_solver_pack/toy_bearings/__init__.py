"""`toy_bearings` -- the WO-19 M9 acceptance fixture: a toy out-of-repo
feldspar solver pack. Registers ONE closed-form direction under its
OWN sub-namespace (`mech.toy_bearings.*`, 10 sec. 3's namespace
etiquette) and nothing else. This package is deliberately trivial: its
only job is to exist outside the feldspar repo's own `python/feldspar`
tree and pass `feldspar.testing.assert_solverpack_conforms` from its
own test session (`tests/test_conformance.py`), proving the
`feldspar.solver_packs` seam is real plug-and-play, not just an
in-repo abstraction."""

from __future__ import annotations

from typani import Ok

from feldspar.core import Accuracy, Domain, Interval
from feldspar.solve import Citation, SolverRegistry, solver

__all__ = ["register"]


@solver(
    namespace="mech.toy_bearings",
    inputs=("mech.toy_bearings.bore_diameter", "mech.toy_bearings.load"),
    outputs=("mech.toy_bearings.contact_pressure",),
    domain=Domain(
        box={
            "mech.toy_bearings.bore_diameter": Interval(1e-3, 1.0),
            "mech.toy_bearings.load": Interval(1.0, 1e5),
        },
        tags=frozenset(),
    ),
    cost=1e-6,
    accuracy={"mech.toy_bearings.contact_pressure": Accuracy(eps_abs=0.0, eps_rel=0.0)},
    citations=(
        Citation(
            kind="handbook",
            ref="WO-19 M9 acceptance fixture -- toy formula, not a real bearing rating",
        ),
    ),
    version="1",
)
def bearing_contact_pressure(x):
    """A toy closed-form direction: load divided by bore diameter --
    not a real bearing-rating formula, just enough physical shape (a
    monotone division) to exercise the kit's corner-monotonicity spot
    check meaningfully."""
    bore = x["mech.toy_bearings.bore_diameter"]
    load = x["mech.toy_bearings.load"]
    return Ok({"mech.toy_bearings.contact_pressure": load / bore})


def register(registry: SolverRegistry) -> None:
    """Registers `bearing_contact_pressure` and nothing else -- the
    `feldspar.solver_packs` entry-point target (`pyproject.toml`)."""
    _ = registry.register(*bearing_contact_pressure.solver_direction).danger_ok
