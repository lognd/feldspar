"""Complexity rung 2 -- multi-direction relations (F7, DX-SETTLED).

One physical law, N searchable directions. REJECTED alternatives:
- N independent @solver functions (00-style): 3x boilerplate, and the
  shared domain/citations/version DRIFT apart (duplication bug).
- Symbolic auto-inversion: magic, fails on non-invertible forms, and
  hides the numerics (division guards) that make directions honest.

WINNER: the Relation builder -- shared metadata declared once,
each direction is an explicit small function (the numerics stay
visible), ids are auto-suffixed, and register() emits N ordinary
directions. Lowers to the raw protocol; digest-equal to hand-built.
"""

from feldspar.solve import EXACT, Relation, SolverRegistry

ideal_gas = Relation(
    namespace="thermo",
    ports=("thermo.pressure", "thermo.specific_volume",
           "thermo.temperature"),
    domain={"thermo.pressure": (1e3, 1e7),
            "thermo.specific_volume": (1e-3, 1e2),
            "thermo.temperature": (200.0, 2000.0)},
    tags=("ideal_gas",),
    cost=1e-6,
    accuracy=EXACT,
    citations=("handbook: Moran, Fund. of Eng. Thermo. 9e, sec. 3.5",),
    version="1",
)

# frob:doc docs/modules/examples.md#examples_solvers
R = 287.05  # J/(kg K)


# frob:doc docs/modules/examples.md#examples_solvers
@ideal_gas.direction(solves_for="thermo.temperature")
def t_from_pv(x):
    return x["thermo.pressure"] * x["thermo.specific_volume"] / R


# frob:doc docs/modules/examples.md#examples_solvers
@ideal_gas.direction(solves_for="thermo.pressure")
def p_from_tv(x):
    return R * x["thermo.temperature"] / x["thermo.specific_volume"]


# frob:doc docs/modules/examples.md#examples_solvers
@ideal_gas.direction(solves_for="thermo.specific_volume")
def v_from_tp(x):
    return R * x["thermo.temperature"] / x["thermo.pressure"]
    # No division guard needed: the shared domain box excludes 0.
    # A direction whose safe domain is SMALLER overrides per-direction:
    #   @ideal_gas.direction(solves_for=..., domain={...override...})


# frob:doc docs/modules/examples.md#examples_solvers
def register(registry: SolverRegistry) -> None:
    # Emits thermo.ideal_gas.t_from_pv / .p_from_tv / .v_from_tp --
    # three rows in the graph, one home for the shared metadata.
    ideal_gas.register(registry).danger_ok
