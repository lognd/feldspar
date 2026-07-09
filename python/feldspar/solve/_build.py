from __future__ import annotations

"""Private shared builder: the ONE place raw SolverInfo/SolveFn pairs get
assembled from author-facing (possibly sugared) arguments. `@solver`
(solver.py) and `make_direction`/`Relation`/`Correlation` (sugar.py) all
call `build_solver_info_and_fn` so a sugar-built direction is digest-
equal to its hand-built twin by construction (03 "Registration
ergonomics"; 02-edge-cases WO-03: "sugar-built direction vs hand-built
twin -> identical SolverInfo digest") -- there is exactly one lowering
path, never a second registration route (AD-4 spirit extended to sugar)."""

from typing import (
    Any,
    Callable,
    Iterable,
    Literal,
    Mapping,
    Optional,
    Tuple,
    Union,
    cast,
)

from typani.result import Ok, Result

from feldspar.core import Accuracy, Domain, Interval
from feldspar.solve import digest as _digest
from feldspar.solve._models import Citation, ClaimSenses, SolveOutput, SolverInfo
from feldspar.solve.errors import SolveError
from feldspar.solve.seeking import CostCurve

RawReturn = Union[Result, SolveOutput, Mapping[str, float], float, int]
# The public one-argument protocol (01-interfaces, unchanged by WO-13):
# a hand-registered `SolveFn` (`registry.register(info, fn)` directly,
# `examples/solvers/00_raw_protocol.py`, `tests/unit/test_calib.py`'s
# fixtures) is `(Mapping[str, float]) -> Result[...]` and NOTHING calls
# it any other way. WO-13's `eps_seeking` solvers are the one exception:
# `wrap_solve_fn` below stamps `.eps_seeking = True` on the wrapped
# callable it returns (mirroring `fea/solver.py`'s existing
# `.probe_tools` attribute-tagging convention), and `plan/execute.py`/
# `calib/harness.py` probe that attribute to decide whether to also
# pass the remaining eps budget as a second positional argument --
# never by widening this type (every non-eps-seeking SolveFn, wrapped
# or raw, keeps working exactly as before).
SolveFn = Callable[[Mapping[str, float]], "Result[SolveOutput, SolveError]"]


def coerce_domain(
    domain: Union[Domain, Mapping[str, Any]], tags: Iterable[str] = ()
) -> Domain:
    """F11: a bare dict IS the domain (box values accept `(lo, hi)`
    tuples or `Interval`s); `Domain` instances pass through unchanged."""
    if isinstance(domain, Domain):
        return domain
    box = {}
    for port, bound in domain.items():
        if isinstance(bound, Interval):
            box[port] = bound
        else:
            lo, hi = bound
            box[port] = Interval(float(lo), float(hi))
    return Domain(box, set(tags))


def coerce_citation(item: Union[Citation, str]) -> Citation:
    """F10: `"kind: ref -- note"` (note optional) coerces to `Citation`."""
    if isinstance(item, Citation):
        return item
    kind, sep, rest = item.partition(": ")
    if not sep:
        raise ValueError(
            f"citation string must be 'kind: ref' or 'kind: ref -- note', got {item!r}"
        )
    ref, _, note = rest.partition(" -- ")
    kind_literal = cast(
        Literal["paper", "handbook", "standard", "calibration"], kind.strip()
    )
    return Citation(kind=kind_literal, ref=ref.strip(), note=note.strip())


def coerce_citations(items: Iterable[Union[Citation, str]]) -> Tuple[Citation, ...]:
    return tuple(coerce_citation(i) for i in items)


def coerce_accuracy(
    accuracy: Union[Accuracy, Mapping[str, Accuracy]], outputs: Iterable[str]
) -> Mapping[str, Accuracy]:
    """F15: a single `Accuracy` applies to every declared output."""
    if isinstance(accuracy, Accuracy):
        return {p: accuracy for p in outputs}
    return dict(accuracy)


