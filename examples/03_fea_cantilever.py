"""FEA is just a model: same call shape as example 01, higher tier.

TARGET-API sketch. The registered FEA direction consumes the
parametric family's SCALAR ports (05 naming convention) and reports a
MEASURED Richardson eps; the second run is a cache hit.
"""

from feldspar.core import Interval
from feldspar.library.mech import register as register_mech
from feldspar.fea.solver import register as register_fea
from feldspar.plan import solve
from feldspar.solve import SolverRegistry


def main() -> None:
    registry = SolverRegistry()
    register_mech(registry)   # closed-form tier (the oracles)
    register_fea(registry)    # discretized tier, same protocol
    registry.freeze()

    known = {
        # 05 geometry port naming (FRICTION F2, now specified):
        "mech.geom.cantilever.length": Interval(0.50, 0.50),   # m
        "mech.geom.cantilever.width": Interval(0.040, 0.042),  # m, tolerance
        "mech.geom.cantilever.height": Interval(0.060, 0.060),
        "mech.material.youngs_modulus": Interval(6.8e10, 7.1e10),  # Al scatter
        "mech.material.poisson": Interval(0.33, 0.33),
        "mech.load.tip_force": Interval(1.0e3, 1.2e3),  # N
    }
    result = solve(
        registry,
        known=known,
        tags={"linear_elastic", "small_deflection"},
        target="mech.deflection.tip",
        eps_budget=1e-5,  # m -- tight enough that Euler-Bernoulli's
        # declared ceiling loses and the FEA direction is routed
    )
    solution = result.unwrap()
    assert solution.eps <= 1e-5          # realized Richardson eps
    print(solution.explain())            # cites element formulation,
    #                                      Richardson, calibration runs

    again = solve(registry, known=known, tags={"linear_elastic", "small_deflection"},
                  target="mech.deflection.tip", eps_budget=1e-5).unwrap()
    assert again.settings_digest == solution.settings_digest  # cache hit path


if __name__ == "__main__":
    main()
