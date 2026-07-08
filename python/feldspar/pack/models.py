from __future__ import annotations

"""`FeaStaticStressModel` / `FeaStaticDeflectionModel` -- the regolith
`Model` wrappers around the engine's discretized (FEA) solve directions
(06 "Models", the WO-27 deliverable).

Both models share ONE base (`_FeaModel`) that does the actual engine
call: convert `DischargeRequest.inputs` (regolith `Interval`s) into
feldspar `Interval`s via the ONE converter pair (`pack.converters`), run
`feldspar.plan.solve.solve()` (the WO-05/06 plan+execute facade, corner
sweep already inside it), and convert the resulting `Solution` into a
regolith `Prediction`. All regolith imports live here, under
`feldspar.pack` (FINV-3/10)."""


from regolith.harness.errors import HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature
from typani.result import Err, Ok, Result

from feldspar.__about__ import __version__
from feldspar.logging import get_logger
from feldspar.pack.converters import to_feldspar_interval
from feldspar.pack.errors import map_engine_error
from feldspar.plan.solve import solve
from feldspar.solve._models import ClaimSenses
from feldspar.solve.registry import SolverRegistry

_log = get_logger(__name__)

__all__ = [
    "DEFAULT_STRESS_CLAIM_KIND",
    "DEFAULT_DEFLECTION_CLAIM_KIND",
    "FeaStaticStressModel",
    "FeaStaticDeflectionModel",
]

# Vocabulary-owned default claim kinds (06 "Models", DECIDED D94/WO-30
# note: `mech.fea.static_stress` was a bootstrap error). Constructors
# accept a `claim_kind` override (OPEN-6 interim) so re-keying onto a
# closed-form claim kind for direct cost competition in one registry
# graph is a one-line change at the call site, not a code change here.
DEFAULT_STRESS_CLAIM_KIND = "mech.static_stress"
DEFAULT_DEFLECTION_CLAIM_KIND = "mech.static_deflection"

# FEA is the expensive (reduced) tier: its cost must stay above every
# closed-form model's cost (regolith's closed-form models all report
# cost=1, `../lithos/python/regolith/harness/models/*.py`) so fat-margin
# claims keep selecting the cheaper closed-form tier when both compete
# under one claim kind (06 "cost declares the honest relative expense").
_REDUCED_TIER_COST = 10

# `Solution.eps` budget the pack solve() call is given: v1 has no
# margin-driven refinement yet (06 "Planned (09 M3)"), so the pack asks
# for the loosest FINITE budget the planner accepts (`plan()`/the Rust
# search core reject a non-finite budget as `PlanError.InvalidBudget`)
# that still lets `solve()`'s post-execution budget re-check pass on any
# realized FEA eps -- the model's honest `eps` is whatever the engine
# actually measured (`Prediction.eps`), never silently tightened or
# widened here.
_EPS_BUDGET = 1e30


def _engine_registry() -> SolverRegistry:
    """The full closed-form + FEA engine registry (WO-07/WO-08), built
    fresh per call. Building a `SolverRegistry` and calling `@solver`-
    decorated `register()` functions only adds Python-side metadata (no
    gmsh/ccx probing happens until a route actually executes), so this
    stays import-cheap and freeze-safe to call lazily at estimate time
    (FINV-3/10: no tool probing at `pack.register()` time)."""
    # Function-local imports: keeps `feldspar.pack` import-cheap (no
    # `feldspar.fea`/`feldspar.library` module-load cost paid until an
    # `estimate()` actually runs).
    from feldspar.fea.solver import register as register_fea
    from feldspar.library.mech import register as register_mech

    registry = SolverRegistry()
    register_mech(registry)
    register_fea(registry)
    registry.freeze()
    return registry


