"""Complexity rung 5 -- expensive solvers and abstraction edges.

Two patterns that MUST stay on the same protocol (09 sec. 1: the
planner cannot tell tiers apart):

- settings-closure subprocess solver (F1): tuning lives in a frozen
  model handed to the decorator; the digest is automatic; the body
  maps every infrastructure failure to a SolveError VALUE.
- abstraction edge (G1): geometry payload -> family scalars, with an
  execution-checked payload domain and sense-aware conservatism.
  (Payload ports land in M2; this file is the M2 target shape.)
"""

from feldspar.core import Accuracy
from feldspar.fea import MeshSettings
from feldspar.solve import ClaimSenses, SolverRegistry, solver
from typani import Err, Ok

MESH = MeshSettings(char_length=2e-3, element="C3D20", seed=7)


@solver(
    namespace="mech",
    inputs=("mech.geom.cantilever.length", "mech.geom.cantilever.width",
            "mech.geom.cantilever.height",
            "mech.material.youngs_modulus", "mech.load.tip_force"),
    outputs=("mech.deflection.tip",),
    domain={"mech.geom.cantilever.length": (0.01, 2.0)},
    tags=("linear_elastic", "small_deflection"),
    cost=8.0,                       # honest seconds, not a fiction
    accuracy=Accuracy(eps_abs=0.0, eps_rel=0.02),   # CEILING; realized
    citations=("standard: CalculiX 2.21 theory manual, C3D20",
               "calibration: run blake3:..."),
    tier="discretized",
    settings=MESH,                  # F1: digested automatically
    version="1",
)
def fea_cantilever_tip(x):
    # mesh -> deck -> run -> parse -> Richardson; every failure a value:
    #   missing tool  -> Err(SolveError.ToolMissing(...))
    #   crash/timeout -> Err(SolveError.ToolFailed/Timeout(...))
    # and the MEASURED eps rides back on the Ok (executor replaces
    # the ceiling with it):
    ...
    return Ok({"mech.deflection.tip": 1.23e-4}, measured_eps=3e-6)


# -- M2 target shape: the abstraction edge (not registrable in M1) --
@solver(
    namespace="mech",
    inputs=("mech.geom.realized",),          # PAYLOAD port (rank=payload)
    outputs=("mech.geom.cantilever.length", "mech.geom.cantilever.width",
             "mech.geom.cantilever.height"),
    payload_domain="solid_root_band(15mm); aspect(2..30); no_holes(root_band)",
    cost=1e-4,
    accuracy=Accuracy(eps_abs=0.0, eps_rel=0.15),   # idealization error,
    citations=("calibration: idealized-vs-FEA sweep blake3:...",),
    conservative_for=ClaimSenses.UPPER,      # G4: never a lower bound
    tier="closed_form",
    version="1",
)
def flange_as_cantilever(payload):
    # Executed check of the payload domain (a scalar box cannot say
    # "no hole in the root band"); violation is:
    #   Err(SolveError.OutOfDomain(...)) -> fallback reroutes to FEA.
    ...
