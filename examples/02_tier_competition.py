"""Two tiers, one port: the budget decides, the failure reroutes.

TARGET-API sketch. A cheap-but-sloppy table solver and a
costly-but-tight closed form both produce mech.stress.von_mises; a
loose budget picks the table, a tight budget forces the formula, and
killing the winner exercises fallback rerouting (04).
"""

from feldspar.core import Accuracy, Citation, Domain, Interval
from feldspar.plan import RoutePolicy, solve
from feldspar.solve import SolverRegistry, solver

COMMON = dict(
    namespace="mech",
    inputs=("mech.pressure.internal", "mech.geom.cylinder.ratio"),
    outputs=("mech.stress.von_mises",),
    domain=Domain(box={"mech.geom.cylinder.ratio": Interval(1.1, 3.0)}, tags=frozenset()),
    version="1",
)


@solver(
    **COMMON,
    solver_id_suffix="chart",
    cost=1e-7,
    accuracy={"mech.stress.von_mises": Accuracy(eps_abs=0.0, eps_rel=0.05)},  # 5% chart
    citations=(Citation(kind="handbook", ref="Roark 9e, Table 13.5 (digitized)"),),
)
def lame_chart(x): ...


@solver(
    **COMMON,
    solver_id_suffix="exact",
    cost=1e-5,
    accuracy={"mech.stress.von_mises": Accuracy(eps_abs=0.0, eps_rel=0.0)},
    citations=(Citation(kind="handbook", ref="Roark 9e, eq. 13.5-2 (Lame)"),),
)
def lame_exact(x): ...


def main() -> None:
    registry = SolverRegistry()
    for fn in (lame_chart, lame_exact):
        registry.register(*fn.solver_direction).unwrap()
    registry.freeze()

    known = {
        "mech.pressure.internal": Interval(2.0e7, 2.1e7),
        "mech.geom.cylinder.ratio": Interval(1.5, 1.5),
    }

    loose = solve(registry, known=known, tags=set(), target="mech.stress.von_mises",
                  eps_budget=5e6).unwrap()
    assert "chart" in loose.route.steps[0].solver_id  # cheap tier wins fat margin

    tight = solve(registry, known=known, tags=set(), target="mech.stress.von_mises",
                  eps_budget=1e5).unwrap()
    assert "exact" in tight.route.steps[0].solver_id  # budget forces the tight tier

    # Fallback: policy point, not a code path we can fake here -- with
    # fallback=False a failing step returns the error; default replans.
    strict = RoutePolicy(fallback=False)
    _ = strict


if __name__ == "__main__":
    main()
