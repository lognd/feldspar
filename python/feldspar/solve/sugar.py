from __future__ import annotations

"""The DX-settled sugar layer (03 "Registration ergonomics";
01-interfaces DX F7-F17): `make_direction`, `Relation`,
`table_solver_1d`/`table_solver_2d`, `Correlation`, `CoupledGroup`.
Every builder here calls the SAME `_build.build_solver_info_and_fn` the
`@solver` decorator uses (`solver.py`) -- there is exactly one lowering
path to the raw protocol, so a sugar-built direction is digest-equal to
its hand-built twin by construction (02-edge-cases WO-03 row)."""

from typing import Any, Callable, Literal, Mapping, Optional, Sequence, Tuple

from typani.result import Err, Ok, Result

from feldspar import _feldspar
from feldspar.core import Accuracy, Interval
from feldspar.logging import get_logger
from feldspar.solve import _build
from feldspar.solve._models import EXACT, ClaimSenses, SolverInfo
from feldspar.solve.digest import canonical_digest
from feldspar.solve.errors import RegistryError, SolveError
from feldspar.solve.solver import SolveFn

_log = get_logger(__name__)

__all__ = [
    "Correlation",
    "CoupledGroup",
    "Relation",
    "make_direction",
    "table_solver_1d",
    "table_solver_2d",
]


def _symbolic_error_from_exc(exc: Exception) -> RegistryError:
    """`_feldspar.SymbolicErrorRaised` -> `RegistryError` (WO-11): the
    Python-boundary re-wrap for `feldspar_core::symbolic::SymbolicError`,
    matching `feldspar/core.py`'s `_domain_violation_from_exc` pattern."""
    variant: str = exc.args[0]
    if variant == "NonInvertible":
        _, variable, reason = exc.args
        return RegistryError.NonInvertible(variable=variable, reason=reason)
    if variant == "MultiBranch":
        _, variable, branches = exc.args
        return RegistryError.MultiBranch(variable=variable, branches=branches)
    if variant == "UnboundablePredicate":
        _, predicate = exc.args
        return RegistryError.UnboundablePredicate(predicate=predicate)
    _, port = exc.args
    return RegistryError.EmptyDomain(port=port)


def make_direction(
    *,
    solver_id: str,
    fn: Callable[..., Any],
    namespace: str,
    inputs: Tuple[str, ...],
    outputs: Tuple[str, ...],
    domain: Any,
    cost: float,
    accuracy: Any,
    citations: Any,
    version: str,
    tier: str = "closed_form",
    settings: Any = None,
    deterministic: bool = True,
    corner_monotone: bool = True,
    conservative_for: "ClaimSenses | str" = ClaimSenses.BOTH,
    tags: Any = (),
) -> Tuple[SolverInfo, SolveFn]:
    """The `@solver` decorator's function-call twin (F9): same
    coercions, same lowering -- for factories that build many near-
    identical solvers (examples/solvers/04_families.py) rather than
    writing each one longhand."""
    return _build.build_solver_info_and_fn(
        solver_id=solver_id,
        namespace=namespace,
        inputs=inputs,
        outputs=outputs,
        domain=domain,
        cost=cost,
        accuracy=accuracy,
        citations=citations,
        version=version,
        tier=tier,
        settings=settings,
        deterministic=deterministic,
        corner_monotone=corner_monotone,
        conservative_for=conservative_for,
        tags=tags,
        raw_fn=fn,
    )


