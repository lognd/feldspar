from __future__ import annotations

"""Richardson extrapolation over mesh refinements for measured_eps (05). WO-08."""

from pydantic import BaseModel, ConfigDict

from feldspar.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "RichardsonResult",
    "richardson_extrapolate",
    "THEORETICAL_ORDER",
    "SAFETY_FACTOR",
]

# Theoretical (not empirically measured) convergence order for the
# quadratic element formulations used across the FEA tier (C3D20, CAX8):
# quadratic shape functions give O(h^2) convergence for displacement/stress
# recovery in CalculiX's isoparametric elements (see the CalculiX Theory
# Manual, section on element interpolation order). With only two mesh
# levels (h, h/2) the order cannot be empirically measured -- that needs
# at least three points -- so this is a fixed, cited constant, not a
# per-call estimate.
THEORETICAL_ORDER = 2.0

# Conservative inflation factor applied to the extrapolation correction
# to form the reported eps in the normal (non-fallback) path. This is a
# chosen conservative margin, not evidence-derived; it can be revisited
# once real ccx/gmsh runs are available to calibrate against.
SAFETY_FACTOR = 1.5


class RichardsonResult(BaseModel):  # frozen
    """Outcome of a two-mesh Richardson extrapolation: value, order used,
    conservative eps, and whether the safe fallback fired."""

    model_config = ConfigDict(frozen=True)

    extrapolated: float
    order_used: float
    eps: float
    fallback_used: bool


def richardson_extrapolate(
    value_h: float,
    value_h2: float,
    order: float = THEORETICAL_ORDER,
    safety_factor: float = SAFETY_FACTOR,
) -> RichardsonResult:
    """Extrapolate a coarse/fine mesh pair (h, h/2) to a refined value
    with a conservative error estimate.

    Design rationale (see docs/spec/05-fea-pipeline.md, "richardson.py"):
    with exactly two mesh levels the convergence order cannot be
    empirically measured (three points are required for that); `order`
    is therefore always the FIXED THEORETICAL order for the element
    formulation in use (THEORETICAL_ORDER=2.0 for the quadratic C3D20/
    CAX8 elements), passed in by the caller, never fit from the data.

    Normal path: apply the standard two-point Richardson formula

        extrapolated = value_h2 + (value_h2 - value_h) / (2**order - 1)

    and report a CONSERVATIVE eps by inflating the extrapolation
    correction by `safety_factor`:

        eps = safety_factor * abs(extrapolated - value_h2)

    Fallback trigger (implausibility guard): if the extrapolation
    correction is LARGER in magnitude than the raw coarse-fine delta
    itself, i.e.

        abs(extrapolated - value_h2) > abs(value_h2 - value_h)

    then the assumed theoretical order is producing a less-conservative,
    not more-refined, estimate for this particular pair (e.g. because the
    pair is non-monotone or nearly degenerate, value_h2 ~= value_h). In
    that case we do NOT trust the extrapolation: we report the finer
    mesh's own value unchanged (`extrapolated = value_h2`) and set
    `eps = abs(value_h2 - value_h)` -- the raw delta, with no division --
    which is strictly larger (more conservative) than the extrapolated
    eps would have been. This matches the documented invariant: fall
    back to conservatism, not optimism, whenever the pair is non-monotone
    or the fixed order is implausible for this data.
    """
    raw_delta = abs(value_h2 - value_h)
    correction = (value_h2 - value_h) / (2.0**order - 1.0)
    extrapolated = value_h2 + correction

    if abs(extrapolated - value_h2) > raw_delta:
        _log.warning(
            "richardson_extrapolate: fallback triggered (correction=%r exceeds "
            "raw_delta=%r for value_h=%r, value_h2=%r, order=%r) -- reporting "
            "conservative coarse-fine delta instead of extrapolated value",
            correction,
            raw_delta,
            value_h,
            value_h2,
            order,
        )
        return RichardsonResult(
            extrapolated=value_h2,
            order_used=order,
            eps=raw_delta,
            fallback_used=True,
        )

    eps = safety_factor * abs(extrapolated - value_h2)
    _log.debug(
        "richardson_extrapolate: normal path (value_h=%r, value_h2=%r, order=%r) "
        "-> extrapolated=%r, eps=%r",
        value_h,
        value_h2,
        order,
        extrapolated,
        eps,
    )
    return RichardsonResult(
        extrapolated=extrapolated,
        order_used=order,
        eps=eps,
        fallback_used=False,
    )
