"""Complexity rung 1 -- coercions (DX-SETTLED, spec 03).

The same solver as 00, with every settled convenience. Rules (all
normalized AT DECORATION TIME into the raw protocol -- the registered
SolverInfo/SolveFn are indistinguishable from 00's, digest-equal):

- F11: Domain box values accept (lo, hi) tuples; tags accept any
  iterable; a dict literal IS the domain when no tags are needed.
- F10: citations accept "kind: ref -- note" strings.
- F13: a plain Mapping return is auto-wrapped in Ok; raising is a
  programmer bug (unchanged).
- F14: with exactly one output, a bare float return is accepted.
- F15: accuracy=EXACT (the Accuracy(0,0) constant) and accuracy may
  be a single Accuracy applied to all outputs.
- F12: ports are DECLARED ONCE per namespace module and registration
  rejects unknown port names -- typo safety for agent-written code.
"""

from feldspar.core import PortDecl
from feldspar.solve import EXACT, SolverRegistry, solver

PORTS = (
    PortDecl(name="mech.section.width", unit="m"),
    PortDecl(name="mech.section.height", unit="m"),
    PortDecl(name="mech.section.second_moment", unit="m^4"),
)


@solver(
    namespace="mech",
    inputs=("mech.section.width", "mech.section.height"),
    outputs=("mech.section.second_moment",),
    domain={"mech.section.width": (1e-4, 1.0),
            "mech.section.height": (1e-4, 1.0)},
    cost=1e-7,
    accuracy=EXACT,
    citations=("handbook: Gere, Mechanics of Materials 9e, App. E",),
    version="1",
)
def rect_second_moment(x):
    return x["mech.section.width"] * x["mech.section.height"] ** 3 / 12.0


def register(registry: SolverRegistry) -> None:
    registry.declare_ports(*PORTS).unwrap()          # F12: once, here
    registry.register(*rect_second_moment.solver_direction).unwrap()
    # A typo'd port in any @solver in this module is now a
    # RegistryError.UnknownPort at register time, not a silent
    # never-routable edge.
