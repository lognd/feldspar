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
from feldspar.pack.errors import map_engine_error, margin_exhausted_error
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

# The FIRST-attempt eps budget of the WO-13 margin-driven refinement
# loop (09 sec. 5, 06 "margin-driven adaptive refinement"): the loosest
# FINITE budget the planner accepts (`plan()`/the Rust search core
# reject a non-finite budget as `PlanError.InvalidBudget`), so the
# cheapest honest answer comes back before any margin translation --
# an eps-seeking direction stops at its first Richardson pair under
# this budget (09 sec. 3). Only if that answer's eps is too fat for
# the claim's margin does `_FeaModel.estimate` translate margin ->
# budget and re-drive the seeker (see `_MAX_MARGIN_ATTEMPTS`).
_EPS_BUDGET = 1e30

# Bound on the WO-13 margin-seeking loop (09 sec. 5): each re-solve
# passes a STRICTLY tighter budget (checked), so this bound is a
# belt-and-suspenders guard against a pathological value that keeps
# drifting toward the limit as the mesh refines -- never the normal
# exit (the normal exits are: claim closes, no positive margin exists,
# or the engine reports the ladder topped out).
_MAX_MARGIN_ATTEMPTS = 4


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

    def _margin_needed(self, value: float, limit: float) -> float:
        """Sense-aware eps the claim can still absorb at `value` (09
        sec. 5): for an upper claim `value + eps <= limit` needs
        `eps <= limit - value`; for a lower claim `value - eps >= limit`
        needs `eps <= value - limit`. Non-positive means the value alone
        already busts the limit -- no eps budget can close the claim."""
        if self.signature.sense.upper:
            return limit - value
        return value - limit

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Convert -> `feldspar.plan.solve.solve()` -> convert back,
        with WO-13 margin-driven adaptive refinement (09 sec. 5, 06
        "margin-driven adaptive refinement").

        The loop: solve at the loose `_EPS_BUDGET` first (cheapest
        honest answer -- an eps-seeking direction stops at its first
        Richardson pair, 09 sec. 3). If `value + eps` (sense-aware)
        already closes the claim against `request.limit`, done. If the
        value ALONE busts the limit, refinement cannot help -- return
        the honest prediction as-is (the harness judges it). Otherwise
        the eps is too fat for the margin: translate margin -> eps
        budget (`_margin_needed`) and re-drive the engine's
        budget-seeking refinement with it, deterministically (same
        request -> same budget sequence -> same rungs). A refinement
        attempt the engine cannot meet (ladder top-out, budget
        exceeded, no route remaining) returns the honest indeterminate
        STATING eps achieved vs needed (`margin_exhausted_error`,
        regolith's what-would-resolve-it family).

        Prediction mapping (06 "estimate(request)"): worst-corner value
        per claim sense, realized Richardson eps, coverage 1.0 + D95
        structured axes, `solver_version` as the `feldspar <version>`
        triple slot (ccx/gmsh are the fixed nominal placeholders
        `fea/solver.py` folds into its own settings_digest), and
        `settings_digest` riding the sanctioned INV-10 channel."""
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
        tags = frozenset({"linear_elastic", "small_deflection"})

        budget = _EPS_BUDGET
        solution = None
        value = 0.0
        for attempt in range(_MAX_MARGIN_ATTEMPTS):
            result = solve(registry, known, tags, self._target, budget, sense=sense)
            if result.is_err:
                if solution is None:
                    # First attempt: a plain engine failure, no margin
                    # story to tell yet.
                    _log.warning(
                        "%s: engine solve failed for claim_kind=%s: %r",
                        self.model_id,
                        self._claim_kind,
                        result.danger_err,
                    )
                    return Err(map_engine_error(self.model_id, result.danger_err))
                # A margin-driven re-solve the engine could not meet:
                # honest indeterminate stating eps achieved vs needed
                # (09 sec. 5; the achieved eps is the best successful
                # attempt's, the needed eps is the margin at its value).
                needed = self._margin_needed(value, request.limit)
                _log.warning(
                    "%s: margin refinement exhausted for claim_kind=%s: "
                    "eps achieved %s vs needed %s (limit=%s): %r",
                    self.model_id,
                    self._claim_kind,
                    solution.eps,
                    needed,
                    request.limit,
                    result.danger_err,
                )
                return Err(
                    margin_exhausted_error(
                        self.model_id,
                        solution.eps,
                        needed,
                        request.limit,
                        result.danger_err,
                    )
                )

            solution = result.danger_ok
            # Worst-corner value per sense: upper claims are conservative
            # on the interval's high end, lower claims on the low end (06
            # "Sense mapping" mirrors the engine's `plan(sense=...)`
            # one-to-one onto `ClaimSense.upper/lower`).
            value = (
                solution.value.hi if self.signature.sense.upper else solution.value.lo
            )
            needed = self._margin_needed(value, request.limit)
            if needed <= 0.0:
                # The value alone busts the limit: no eps budget closes
                # this claim; refinement is pointless. Honest as-is.
                _log.info(
                    "%s: value %s alone busts limit %s (claim_kind=%s); "
                    "refinement cannot close, returning honest prediction",
                    self.model_id,
                    value,
                    request.limit,
                    self._claim_kind,
                )
                break
            if solution.eps <= needed:
                _log.info(
                    "%s: claim closes at eps=%s (needed=%s, attempt %d)",
                    self.model_id,
                    solution.eps,
                    needed,
                    attempt,
                )
                break
            if needed >= budget:
                # Already asked the engine for at least this tightness;
                # a re-solve with the same-or-looser budget cannot
                # improve. Honest as-is (unreachable off the loose first
                # budget; guards the loop's strict-decrease invariant).
                _log.info(
                    "%s: needed budget %s is not tighter than the last "
                    "request %s; stopping margin seeking",
                    self.model_id,
                    needed,
                    budget,
                )
                break
            _log.info(
                "%s: margin translation (09 sec. 5): eps=%s too fat for "
                "margin %s at limit %s; re-solving with eps_budget=%s "
                "(attempt %d)",
                self.model_id,
                solution.eps,
                needed,
                request.limit,
                needed,
                attempt + 1,
            )
            budget = needed
        else:
            _log.warning(
                "%s: margin seeking hit the attempt bound (%d); returning "
                "the best achieved prediction",
                self.model_id,
                _MAX_MARGIN_ATTEMPTS,
            )

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
