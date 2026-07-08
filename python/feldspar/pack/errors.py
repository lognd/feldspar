from __future__ import annotations

"""The ONE feldspar-error -> regolith-error mapping (06 "Failures").

Every `feldspar.solve.errors.SolveError` variant (and, since the pack's
`estimate()` calls the full `feldspar.plan.solve.solve()` facade, every
`feldspar.plan.errors.PlanError` variant too) maps to a regolith
`DomainError` carrying the original message embedded -- honest
indeterminate, never a silent wrong answer, never an exception. This is
the ONE function that does that mapping (no scattered ad hoc mapping,
06 "Failures")."""

from typing import Any

from regolith.harness.errors import DomainError

__all__ = ["map_engine_error"]


def _describe(error: Any) -> str:
    """A greppable `Kind(field=value, ...)` rendering of a `_TaggedError`.

    `SolveError`/`PlanError` share the `_TaggedError` base (`kind` +
    keyword fields); this renders both uniformly without importing
    either concrete union (keeps this module error-shape-agnostic)."""
    kind = getattr(error, "kind", type(error).__name__)
    fields = getattr(error, "_fields", None)
    if fields:
        rendered = ", ".join(f"{k}={v!r}" for k, v in fields.items())
        return f"{kind}({rendered})"
    return f"{kind}({error!r})"


def map_engine_error(model_id: str, error: Any) -> DomainError:
    """Any feldspar `SolveError`/`PlanError` value -> a regolith `DomainError`.

    Unmapped/uncertain cases (every variant lands here -- there is no
    per-variant special case) are honest indeterminate: the caller's
    `Model.estimate` returns `Err(DomainError(...))`, which
    `Model.discharge` turns into `indeterminate` evidence, never a pass
    and never a raised exception (06 "Failures")."""
    return DomainError(
        model_id=model_id,
        message=f"feldspar engine failure: {_describe(error)}",
    )