class _FeaModel(Model):
    """Shared discharge plumbing for the two FEA-backed regolith models.

    Subclasses fix the engine `target` port, `claim_kind` default, and
    required `inputs`; `estimate()` here is the ONE convert -> solve ->
    convert-back implementation (no duplication between the stress and
    deflection models)."""

    def __init__(
        self,
        *,
        claim_kind: str,
        target: str,
        inputs: "tuple[str, ...]",
    ) -> None:
        """Bind this model instance to `claim_kind` (OPEN-6 interim
        override), the engine port it solves for, and the signature
        input ports it declares (== the engine's port names, 06
        "signature.inputs are the scalar ports")."""
        self._claim_kind = claim_kind
        self._target = target
        self._inputs = inputs

    @property
    def version(self) -> str:
        """The model's own version id (bump on any physics/eps change)."""
        return "1"

    @property
    def cost(self) -> int:
        """FEA is the reduced (expensive) tier -- always costlier than
        any cost=1 closed-form model (06 "cost declares the honest
        relative expense")."""
        return _REDUCED_TIER_COST

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Convert -> `feldspar.plan.solve.solve()` -> convert back.

        Worst-corner value per claim sense (`solve()`'s `sense=` is fed
        the signature's own sense, 06 "Sense mapping"), realized
        Richardson eps, coverage 1.0 (full corner sweep), `solver_version`
        as the `feldspar <version>` triple slot (ccx/gmsh versions are
        the fixed nominal placeholders `fea/solver.py` folds into its own
        settings_digest -- there is no live tool-version probe to append
        here without duplicating that fold), and `settings_digest` riding
        the request's route settings digest as the sanctioned INV-10
        channel (06 "estimate(request)")."""
        known = {
            name: to_feldspar_interval(interval)
            for name, interval in request.inputs.items()
        }
        sense = ClaimSenses.UPPER if self.signature.sense.upper else ClaimSenses.LOWER
        registry = _engine_registry()
        # Both the closed-form and FEA directions this pack wraps declare
        # `linear_elastic`/`small_deflection` domain tags (06's regime
        # note: the WO-27 claim kinds ARE linear-elastic small-deflection
        # statics by construction) -- offering the full tag set here lets
        # `plan()` route to whichever direction's declared tags subset it
        # (a direction with a narrower tag requirement, e.g. the cylinder
        # family's `linear_elastic`-only box, still matches).
        result = solve(
            registry,
            known,
            frozenset({"linear_elastic", "small_deflection"}),
            self._target,
            _EPS_BUDGET,
            sense=sense,
        )
        if result.is_err:
            _log.warning(
                "%s: engine solve failed for claim_kind=%s: %r",
                self.model_id,
                self._claim_kind,
                result.danger_err,
            )
            return Err(map_engine_error(self.model_id, result.danger_err))

        solution = result.danger_ok
        # Worst-corner value per sense: upper claims are conservative on
        # the interval's high end, lower claims on the low end (06
        # "Sense mapping" mirrors the engine's `plan(sense=...)` one-to-
        # one onto `ClaimSense.upper/lower`).
        value = solution.value.hi if self.signature.sense.upper else solution.value.lo

        solver_version = f"feldspar {__version__} / ccx unknown / gmsh unknown"
        return Ok(
            Prediction(
                value=value,
                eps=solution.eps,
                coverage=1.0,
                in_domain=True,
                solver_version=solver_version,
                settings_digest=solution.settings_digest,
            )
        )


class FeaStaticStressModel(_FeaModel):
    """Reduced-tier von-Mises static stress, upper bound (06's table).

    Wraps `fea.static_stress.cylinder_bore` (WO-08): the engine's
    discretized thick-wall-cylinder direction."""

    def __init__(self, *, claim_kind: str = DEFAULT_STRESS_CLAIM_KIND) -> None:
        """`claim_kind` defaults to the vocabulary-owned kind; pass an
        override to compete under a closed-form kind (OPEN-6 interim)."""
        super().__init__(
            claim_kind=claim_kind,
            target="mech.stress.von_mises",
            inputs=(
                "mech.load.internal_pressure",
                "mech.geom.cylinder.inner_radius",
                "mech.geom.cylinder.outer_radius",
                "mech.material.youngs_modulus",
                "mech.material.poisson",
            ),
        )

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound von-Mises bore-stress claim (06's table)."""
        return ModelSignature(
            name="fea_static_stress",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=self._inputs,
            domain=("linear_elastic", "small_deflection", "discretized"),
        )


class FeaStaticDeflectionModel(_FeaModel):
    """Reduced-tier static deflection, upper bound (06's table).

    Wraps `fea.static_deflection.cantilever` (WO-08): the engine's
    discretized cantilever direction."""

    def __init__(self, *, claim_kind: str = DEFAULT_DEFLECTION_CLAIM_KIND) -> None:
        """`claim_kind` defaults to the vocabulary-owned kind; pass an
        override to compete under a closed-form kind (OPEN-6 interim)."""
        super().__init__(
            claim_kind=claim_kind,
            target="mech.deflection.tip",
            inputs=(
                "mech.geom.cantilever.length",
                "mech.geom.cantilever.width",
                "mech.geom.cantilever.height",
                "mech.material.youngs_modulus",
                "mech.material.poisson",
                "mech.load.tip_force",
            ),
        )

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound tip-deflection claim (06's table)."""
        return ModelSignature(
            name="fea_static_deflection",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=self._inputs,
            domain=("linear_elastic", "small_deflection", "discretized"),
        )
