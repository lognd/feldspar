from __future__ import annotations

"""`AttemptRecord`, `Solution`, `execute()`, `route_settings_digest()` --
the WO-06 execution facade (01-interfaces `feldspar.plan`, 04-routing
"Execution"). Walks a planned `Route` in order, running the REAL
`SolveFn` corner sweep per step (the planner's estimate used a sum
surrogate, WO-05 notes; this is where the exact sweep replaces it,
FINV-4: same core `corner_sweep`/`inflate`/`total_error` routines) --
never re-searches (`Route` already carries everything needed)."""

import math
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from feldspar.core import Interval, PortDecl, corner_sweep, inflate
from feldspar.logging_setup import get_logger
from feldspar.plan.route import Route
from feldspar.solve._build import invoke_solve_fn
from feldspar.solve._models import Citation
from feldspar.solve.digest import canonical_digest
from feldspar.solve.errors import SolveError
from feldspar.solve.payload import PayloadRef

if TYPE_CHECKING:
    from feldspar.plan.cache import PayloadStepCache
    from feldspar.solve.registry import SolverRegistry

__all__ = [
    "AttemptRecord",
    "Solution",
    "error_to_record_fields",
    "execute",
    "execute_with_attribution",
    "route_settings_digest",
]

_log = get_logger(__name__)


# frob:doc docs/modules/plan.md#plan_execute
class AttemptRecord(BaseModel):
    """One reroute-loop attempt (04-routing "Fallback rerouting"): the
    exclusion set going INTO this attempt, which step (if any) failed --
    `None` means `plan()` itself failed, not an executed step -- and the
    failure as a JSON-safe kind/detail pair (never the live `PlanError`/
    `SolveError` object: those aren't pydantic models, and keeping this
    model plain-JSON-shaped is what lets `Solution` digest cleanly
    through `canonical_digest`, AD-5)."""

    model_config = ConfigDict(frozen=True)

    excluded: Tuple[str, ...]
    route_digest: Optional[str] = None
    failed_solver_id: Optional[str] = None
    error_kind: str
    error_detail: Mapping[str, Any] = {}


# frob:doc docs/modules/plan.md#plan_execute
def error_to_record_fields(error: Any) -> Tuple[str, Mapping[str, Any]]:
    """`(kind, detail)` for any `_TaggedError`-shaped value (`PlanError`/
    `SolveError`) -- the ONE place a live error value gets lowered into
    an `AttemptRecord`'s plain fields (no duplication across `solve.py`
    call sites)."""
    fields = getattr(error, "_fields", {})
    detail = {
        k: (v if isinstance(v, (str, int, float, bool)) or v is None else repr(v))
        for k, v in fields.items()
    }
    return error.kind, detail


