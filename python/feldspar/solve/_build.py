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

RawReturn = Union[Result, SolveOutput, Mapping[str, float], float, int]
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


def wrap_solve_fn(raw_fn: Callable[..., Any], outputs: Tuple[str, ...]) -> SolveFn:
    """F13/F14/F16 return normalization: the author-facing return type is
    `Result | SolveOutput | Mapping | float` (float only with exactly one
    output); this wraps it into the strict `SolveFn` protocol
    (`Result[SolveOutput, SolveError]`) every registered solver has.
    Raising remains a programmer bug (F13), same as `Interval`'s direct-
    construction-raises precedent -- never converted into a SolveError
    value here."""
    single_output = outputs[0] if len(outputs) == 1 else None

    def wrapped(x: Mapping[str, float]) -> "Result[SolveOutput, SolveError]":
        raw = raw_fn(x)
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

    return wrapped


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
    )
    return info, wrap_solve_fn(raw_fn, outputs_tuple)