def wrap_solve_fn(
    raw_fn: Callable[..., Any],
    outputs: Tuple[str, ...],
    eps_seeking: bool = False,
) -> SolveFn:
    """F13/F14/F16 return normalization: the author-facing return type is
    `Result | SolveOutput | Mapping | float` (float only with exactly one
    output); this wraps it into the strict `SolveFn` protocol
    (`Result[SolveOutput, SolveError]`) every registered solver has.
    Raising remains a programmer bug (F13), same as `Interval`'s direct-
    construction-raises precedent -- never converted into a SolveError
    value here.

    WO-13: `wrapped` is stamped `.eps_seeking = eps_seeking` (module
    docstring's attribute-tagging convention); when `True`, `raw_fn`
    itself is called AS `(x, eps_budget)` so an author's `eps_seeking=
    True` solver body can drive its own ladder (09 sec. 3) -- the
    executor calls `wrapped(x, eps_budget)` only for tagged solvers,
    every other (untagged) `SolveFn` keeps its original one-argument
    call untouched."""
    single_output = outputs[0] if len(outputs) == 1 else None

    def wrapped(
        x: Mapping[str, float], eps_budget: Optional[float] = None
    ) -> "Result[SolveOutput, SolveError]":
        raw = raw_fn(x, eps_budget) if eps_seeking else raw_fn(x)
        if isinstance(raw, Result):
            if raw.is_err:
                return raw
            raw = raw.danger_ok
        if isinstance(raw, SolveOutput):
            return Ok(raw)
        if isinstance(raw, Mapping):
            return Ok(SolveOutput(values=dict(raw)))
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            if single_output is None:
                raise TypeError(
                    f"{raw_fn!r} returned a bare float but declares "
                    f"{len(outputs)} outputs {outputs} (F14 requires exactly one)"
                )
            return Ok(SolveOutput(values={single_output: float(raw)}))
        raise TypeError(
            f"{raw_fn!r} returned an unrecognized SolveFn type: {type(raw)!r}"
        )

    wrapped.eps_seeking = eps_seeking  # ty: ignore[unresolved-attribute]
    return wrapped


def invoke_solve_fn(
    fn: SolveFn, x: Mapping[str, float], eps_budget: Optional[float] = None
) -> "Result[SolveOutput, SolveError]":
    """The ONE call-site for invoking a registered `SolveFn` (WO-13, 09
    sec. 3): probes the `.eps_seeking` attribute `wrap_solve_fn` stamps
    to decide whether to also pass `eps_budget` -- every caller
    (`plan/execute.py`'s corner sweep, `calib/harness.py`'s sampling
    loops) goes through this so the branch exists in exactly one place
    (house rule: no duplication). A raw hand-registered `SolveFn` with
    no such attribute (`registry.register(info, fn)` directly,
    `examples/solvers/00_raw_protocol.py`) is called with the original
    one argument, unchanged."""
    if getattr(fn, "eps_seeking", False):
        return fn(x, eps_budget)  # ty: ignore[too-many-positional-arguments]
    return fn(x)


def build_solver_info_and_fn(
    *,
    solver_id: str,
    namespace: str,
    inputs: Iterable[str],
    outputs: Iterable[str],
    domain: Union[Domain, Mapping[str, Any]],
    cost: float,
    accuracy: Union[Accuracy, Mapping[str, Accuracy]],
    citations: Iterable[Union[Citation, str]],
    version: str,
    tier: str = "closed_form",
    settings: Any = None,
    deterministic: bool = True,
    corner_monotone: bool = True,
    conservative_for: Union[ClaimSenses, str] = ClaimSenses.BOTH,
    tags: Iterable[str] = (),
    raw_fn: Callable[..., Any],
    algebraic_form: Optional[str] = None,
    solved_for: Optional[str] = None,
    branch: Optional[str] = None,
    admission_predicate: Optional[str] = None,
    derivation_digest: Optional[str] = None,
    law_lhs: Optional[Any] = None,
    law_rhs: Optional[Any] = None,
    eps_seeking: bool = False,
    cost_curve: Optional[CostCurve] = None,
) -> Tuple[SolverInfo, SolveFn]:
    """The one lowering path from author-facing (sugared or raw)
    arguments to a registered `(SolverInfo, SolveFn)` pair."""
    outputs_tuple = tuple(outputs)
    domain_obj = coerce_domain(domain, tags)
    accuracy_map = coerce_accuracy(accuracy, outputs_tuple)
    citations_tuple = coerce_citations(citations)
    conservative = ClaimSenses.coerce(conservative_for)
    settings_digest_value = _digest.settings_digest(settings)

    info = SolverInfo(
        solver_id=solver_id,
        namespace=namespace,
        version=version,
        inputs=tuple(inputs),
        outputs=outputs_tuple,
        domain=domain_obj,
        cost=cost,
        accuracy=accuracy_map,
        citations=citations_tuple,
        tier=cast(
            Literal["table", "closed_form", "reduced", "discretized", "coupled"], tier
        ),
        deterministic=deterministic,
        corner_monotone=corner_monotone,
        conservative_for=conservative,
        settings_digest=settings_digest_value,
        algebraic_form=algebraic_form,
        solved_for=solved_for,
        branch=branch,
        admission_predicate=admission_predicate,
        derivation_digest=derivation_digest,
        law_lhs=law_lhs,
        law_rhs=law_rhs,
        eps_seeking=eps_seeking,
        cost_curve=cost_curve,
    )
    return info, wrap_solve_fn(raw_fn, outputs_tuple, eps_seeking=eps_seeking)