# frob:doc docs/modules/plan.md#plan_execute
class Solution(BaseModel):
    """A successful `solve()`/`execute()` result (01-interfaces
    `Solution`, 04-routing "Execution"). `eps` is the FINAL step's
    realized model error only -- every upstream step's error already
    rides in `value`'s width via `inflate` at each consuming step (02,
    audit A-1), so `total_error(value, eps)` (WO-04) is the budget-
    checked total."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    target: str
    value: Interval
    eps: float
    route: Route
    settings_digest: str
    solver_versions: Mapping[str, str]
    attempts: Tuple[AttemptRecord, ...] = ()
    cache_hit: bool = False

    # WO-10 (`plan/report.py` `explain()`/`to_dict()`) rendering data:
    # captured here at execution time (declared metadata copied off the
    # frozen registry, never recomputed) so the justification report is
    # a PURE RENDERING of what `Solution` carries, with no registry/
    # solver access at render time (04-routing "Justification report").
    # Keyed by `solver_id`, matching `solver_versions`'s convention.
    step_eps: Mapping[str, float] = {}
    step_citations: Mapping[str, Tuple[Citation, ...]] = {}
    step_declared_domain: Mapping[str, Any] = {}  # feldspar.core.Domain

    # WO-11 symbolic-derivation provenance (`SolverInfo.algebraic_form`/
    # `.admission_predicate`), carried the same way -- keyed by
    # `solver_id`, key omitted entirely for a hand-written (non-symbolic)
    # step (`report.py`'s renderer treats a missing key as "not carried").
    step_algebraic_form: Mapping[str, str] = {}
    step_admission_predicate: Mapping[str, str] = {}

    # The caller's `eps_budget` for THIS solve, if known (`solve()`
    # stamps it; a bare `execute()` call has no budget context and
    # leaves this `None` -- `explain()` renders "no budget context"
    # rather than fabricating a decomposition, 04-routing "Execution").
    eps_budget: Optional[float] = None

    # frob:doc docs/modules/plan.md#plan_execute
    def explain(self) -> str:
        """Renders the step-by-step justification report (04-routing
        "Justification report"): PURE rendering of this `Solution`'s
        already-carried data, no recomputation, no solver/registry
        calls."""
        from feldspar.plan.report import render_explain

        return render_explain(self)

    # frob:doc docs/modules/plan.md#plan_execute
    def to_dict(self) -> "Dict[str, Any]":
        """Machine-readable twin of `explain()` -- same data, JSON-safe
        shape."""
        from feldspar.plan.report import render_to_dict

        return render_to_dict(self)


# frob:doc docs/modules/plan.md#plan_execute
def route_settings_digest(route: Route, registry: "SolverRegistry") -> str:
    """Folds every step's `SolverInfo.settings_digest` (03, F1) in route
    order into ONE digest (04-routing "Execution": "fold settings
    digests ... into a Solution"). Shared by `execute()` (the field it
    stamps onto `Solution`) and `cache.py` (a cache-key component) so
    there is exactly one settings-fold implementation, not one per
    caller (house rule: no duplication)."""
    solver_map = {info.solver_id: info for info, _fn in registry}
    digests = [solver_map[step.solver_id].settings_digest for step in route.steps]
    return canonical_digest(digests)


def _is_payload_port(port_table: Mapping[str, PortDecl], port: str) -> bool:
    """A port is a payload port iff its DECLARED rank is `payload(kind)`
    (WO-12, 09 sec. 4); an undeclared port is scalar by convention (the
    F12 opt-in rule: no port table, no payload semantics)."""
    decl = port_table.get(port)
    return decl is not None and decl.rank.kind == "payload"


def _declared_kind(port_table: Mapping[str, PortDecl], port: str) -> str:
    return port_table[port].rank.payload_kind or ""


def _split_step_inputs(
    info: Any,
    port_table: Mapping[str, PortDecl],
    values: Mapping[str, Interval],
    payload_values: Mapping[str, PayloadRef],
) -> "Result[Tuple[List[str], Dict[str, PayloadRef]], SolveError]":
    """Partitions a step's declared inputs into scalar ports (corner-
    swept) and payload ports (passed through exact-by-reference, WO-12).
    A payload-declared port with no supplied ref is
    `SolveError.MissingPayload`; a supplied ref whose kind differs from
    the port's declared kind is `SolveError.PayloadKindMismatch` (the
    execution-time twin of the registration kind check, 09 sec. 4)."""
    scalar_ports: List[str] = []
    payload_inputs: Dict[str, PayloadRef] = {}
    for port in info.inputs:
        ref = payload_values.get(port)
        if ref is not None:
            if _is_payload_port(port_table, port):
                expected = _declared_kind(port_table, port)
                if ref.kind != expected:
                    _log.warning(
                        "payload kind mismatch at %s: declared %s, got %s",
                        port,
                        expected,
                        ref.kind,
                    )
                    return Err(
                        SolveError.PayloadKindMismatch(
                            port=port, expected_kind=expected, actual_kind=ref.kind
                        )
                    )
            payload_inputs[port] = ref
            continue
        if port in values:
            scalar_ports.append(port)
            continue
        if _is_payload_port(port_table, port):
            _log.warning("missing payload for declared payload port %s", port)
            return Err(SolveError.MissingPayload(port=port))
        # A missing SCALAR input is unreachable off a well-formed Route
        # (the planner only commits steps whose inputs are achieved), so
        # falling through to the executor's KeyError below is the
        # programmer-bug path, deliberately not a SolveError.
        scalar_ports.append(port)
    return Ok((scalar_ports, payload_inputs))


def _check_step_output(
    info: Any, out_values: Mapping[str, float], scalar_outputs: List[str]
) -> "Result[None, SolveError]":
    for port in scalar_outputs:
        if port not in out_values:
            return Err(SolveError.MissingOutput(port=port))
    for port, value in out_values.items():
        if not math.isfinite(value):
            return Err(SolveError.NonFinite(port=port))
    return Ok(None)


def _check_step_output_domain(
    info: Any, hull: Mapping[str, Interval], step_eps: float
) -> "Result[None, SolveError]":
    """The execution-time twin of the planner's INPUT-only admission
    filter (`feldspar_core::search`, 04-routing point 2): a solver's
    declared `Domain.box` entry for one of its own OUTPUT ports is a
    validity constraint on the REALIZED result, not a plan-time
    precondition (the output isn't known before the step runs, so
    checking it at plan time would make every `Relation`-declared
    multi-direction solver permanently unroutable -- the bug this
    function's addition closes). Checked here, once, against the
    realized output hull INFLATED BY this step's own realized `step_eps`
    -- the same `inflate()` the input-side admission filter applies
    (:443) -- not the raw hull: the honest-conservative posture of the
    rest of the pipeline is that a value's error band is part of the
    value for admission purposes, so a hull that is in-box but whose
    error band escapes it is still an out-of-domain result. An
    out-of-box (post-inflation) output is an honest `SolveError` the
    fallback reroute (04-routing "Fallback rerouting") handles like any
    other step failure -- never a silent pass."""
    for port, allowed in info.domain.box.items():
        value = hull.get(port)
        if value is None:
            # Not one of this step's outputs (could be an input-side box
            # entry, or a port this step doesn't touch at all) -- nothing
            # to check here.
            continue
        inflated = inflate(value, step_eps)
        if not inflated.is_subset(allowed):
            return Err(
                SolveError.OutputOutOfDomain(
                    port=port,
                    lo=inflated.lo,
                    hi=inflated.hi,
                    box_lo=allowed.lo,
                    box_hi=allowed.hi,
                )
            )
    return Ok(None)


def _make_corner_fn(
    info: Any,
    fn: Any,
    measured: List[float],
    payload_inputs: Mapping[str, PayloadRef],
    scalar_outputs: List[str],
    payload_outputs: List[str],
    port_table: Mapping[str, PortDecl],
    produced: Dict[str, List[PayloadRef]],
    remaining_budget: Optional[float] = None,
) -> Any:
    """Builds the `corner_sweep` callback for one step: runs the real
    `SolveFn`, checks finiteness/output-completeness (audit A-4, friction
    G12), validates and collects any reported `measured_eps` (which
    replaces the declared accuracy ceiling for THIS step, 04-routing),
    and returns the plain `Mapping[str, float]` `corner_sweep` hulls.

    WO-12 payload flow: `payload_inputs` merge into every corner mapping
    unchanged (exact by reference -- payloads are never swept); each
    declared payload OUTPUT must appear in `SolveOutput.payloads` with
    the port's declared kind, and is collected into `produced` for the
    caller's corner-invariance check (a payload output that varies
    across corners would need hulling, which payloads by definition
    cannot have).

    WO-13 (09 sec. 3): `remaining_budget` is passed to an `eps_seeking`
    step's `SolveFn` ONLY, via `invoke_solve_fn` (the one call-site that
    probes `.eps_seeking`, `_build.wrap_solve_fn`'s attribute-tagging
    convention). Every other `SolveFn` (eps_seeking=False, or a raw
    hand-registered callable with no such attribute at all) keeps the
    exact pre-WO-13 one-argument call -- backward compatible with every
    solver that predates this WO."""

    def corner_fn(
        corner: Mapping[str, float],
    ) -> "Result[Mapping[str, float], SolveError]":
        full_corner: Dict[str, Any] = dict(corner)
        full_corner.update(payload_inputs)
        res = invoke_solve_fn(fn, full_corner, remaining_budget)
        if res.is_err:
            return res.swap_ok(dict)
        out = res.danger_ok  # SolveOutput
        checked = _check_step_output(info, out.values, scalar_outputs)
        if checked.is_err:
            return checked.swap_ok(dict)
        for port in payload_outputs:
            ref = out.payloads.get(port)
            if ref is None:
                _log.warning(
                    "payload output %s missing from %s's SolveOutput.payloads",
                    port,
                    info.solver_id,
                )
                return Err(SolveError.MissingOutput(port=port))
            expected = _declared_kind(port_table, port)
            if ref.kind != expected:
                _log.warning(
                    "payload output kind mismatch at %s: declared %s, got %s",
                    port,
                    expected,
                    ref.kind,
                )
                return Err(
                    SolveError.PayloadKindMismatch(
                        port=port, expected_kind=expected, actual_kind=ref.kind
                    )
                )
            produced.setdefault(port, []).append(ref)
        if out.measured_eps is not None:
            if not math.isfinite(out.measured_eps) or out.measured_eps < 0:
                return Err(
                    SolveError.InvalidMeasurement(
                        reason=f"measured_eps={out.measured_eps!r} for {info.solver_id}"
                    )
                )
            measured.append(out.measured_eps)
        return Ok({port: out.values[port] for port in scalar_outputs})

    return corner_fn


# frob:doc docs/modules/plan.md#plan_execute
def execute(
    route: Route,
    registry: "SolverRegistry",
    known: Mapping[str, Interval],
    payloads: Optional[Mapping[str, PayloadRef]] = None,
    step_cache: "Optional[PayloadStepCache]" = None,
    eps_budget: Optional[float] = None,
) -> "Result[Solution, SolveError]":
    """Public `execute()` (01-interfaces): thin wrapper over
    `execute_with_attribution` that drops the failing-step attribution
    the public `SolveError`-only contract has no slot for. `payloads`
    supplies the request's known payload-port refs (WO-12); `step_cache`
    is the per-payload/per-rung step cache (04-routing "Solve cache",
    WO-12 extension). `eps_budget` (WO-13, 09 sec. 3) is the caller's
    total eps budget for this route, if known -- threaded to any
    `eps_seeking` step as its REMAINING budget (`None` here means "no
    budget context", which an eps-seeking step's ladder treats as
    "run the fixed first pair, do not seek")."""
    result = execute_with_attribution(
        route, registry, known, payloads, step_cache, eps_budget
    )
    if result.is_err:
        _solver_id, err = result.danger_err
        return Err(err)
    return result.swap_err(SolveError)


# frob:doc docs/modules/plan.md#plan_execute
def execute_with_attribution(
    route: Route,
    registry: "SolverRegistry",
    known: Mapping[str, Interval],
    payloads: Optional[Mapping[str, PayloadRef]] = None,
    step_cache: "Optional[PayloadStepCache]" = None,
    eps_budget: Optional[float] = None,
) -> "Result[Solution, Tuple[Optional[str], SolveError]]":
    """Same walk as `execute()`, but on failure also reports WHICH
    step's `solver_id` raised (`None` only in the impossible zero-step
    case) -- `solve.py`'s reroute loop needs this to update its
    exclusion set; the public `execute()` signature (01-interfaces) has
    no slot for it, so this is the shared implementation both call
    into (house rule: no duplication)."""
    return _execute_impl(route, registry, known, payloads, step_cache, eps_budget)


def _execute_impl(
    route: Route,
    registry: "SolverRegistry",
    known: Mapping[str, Interval],
    payloads: Optional[Mapping[str, PayloadRef]] = None,
    step_cache: "Optional[PayloadStepCache]" = None,
    eps_budget: Optional[float] = None,
) -> "Result[Solution, Tuple[Optional[str], SolveError]]":
    """Walks `route` in order (01-interfaces `execute`): per step,
    corner-sweeps eps-INFLATED inputs through the real `SolveFn`, hulls
    outputs, and charges the step's REALIZED eps (measured, when the
    solver reports one, else the declared `Accuracy.worst_over` the
    achieved hull -- the same `worst_over` the planner's estimate uses,
    FINV-4). A zero-step route (G12: target already known) returns the
    known interval at eps 0 directly.

    WO-12: payload ports flow beside the interval channel -- payload
    inputs merge into every corner exact-by-reference, payload outputs
    come back on `SolveOutput.payloads` (corner-INVARIANT, checked) and
    feed downstream steps' `payload_values`. Payload-touching
    deterministic steps consult/populate `step_cache` (keyed on payload
    digests + the scalar box, 09 secs. 3-4) so one mesh feeds multiple
    solves without re-running gmsh."""
    solver_map = {info.solver_id: (info, fn) for info, fn in registry}
    port_table = registry.port_table()
    payload_values: Dict[str, PayloadRef] = dict(payloads or {})
    values: Dict[str, Interval] = dict(known)
    eps_map: Dict[str, float] = {port: 0.0 for port in known}
    solver_versions: Dict[str, str] = {}
    step_eps_map: Dict[str, float] = {}
    step_citations_map: Dict[str, Tuple[Citation, ...]] = {}
    step_declared_domain_map: Dict[str, Any] = {}
    step_algebraic_form_map: Dict[str, str] = {}
    step_admission_predicate_map: Dict[str, str] = {}
    final_eps = 0.0

    if not route.steps:
        value = values[route.target]
        _log.info(
            "execute: zero-step route for target=%s (already known)", route.target
        )
        return Ok(
            Solution(
                target=route.target,
                value=value,
                eps=0.0,
                route=route,
                settings_digest=route_settings_digest(route, registry),
                solver_versions={},
                attempts=(),
                cache_hit=False,
            )
        )

    for step in route.steps:
        info, fn = solver_map[step.solver_id]
        split = _split_step_inputs(info, port_table, values, payload_values)
        if split.is_err:
            _log.warning(
                "execute: step %s input split failed: %r", step.solver_id, split.err
            )
            return Err((step.solver_id, split.danger_err))
        scalar_ports, payload_inputs = split.danger_ok
        payload_outputs = [
            port for port in info.outputs if _is_payload_port(port_table, port)
        ]
        scalar_outputs = [port for port in info.outputs if port not in payload_outputs]
        box = {
            port: inflate(values[port], eps_map.get(port, 0.0)) for port in scalar_ports
        }

        # WO-13 (09 sec. 3): the remaining eps budget passed to THIS
        # step -- `eps_budget` minus the worst-case eps already charged
        # to reach this step's own scalar inputs (the same `eps_map`
        # value domain checks already inflate by). This is a
        # conservative, v1-simple approximation of "remaining budget"
        # (the true accumulation is inflate-based per port, not a
        # simple subtraction across steps) -- adequate because the
        # acceptance scenario (09 sec. 3, WO-13) is a single eps-seeking
        # step at the end of a route; a multi-eps-seeking-step route's
        # exact budget split is future work, not required here.
        # `None` propagates as "no budget context" (a bare `execute()`
        # call with no caller budget).
        remaining_budget: Optional[float] = None
        if eps_budget is not None:
            upstream_eps = max(
                (eps_map.get(port, 0.0) for port in scalar_ports), default=0.0
            )
            remaining_budget = max(eps_budget - upstream_eps, 0.0)

        # WO-12 per-payload step cache: only DETERMINISTIC, payload-
        # touching steps participate (scalar-only routes keep their
        # exact pre-WO-12 behavior; a nondeterministic step is never
        # cached, mirroring is_route_cacheable). A hit is only honored
        # if the step's tools are still present (A-5's argument applied
        # per-step: a recompute would fail ToolMissing, so a hit must
        # too -- the miss path lets the real failure surface).
        step_key: Optional[str] = None
        cached_step = None
        if (
            step_cache is not None
            and info.deterministic
            and (payload_inputs or payload_outputs)
        ):
            step_key = step_cache.key(info, box, payload_inputs)
            cached_step = step_cache.get(
                step_key, probe_tools=getattr(fn, "probe_tools", None)
            )

        if cached_step is not None:
            hull, produced_refs, step_eps = cached_step
            _log.info(
                "execute: step %s served from step cache (key=%s)",
                step.solver_id,
                step_key,
            )
        else:
            measured: List[float] = []
            produced: Dict[str, List[PayloadRef]] = {}
            swept = corner_sweep(
                box,
                _make_corner_fn(
                    info,
                    fn,
                    measured,
                    payload_inputs,
                    scalar_outputs,
                    payload_outputs,
                    port_table,
                    produced,
                    remaining_budget,
                ),
            )
            if swept.is_err:
                _log.warning("execute: step %s failed: %r", step.solver_id, swept.err)
                return Err((step.solver_id, swept.danger_err))
            hull = swept.danger_ok

            produced_refs: Dict[str, PayloadRef] = {}
            for port, refs in produced.items():
                first = refs[0]
                if any(ref != first for ref in refs[1:]):
                    _log.warning(
                        "execute: payload output %s of %s varied across corners",
                        port,
                        step.solver_id,
                    )
                    return Err(
                        (
                            step.solver_id,
                            SolveError.InvalidMeasurement(
                                reason=(
                                    f"payload output {port} of {info.solver_id} "
                                    "varied across corners (payloads are exact "
                                    "by reference, 09 sec. 4)"
                                )
                            ),
                        )
                    )
                produced_refs[port] = first

            if measured:
                step_eps = max(measured)
            else:
                step_eps = max(
                    (
                        info.accuracy[port].worst_over(hull[port])
                        for port in scalar_outputs
                    ),
                    default=0.0,
                )
            if step_cache is not None and step_key is not None:
                step_cache.put(step_key, hull, produced_refs, step_eps)
        _log.debug("execute: step %s realized_eps=%s", step.solver_id, step_eps)

        domain_check = _check_step_output_domain(info, hull, step_eps)
        if domain_check.is_err:
            _log.warning(
                "execute: step %s realized output out of declared domain: %r",
                step.solver_id,
                domain_check.err,
            )
            return Err((step.solver_id, domain_check.danger_err))

        for port, iv in hull.items():
            values[port] = iv
            eps_map[port] = step_eps
        for port, ref in produced_refs.items():
            payload_values[port] = ref
        solver_versions[step.solver_id] = info.version
        step_eps_map[step.solver_id] = step_eps
        step_citations_map[step.solver_id] = info.citations
        step_declared_domain_map[step.solver_id] = info.domain
        if info.algebraic_form is not None:
            step_algebraic_form_map[step.solver_id] = info.algebraic_form
        if info.admission_predicate is not None:
            step_admission_predicate_map[step.solver_id] = info.admission_predicate
        final_eps = step_eps

    value = values[route.target]
    solution = Solution(
        target=route.target,
        value=value,
        eps=final_eps,
        route=route,
        settings_digest=route_settings_digest(route, registry),
        solver_versions=solver_versions,
        attempts=(),
        cache_hit=False,
        step_eps=step_eps_map,
        step_citations=step_citations_map,
        step_declared_domain=step_declared_domain_map,
        step_algebraic_form=step_algebraic_form_map,
        step_admission_predicate=step_admission_predicate_map,
    )
    _log.info(
        "execute: succeeded target=%s eps=%s steps=%d",
        route.target,
        final_eps,
        len(route.steps),
    )
    return Ok(solution)
