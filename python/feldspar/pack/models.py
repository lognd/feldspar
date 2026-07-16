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


import itertools
import math
from collections.abc import Callable, Sequence

from regolith._schema.models import CoverageAxis, CoverageDomain1, CoverageMethod1
from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature
from typani.result import Err, Ok, Result

from feldspar import _feldspar
from feldspar.__about__ import __version__
from feldspar.fluids.network import (
    FLOWNET_PORT,
    SolvedNetwork,
    edge_dp,
    find_path_edges,
    solve_flownet_bytes,
)
from feldspar.logging_setup import get_logger
from feldspar.pack.converters import to_feldspar_interval, to_feldspar_payload_ref
from feldspar.pack.errors import map_engine_error, margin_exhausted_error
from feldspar.pack.payload_bridge import NoStoreResolver, RegolithResolverAdapter
from feldspar.plan.solve import solve
from feldspar.solve._models import ClaimSenses
from feldspar.solve.payload import PayloadResolver
from feldspar.solve.registry import SolverRegistry

_log = get_logger(__name__)

__all__ = [
    "DEFAULT_STRESS_CLAIM_KIND",
    "DEFAULT_DEFLECTION_CLAIM_KIND",
    "DEFAULT_STIFFNESS_CLAIM_KIND",
    "DEFAULT_RAIL_LO_CLAIM_KIND",
    "DEFAULT_RAIL_HI_CLAIM_KIND",
    "FeaStaticStressModel",
    "FeaStaticDeflectionModel",
    "FeaStaticDeflectionFromGeometryModel",
    "MechStiffnessModel",
    "ElecRailModel",
    "MemberFlexuralCapacityModel",
    "MemberAxialCapacityModel",
    "EulerBucklingLoadModel",
    "BoltLoadFactorModel",
    "WeldUtilizationModel",
    "BearingRatingLifeModel",
    "FatigueGoodmanFactorOfSafetyModel",
    "FatigueGerberFactorOfSafetyModel",
    "LeadscrewTorqueRaiseModel",
    "ThermalTransientStepTemperatureModel",
    "ThermalTransientDutyCyclePeakTemperatureModel",
    "ShaftCriticalSpeedModel",
    "DriveAccelTorqueModel",
    "PlateMaxStressModel",
    "PlateMaxDeflectionModel",
    "MicrostripImpedanceModel",
    "StriplineImpedanceModel",
    "SeriesTerminationModel",
    "TheveninTerminationR1Model",
    "TheveninTerminationR2Model",
    "AcShuntResistorModel",
    "AcShuntCapacitorModel",
    "DEFAULT_FLUIDS_MDOT_LO_CLAIM_KIND",
    "DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND",
    "DEFAULT_FLUIDS_FLOW_IMBALANCE_CLAIM_KIND",
    "DEFAULT_FLUIDS_DP_CLAIM_KIND",
    "FluidsMdotModel",
    "FluidsFlowImbalanceModel",
    "FluidsDpModel",
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
    """The full closed-form + FEA + payload-step engine registry,
    built fresh per call. The composition itself (module list, F12
    registration order, freeze) lives in `feldspar.catalog.
    build_engine_catalog` -- the regolith-free one home the unit-level
    composition test drives (WO111b composition fix); this wrapper
    only supplies the pack's `NoStoreResolver` default. Import-cheap
    and freeze-safe to call lazily at estimate time (FINV-3/10: no
    tool probing at `pack.register()` time -- the catalog module's own
    imports are function-local)."""
    from feldspar.catalog import build_engine_catalog

    engine_resolver = resolver if resolver is not None else NoStoreResolver()
    return build_engine_catalog(engine_resolver)


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
        engine_tags: "frozenset[str] | None" = None,
    ) -> None:
        """Bind this model instance to `claim_kind` (OPEN-6 interim
        override), the engine port it solves for, and the signature
        input ports it declares (== the engine's port names, 06
        "signature.inputs are the scalar ports").

        `engine_tags` (cycle-33 pack-exposure generalization) is the
        offered tag set `plan()` matches against a solver direction's
        own `Domain.tags` (04-routing: a route is admissible only if
        its tags are covered by the offered set). Defaults to `None`,
        which keeps the original FEA-only behavior of always offering
        `{"linear_elastic", "small_deflection"}` (the WO-27 obligations'
        own tag set, unchanged for `FeaStaticStressModel`/
        `FeaStaticDeflectionModel`/`FeaStaticDeflectionFromGeometryModel`).
        A non-FEA closed-form direction (WO-24 library depth wave) wired
        through this same base passes its OWN solver's declared tags
        here instead -- see `_ClosedFormEngineModel` below.

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
        self._engine_tags = (
            engine_tags
            if engine_tags is not None
            else frozenset({"linear_elastic", "small_deflection"})
        )

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
        # The FEA directions this pack wraps declare `linear_elastic`/
        # `small_deflection` domain tags (06's regime note: the WO-27
        # claim kinds ARE linear-elastic small-deflection statics by
        # construction) -- offering that tag set lets `plan()` route to
        # whichever direction's declared tags subset it (a direction
        # with a narrower tag requirement, e.g. the cylinder family's
        # `linear_elastic`-only box, still matches). A non-FEA subclass
        # (`_ClosedFormEngineModel`) offers its own target direction's
        # declared tags instead via `self._engine_tags`.
        tags = self._engine_tags

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

        return Ok(
            Prediction(
                value=value,
                eps=solution.eps,
                coverage=1.0,
                coverage_axes=_structured_coverage(request),
                in_domain=True,
                solver_version=self._solver_version(),
                settings_digest=solution.settings_digest,
            )
        )

    def _solver_version(self) -> str:
        """The `solver_version` slot's tool-provenance string. FEA
        routes fold in the fixed ccx/gmsh nominal placeholders
        (`fea/solver.py` folds the real versions into its own
        `settings_digest`, this slot just states which tools were on
        the route); `_ClosedFormEngineModel` overrides this -- a
        closed-form algebraic route never touches ccx or gmsh, so
        naming them would be a false provenance claim."""
        return f"feldspar {__version__} / ccx unknown / gmsh unknown"


class _ClosedFormEngineModel(_FeaModel):
    """`_FeaModel`'s convert -> `solve()` -> convert-back plumbing,
    reused verbatim (NO DUPLICATION) for a WO-24 library-depth closed-
    form engine direction instead of an FEA one: cost drops to the
    cheapest tier (no mesh/ccx involved) and `solver_version` drops the
    ccx/gmsh placeholders (they were never on the route).

    Cycle-33 pack-exposure inventory: `member_capacity.py`,
    `bolted_joints.py`, `weld_groups.py`, and `bearing_life.py` each
    landed complete, calibrated, cited `@solver` directions in
    `_engine_registry()` (WO-24 dispatches #1/#3/#4) with NO regolith
    `Model` wrapper -- reachable inside feldspar's own planner, but
    invisible to a lithos discharge. Every subclass below closes one of
    those gaps by binding `target`/`inputs`/`engine_tags` to an
    already-registered, already-tested direction; none reimplements
    physics."""

    @property
    def cost(self) -> int:
        """Closed-form algebraic routes are the cheapest tier (mirrors
        `MechStiffnessModel`/`ElecRailModel`'s `cost=1`, always cheaper
        than the FEA `_REDUCED_TIER_COST` base class default)."""
        return 1

    def _solver_version(self) -> str:
        """No ccx/gmsh on a closed-form route -- state that plainly
        instead of inheriting the FEA placeholder string."""
        return f"feldspar {__version__} / closed-form"


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

    Resolution (D154, lithos design-log `2026-07-08-cycle-28.md`): this
    `estimate` override names a keyword-only `resolver` parameter, the
    capability check `regolith.harness.model._accepts_resolver` looks
    for -- opting into the orchestrator's real `PayloadStore` handle
    when `Model.discharge` has one to thread. `pack.payload_bridge.
    RegolithResolverAdapter` wraps that lithos callable into feldspar's
    own `PayloadResolver` protocol (parsing resolved bytes against the
    D154 schema-version envelope). A discharge with no resolver
    threaded (every pre-D154 caller, or a build with no `PayloadStore`
    configured) still honestly indeterminates via `NoStoreResolver` --
    never a silent success, never an exception, and never feldspar doing
    its own storage IO (06 "digests resolved through the orchestrator
    store handle only")."""

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

    def estimate(
        self,
        request: DischargeRequest,
        *,
        resolver: Callable[[str], Result[bytes, object]] | None = None,
    ) -> Result[Prediction, HarnessError]:
        """Convert the geometry `PayloadRef` and scalar inputs, then run
        the engine's payload-step pipeline through `solve()`.

        ``resolver`` (D154) is the keyword-only opt-in
        `regolith.harness.model._accepts_resolver` detects: naming it,
        never registering separately, is how a model declares it wants
        the orchestrator's real payload-store handle. Structural typing
        only (`Callable[[str], Result[bytes, object]]`) -- this module
        never imports the lithos `PayloadResolver` type alias itself
        (FINV-3). When a resolver is threaded, `pack.payload_bridge.
        RegolithResolverAdapter` wraps it into feldspar's own
        `PayloadResolver` protocol; with none, this falls back to the
        pre-D154 `NoStoreResolver` honest-indeterminate path unchanged."""
        known = {
            name: to_feldspar_interval(interval)
            for name, interval in request.inputs.items()
        }
        geometry_ref = request.payloads[_GEOMETRY_PAYLOAD_PORT]
        payloads = {_GEOMETRY_PAYLOAD_PORT: to_feldspar_payload_ref(geometry_ref)}
        sense = ClaimSenses.UPPER if self.signature.sense.upper else ClaimSenses.LOWER
        engine_resolver: PayloadResolver = (
            RegolithResolverAdapter(resolver)
            if resolver is not None
            else NoStoreResolver()
        )
        registry = _engine_registry(engine_resolver)
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


# ---------------------------------------------------------------------------
# MechStiffnessModel / ElecRailModel -- the two closed-form regolith
# models a freshly scaffolded project's `mech.stiffness`/`elec.rail`
# claims need to have ANYTHING to discharge against (the north-star
# gap: a scaffolded project with no matching model can never ship).
# Both go straight to the `_feldspar` Rust formula the sibling
# `library` module already registered for the engine's own routing
# (NO DUPLICATION) -- they skip `_engine_registry()`/`solve()`
# entirely because a two/four-scalar closed form corner-sweeps in a
# handful of Python-level calls, the same shape regolith's own
# built-in closed-form models use (e.g. `lame_cylinder.py`), not the
# FEA-tier plan/execute machinery above.
# ---------------------------------------------------------------------------

DEFAULT_STIFFNESS_CLAIM_KIND = "mech.stiffness"
DEFAULT_RAIL_LO_CLAIM_KIND = "elec.rail.lo"
DEFAULT_RAIL_HI_CLAIM_KIND = "elec.rail.hi"

#: Required scalar inputs (SI base units): Pa, m^4, m.
_STIFFNESS_INPUTS = ("e_modulus", "i_area", "length")

#: Required scalar inputs (SI base units): V, ohm, ohm, ohm.
_RAIL_INPUTS = ("vin", "r1", "r2", "rload")


def _finite_corner_sweep(
    *,
    model_id: str,
    corner_names: Sequence[str],
    corner_bounds: Sequence[tuple[float, float]],
    compute: Callable[..., tuple[float, float]],
    is_bad: Callable[[float], bool],
    metric_name: str,
    bad_description: str,
) -> Result[tuple[float, float], DomainError]:
    """Exhaustive corner sweep shared by `MechStiffnessModel.estimate`
    and `ElecRailModel.estimate` -- the two closed-form models that
    call `_feldspar` FFI directly instead of routing through
    `_FeaModel`/`solve()` (NO DUPLICATION for the sweep/finiteness/hull
    mechanics both hand-rolled the same way).

    For every corner combination (lo/hi per input in `corner_bounds`,
    `2**len(corner_bounds)` total), calls `compute(*combo)` -> `(guard_value,
    fold_value)`: `guard_value` is checked by `is_bad` and named in the
    error message on failure (`metric_name`/`bad_description` give the
    exact wording), `fold_value` is the value hulled into the returned
    `(lo_hull, hi_hull)`. Returns `Err(DomainError)` naming the first
    offending corner, or `Ok((lo_hull, hi_hull))` across every corner."""
    value_sets = [sorted({lo, hi}) for lo, hi in corner_bounds]
    lo_hull = math.inf
    hi_hull = -math.inf
    for combo in itertools.product(*value_sets):
        guard_value, fold_value = compute(*combo)
        if is_bad(guard_value):
            named = " ".join(
                f"{name}={value}"
                for name, value in zip(corner_names, combo, strict=True)
            )
            return Err(
                DomainError(
                    model_id=model_id,
                    message=(
                        f"{metric_name} {bad_description} at {named}: "
                        f"{metric_name}={guard_value}"
                    ),
                )
            )
        lo_hull = min(lo_hull, fold_value)
        hi_hull = max(hi_hull, fold_value)
    return Ok((lo_hull, hi_hull))


class MechStiffnessModel(Model):
    """Closed-form cantilever tip stiffness `k = 3*E*I/L**3`, a floor
    claim (`mech.stiffness`, `value >= limit`).

    Reuses `library.mech.cantilever_tip_deflection`'s Rust formula
    (`_feldspar.mech_cantilever_tip_deflection`) at unit force instead
    of reimplementing the algebra (NO DUPLICATION): at `force=1.0`,
    `deflection = 1.0 / (3*E*I/L**3) = 1.0 / k`, so `k = 1.0 /
    deflection` is the exact algebraic inverse of the one physics
    formula the sibling library module already owns, not a second
    copy of it."""

    def __init__(self, *, claim_kind: str = DEFAULT_STIFFNESS_CLAIM_KIND) -> None:
        """`claim_kind` defaults to the vocabulary-owned kind; pass an
        override to compete under a different kind (OPEN-6 interim,
        mirrors `_FeaModel.__init__`)."""
        self._claim_kind = claim_kind

    @property
    def signature(self) -> ModelSignature:
        """Floor (lower-bound) stiffness claim over the three beam
        inputs."""
        return ModelSignature(
            name="mech_stiffness",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=_STIFFNESS_INPUTS,
            domain=("linear_elastic", "small_deflection", "closed_form"),
        )

    @property
    def version(self) -> str:
        """The model's own version id (bump on any physics/eps change)."""
        return "1"

    @property
    def cost(self) -> int:
        """Closed-form: the cheapest tier (mirrors the library's own
        `cost=1e-7` intent at the pack's integer cost granularity)."""
        return 1

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Worst-corner (minimum, INV-9: a floor claim's honest
        prediction is conservative-low) stiffness over the interval
        box, evaluated by an exhaustive 2**3 corner sweep of the exact
        Rust formula."""
        e_modulus = request.inputs["e_modulus"]
        i_area = request.inputs["i_area"]
        length = request.inputs["length"]

        if e_modulus.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"e_modulus must be strictly positive: "
                        f"e_modulus.lo={e_modulus.lo}"
                    ),
                )
            )
        if i_area.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"i_area must be strictly positive: i_area.lo={i_area.lo}",
                )
            )
        if length.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"length must be strictly positive: length.lo={length.lo}",
                )
            )

        def _compute(e: float, i: float, length_corner: float) -> tuple[float, float]:
            """One corner: FFI deflection at unit force is the guard
            value, its reciprocal (stiffness) is the folded value."""
            deflection = _feldspar.mech_cantilever_tip_deflection(
                1.0, length_corner, e, i
            )
            stiffness = 1.0 / deflection if deflection != 0.0 else math.inf
            return deflection, stiffness

        sweep = _finite_corner_sweep(
            model_id=self.model_id,
            corner_names=("e_modulus", "i_area", "length"),
            corner_bounds=(
                (e_modulus.lo, e_modulus.hi),
                (i_area.lo, i_area.hi),
                (length.lo, length.hi),
            ),
            compute=_compute,
            is_bad=(
                lambda deflection: not math.isfinite(deflection) or deflection <= 0.0
            ),
            metric_name="deflection",
            bad_description="non-finite or non-positive",
        )
        if sweep.is_err:
            return Err(sweep.danger_err)
        worst, _ = sweep.danger_ok

        _log.info(
            "%s: worst-corner stiffness=%s over e_modulus=%s i_area=%s length=%s",
            self.model_id,
            worst,
            e_modulus,
            i_area,
            length,
        )
        return Ok(Prediction(value=worst, eps=0.0, coverage=1.0, in_domain=True))


class ElecRailModel(Model):
    """Closed-form loaded resistor-divider rail voltage, one instance
    per obligation half (`elec.rail: within [lo, hi]` lowers to TWO
    obligations, D94: one model MAY register under multiple kinds).

    Reuses `library.elec.divider_loaded`'s Rust formula
    (`_feldspar.elec_divider_loaded_vout`) verbatim (NO DUPLICATION);
    `claim_kind`/`sense` are bound at construction, mirroring
    `_FeaModel`'s `claim_kind` override -- `pack.register()`
    instantiates this class twice, once per rail half, rather than
    duplicating the divider math."""

    def __init__(self, *, claim_kind: str, sense: ClaimSense) -> None:
        """Binds this instance to one rail half: `claim_kind` selects
        the obligation kind (`elec.rail.lo`/`elec.rail.hi`), `sense`
        selects which corner is conservative (`lower_bound()` for the
        `.lo` floor half, `upper_bound()` for the `.hi` ceiling
        half)."""
        self._claim_kind = claim_kind
        self._sense = sense

    @property
    def signature(self) -> ModelSignature:
        """A lo-floor or hi-ceiling rail claim (per `self._sense`) over
        the four divider inputs."""
        return ModelSignature(
            name=f"elec_rail_{'hi' if self._sense.upper else 'lo'}",
            claim_kind=self._claim_kind,
            sense=self._sense,
            inputs=_RAIL_INPUTS,
            domain=("linear", "small_signal", "closed_form"),
        )

    @property
    def version(self) -> str:
        """The model's own version id (bump on any physics/eps change)."""
        return "1"

    @property
    def cost(self) -> int:
        """Closed-form: the cheapest tier."""
        return 1

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Worst-corner rail voltage over the interval box (max for the
        `.hi` ceiling half, min for the `.lo` floor half, INV-9),
        evaluated by an exhaustive 2**4 corner sweep of the exact Rust
        divider formula."""
        vin = request.inputs["vin"]
        r1 = request.inputs["r1"]
        r2 = request.inputs["r2"]
        rload = request.inputs["rload"]

        if vin.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"vin must be non-negative: vin.lo={vin.lo}",
                )
            )
        if r1.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"r1 must be strictly positive: r1.lo={r1.lo}",
                )
            )
        if r2.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"r2 must be strictly positive: r2.lo={r2.lo}",
                )
            )
        if rload.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"rload must be strictly positive: rload.lo={rload.lo}",
                )
            )

        def _compute(v: float, a: float, b: float, c: float) -> tuple[float, float]:
            """One corner: FFI vout is both the guard value and the
            folded value (no transform, unlike the stiffness model)."""
            vout = _feldspar.elec_divider_loaded_vout(v, a, b, c)
            return vout, vout

        sweep = _finite_corner_sweep(
            model_id=self.model_id,
            corner_names=("vin", "r1", "r2", "rload"),
            corner_bounds=(
                (vin.lo, vin.hi),
                (r1.lo, r1.hi),
                (r2.lo, r2.hi),
                (rload.lo, rload.hi),
            ),
            compute=_compute,
            is_bad=lambda vout: not math.isfinite(vout),
            metric_name="vout",
            bad_description="non-finite",
        )
        if sweep.is_err:
            return Err(sweep.danger_err)
        lo_hull, hi_hull = sweep.danger_ok

        value = hi_hull if self._sense.upper else lo_hull
        _log.info(
            "%s: worst-corner vout=%s (sense.upper=%s) over vin=%s r1=%s "
            "r2=%s rload=%s",
            self.model_id,
            value,
            self._sense.upper,
            vin,
            r1,
            r2,
            rload,
        )
        return Ok(Prediction(value=value, eps=0.0, coverage=1.0, in_domain=True))


# ---------------------------------------------------------------------------
# Cycle-33 pack-exposure wave: WO-24 library-depth directions (dispatches
# #1/#3/#4, `member_capacity.py`/`bolted_joints.py`/`weld_groups.py`/
# `bearing_life.py`) that landed complete, calibrated, cited `@solver`
# directions in `_engine_registry()` with no regolith `Model` wrapper --
# reachable inside feldspar's own planner, invisible to a lithos
# discharge. Each class below is a thin `_ClosedFormEngineModel` bind
# (claim_kind/target/inputs/engine_tags only, per direction's own
# `library/*.py` registration) -- NO physics duplicated here.
#
# Exposed here are each module's single TOP-LEVEL "final answer" output
# (a capacity, a utilization ratio, a rating life, a load factor) --
# INTERMEDIATE distribution outputs that exist to be composed by a
# caller into a further step, not to be claims in their own right, are
# named RESIDUALS instead (matching this file's own precedent: E3's
# internal `Fe`/`Fcr` are not separately exposed either):
#
#   - `bolt_group_shear_torsion` / `bolt_group_tension_from_moment`
#     (mech.joint.group.shear_resultant / .tension_critical): per-bolt
#     force components a caller compares against a bolt's own shear/
#     tension allowable -- the allowable itself has no producer in this
#     repo (CALLER-SUPPLIED), so there is no single sense-bearing claim
#     limit to discharge against yet.
#   - `weld_group_inplane_shear_torsion` / `weld_group_outofplane_bending`
#     (mech.weld.group.inplane_line_force / .bending_line_force):
#     intermediate unit line forces `weld_group_utilization` (exposed
#     below) already composes into the one meaningful top-level claim
#     (a stress utilization ratio) -- exposing the two partial forces
#     separately would invite a caller to compare a line force (N/m)
#     directly against a stress limit (Pa), an honest-but-useless claim
#     shape this pack declines to manufacture.
#   - `bearing_basic_rating_life_l10_ball` / `_l10_roller` (mech.bearing.l10,
#     millions of revolutions): `bearing_basic_rating_life_l10h` (exposed
#     below) is the SAME chain one step further, in the unit (hours) an
#     actual duty-cycle claim limit is stated in -- L10 alone is an
#     intermediate a caller chains, same shape as the two line-force
#     directions above.
#
# `thermal_transient.py`'s four directions are a NAMED RESIDUAL of this
# whole wave, NOT an oversight: dispatch #5's own close-out (WO-24
# ledger, this file's sibling WO doc) already decided their lithos-side
# claim-kind names (`thermo.junction_temperature_transient`/
# `_duty_cycle`) belong to a FUTURE lithos-side model pack with its own
# `NumericReducedTierModel` subclass, explicitly out of feldspar's own
# `pack` module's scope -- re-deciding that here would contradict a
# recorded decision, not extend it.
# ---------------------------------------------------------------------------

DEFAULT_MEMBER_FLEXURAL_CAPACITY_CLAIM_KIND = "mech.member.flexural_capacity"
DEFAULT_MEMBER_AXIAL_CAPACITY_CLAIM_KIND = "mech.member.axial_capacity"
DEFAULT_EULER_BUCKLING_LOAD_CLAIM_KIND = "mech.member.euler_buckling_load"
DEFAULT_BOLT_LOAD_FACTOR_CLAIM_KIND = "mech.joint.bolt_load_factor"
DEFAULT_WELD_UTILIZATION_CLAIM_KIND = "mech.weld.utilization"
DEFAULT_BEARING_RATING_LIFE_CLAIM_KIND = "mech.bearing.rating_life_hours"
DEFAULT_FATIGUE_GOODMAN_FACTOR_OF_SAFETY_CLAIM_KIND = "mech.fatigue.factor_of_safety"
DEFAULT_FATIGUE_GERBER_FACTOR_OF_SAFETY_CLAIM_KIND = (
    "mech.fatigue.gerber_factor_of_safety"
)
# WO111b (lithos WO-110-F6/F4): S-N cycles-to-failure (scalar) and
# Miner's-rule cumulative damage over a declared load-block spectrum
# payload -- the fleet's `mech.fatigue.damage(<part>, over=<spectrum>)
# < 1.0` call form (D223 feldspar-side fatigue depth).
DEFAULT_FATIGUE_CYCLES_TO_FAILURE_CLAIM_KIND = "mech.fatigue.cycles_to_failure"
DEFAULT_FATIGUE_DAMAGE_CLAIM_KIND = "mech.fatigue.damage"
DEFAULT_LEADSCREW_TORQUE_RAISE_CLAIM_KIND = "mech.drive.leadscrew_torque_raise"
DEFAULT_DRIVE_ACCEL_TORQUE_CLAIM_KIND = "mech.drive.accel_torque"
DEFAULT_JUNCTION_TEMPERATURE_TRANSIENT_CLAIM_KIND = (
    "thermo.junction_temperature_transient"
)
DEFAULT_JUNCTION_TEMPERATURE_DUTY_CYCLE_CLAIM_KIND = (
    "thermo.junction_temperature_duty_cycle"
)
DEFAULT_SHAFT_CRITICAL_SPEED_CLAIM_KIND = "mech.critical_speed"
DEFAULT_PLATE_MAX_STRESS_CLAIM_KIND = "mech.plate.max_stress"
DEFAULT_PLATE_MAX_DEFLECTION_CLAIM_KIND = "mech.plate.max_deflection"


class MemberFlexuralCapacityModel(_ClosedFormEngineModel):
    """AISC 360-16 F2.1 compact/braced flexural yield capacity
    (`library.member_capacity.flexural_yield_capacity_f2`), a floor
    claim (`value >= limit`, INV-9: a capacity claim is honest as its
    conservative-LOW corner)."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_MEMBER_FLEXURAL_CAPACITY_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.member.flexure.capacity",
            inputs=("mech.member.flexure.fy", "mech.member.flexure.zx"),
            engine_tags=frozenset({"compact", "braced", "steel"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_member_flexural_capacity_f2",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("compact", "braced", "steel", "aisc_360_16_f2"),
        )


class MemberAxialCapacityModel(_ClosedFormEngineModel):
    """AISC 360-16 E3 axial yield/flexural-buckling capacity
    (`library.member_capacity.axial_yield_buckling_capacity_e3`), a
    floor claim."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_MEMBER_AXIAL_CAPACITY_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.member.axial.capacity",
            inputs=(
                "mech.member.axial.fy",
                "mech.member.axial.ag",
                "mech.member.axial.e",
                "mech.member.axial.kl_over_r",
            ),
            engine_tags=frozenset({"steel", "no_slender_elements"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_member_axial_capacity_e3",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("steel", "no_slender_elements", "aisc_360_16_e3"),
        )


class EulerBucklingLoadModel(_ClosedFormEngineModel):
    """Classical Euler elastic critical buckling load
    (`library.member_capacity.euler_critical_buckling_load`), a floor
    claim over caller-supplied `E, I, K, L` (no yield-strength branch,
    the purely-elastic sibling of `MemberAxialCapacityModel`)."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_EULER_BUCKLING_LOAD_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.member.euler.pcr",
            inputs=(
                "mech.member.euler.e",
                "mech.member.euler.i",
                "mech.member.euler.k",
                "mech.member.euler.length",
            ),
            engine_tags=frozenset({"elastic", "prismatic", "no_slender_elements"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_member_euler_buckling_load",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("elastic", "prismatic", "no_slender_elements", "timoshenko_ch2"),
        )


class BoltLoadFactorModel(_ClosedFormEngineModel):
    """VDI 2230-class single-bolt load factor
    (`library.bolted_joints.bolt_single_load_factor_vdi2230`), a floor
    claim: a joint's load factor phi must stay ABOVE a stated minimum
    margin against embedment/loosening (VDI 2230 Blatt 1:2015, memo
    sec. 8.1)."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_BOLT_LOAD_FACTOR_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.joint.bolt.load_factor",
            inputs=(
                "mech.joint.bolt.cb",
                "mech.joint.bolt.cp",
                "mech.joint.bolt.fv",
                "mech.joint.bolt.fa",
            ),
            engine_tags=frozenset(
                {
                    "elastic",
                    "no_gasket_creep",
                    "concentric_load",
                    "friction_grip_out_of_scope",
                }
            ),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_joint_bolt_load_factor_vdi2230",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=(
                "elastic",
                "no_gasket_creep",
                "concentric_load",
                "vdi_2230_blatt1",
            ),
        )


class WeldUtilizationModel(_ClosedFormEngineModel):
    """Fillet weld-group elastic-line utilization ratio
    (`library.weld_groups.weld_group_utilization`), a ceiling claim:
    `utilization_ratio` must stay AT OR BELOW a stated limit (the
    caller's own allowable margin, typically `1.0` -- this model
    reports the ratio itself, INV-9 conservative-HIGH corner, the
    caller's obligation states the limit)."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_WELD_UTILIZATION_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.weld.group.utilization_ratio",
            inputs=(
                "mech.weld.group.inplane_line_force",
                "mech.weld.group.bending_line_force",
                "mech.weld.group.leg_size",
                "mech.weld.group.allowable_stress",
            ),
            engine_tags=frozenset({"elastic", "fillet", "static"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_weld_group_utilization",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=self._inputs,
            domain=("elastic", "fillet", "static", "aws_d1.1_j2.4"),
        )


class BearingRatingLifeModel(_ClosedFormEngineModel):
    """ISO 281:2007 basic dynamic rating life in hours at constant
    speed (`library.bearing_life.bearing_basic_rating_life_l10h`), a
    floor claim: `L10h` (hours) must stay AT OR ABOVE the caller's
    stated service-life requirement. Takes the already-computed `L10`
    (millions of revolutions, from `bearing_basic_rating_life_l10_ball`
    /`_l10_roller`, both named residuals of this exposure wave -- a
    caller chains those first, same seam as `MechStiffnessModel`'s own
    caller-supplied section properties) and `speed_rpm` directly."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_BEARING_RATING_LIFE_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.bearing.l10h",
            inputs=("mech.bearing.l10", "mech.bearing.speed_rpm"),
            engine_tags=frozenset({"iso_281", "constant_speed"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_bearing_rating_life_l10h",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("iso_281", "constant_speed", "basic_rating", "no_a_iso"),
        )


class FatigueGoodmanFactorOfSafetyModel(_ClosedFormEngineModel):
    """Modified-Goodman fatigue factor of safety, fatigue-governs
    branch (`library.fatigue.fatigue_goodman_factor_of_safety`), a
    floor claim: `factor_of_safety` must stay AT OR ABOVE the
    caller's stated margin (typically `1.0`). Takes the already-
    Marin-composed `Se` and an already-Kf-multiplied
    `sigma_a`/`sigma_m` pair directly -- the Marin composition
    (`fatigue_marin_endurance_limit`) and the Kf notch-sensitivity
    multiplication both stay caller-resolved upstream steps, same
    "caller-resolved aggregate" seam `BearingRatingLifeModel`'s `L10`
    input uses (WO-24 deliverable 4's own module docstring has the
    full named-cut reasoning: no static-yielding branch, no Kf
    derivation, no Marin factor-table transcription beyond the one
    calibrated Table 6-2 row)."""

    def __init__(
        self,
        *,
        claim_kind: str = DEFAULT_FATIGUE_GOODMAN_FACTOR_OF_SAFETY_CLAIM_KIND,
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.fatigue.goodman.factor_of_safety",
            inputs=(
                "mech.fatigue.goodman.se",
                "mech.fatigue.goodman.sut",
                "mech.fatigue.goodman.sigma_a",
                "mech.fatigue.goodman.sigma_m",
            ),
            engine_tags=frozenset({"steel", "hcf", "fatigue_governs"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_fatigue_goodman_factor_of_safety",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("steel", "hcf", "fatigue_governs", "kf_pre_applied"),
        )


class FatigueGerberFactorOfSafetyModel(_ClosedFormEngineModel):
    """Gerber-parabola fatigue factor of safety
    (`library.fatigue.fatigue_gerber_factor_of_safety`, Shigley 11e
    Table 6-7 / eq. 6-48, memo sec. 18), a floor claim: the Gerber
    factor of safety must stay AT OR ABOVE the caller's stated margin
    (typically `1.0`). The less-conservative parabolic sibling of
    `FatigueGoodmanFactorOfSafetyModel`; same caller-resolved inputs
    (Marin-composed `Se`, Kf-pre-multiplied `sigma_a`/`sigma_m`)."""

    def __init__(
        self,
        *,
        claim_kind: str = DEFAULT_FATIGUE_GERBER_FACTOR_OF_SAFETY_CLAIM_KIND,
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.fatigue.gerber.factor_of_safety",
            inputs=(
                "mech.fatigue.gerber.se",
                "mech.fatigue.gerber.sut",
                "mech.fatigue.gerber.sigma_a",
                "mech.fatigue.gerber.sigma_m",
            ),
            engine_tags=frozenset({"steel", "hcf", "fatigue_governs"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_fatigue_gerber_factor_of_safety",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("steel", "hcf", "fatigue_governs", "kf_pre_applied", "gerber"),
        )


class FatigueSnCyclesToFailureModel(_ClosedFormEngineModel):
    """S-N log-log knee-line cycles-to-failure
    (`library.fatigue.fatigue_sn_cycles_to_failure`, Shigley 11e eqs.
    6-13/6-14, memo sec. 20.1), a floor claim: the computed `N` must
    stay AT OR ABOVE the caller's stated required-life bound. Scalar
    inputs only (no spectrum payload -- one alternating-stress level);
    `FatigueMinerDamageModel` is the multi-block sibling over a
    declared spectrum payload (WO111b, lithos WO-110-F6/F4)."""

    def __init__(
        self,
        *,
        claim_kind: str = DEFAULT_FATIGUE_CYCLES_TO_FAILURE_CLAIM_KIND,
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.fatigue.sn.cycles_to_failure",
            inputs=(
                "mech.fatigue.sn.sigma_a",
                "mech.fatigue.sn.sut",
                "mech.fatigue.sn.se",
                "mech.fatigue.sn.f",
            ),
            engine_tags=frozenset({"steel", "hcf"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_fatigue_sn_cycles_to_failure",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("steel", "hcf", "kf_pre_applied", "sn_knee_line"),
        )


def _miner_spectrum_payload_port() -> str:
    """The Miner-damage spectrum payload port name AT THE REGOLITH
    BOUNDARY: a function-local import of `feldspar.mech.fatigue.
    MINER_SPECTRUM_PORT` (single home for the literal, NO DUPLICATION
    -- mirrors this module's own `_engine_registry()` convention of
    keeping `feldspar.mech`/`feldspar.fea` imports function-local,
    FINV-3/10 import-cheap posture)."""
    from feldspar.mech.fatigue import MINER_SPECTRUM_PORT

    return MINER_SPECTRUM_PORT


class FatigueMinerDamageModel(Model):
    """The D96 payload-channel Miner's-rule cumulative-damage model
    (06 "Planned (09 M4)", same shape `FeaStaticDeflectionFromGeometryModel`
    uses): consumes a `spectrum` payload ref
    (`{"sigma_a": [...], "cycles": [...]}`) on `DischargeRequest.
    payloads` instead of scalar load inputs, routing through
    `feldspar.library.fatigue`'s `mech.fatigue.miner_damage` direction.
    Serves the fleet's `mech.fatigue.damage(<part>, over=<spectrum>) <
    1.0` call form (lithos WO-110-F6/F4, WO111b deliverable 1).

    Payload-kind matching in signature selection: a request missing
    the spectrum payload is an honest `no_model`/non-match
    (`ModelSignature.accepts_payloads`) -- this class never assumes a
    default spectrum. Resolution follows the SAME D154 keyword-only
    `resolver` opt-in `FeaStaticDeflectionFromGeometryModel` uses (NO
    DUPLICATION of that threading logic -- both classes independently
    implement the same small opt-in shape since neither is a common
    base of the other; see that class's own docstring for the full
    resolver-threading reasoning). With no resolver threaded (every
    pre-D154 caller, or a build with no `PayloadStore` configured),
    this honestly indeterminates via `NoStoreResolver` -- never a
    silent success, never an exception."""

    def __init__(self, *, claim_kind: str = DEFAULT_FATIGUE_DAMAGE_CLAIM_KIND) -> None:
        """`claim_kind` defaults to the vocabulary-owned kind (lithos
        WO-110's `mech.fatigue.damage` call form)."""
        self._claim_kind = claim_kind

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound cumulative-damage claim (`D < limit`, typically
        `1.0`) over a spectrum PAYLOAD plus the S-N scalar inputs
        `feldspar.library.fatigue._make_miner_damage_direction` needs."""
        return ModelSignature(
            name="mech_fatigue_miner_damage",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=(
                "mech.fatigue.miner.sut",
                "mech.fatigue.miner.se",
                "mech.fatigue.miner.f",
            ),
            domain=("steel", "hcf"),
            payload_kinds={_miner_spectrum_payload_port(): "spectrum"},
        )

    @property
    def version(self) -> str:
        """The model's own version id (bump on any physics/eps change)."""
        return "1"

    @property
    def cost(self) -> int:
        """Same payload tier as `FeaStaticDeflectionFromGeometryModel`
        (spectrum-block accumulation is cheap per se, but the payload
        channel itself is the costlier tier, 06 "cost declares the
        honest relative expense")."""
        return _PAYLOAD_TIER_COST

    def estimate(
        self,
        request: DischargeRequest,
        *,
        resolver: Callable[[str], Result[bytes, object]] | None = None,
    ) -> Result[Prediction, HarnessError]:
        """Convert the spectrum `PayloadRef` and scalar S-N inputs,
        then run the engine's Miner-damage direction through
        `solve()`. `resolver` (D154) mirrors
        `FeaStaticDeflectionFromGeometryModel.estimate`'s keyword-only
        opt-in verbatim -- see that method's docstring for the full
        threading reasoning (NO DUPLICATION of the explanation, this
        is the same mechanism applied to a different payload port)."""
        known = {
            name: to_feldspar_interval(interval)
            for name, interval in request.inputs.items()
        }
        spectrum_port = _miner_spectrum_payload_port()
        spectrum_ref = request.payloads[spectrum_port]
        payloads = {spectrum_port: to_feldspar_payload_ref(spectrum_ref)}
        sense = ClaimSenses.UPPER if self.signature.sense.upper else ClaimSenses.LOWER
        engine_resolver: PayloadResolver = (
            RegolithResolverAdapter(resolver)
            if resolver is not None
            else NoStoreResolver()
        )
        registry = _engine_registry(engine_resolver)
        result = solve(
            registry,
            known,
            frozenset({"steel", "hcf"}),
            "mech.fatigue.miner.damage",
            _EPS_BUDGET,
            sense=sense,
            payloads=payloads,
        )
        if result.is_err:
            _log.info(
                "%s: engine solve deferred for claim_kind=%s: %r",
                self.model_id,
                self._claim_kind,
                result.danger_err,
            )
            return Err(map_engine_error(self.model_id, result.danger_err))

        solution = result.danger_ok
        value = solution.value.hi if self.signature.sense.upper else solution.value.lo
        return Ok(
            Prediction(
                value=value,
                eps=solution.eps,
                coverage=1.0,
                coverage_axes=_structured_coverage(request),
                in_domain=True,
                solver_version=f"feldspar {__version__} / closed-form",
                settings_digest=solution.settings_digest,
            )
        )


class LeadscrewTorqueRaiseModel(_ClosedFormEngineModel):
    """Square-thread power-screw torque to raise a load
    (`library.leadscrew.leadscrew_torque_raise`), a ceiling claim: the
    REQUIRED drive torque must stay AT OR BELOW the caller's available
    motor/actuator torque (the caller's own obligation states that
    limit; same "this model reports the demand, the obligation states
    the supply" shape `WeldUtilizationModel`'s ratio uses). Thrust-
    collar friction (`leadscrew_collar_torque`) and the self-locking
    margin are NOT folded in here -- named residuals, a caller
    composes them separately (same "caller composes" seam every
    WO-24 module uses, `library.leadscrew`'s own module docstring has
    the full reasoning)."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_LEADSCREW_TORQUE_RAISE_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.drive.leadscrew.torque_raise",
            inputs=(
                "mech.drive.leadscrew.force",
                "mech.drive.leadscrew.dm",
                "mech.drive.leadscrew.lead",
                "mech.drive.leadscrew.friction",
            ),
            engine_tags=frozenset({"square_thread", "no_collar"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_leadscrew_torque_raise",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=self._inputs,
            domain=("square_thread", "no_collar", "no_acme_correction"),
        )


# ---------------------------------------------------------------------------
# WO-111 cycle-35 Class-C wave: model growth the fleet's undischarged
# claims actually need (lithos design-log 2026-07-13-cycle-35 D223,
# F130's CLASS C). Two families are pure EXPOSURE of already-landed,
# already-calibrated library directions (thermal transient, WO-24
# deliverable 6, memo sec. 12); three are NEW physics landed this WO
# (shaft critical speed, Roark flat plate, Gerber fatigue, drive accel
# torque -- see their `library/*.py` modules and memo secs. 16-19).
# Every subclass below is the same thin `_ClosedFormEngineModel` bind
# -- no physics duplicated here.
#
# Thermal transient: dispatch #5's WO-24 close-out DECIDED these two
# lithos-side claim-kind names (`thermo.junction_temperature_transient`
# / `_duty_cycle`) and deferred registration to "a future lithos-side
# model pack". D223 supersedes that deferral: the transient junction-
# temperature physics belongs in the solver pack and is exposed HERE
# (85 corpus `thermo.junction_temperature_inputs_missing` waives, the
# largest single Class-D/C model-routing gap F130 measured). Both are
# UPPER-bound claims: a junction temperature must stay AT OR BELOW the
# device's rated limit, so the model reports the conservative-HIGH
# corner (INV-9), the obligation states the limit.
# ---------------------------------------------------------------------------


class ThermalTransientStepTemperatureModel(_ClosedFormEngineModel):
    """Single-node lumped-capacitance step-response junction temperature
    (`library.thermal_transient.step_temperature`, Incropera ch. 5 sec.
    5.2, memo sec. 12.1), an upper-bound claim: `T(t)` at the queried
    elapsed time must stay AT OR BELOW the rated limit. The transient
    generalization of lithos's steady `thermo.junction_temperature`
    built-in (its `t -> infinity` limit). Constant `R_th`/`C_th` and a
    caller-asserted Biot number below 0.1 are the lumped-capacitance
    preconditions the wrapped direction enforces in-function."""

    def __init__(
        self,
        *,
        claim_kind: str = DEFAULT_JUNCTION_TEMPERATURE_TRANSIENT_CLAIM_KIND,
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="heat.transient.temperature",
            inputs=(
                "heat.transient.t_amb",
                "heat.transient.power",
                "heat.transient.r_th",
                "heat.transient.c_th",
                "heat.transient.time",
                "heat.transient.biot_number",
            ),
            engine_tags=frozenset(
                {"lumped_capacitance", "single_node", "constant_properties"}
            ),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="thermo_junction_temperature_transient",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=self._inputs,
            domain=("lumped_capacitance", "single_node", "constant_properties"),
        )


class ThermalTransientDutyCyclePeakTemperatureModel(_ClosedFormEngineModel):
    """Periodic-steady-state peak junction temperature under a square-
    wave (duty-cycled) power pulse train
    (`library.thermal_transient.duty_cycle_peak_temperature`, memo sec.
    12.3, the VRM case), an upper-bound claim: the periodic PEAK must
    stay AT OR BELOW the rated limit. Reports the conservative-HIGH
    corner over the input box."""

    def __init__(
        self,
        *,
        claim_kind: str = DEFAULT_JUNCTION_TEMPERATURE_DUTY_CYCLE_CLAIM_KIND,
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="heat.transient.duty_peak_temperature",
            inputs=(
                "heat.transient.t_amb",
                "heat.transient.power",
                "heat.transient.r_th",
                "heat.transient.c_th",
                "heat.transient.t_on",
                "heat.transient.t_off",
                "heat.transient.biot_number",
            ),
            engine_tags=frozenset(
                {
                    "lumped_capacitance",
                    "single_node",
                    "constant_properties",
                    "periodic_steady_state",
                }
            ),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="thermo_junction_temperature_duty_cycle",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=self._inputs,
            domain=(
                "lumped_capacitance",
                "single_node",
                "constant_properties",
                "periodic_steady_state",
            ),
        )


class ShaftCriticalSpeedModel(_ClosedFormEngineModel):
    """Single-mass shaft first critical (whirl) speed from lateral
    stiffness and lumped mass (`library.critical_speed.
    shaft_critical_speed_from_stiffness`, Shigley 11e eq. 7-22, memo
    sec. 16.1), a FLOOR claim: the critical speed must stay AT OR ABOVE
    the operating speed (a running shaft must not reach whirl). Reports
    the conservative-LOW corner (INV-9), the obligation states the
    operating-speed floor. Rayleigh's static-deflection view is a second
    registered direction (`shaft_critical_speed_rayleigh_single_mass`),
    a named residual a caller reaches directly when it has `delta`
    instead of `k`,`m`."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_SHAFT_CRITICAL_SPEED_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.critical_speed.rpm",
            inputs=("mech.critical_speed.stiffness", "mech.critical_speed.mass"),
            engine_tags=frozenset({"single_mass", "undamped", "first_mode"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_shaft_critical_speed",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("single_mass", "undamped", "first_mode", "shigley_ch7"),
        )


class DriveAccelTorqueModel(_ClosedFormEngineModel):
    """Reflected-inertia acceleration torque for a geared motion axis
    (`library.drive.drive_acceleration_torque`, Norton/Slocum, memo sec.
    19), a CEILING claim: the required motor torque must stay AT OR BELOW
    the motor's available torque (the obligation states the supply, this
    model reports the demand). Reports the conservative-HIGH corner."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_DRIVE_ACCEL_TORQUE_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.drive.accel.torque_required",
            inputs=(
                "mech.drive.accel.j_motor",
                "mech.drive.accel.j_load",
                "mech.drive.accel.gear_ratio",
                "mech.drive.accel.efficiency",
                "mech.drive.accel.alpha",
                "mech.drive.accel.t_load",
            ),
            engine_tags=frozenset(
                {"rigid_drivetrain", "single_stage", "constant_efficiency"}
            ),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_drive_accel_torque",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=self._inputs,
            domain=("rigid_drivetrain", "single_stage", "constant_efficiency"),
        )


class PlateMaxStressModel(_ClosedFormEngineModel):
    """Peak bending stress in a uniformly loaded simply-supported
    circular flat plate (`library.plate.
    plate_circular_uniform_ss_max_stress`, Roark 8th ed. Table 11.2
    case 10a, memo sec. 17.1), a CEILING claim: peak stress must stay AT
    OR BELOW the allowable. Simply-supported is the conservative choice
    under uncertain edge fixity (higher stress than clamped); the clamped
    direction is a registered residual a caller reaches when the edge is
    truly built-in. Reports the conservative-HIGH corner."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_PLATE_MAX_STRESS_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.plate.circular.ss_max_stress",
            inputs=(
                "mech.plate.circular.q",
                "mech.plate.circular.a",
                "mech.plate.circular.t",
                "mech.plate.circular.e",
                "mech.plate.circular.nu",
            ),
            engine_tags=frozenset({"thin_plate", "small_deflection", "circular"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_plate_circular_ss_max_stress",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=self._inputs,
            domain=("thin_plate", "small_deflection", "circular", "roark_11.2_10a"),
        )


class PlateMaxDeflectionModel(_ClosedFormEngineModel):
    """Center deflection of a uniformly loaded simply-supported circular
    flat plate (`library.plate.plate_circular_uniform_ss_max_deflection`,
    Roark 8th ed. Table 11.2 case 10a, memo sec. 17.2), a CEILING claim:
    deflection must stay AT OR BELOW a serviceability limit. Simply-
    supported is the conservative choice; reports the conservative-HIGH
    corner."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_PLATE_MAX_DEFLECTION_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="mech.plate.circular.ss_max_deflection",
            inputs=(
                "mech.plate.circular.q",
                "mech.plate.circular.a",
                "mech.plate.circular.t",
                "mech.plate.circular.e",
                "mech.plate.circular.nu",
            ),
            engine_tags=frozenset({"thin_plate", "small_deflection", "circular"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="mech_plate_circular_ss_max_deflection",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=self._inputs,
            domain=("thin_plate", "small_deflection", "circular", "roark_11.2_10a"),
        )


# ---------------------------------------------------------------------------
# WO-25 signal-integrity wave: `library.signal_integrity`'s directions
# (Hammerstad-Jensen microstrip, Cohn exact stripline, exact-algebra
# termination sizing) exposed the SAME way the cycle-33 pack-exposure
# wave above exposed WO-24's -- thin `_ClosedFormEngineModel` binds, no
# physics duplicated here (lithos design-log 2026-07-10-cycle-32 D186,
# lithos:docs/spec/toolchain/35-signal-integrity.md sec. 1.6).
#
# Impedance claims lower to TWO obligations (D186 sec. 1 point 2,
# `elec.impedance(<net|class>) within [lo, hi] ohm`), the SAME shape
# `ElecRailModel` uses for `elec.rail.lo`/`.hi`: `MicrostripImpedanceModel`
# and `StriplineImpedanceModel` each take a `sense` at construction and
# `pack.register()` instantiates each twice (once per half).
#
# `diff_pair_z` (deliverable 1's third impedance form) is NOT exposed --
# `library.signal_integrity` never registered it (named cut, see that
# module's own docstring: no independently verifiable published
# numeric table could be confirmed within the WO-25 dispatch's research
# budget). This is a residual to RECORD, not an oversight to silently
# paper over.
# ---------------------------------------------------------------------------

DEFAULT_MICROSTRIP_Z0_LO_CLAIM_KIND = "elec.si.microstrip_z0.lo"
DEFAULT_MICROSTRIP_Z0_HI_CLAIM_KIND = "elec.si.microstrip_z0.hi"
DEFAULT_STRIPLINE_Z0_LO_CLAIM_KIND = "elec.si.stripline_z0.lo"
DEFAULT_STRIPLINE_Z0_HI_CLAIM_KIND = "elec.si.stripline_z0.hi"
DEFAULT_SERIES_TERMINATION_CLAIM_KIND = "elec.si.series_termination.rs"
DEFAULT_THEVENIN_TERMINATION_R1_CLAIM_KIND = "elec.si.thevenin_termination.r1"
DEFAULT_THEVENIN_TERMINATION_R2_CLAIM_KIND = "elec.si.thevenin_termination.r2"
DEFAULT_AC_SHUNT_R_CLAIM_KIND = "elec.si.ac_shunt.r"
DEFAULT_AC_SHUNT_C_CLAIM_KIND = "elec.si.ac_shunt.c"


class MicrostripImpedanceModel(_ClosedFormEngineModel):
    """Hammerstad-Jensen microstrip characteristic impedance
    (`library.signal_integrity.microstrip_z0`), one instance per
    `within [lo, hi]` half (D186 sec. 1 point 2, mirrors `ElecRailModel`):
    `sense=lower_bound()` for the `.lo` floor half (the worst-corner
    LOW Z0 over the input box must still clear the claim's lower
    limit), `sense=upper_bound()` for the `.hi` ceiling half."""

    def __init__(
        self,
        *,
        claim_kind: str,
        sense: ClaimSense,
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="elec.si.microstrip.z0",
            inputs=(
                "elec.si.microstrip.w",
                "elec.si.microstrip.h",
                "elec.si.microstrip.t",
                "elec.si.microstrip.er",
            ),
            engine_tags=frozenset({"tem", "surface_microstrip", "hammerstad_jensen"}),
        )
        self._sense = sense

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name=f"elec_si_microstrip_z0_{'hi' if self._sense.upper else 'lo'}",
            claim_kind=self._claim_kind,
            sense=self._sense,
            inputs=self._inputs,
            domain=("tem", "surface_microstrip", "hammerstad_jensen"),
        )


class StriplineImpedanceModel(_ClosedFormEngineModel):
    """Cohn's exact symmetric-stripline characteristic impedance
    (`library.signal_integrity.stripline_z0`), one instance per
    `within [lo, hi]` half (same shape as `MicrostripImpedanceModel`
    above)."""

    def __init__(
        self,
        *,
        claim_kind: str,
        sense: ClaimSense,
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="elec.si.stripline.z0",
            inputs=(
                "elec.si.stripline.w",
                "elec.si.stripline.b",
                "elec.si.stripline.er",
            ),
            engine_tags=frozenset(
                {"tem", "symmetric_stripline", "centred_track", "zero_thickness"}
            ),
        )
        self._sense = sense

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name=f"elec_si_stripline_z0_{'hi' if self._sense.upper else 'lo'}",
            claim_kind=self._claim_kind,
            sense=self._sense,
            inputs=self._inputs,
            domain=(
                "tem",
                "symmetric_stripline",
                "centred_track",
                "zero_thickness",
            ),
        )


class SeriesTerminationModel(_ClosedFormEngineModel):
    """Source-series termination resistor sizing
    (`library.signal_integrity.series_termination`), a floor claim:
    the caller's chosen `Rs` must be AT LEAST the worst-corner sized
    value (INV-9 conservative-low corner) so the series+driver
    impedance never UNDER-shoots the line's Z0."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_SERIES_TERMINATION_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="elec.si.series_termination.rs",
            inputs=(
                "elec.si.series_termination.z0",
                "elec.si.series_termination.ro",
            ),
            engine_tags=frozenset({"source_series", "matched_line"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="elec_si_series_termination_rs",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("source_series", "matched_line", "johnson_graham_ch4"),
        )


class TheveninTerminationR1Model(_ClosedFormEngineModel):
    """Thevenin (parallel) termination pull-up leg sizing
    (`library.signal_integrity.thevenin_termination_r1`), a floor
    claim over the same three inputs `TheveninTerminationR2Model`
    consumes (the algebraic twin, D94: one model MAY register under
    multiple kinds -- here two SEPARATE kinds share one input set,
    same posture as `ElecRailModel`'s two obligation halves)."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_THEVENIN_TERMINATION_R1_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="elec.si.thevenin_termination.r1",
            inputs=(
                "elec.si.thevenin_termination.z0",
                "elec.si.thevenin_termination.vcc",
                "elec.si.thevenin_termination.vbias",
            ),
            engine_tags=frozenset({"thevenin_parallel", "matched_line"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="elec_si_thevenin_termination_r1",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("thevenin_parallel", "matched_line", "johnson_graham_ch4"),
        )


class TheveninTerminationR2Model(_ClosedFormEngineModel):
    """Thevenin (parallel) termination pull-down leg sizing
    (`library.signal_integrity.thevenin_termination_r2`), the
    algebraic twin of `TheveninTerminationR1Model` (SAME derivation,
    the other unknown -- NO DUPLICATION)."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_THEVENIN_TERMINATION_R2_CLAIM_KIND
    ) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="elec.si.thevenin_termination.r2",
            inputs=(
                "elec.si.thevenin_termination.z0",
                "elec.si.thevenin_termination.vcc",
                "elec.si.thevenin_termination.vbias",
            ),
            engine_tags=frozenset({"thevenin_parallel", "matched_line"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="elec_si_thevenin_termination_r2",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("thevenin_parallel", "matched_line", "johnson_graham_ch4"),
        )


class AcShuntResistorModel(_ClosedFormEngineModel):
    """AC shunt termination resistor sizing
    (`library.signal_integrity.ac_shunt_sizing_r`), a floor claim: `R`
    matches `Z0` exactly (the matched-shunt condition), exact
    algebra."""

    def __init__(self, *, claim_kind: str = DEFAULT_AC_SHUNT_R_CLAIM_KIND) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="elec.si.ac_shunt.r",
            inputs=("elec.si.ac_shunt.z0",),
            engine_tags=frozenset({"ac_shunt"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="elec_si_ac_shunt_sizing_r",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("ac_shunt", "johnson_graham_ch4"),
        )


class AcShuntCapacitorModel(_ClosedFormEngineModel):
    """AC shunt termination capacitor sizing
    (`library.signal_integrity.ac_shunt_sizing_c`), a floor claim over
    the quarter-rise-time heuristic (NAMED heuristic, wide declared
    accuracy -- see the library module's own docstring; this wrapper
    adds no additional approximation, it only routes to the already-
    honestly-declared direction)."""

    def __init__(self, *, claim_kind: str = DEFAULT_AC_SHUNT_C_CLAIM_KIND) -> None:
        super().__init__(
            claim_kind=claim_kind,
            target="elec.si.ac_shunt.c",
            inputs=("elec.si.ac_shunt.rise_time", "elec.si.ac_shunt.r"),
            engine_tags=frozenset({"ac_shunt", "quarter_rise_time_heuristic"}),
        )

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="elec_si_ac_shunt_sizing_c",
            claim_kind=self._claim_kind,
            sense=ClaimSense.lower_bound(),
            inputs=self._inputs,
            domain=("ac_shunt", "quarter_rise_time_heuristic", "johnson_graham_ch4"),
        )


# ---------------------------------------------------------------------------
# WO-141 "feldspar fluids pack bridge": wraps `feldspar.fluids.network`'s
# Hardy-Cross loop solver (already consuming the lithos `FlownetPayload`,
# `network.py`'s own module doc) as three regolith `Model`s, so the
# fluid corpus's `fluids.mdot`/`fluids.flow_imbalance`/multi-path
# `fluids.dp` claims stop honestly-waiving for want of ANY registered
# model (lithos recon `scratch_recon_thermo_fluids.md` sec. 1.5/5,
# F126.1) and start discharging for real when this pack is installed.
#
# EDGE/NODE SELECTION CONVENTION (the one piece of wiring this WO
# invents, since it has no lithos-side counterpart yet -- flagged for
# the lithos-side translate work, WO-141's other half, to confirm or
# adapt): the `FlownetPayload` schema (fluorite/03 sec. 2) has no
# "which edge/node does this claim mean" field, and `DischargeRequest`
# has no string-valued channel beyond payload refs -- `inputs` is
# `Mapping[str, Interval]` (regolith/07, `harness/model.py`), floats
# only. Rather than invent a NEW lithos-side payload kind or schema
# field (out of this WO's scope -- schemas are single-sourced Rust,
# `lithos:CLAUDE.md`), these models reuse the ONE existing dynamic
# channel `ModelSignature.accepts` already permits: `accepts()` only
# requires the DECLARED `inputs` tuple's ports be PRESENT (a subset
# check, `harness/signature.py:74-82`), so a request MAY carry
# additional named scalar entries beyond what any signature declares.
# The convention: the translate side names the SELECTED edge/node ids
# themselves as EXTRA keys in `DischargeRequest.inputs` (any pinned
# `Interval`, e.g. `Interval(lo=1.0, hi=1.0)`, as a presence flag) --
# `estimate()` here intersects `request.inputs.keys()` against the
# resolved network's actual edge/node ids to recover the selection,
# never guessing which edge a claim means. This needs ZERO lithos
# schema changes: it is ordinary `given:` scalar data from the
# translate side's point of view, just keyed by the domain identifier
# instead of a physical-quantity name.
# ---------------------------------------------------------------------------

DEFAULT_FLUIDS_MDOT_LO_CLAIM_KIND = "fluids.mdot.lo"
DEFAULT_FLUIDS_MDOT_HI_CLAIM_KIND = "fluids.mdot.hi"
DEFAULT_FLUIDS_FLOW_IMBALANCE_CLAIM_KIND = "fluids.flow_imbalance"
DEFAULT_FLUIDS_DP_CLAIM_KIND = "fluids.dp"

#: `fluids.dp`'s two path-endpoint selector keys carry a fixed role
#: value (0.0 for the "from" node, 1.0 for the "to" node) so direction
#: survives even though the endpoints arrive as unordered dict keys --
#: see `FluidsDpModel`'s own docstring.
_DP_FROM_ROLE = 0.0
_DP_TO_ROLE = 1.0


def _resolve_solved_network(
    request: DischargeRequest,
    resolver: "Callable[[str], Result[bytes, object]] | None",
    model_id: str,
) -> "Result[SolvedNetwork, HarnessError]":
    """Shared plumbing (NO DUPLICATION) for the three flownet-query
    models below: resolves `request.payloads[FLOWNET_PORT]` through
    the D154 resolver-threading convention
    (`FeaStaticDeflectionFromGeometryModel`/`FatigueMinerDamageModel`'s
    own opt-in verbatim -- see either docstring for the full threading
    reasoning, not repeated here) and runs the Hardy-Cross solve. A
    request with no `FLOWNET_PORT` payload never reaches this function
    (`ModelSignature.accepts_payloads` already filtered it out as a
    non-match at selection time); an unresolvable digest, a schema-
    version mismatch, or a solve failure (unsupported edge kind,
    disconnected net, non-convergence) is the honest `DomainError`
    the caller returns as-is (06 "Failures"), never a raised
    exception."""
    flownet_ref = request.payloads[FLOWNET_PORT]
    engine_resolver = (
        RegolithResolverAdapter(resolver) if resolver is not None else NoStoreResolver()
    )
    resolved = engine_resolver.resolve(to_feldspar_payload_ref(flownet_ref))
    if resolved.is_err:
        _log.info("%s: flownet payload unresolvable: %r", model_id, resolved.danger_err)
        return Err(map_engine_error(model_id, resolved.danger_err))
    solved = solve_flownet_bytes(resolved.danger_ok)
    if solved.is_err:
        _log.info("%s: hardy-cross solve failed: %r", model_id, solved.danger_err)
        return Err(map_engine_error(model_id, solved.danger_err))
    return Ok(solved.danger_ok)


class FluidsMdotModel(Model):
    """Single-edge mass/volumetric flow-rate query over a solved
    Hardy-Cross network (`fluids.mdot(<edge>)`), one instance per
    bound half (lo/hi, the `ElecRailModel` two-instance shape --
    `pack.register()` would instantiate this twice for a window claim
    `fluids.mdot(edge) in [lo, hi]`, once for a single-direction
    comparison `fluids.mdot(edge) >= lo`).

    Reports the converged `flow_rate` (m^3/s, signed by the edge's own
    `a->b` sense) of whichever ONE edge in the resolved flownet the
    request's extra `inputs` keys select (see this file's WO-141
    section-comment for the selection convention). Exactly one
    matching edge id is required to close the claim; zero or more than
    one is an honest `DomainError` naming the ambiguity -- never a
    guess at which edge was meant."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_FLUIDS_MDOT_LO_CLAIM_KIND, sense: ClaimSense
    ) -> None:
        """`claim_kind` defaults to the lower-bound vocabulary kind;
        `sense` is required (mirrors `ElecRailModel`'s constructor --
        `pack.register()` binds one lo/hi pair explicitly, no implicit
        default direction)."""
        self._claim_kind = claim_kind
        self._sense = sense

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name=f"fluids_mdot_{'hi' if self._sense.upper else 'lo'}",
            claim_kind=self._claim_kind,
            sense=self._sense,
            inputs=(),
            domain=("incompressible", "network", "hardy_cross"),
            payload_kinds={FLOWNET_PORT: "flownet"},
        )

    @property
    def version(self) -> str:
        return "1"

    @property
    def cost(self) -> int:
        """Payload-tier cost (mirrors `FeaStaticDeflectionFromGeometryModel`
        /`FatigueMinerDamageModel`): a full network solve is costlier
        than any scalar closed form, so a cheaper declared-`mdot`
        closed form (if one is ever registered under the same kind)
        keeps winning when it applies."""
        return _PAYLOAD_TIER_COST

    def estimate(
        self,
        request: DischargeRequest,
        *,
        resolver: Callable[[str], Result[bytes, object]] | None = None,
    ) -> Result[Prediction, HarnessError]:
        network_result = _resolve_solved_network(request, resolver, self.model_id)
        if network_result.is_err:
            return Err(network_result.danger_err)
        network = network_result.danger_ok

        selected = [edge_id for edge_id in request.inputs if edge_id in network.by_id]
        if len(selected) != 1:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"fluids.mdot needs exactly one selected edge id among "
                        f"the request's inputs to match a flownet edge; found "
                        f"{len(selected)}: {sorted(selected)}"
                    ),
                )
            )
        edge = network.by_id[selected[0]]
        _log.info(
            "%s: edge=%s flow_rate=%s (sense.upper=%s)",
            self.model_id,
            edge.id,
            edge.flow,
            self._sense.upper,
        )
        return Ok(Prediction(value=edge.flow, eps=0.0, coverage=1.0, in_domain=True))


class FluidsFlowImbalanceModel(Model):
    """Sibling-branch flow-distribution-uniformity query over a solved
    Hardy-Cross network (`fluids.flow_imbalance([e1, e2, ...])`), an
    upper-bound claim: `(max - min) / mean` of `|flow|` over the
    SELECTED sibling edges must stay AT OR BELOW the caller's stated
    fraction (the fluorite corpus's `balance: fluids.flow_imbalance(...)
    < 5%` shape, `docs/guide/03-fluorite-guide.md:239` -- read there,
    not reproduced here).

    The selected edge SET is whichever two-or-more edge ids the
    request's extra `inputs` keys name (this file's WO-141 section
    comment); fewer than two matching edges cannot express an
    imbalance and is an honest `DomainError`, not a fabricated `0%`."""

    def __init__(
        self, *, claim_kind: str = DEFAULT_FLUIDS_FLOW_IMBALANCE_CLAIM_KIND
    ) -> None:
        self._claim_kind = claim_kind

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="fluids_flow_imbalance",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=(),
            domain=("incompressible", "network", "hardy_cross"),
            payload_kinds={FLOWNET_PORT: "flownet"},
        )

    @property
    def version(self) -> str:
        return "1"

    @property
    def cost(self) -> int:
        return _PAYLOAD_TIER_COST

    def estimate(
        self,
        request: DischargeRequest,
        *,
        resolver: Callable[[str], Result[bytes, object]] | None = None,
    ) -> Result[Prediction, HarnessError]:
        network_result = _resolve_solved_network(request, resolver, self.model_id)
        if network_result.is_err:
            return Err(network_result.danger_err)
        network = network_result.danger_ok

        selected = sorted(
            edge_id for edge_id in request.inputs if edge_id in network.by_id
        )
        if len(selected) < 2:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"fluids.flow_imbalance needs at least two selected "
                        f"edge ids among the request's inputs that match "
                        f"flownet edges; found {len(selected)}: {selected}"
                    ),
                )
            )
        flows = [abs(network.by_id[edge_id].flow) for edge_id in selected]
        mean_flow = sum(flows) / len(flows)
        if mean_flow <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"fluids.flow_imbalance over edges {selected} has zero "
                        "mean flow -- imbalance fraction is undefined, not "
                        "reportable as 0%"
                    ),
                )
            )
        imbalance = (max(flows) - min(flows)) / mean_flow
        _log.info(
            "%s: edges=%s flows=%s imbalance=%s",
            self.model_id,
            selected,
            flows,
            imbalance,
        )
        return Ok(Prediction(value=imbalance, eps=0.0, coverage=1.0, in_domain=True))


class FluidsDpModel(Model):
    """Multi-segment (multi-path) pressure-drop query over a solved
    Hardy-Cross network (`fluids.dp(<from> -> <to>)`), an upper-bound
    claim: the summed signed pressure drop along the network path
    connecting the two named nodes must stay AT OR BELOW the caller's
    stated limit -- the F132.3 refusal this WO burns
    (`examples/flagships/espresso_machine/brew_water.fluo:169`, lithos
    recon sec. 1.4/2b): a flowmeter-plus-check-valve span (or any
    multi-component path) that the single-segment
    `FluidPressureDropModel` (lithos harness, one Darcy-Weisbach edge
    only) cannot express.

    Registers under the SAME claim kind (`fluids.dp`, default) the
    lithos single-segment closed form uses (D94: multiple models MAY
    compete under one kind) -- this payload-tier model only wins the
    cost competition when the single-segment model's declared inputs
    are absent AND a flownet payload is present, i.e. exactly the
    multi-path case the single-segment model cannot cover.

    Path endpoints: the request's extra `inputs` keys name exactly TWO
    node ids present in the resolved flownet (this file's WO-141
    section comment); each carries a fixed ROLE value distinguishing
    direction -- `_DP_FROM_ROLE` (0.0) for the origin, `_DP_TO_ROLE`
    (1.0) for the destination (an unordered pair of dict keys alone
    cannot carry direction, and `fluids.dp(a -> b)` is directional:
    `dp(a -> b) == -dp(b -> a)`). Anything other than exactly one
    origin and one destination match is an honest `DomainError`."""

    def __init__(self, *, claim_kind: str = DEFAULT_FLUIDS_DP_CLAIM_KIND) -> None:
        self._claim_kind = claim_kind

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="fluids_dp_multipath",
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=(),
            domain=("incompressible", "network", "hardy_cross", "multi_path"),
            payload_kinds={FLOWNET_PORT: "flownet"},
        )

    @property
    def version(self) -> str:
        return "1"

    @property
    def cost(self) -> int:
        """Costlier than the single-segment closed form (a full
        network solve + path search vs. one declared-input formula),
        so the cheaper single-segment model keeps winning whenever its
        own scalar inputs are actually supplied (06 "cost declares the
        honest relative expense")."""
        return _PAYLOAD_TIER_COST

    def estimate(
        self,
        request: DischargeRequest,
        *,
        resolver: Callable[[str], Result[bytes, object]] | None = None,
    ) -> Result[Prediction, HarnessError]:
        network_result = _resolve_solved_network(request, resolver, self.model_id)
        if network_result.is_err:
            return Err(network_result.danger_err)
        network = network_result.danger_ok

        from_nodes = [
            node_id
            for node_id, interval in request.inputs.items()
            if node_id in network.incidence
            and interval.lo == interval.hi == _DP_FROM_ROLE
        ]
        to_nodes = [
            node_id
            for node_id, interval in request.inputs.items()
            if node_id in network.incidence
            and interval.lo == interval.hi == _DP_TO_ROLE
        ]
        if len(from_nodes) != 1 or len(to_nodes) != 1:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        "fluids.dp needs exactly one 'from' node "
                        f"(role={_DP_FROM_ROLE}) and one 'to' node "
                        f"(role={_DP_TO_ROLE}) among the request's inputs "
                        f"matching flownet node ids; found "
                        f"from={sorted(from_nodes)} to={sorted(to_nodes)}"
                    ),
                )
            )

        path_result = find_path_edges(network, from_nodes[0], to_nodes[0])
        if path_result.is_err:
            return Err(map_engine_error(self.model_id, path_result.danger_err))
        path = path_result.danger_ok
        total_dp = sum(sign * edge_dp(edge) for edge, sign in path)
        _log.info(
            "%s: path %s -> %s (%d edges) total dp=%s",
            self.model_id,
            from_nodes[0],
            to_nodes[0],
            len(path),
            total_dp,
        )
        return Ok(Prediction(value=total_dp, eps=0.0, coverage=1.0, in_domain=True))
