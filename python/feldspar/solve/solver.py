from __future__ import annotations

"""`SolverInfo`, `Citation`, `ClaimSenses`, `SolveOutput`, `EXACT`, and the
`@solver` decorator -- the registration surface (01-interfaces
`feldspar.solve`, 03).

Module-level `register(registry) -> None` convention (AD-4): a solver-
authoring module builds its `SolverInfo`/`SolveFn` pairs at IMPORT time
(via `@solver`, `make_direction`, `Relation`, `table_solver_1d/2d`, or
`Correlation` -- see `sugar.py`) with NO global registry access, then
exposes a single `register(registry: SolverRegistry) -> None` function
that the catalog loader calls explicitly, in whatever order it likes.
Since nothing touches a shared registry until `register()` runs,
permuting the import/registration order across modules can never change
which solvers exist or their digest (FINV-1/AD-4;
`tests/unit/test_registry.py::test_import_order_permutation_invariant`)."""

from typing import Any, Callable, Optional, Tuple, TypeVar

from feldspar.solve import _build
from feldspar.solve._models import (
    EXACT,
    Citation,
    ClaimSenses,
    SolveOutput,
    SolverInfo,
)

__all__ = [
    "Citation",
    "ClaimSenses",
    "EXACT",
    "SolveFn",
    "SolveOutput",
    "SolverInfo",
    "solver",
]

SolveFn = Callable[[Any], Any]  # Result[SolveOutput, SolveError]

F = TypeVar("F", bound=Callable[..., Any])


def solver(
    *,
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
    solver_id_suffix: Optional[str] = None,
    tags: Any = (),
) -> Callable[[F], F]:
    """Attaches `fn.solver_direction: tuple[SolverInfo, SolveFn]`
    (01-interfaces). `solver_id = f"{namespace}.{fn.__name__}"` (plus
    `.{solver_id_suffix}` if given). NO global state (AD-4): this only
    builds the pair and stashes it on the function object; nothing
    touches a registry until the module's `register(registry)` is
    called. All F10/F11/F13/F14/F15/F16 coercions are already active
    here -- 01_sugar_coercions.py imports this SAME decorator, not a
    separate sugared one (00 and 01 lower to identical SolverInfo
    digests)."""

    def deco(fn: F) -> F:
        solver_id = f"{namespace}.{fn.__name__}"  # ty: ignore[unresolved-attribute]
        if solver_id_suffix:
            solver_id = f"{solver_id}.{solver_id_suffix}"
        info, wrapped = _build.build_solver_info_and_fn(
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
        fn.solver_direction = (info, wrapped)  # ty: ignore[unresolved-attribute]
        return fn

    return deco
