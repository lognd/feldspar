"""Complexity rung 0 -- the raw protocol, no sugar. BASELINE.

One trivial formula (rectangular second moment of area), written with
zero conveniences, to measure the floor of boilerplate every sugar
proposal is judged against. Verdict (see README): 28 lines for a
one-line formula is too much friction for a 300-entry catalog; the
coercions in 01_sugar_coercions.py are REQUIRED, and every sugar
form must LOWER to exactly this -- one protocol, sugar on top.
"""

from feldspar.core import Accuracy, Domain, Interval
from feldspar.solve import Citation, SolverRegistry, solver
from typani import Ok


@solver(
    namespace="mech",
    inputs=("mech.section.width", "mech.section.height"),
    outputs=("mech.section.second_moment",),
    domain=Domain(
        box={
            "mech.section.width": Interval(1e-4, 1.0),
            "mech.section.height": Interval(1e-4, 1.0),
        },
        tags=frozenset(),
    ),
    cost=1e-7,
    accuracy={"mech.section.second_moment": Accuracy(eps_abs=0.0, eps_rel=0.0)},
    citations=(
        Citation(kind="handbook", ref="Gere, Mechanics of Materials 9e, App. E"),
    ),
    version="1",
)
def rect_second_moment(x):
    b, h = x["mech.section.width"], x["mech.section.height"]
    return Ok({"mech.section.second_moment": b * h**3 / 12.0})


def register(registry: SolverRegistry) -> None:
    registry.register(*rect_second_moment.solver_direction).unwrap()
