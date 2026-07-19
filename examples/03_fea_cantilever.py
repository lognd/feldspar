"""FEA is just a model: same call shape as example 01, higher tier.

TARGET-API sketch. The registered FEA direction consumes the
parametric family's SCALAR ports (05 naming convention) and reports a
MEASURED Richardson eps; the second run is a cache hit.
"""

from feldspar.core import Interval
from feldspar.fea.solver import register as register_fea
from feldspar.library.mech import register as register_mech
from feldspar.plan import solve
from feldspar.solve import SolverRegistry

# The declared closed-form (Euler-Bernoulli) direction's box does not
# admit this geometry, so only the FEA direction is a candidate route
# here -- and the planner's a priori sum-surrogate estimate is
# dominated by youngs_modulus's magnitude, so a realistic eps budget
# needs to be generous at PLANNING time; the REALIZED (post-execution)
# eps is what the assertion below actually checks.
# frob:doc docs/modules/examples.md#examples_top
EPS_BUDGET = 1e10


def _tool_missing(err: object) -> str | None:
    """If `err` (a `SolveError`/`PlanError`) is, or wraps via
    `NoRouteRemaining`, a `ToolMissing` failure, the missing tool's
    name -- else `None`. Lets the example degrade gracefully on hosts
    (like this one) without `gmsh` installed, mirroring how `fea`-marked
    tests are excluded from the default gate rather than crashing."""
    kind = getattr(err, "kind", None)
    if kind == "ToolMissing":
        return err.tool  # type: ignore[attr-defined]
    if kind == "NoRouteRemaining":
        for attempt in err.attempts:  # type: ignore[attr-defined]
            if attempt.error_kind == "ToolMissing":
                return attempt.error_detail.get("tool", "unknown tool")
    return None


# frob:doc docs/modules/examples.md#examples_top
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
        eps_budget=EPS_BUDGET,
    )
    if result.is_err:
        tool = _tool_missing(result.err)
        if tool is not None:
            print(
                f"FEA direction needs '{tool}', not installed on this host "
                f"(pip install feldspar[mesh] + a real {tool} binary). "
                "Exiting gracefully -- this mirrors how fea-marked tests "
                "degrade instead of crashing."
            )
            return
        raise SystemExit(f"unexpected solve failure: {result.err}")

    solution = result.danger_ok
    print(solution.explain())            # cites element formulation,
    #                                      Richardson, calibration runs

    again = solve(registry, known=known, tags={"linear_elastic", "small_deflection"},
                  target="mech.deflection.tip", eps_budget=EPS_BUDGET)
    if again.is_ok:
        assert again.danger_ok.settings_digest == solution.settings_digest


if __name__ == "__main__":
    main()