class Relation:
    """Multi-direction physical law builder (F7): shared metadata
    declared once, each direction an explicit small function, ids
    auto-suffixed by the direction function's `__name__`
    (examples/solvers/02_relations.py)."""

    def __init__(
        self,
        *,
        namespace: str,
        ports: Tuple[str, ...],
        domain: Any,
        cost: float,
        version: str,
        citations: Any,
        tags: Any = (),
        tier: str = "closed_form",
        settings: Any = None,
        accuracy: Any = EXACT,
    ) -> None:
        # 01-interfaces' Relation.__init__ doesn't list `accuracy=` (only
        # `.direction()` does) -- but examples/solvers/02_relations.py
        # passes it to the CONSTRUCTOR, applied to every direction that
        # doesn't override it at `.direction()`. The example wins per
        # the house rule; flagged in the WO-03 closing report.
        self._namespace = namespace
        self._ports = tuple(ports)
        self._domain = domain
        self._cost = cost
        self._version = version
        self._citations = citations
        self._tags = tags
        self._tier = tier
        self._settings = settings
        self._default_accuracy = accuracy
        self._directions: list[Tuple[SolverInfo, SolveFn]] = []

    def direction(
        self,
        *,
        solves_for: str,
        inputs: Optional[Tuple[str, ...]] = None,
        accuracy: Any = None,
        domain: Any = None,
        corner_monotone: bool = True,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        if solves_for not in self._ports:
            raise ValueError(
                f"direction solves_for={solves_for!r} is not one of this "
                f"Relation's ports {self._ports}"
            )
        if inputs is not None:
            resolved_inputs = inputs
        else:
            resolved_inputs = tuple(p for p in self._ports if p != solves_for)
        for port in resolved_inputs:
            if port not in self._ports:
                raise ValueError(
                    f"direction input {port!r} is outside this Relation's "
                    f"ports {self._ports}"
                )

        def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
            solver_id = f"{self._namespace}.{fn.__name__}"  # ty: ignore[unresolved-attribute]
            info, wrapped = _build.build_solver_info_and_fn(
                solver_id=solver_id,
                namespace=self._namespace,
                inputs=resolved_inputs,
                outputs=(solves_for,),
                domain=domain if domain is not None else self._domain,
                cost=self._cost,
                accuracy=accuracy if accuracy is not None else self._default_accuracy,
                citations=self._citations,
                version=self._version,
                tier=self._tier,
                settings=self._settings,
                deterministic=True,
                corner_monotone=corner_monotone,
                conservative_for=ClaimSenses.BOTH,
                tags=self._tags,
                raw_fn=fn,
            )
            self._directions.append((info, wrapped))
            return fn

        return deco

    def law(
        self,
        *,
        lhs: Any,
        rhs: Any,
        predicates: Any = (),
        branches: Any = None,
        declared_box: Any = None,
    ) -> "Result[None, RegistryError]":
        """Symbolic direction declaration (WO-11, 11 sec. 1-2): derives
        EVERY invertible target of `lhs == rhs` and appends one
        `(SolverInfo, SolveFn)` per target to `self._directions`, the
        same list `.direction()` populates -- hand-written and derived
        directions coexist under one `Relation`. Non-invertible
        variables simply aren't in `_feldspar.invertible_targets`'s
        result (by construction); if the author wants one anyway, they
        write it by hand via `.direction()` beside this call."""
        targets = _feldspar.invertible_targets(lhs, rhs)
        explicit_predicates = tuple(predicates)
        # `predicate_to_box` needs a declared box side for any port its
        # predicates can't derive a bound for -- the Relation's own
        # declared domain (if box-shaped) already has one for every
        # port, so seed from that and let an explicit `declared_box=`
        # override/extend it.
        box_intervals: dict = dict(
            getattr(_build.coerce_domain(self._domain), "box", {})
        )
        if declared_box is not None:
            for k, v in dict(declared_box).items():
                box_intervals[k] = (
                    v if isinstance(v, Interval) else Interval(float(v[0]), float(v[1]))
                )

        for target in targets:
            branch_choice = branches.get(target) if branches else None
            try:
                rhs_expr, branch_label, admission, form = _feldspar.invert_for(
                    lhs, rhs, target, branch=branch_choice
                )
            except _feldspar.SymbolicErrorRaised as exc:
                return Err(_symbolic_error_from_exc(exc))

            # Only AUTHOR-DECLARED predicates (`predicates=`) feed box
            # derivation (11 sec. 2: dispatch box derived from DECLARED
            # predicates, with an author box for the sides they can't
            # bound). Inversion's own ADMISSION predicates (e.g. a sqrt's
            # `>= 0` range) are frequently multi-variable ratios that
            # `predicate_to_box`'s v1 single-port-affine engine cannot
            # (and must not silently pretend to) bound -- those ride into
            # provenance/`explain()` only (WO-11 "Provenance + explain()"),
            # never into the registered dispatch box. The Relation's own
            # declared domain (or an explicit `domain=` override, not
            # exposed on this path) remains the box when there are no
            # explicit predicates to derive from.
            if explicit_predicates:
                try:
                    domain_obj = _feldspar.predicate_to_box(
                        list(explicit_predicates), dict(box_intervals), set(self._tags)
                    )
                except _feldspar.SymbolicErrorRaised as exc:
                    return Err(_symbolic_error_from_exc(exc))
            else:
                domain_obj = self._domain

            admission_predicate = (
                "; ".join(p.canonical_string() for p in admission) or None
            )
            algebraic_form = form
            derivation_digest = canonical_digest(
                {
                    "canon_version": 1,
                    "form": algebraic_form,
                    "solved_for": target,
                    "branch": branch_label,
                }
            )

            def _make_raw_fn(
                rhs_expr: Any, target: str
            ) -> Callable[[Mapping[str, float]], Any]:
                def raw_fn(
                    inputs: Mapping[str, float],
                ) -> "Result[Mapping[str, float], SolveError]":
                    try:
                        return Ok({target: rhs_expr.eval(dict(inputs))})
                    except _feldspar.EvalErrorRaised as exc:
                        variant = exc.args[0]
                        if variant == "MissingPort":
                            return Err(SolveError.MissingOutput(port=exc.args[1]))
                        return Err(SolveError.NonFinite(port=target))

                return raw_fn

            inputs_tuple = tuple(p for p in self._ports if p != target)
            solver_id = f"{self._namespace}.solve_{target}"
            info, wrapped = _build.build_solver_info_and_fn(
                solver_id=solver_id,
                namespace=self._namespace,
                inputs=inputs_tuple,
                outputs=(target,),
                domain=domain_obj,
                cost=self._cost,
                accuracy=self._default_accuracy,
                citations=self._citations,
                version=self._version,
                tier=self._tier,
                settings=self._settings,
                raw_fn=_make_raw_fn(rhs_expr, target),
                algebraic_form=algebraic_form,
                solved_for=target,
                branch=branch_label,
                admission_predicate=admission_predicate,
                derivation_digest=derivation_digest,
            )
            self._directions.append((info, wrapped))

        return Ok(None)

    def register(self, registry: Any) -> "Result[None, RegistryError]":
        for info, fn in self._directions:
            result = registry.register(info, fn)
            if result.is_err:
                return result
        return Ok(None)


def _check_strictly_ascending(x: Sequence[float]) -> None:
    for a, b in zip(x, x[1:], strict=False):
        if not (a < b):
            # Like Interval's direct-construction-raises precedent: bad
            # LITERAL table data handed by the author is a programmer
            # bug, caught immediately -- not a routed RegistryError.
            # RegistryError.BadTable exists (and is directly
            # constructible/testable) for the registry-facing shape of
            # this same failure per 01-interfaces/02-edge-cases; it
            # cannot be threaded through here without breaking
            # table_solver_1d's bare-tuple return contract that
            # examples/solvers/03_tables_correlations.py's
            # `registry.register(*sat_water)` relies on.
            raise ValueError(f"table x values must be strictly ascending, got {x!r}")


def table_solver_1d(
    *,
    namespace: str,
    x_port: str,
    y_port: str,
    x: Sequence[float],
    y: Sequence[float],
    method: Literal["linear", "pchip"],
    eps_abs: float,
    citations: Any,
    version: str,
    cost: float = 1e-6,
) -> Tuple[SolverInfo, SolveFn]:
    """Table lookup (F8): the domain box IS the table extent; `eps_abs`
    is EXPLICIT AND CITED, never auto-derived (an auto-derived bound
    would claim knowledge of unsampled data)."""
    xs = tuple(float(v) for v in x)
    ys = tuple(float(v) for v in y)
    _check_strictly_ascending(xs)
    if len(xs) != len(ys):
        raise ValueError(
            f"table x and y must be the same length, got {len(xs)} and {len(ys)}"
        )

    def _interp_linear(v: float) -> float:
        if v <= xs[0]:
            return ys[0]
        if v >= xs[-1]:
            return ys[-1]
        for i in range(1, len(xs)):
            if v <= xs[i]:
                t = (v - xs[i - 1]) / (xs[i] - xs[i - 1])
                return ys[i - 1] + t * (ys[i] - ys[i - 1])
        return ys[-1]  # pragma: no cover -- unreachable, xs[-1] caught above

    def fn(inputs: Any) -> Any:
        # WO-07+ swaps in a real pchip spline; linear is the M1 floor
        # for both methods (still corner-monotone, still cited eps_abs).
        return {y_port: _interp_linear(inputs[x_port])}

    return make_direction(
        solver_id=f"{namespace}.{y_port.rsplit('.', 1)[-1]}_table",
        fn=fn,
        namespace=namespace,
        inputs=(x_port,),
        outputs=(y_port,),
        domain={x_port: (xs[0], xs[-1])},
        cost=cost,
        accuracy=Accuracy(eps_abs, 0.0),
        citations=citations,
        version=version,
        tier="table",
    )


def table_solver_2d(
    *,
    namespace: str,
    x_port: str,
    y_port: str,
    z_port: str,
    x: Sequence[float],
    y: Sequence[float],
    z: Sequence[Sequence[float]],
    method: Literal["linear", "pchip"],
    eps_abs: float,
    citations: Any,
    version: str,
    cost: float = 1e-6,
) -> Tuple[SolverInfo, SolveFn]:
    """`table_solver_1d` mirrors (01-interfaces): a bilinear lookup over
    a `z[len(x)][len(y)]` grid; domain box is the (x, y) extent."""
    xs = tuple(float(v) for v in x)
    ys = tuple(float(v) for v in y)
    _check_strictly_ascending(xs)
    _check_strictly_ascending(ys)
    grid = tuple(tuple(float(v) for v in row) for row in z)
    if len(grid) != len(xs) or any(len(row) != len(ys) for row in grid):
        raise ValueError("table z must be shaped [len(x)][len(y)]")

    def _clamp_index(v: float, axis: Tuple[float, ...]) -> int:
        if v <= axis[0]:
            return 0
        if v >= axis[-1]:
            return len(axis) - 2
        for i in range(1, len(axis)):
            if v <= axis[i]:
                return i - 1
        return len(axis) - 2  # pragma: no cover -- unreachable

    def fn(inputs: Any) -> Any:
        xv, yv = inputs[x_port], inputs[y_port]
        i = _clamp_index(xv, xs)
        j = _clamp_index(yv, ys)
        tx = 0.0 if xs[i + 1] == xs[i] else (xv - xs[i]) / (xs[i + 1] - xs[i])
        ty = 0.0 if ys[j + 1] == ys[j] else (yv - ys[j]) / (ys[j + 1] - ys[j])
        z00, z01 = grid[i][j], grid[i][j + 1]
        z10, z11 = grid[i + 1][j], grid[i + 1][j + 1]
        z0 = z00 + ty * (z01 - z00)
        z1 = z10 + ty * (z11 - z10)
        return {z_port: z0 + tx * (z1 - z0)}

    return make_direction(
        solver_id=f"{namespace}.{z_port.rsplit('.', 1)[-1]}_table",
        fn=fn,
        namespace=namespace,
        inputs=(x_port, y_port),
        outputs=(z_port,),
        domain={x_port: (xs[0], xs[-1]), y_port: (ys[0], ys[-1])},
        cost=cost,
        accuracy=Accuracy(eps_abs, 0.0),
        citations=citations,
        version=version,
        tier="table",
    )


class Correlation:
    """Published formula + validity box + accuracy band + citation as
    ONE object (F8) -- the literature ships these four together, and
    splitting them across decorator arguments is where transcription
    errors live (examples/solvers/03_tables_correlations.py)."""

    def __init__(
        self,
        *,
        namespace: str,
        inputs: Tuple[str, ...],
        output: str,
        domain: Any,
        accuracy_rel: float,
        citations: Any,
        version: str,
        cost: float = 1e-6,
        tags: Any = (),
    ) -> None:
        if accuracy_rel <= 0:
            raise ValueError(
                f"Correlation accuracy_rel must be > 0, got {accuracy_rel}"
            )
        self._namespace = namespace
        self._inputs = tuple(inputs)
        self._output = output
        self._domain = domain
        self._accuracy_rel = accuracy_rel
        self._citations = citations
        self._version = version
        self._cost = cost
        self._tags = tags
        self._built: Optional[Tuple[SolverInfo, SolveFn]] = None

    def formula(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        solver_id = f"{self._namespace}.{fn.__name__.lstrip('_')}"  # ty: ignore[unresolved-attribute]
        self._built = _build.build_solver_info_and_fn(
            solver_id=solver_id,
            namespace=self._namespace,
            inputs=self._inputs,
            outputs=(self._output,),
            domain=self._domain,
            cost=self._cost,
            accuracy=Accuracy(0.0, self._accuracy_rel),
            citations=self._citations,
            version=self._version,
            tier="closed_form",
            tags=self._tags,
            raw_fn=fn,
        )
        return fn

    def register(self, registry: Any) -> "Result[None, RegistryError]":
        if self._built is None:
            raise RuntimeError(
                "Correlation.formula(...) must decorate a function before register()"
            )
        return registry.register(*self._built)


class CoupledGroup:
    """Strong two-way coupling as ONE composite solver (09 sec. 4b, M8;
    examples/solvers/06_coupled_groups.py). The planner sees a single
    composite `SolverInfo` (`tier="coupled"`) over the group's boundary
    ports; the internal member cycle never appears in the graph.

    M8 TARGET SHAPE ONLY -- frozen here per WO-03 so the example is
    importable and the interface is settled, but the fixed-point closure
    itself (damped iteration, convergence/`NoConvergence`, the realized
    eps charge) is WO-08+/M8 work. Calling the composite solver in M1
    raises `NotImplementedError`; `register()` still performs the real
    registry-level checks (citations, cost, ports, EXACT-forbidden)."""

    def __init__(
        self,
        *,
        group_id: str,
        namespace: str,
        members: Tuple[str, ...],
        boundary_inputs: Tuple[str, ...],
        boundary_outputs: Tuple[str, ...],
        closure: str,
        settings: Any,
        accuracy: Accuracy,
        citations: Any,
        conservative_for: "ClaimSenses | str" = ClaimSenses.BOTH,
        cost: float,
        version: str,
    ) -> None:
        if accuracy == EXACT:
            raise ValueError("CoupledGroup accuracy must not be EXACT (09 sec. 4b)")
        self._group_id = group_id
        self._namespace = namespace
        self._members = members
        self._boundary_inputs = boundary_inputs
        self._boundary_outputs = boundary_outputs
        self._closure = closure
        self._settings = settings
        self._accuracy = accuracy
        self._citations = citations
        self._conservative_for = conservative_for
        self._cost = cost
        self._version = version

    def _not_implemented_closure(self, x: Any) -> Any:
        raise NotImplementedError(
            f"CoupledGroup {self._group_id!r} closure ({self._closure}) lands in "
            "WO-08+/M8; this is the frozen M1 interface shape only (09 sec. 4b)"
        )

    def register(self, registry: Any) -> "Result[None, RegistryError]":
        info, _fn = _build.build_solver_info_and_fn(
            solver_id=self._group_id,
            namespace=self._namespace,
            inputs=self._boundary_inputs,
            outputs=self._boundary_outputs,
            domain={},
            cost=self._cost,
            accuracy=self._accuracy,
            citations=self._citations,
            version=self._version,
            tier="coupled",
            settings=self._settings,
            conservative_for=self._conservative_for,
            raw_fn=self._not_implemented_closure,
        )
        _log.info(
            "registering coupled group %s (members=%s, closure=%s)",
            self._group_id,
            self._members,
            self._closure,
        )
        return registry.register(info, _fn)
