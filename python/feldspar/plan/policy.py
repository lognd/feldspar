from __future__ import annotations

"""`RoutePolicy` -- solve-time behavior toggles (01-interfaces
`feldspar.plan`, WO-06, 04-routing "Fallback rerouting"/"Solve cache").
`threads` is honored SERIALLY until M5 parallel execution lands (09
sec. 6): the only valid value in v1 is `1`; anything else is a
request-validation error caught at construction, not at solve time."""

from pydantic import BaseModel, ConfigDict, field_validator

__all__ = ["RoutePolicy"]


# frob:doc docs/modules/plan.md#plan_policy
class RoutePolicy(BaseModel):
    """`fallback` (default reroute-on-failure, 04), `cache` (default ON
    content-addressed solve cache, AD-9), `threads` (M5 stub, value 1
    only in v1)."""

    model_config = ConfigDict(frozen=True)

    fallback: bool = True
    cache: bool = True
    threads: int = 1

    @field_validator("threads")
    @classmethod
    def _threads_is_one(cls, value: int) -> int:
        if value != 1:
            raise ValueError(
                f"RoutePolicy.threads must be 1 in v1 (parallel execution is "
                f"M5, 09 sec. 6); got {value!r}"
            )
        return value
