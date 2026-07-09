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


from regolith._schema.models import CoverageAxis, CoverageDomain1, CoverageMethod1
from regolith.harness.errors import HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature
from typani.result import Err, Ok, Result

from feldspar.__about__ import __version__
from feldspar.logging_setup import get_logger
from feldspar.pack.converters import to_feldspar_interval, to_feldspar_payload_ref
from feldspar.pack.errors import map_engine_error
from feldspar.pack.payload_bridge import NoStoreResolver
from feldspar.plan.solve import solve
from feldspar.solve._models import ClaimSenses
from feldspar.solve.payload import PayloadResolver
from feldspar.solve.registry import SolverRegistry

_log = get_logger(__name__)

__all__ = [
    "DEFAULT_STRESS_CLAIM_KIND",
    "DEFAULT_DEFLECTION_CLAIM_KIND",
    "FeaStaticStressModel",
    "FeaStaticDeflectionModel",
    "FeaStaticDeflectionFromGeometryModel",
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
# cost=1, `lithos:python/regolith/harness/models/*.py`) so fat-margin
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


def _engine_registry(resolver: "PayloadResolver | None" = None) -> SolverRegistry:
    """The full closed-form + FEA + payload-step engine registry
    (WO-07/WO-08/WO-12), built fresh per call. Building a
    `SolverRegistry` and calling `@solver`-decorated `register()`
    functions only adds Python-side metadata (no gmsh/ccx probing
    happens until a route actually executes), so this stays import-cheap
    and freeze-safe to call lazily at estimate time (FINV-3/10: no tool
    probing at `pack.register()` time).

    F12 ordering (WO-12's close-out note, resolved here as WO-14
    boundary work): `feldspar.fea.payload_steps.register()` calls
    `declare_ports()`, which arms the registry's port-table guard for
    every LATER `register()` call -- so the declaration-free WO-07/
    WO-08 modules (`library.mech`, `fea.solver`) MUST register first,
    while the port table is still empty, and `payload_steps` last. This
    is the ONE combined catalog every pack model builds against, so the
    ordering constraint has exactly one home."""
    # Function-local imports: keeps `feldspar.pack` import-cheap (no
    # `feldspar.fea`/`feldspar.library` module-load cost paid until an
    # `estimate()` actually runs).
    from feldspar.fea import payload_steps
    from feldspar.fea.solver import register as register_fea
    from feldspar.library.fluids import register as register_fluids
    from feldspar.library.heat import register as register_heat
    from feldspar.library.mech import register as register_mech

    registry = SolverRegistry()
    register_mech(registry)
    register_fluids(registry)
    register_heat(registry)
    register_fea(registry)
    payload_steps.register(
        registry, resolver if resolver is not None else NoStoreResolver()
    )
    registry.freeze()
    return registry


def _structured_coverage(request: DischargeRequest) -> "tuple[CoverageAxis, ...]":
    """Structured `Coverage` axes (D95, 06 "estimate(request)") from the
    request's real sweep shape: every non-degenerate (`lo != hi`) scalar
    input is a corner-sampled continuous axis (the engine's corner sweep
    IS full-corners coverage of that axis, `CoverageMethod1.corners`); a
    pinned (`lo == hi`) input contributes no axis (nothing was swept).
    `fraction` stays the conservative collapse (`Prediction.coverage`
    keeps reporting `1.0` alongside this -- a full corner sweep is
    complete coverage of every swept axis by construction), so this
    reports axes only, never a second fraction."""
    axes = []
    for name, interval in sorted(request.inputs.items()):
        if interval.lo == interval.hi:
            continue
        axes.append(
            CoverageAxis(
                axis=name,
                domain=CoverageDomain1(interval=f"[{interval.lo:g}, {interval.hi:g}]"),
                method=CoverageMethod1.corners,
            )
        )
    return tuple(axes)


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
        required_regimes: "tuple[str, ...]" = (),
    ) -> None:
        """Bind this model instance to `claim_kind` (OPEN-6 interim
        override), the engine port it solves for, and the signature
        input ports it declares (== the engine's port names, 06
        "signature.inputs are the scalar ports").

        `required_regimes` (A-10/D97) defaults to `()`, the v1 degenerate
        case 06 "Regime tags" keeps valid: these two claim kinds ARE
        linear-elastic small-deflection statics by construction (the WO-
        27 obligations guarantee the tag set), so gating on it would be
        redundant, not honest -- an empty tuple always matches regardless
        of `DischargeRequest.regimes`, so passing no override never
        changes behavior. Pass a non-empty override to demand a specific
        regime tag be present (tested in `test_pack_regime_channel.py`,
        proving the channel dispatches both ways)."""
        self._claim_kind = claim_kind
        self._target = target
        self._inputs = inputs
        self._required_regimes = required_regimes

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
                coverage_axes=_structured_coverage(request),
                in_domain=True,
                solver_version=solver_version,
                settings_digest=solution.settings_digest,
            )
        )


class FeaStaticStressModel(_FeaModel):
    """Reduced-tier von-Mises static stress, upper bound (06's table).

    Wraps `fea.static_stress.cylinder_bore` (WO-08): the engine's
    discretized thick-wall-cylinder direction."""

    def __init__(
        self,
        *,
        claim_kind: str = DEFAULT_STRESS_CLAIM_KIND,
        required_regimes: "tuple[str, ...]" = (),
    ) -> None:
        """`claim_kind` defaults to the vocabulary-owned kind; pass an
        override to compete under a closed-form kind (OPEN-6 interim).
        `required_regimes` defaults to `()` (06 "Regime tags" v1
        degenerate case, see `_FeaModel.__init__`)."""
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
            required_regimes=required_regimes,
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
            required_regimes=self._required_regimes,
        )


