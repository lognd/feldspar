"""Complexity rung 3 -- tables and published correlations (F8).

DX-SETTLED, two builders:

- table_solver_1d/2d: data in, solver out; the domain box IS the
  table extent (auto); interpolation eps is EXPLICIT AND CITED, never
  auto-derived (an auto-derived error bound is a lie about data we
  did not sample).
- Correlation: a published formula + its published validity box + its
  published accuracy band + its citation as ONE object -- because in
  the literature those four arrive together, and splitting them
  across decorator arguments is where transcription errors live.
"""

from feldspar.solve import Correlation, SolverRegistry, table_solver_1d

# -- Table: saturation temperature of water vs pressure (excerpt) ----
sat_water = table_solver_1d(
    namespace="thermo",
    x_port="thermo.pressure",
    y_port="thermo.saturation_temperature",
    x=(1e3, 1e4, 5e4, 1e5, 5e5, 1e6),          # Pa (ascending, checked)
    y=(280.1, 318.9, 354.4, 372.7, 425.0, 453.0),  # K
    method="pchip",                             # monotone -> honest corners
    eps_abs=0.4,                                # K; from the source's
                                                # tabulation step, cited:
    citations=("handbook: NIST Webbook, saturation curve, 0.4K grid",),
    version="1",
)

# -- Correlation: Gnielinski internal forced convection --------------
gnielinski = Correlation(
    namespace="heat",
    inputs=("fluids.reynolds", "fluids.prandtl", "fluids.friction_factor"),
    output="heat.nusselt",
    # The PUBLISHED applicability range is the domain -- verbatim:
    domain={"fluids.reynolds": (3e3, 5e6), "fluids.prandtl": (0.5, 2000.0)},
    # The PUBLISHED accuracy band is the declared eps -- verbatim:
    accuracy_rel=0.10,
    citations=("paper: Gnielinski 1976, Int. Chem. Eng. 16 -- +-10% band",),
    version="1",
    cost=1e-6,
)


@gnielinski.formula
def _nu(x):
    f, re, pr = (x["fluids.friction_factor"], x["fluids.reynolds"],
                 x["fluids.prandtl"])
    return ((f / 8) * (re - 1000) * pr
            / (1 + 12.7 * (f / 8) ** 0.5 * (pr ** (2 / 3) - 1)))


def register(registry: SolverRegistry) -> None:
    registry.register(*sat_water).unwrap()
    gnielinski.register(registry).unwrap()
