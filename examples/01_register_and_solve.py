"""Minimal happy path: register a closed-form solver, solve, explain.

TARGET-API sketch (pre-implementation, examples are the spec's
pressure tests): if this file cannot stay this simple, the spec is
wrong, not the file.
"""

import logging

from feldspar.core import Accuracy, Citation, Domain, Interval
from feldspar.plan import RoutePolicy, solve
from feldspar.solve import SolverRegistry, solver

logging.basicConfig(level=logging.INFO)

R_AIR = 287.05  # J/(kg K), dry air


@solver(
    namespace="thermo",
    inputs=("thermo.pressure", "thermo.specific_volume"),
    outputs=("thermo.temperature",),
    domain=Domain(
        box={
            "thermo.pressure": Interval(1e3, 1e7),
            "thermo.specific_volume": Interval(1e-3, 1e2),
        },
        tags=frozenset({"ideal_gas"}),
    ),
    cost=1e-6,
    accuracy={"thermo.temperature": Accuracy(eps_abs=0.0, eps_rel=0.0)},
    citations=(
        Citation(kind="handbook", ref="Moran, Fund. of Eng. Thermo., 9e, sec. 3.5"),
    ),
    version="1",
)
def ideal_gas_pv_to_t(x):
    return {"thermo.temperature": x["thermo.pressure"] * x["thermo.specific_volume"] / R_AIR}


def main() -> None:
    registry = SolverRegistry()
    registry.register(*ideal_gas_pv_to_t.solver_direction).unwrap()
    registry.freeze()

    result = solve(
        registry,
        known={
            "thermo.pressure": Interval(101_000.0, 102_000.0),  # Pa, tolerance band
            "thermo.specific_volume": Interval(0.83, 0.85),  # m^3/kg
        },
        tags={"ideal_gas"},
        target="thermo.temperature",
        eps_budget=5.0,  # K, absolute in target units (FRICTION F4)
        policy=RoutePolicy(),
    )
    solution = result.unwrap()
    print(solution.value)  # Interval around ~295 K, width from input spread
    print(solution.explain())


if __name__ == "__main__":
    main()