class FeaStaticDeflectionModel(_FeaModel):
    """Reduced-tier static deflection, upper bound (06's table).

    Wraps `fea.static_deflection.cantilever` (WO-08): the engine's
    discretized cantilever direction."""

    def __init__(
        self,
        *,
        claim_kind: str = DEFAULT_DEFLECTION_CLAIM_KIND,
        required_regimes: "tuple[str, ...]" = (),
    ) -> None:
        """`claim_kind` defaults to the vocabulary-owned kind; pass an
        override to compete under a closed-form kind (OPEN-6 interim).
        `required_regimes` defaults to `()` (06 "Regime tags" v1
        degenerate case, see `_FeaModel.__init__`)."""
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
            required_regimes=required_regimes,
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
            required_regimes=self._required_regimes,
        )


# Costlier than the scalar FEA tier above: the geometry-payload route
# pays a mesh generation step ahead of the ccx solve (06 "cost declares
# the honest relative expense" extends to intra-tier ordering, not just
# closed-form vs. FEA).
_PAYLOAD_TIER_COST = 20

#: The engine's cantilever parametric-geometry payload port (mirrors
#: `feldspar.fea.payload_steps.GEOMETRY_PORT` verbatim: 06 "signature
#: inputs and engine ports are the same strings" extends to payload
#: ports too, so the regolith signature's `payload_kinds` key and the
#: engine `PayloadResolver` call both name this same port).
_GEOMETRY_PAYLOAD_PORT = "mech.geom.cantilever.parametric"


class FeaStaticDeflectionFromGeometryModel(Model):
    """The D96 payload-channel deflection model (06 "Planned (09 M4)",
    WO-14 boundary v2): consumes a `geometry.parametric` payload ref on
    `DischargeRequest.payloads` instead of scalar geometry ports, routing
    through `feldspar.fea.payload_steps`'s mesh -> ccx pipeline.

    Payload-kind matching in signature selection (06 "DischargeRequest.
    payloads consumed"): a request missing the geometry payload is an
    honest `no_model`/non-match (`ModelSignature.accepts_payloads`) --
    this class never assumes a default geometry.

    Resolution itself is a NAMED, escalated residual (see `pack.
    payload_bridge`): `Model.estimate` has no orchestrator payload-store
    handle to resolve the ref's digest through yet (regolith has not
    threaded one down its discharge path), so every MATCHED request
    still honestly indeterminates via `NoStoreResolver` -- never a
    silent success, never an exception, and never feldspar doing its
    own storage IO (06 "digests resolved through the orchestrator store
    handle only")."""

    def __init__(self, *, claim_kind: str = DEFAULT_DEFLECTION_CLAIM_KIND) -> None:
        """`claim_kind` defaults to the same vocabulary-owned kind the
        scalar deflection model uses (D94: one model MAY register under
        multiple kinds, and multiple models MAY compete under one kind;
        cost ordering, not exclusivity, decides)."""
        self._claim_kind = claim_kind

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound tip-deflection claim over a geometry PAYLOAD plus
        the same material/load scalars the mesh-consuming direction
        needs (`feldspar.fea.payload_steps._make_static_from_mesh_direction`)."""
        return ModelSignature(
            name="fea_static_deflection_from_geometry",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=(
                "mech.material.youngs_modulus",
                "mech.material.poisson",
                "mech.load.tip_force",
            ),
            domain=("linear_elastic", "small_deflection", "discretized"),
            payload_kinds={_GEOMETRY_PAYLOAD_PORT: "geometry.parametric"},
        )

    @property
    def version(self) -> str:
        """The model's own version id (bump on any physics/eps change)."""
        return "1"

    @property
    def cost(self) -> int:
        """Costlier than the scalar FEA tier (mesh generation ahead of
        the ccx solve, 06 "cost declares the honest relative expense")."""
        return _PAYLOAD_TIER_COST

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Convert the geometry `PayloadRef` and scalar inputs, then run
        the engine's payload-step pipeline through `solve()`. Honestly
        indeterminate today (see class docstring) via `NoStoreResolver`
        until regolith threads a real store handle to `Model.estimate`."""
        known = {
            name: to_feldspar_interval(interval)
            for name, interval in request.inputs.items()
        }
        geometry_ref = request.payloads[_GEOMETRY_PAYLOAD_PORT]
        payloads = {_GEOMETRY_PAYLOAD_PORT: to_feldspar_payload_ref(geometry_ref)}
        sense = ClaimSenses.UPPER if self.signature.sense.upper else ClaimSenses.LOWER
        registry = _engine_registry(NoStoreResolver())
        result = solve(
            registry,
            known,
            frozenset({"linear_elastic", "small_deflection"}),
            "mech.deflection.tip",
            _EPS_BUDGET,
            sense=sense,
            payloads=payloads,
        )
        if result.is_err:
            _log.info(
                "%s: engine solve deferred for claim_kind=%s: %r (see "
                "pack.payload_bridge for the escalated resolver-threading "
                "residual)",
                self.model_id,
                self._claim_kind,
                result.danger_err,
            )
            return Err(map_engine_error(self.model_id, result.danger_err))

        solution = result.danger_ok
        value = solution.value.hi if self.signature.sense.upper else solution.value.lo
        solver_version = f"feldspar {__version__} / ccx unknown / gmsh unknown"
        return Ok(
            Prediction(
                value=value,
                eps=solution.eps,
                coverage=1.0,
                coverage_axes=_structured_coverage(request),
                in_domain=True,
                solver_version=solver_version,
                settings_digest=solution.settings_digest,
            )
        )
