"""Complexity rung 6 -- coupled groups (G22; defines tier="coupled").

The regen chamber's loop -- hot-gas convection <-> wall conduction <->
coolant convection <-> coolant bulk rise -- is a genuine two-way
coupling no DAG edge ordering can express. G20's envelope trick
(hot-corner R_ds_on) works for WEAK cycles; a regen jacket's coupling
is strong and distributed, and corner-enveloping it is uselessly
conservative. The settled design (09 sec. 4b):

- A CoupledGroup registers MEMBER solvers plus a deterministic
  fixed-point CLOSURE; the planner sees ONE composite SolverInfo
  (tier="coupled") over the group's BOUNDARY ports. The internal
  cycle never appears in the graph -- the graph stays a DAG by
  construction, and ordinary cyclic registrations remain an error.
- Composite accuracy is CALIBRATED AS A UNIT (member eps values do
  not compose linearly through a fixed point); EXACT is forbidden
  for coupled groups, and the closure residual at convergence is
  charged into the realized eps (SolveOutput.measured_eps).
- The closure is deterministic: fixed damping, fixed iteration
  order, tol and max_iter in settings (digested). Non-convergence is
  SolveError.NoConvergence -- a value; fallback rerouting applies.

M8 target shape (not in M1; interfaces frozen here for the WO).
"""

from feldspar.core import Accuracy
from feldspar.solve import CoupledGroup, SolverRegistry

regen_wall = CoupledGroup(
    group_id="heat.regen_wall_loop",
    namespace="heat",
    members=(
        "heat.bartz_hot_side",  # q_hot(T_wall_hot, gas state)
        "heat.wall_conduction_1d",  # dT(q, k(T), thickness)
        "heat.gnielinski_channel",  # h_cool(Re, Pr at T_film)
        "fluids.channel_bulk_rise",  # T_cool(x) from absorbed q
    ),
    boundary_inputs=(
        "prop.chamber_pressure",
        "prop.mixture_ratio",
        "fluids.coolant_mdot",
        "fluids.coolant_inlet_temp",
        "mech.geom.regen_channel.width",
        "mech.geom.regen_channel.depth",
        "mech.geom.regen_channel.count",
        "mech.geom.liner.wall_thickness",
    ),
    boundary_outputs=(
        "thermo.wall_temp.hot_side_max",  # G24: extremal reductions;
        "thermo.wall_temp.delta_max",  # stations are internal in
        "fluids.coolant_outlet_temp",  # v1 (OPEN-14)
        "heat.flux.throat",
    ),
    closure="damped_fixed_point",
    settings=dict(
        damping=0.5, tol=1e-4, max_iter=200, stations=64, march="injector_to_exit"
    ),
    # Composite, calibrated as a unit -- NOT derived from member eps:
    accuracy=Accuracy(eps_abs=0.0, eps_rel=0.12),
    citations=(
        "paper: Bartz 1957, Jet Propulsion 27 -- +-25% band",
        "handbook: NASA SP-8087 sec. 2 (regen design methods)",
        "calibration: composite vs conjugate FEA sweep blake3:...",
    ),
    conservative_for="upper",  # hot-side envelope choices
    cost=0.3,
    version="1",
)


# frob:doc docs/modules/examples.md#examples_solvers
def register(registry: SolverRegistry) -> None:
    # Members register normally (independently routable OUTSIDE the
    # cycle); the group adds the composite row. Registering members
    # whose ports form a cycle WITHOUT a group stays a registry error.
    _ = regen_wall.register(registry).danger_ok
