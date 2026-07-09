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

__all__ = ["map_engine_error", "margin_exhausted_error"]


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


def margin_exhausted_error(
    model_id: str,
    eps_achieved: float,
    eps_needed: float,
    limit: float,
    error: Any,
) -> DomainError:
    """WO-13 (09 sec. 5): the honest indeterminate for a margin-driven
    refinement that topped out -- STATES eps achieved vs needed (the
    input to regolith's "what would resolve it" diagnostic family,
    regolith/07 sec. 4), plus the underlying engine error, in one
    greppable message. Lives here so the pack's error-message rendering
    stays in its one home (06 "Failures")."""
    return DomainError(
        model_id=model_id,
        message=(
            "margin-driven refinement exhausted: eps achieved "
            f"{eps_achieved!r} vs needed {eps_needed!r} to close the claim "
            f"at limit {limit!r} (engine: {_describe(error)})"
        ),
    )
