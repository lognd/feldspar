from __future__ import annotations

"""Payload ports (WO-12, 09 sec. 4): the content-addressed, exact-by-
reference value carried by a `PortDecl` whose `Rank` is `Rank.payload(kind)`.

`PAYLOAD_KINDS` is the ONE place the kind vocabulary lives on the Python
side (the tripwire in CLAUDE.md is about extension strings, not payload
kinds, but the same "single home" discipline applies here per 09 sec. 4:
the table is quoted VERBATIM from spec and nowhere else). A payload
VALUE (`PayloadRef`) is `{kind, digest, origin}`: exact by reference, so
its digest folds into a request/solve digest as just that ref (no store
IO happens in feldspar -- `PayloadResolver` is the orchestrator-provided
seam a pack model calls through, per the D96/OPEN-2 contract)."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator
from typani.result import Result

from feldspar.core import DomainViolation
from feldspar.logging_setup import get_logger
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = [
    "PAYLOAD_KINDS",
    "PayloadRef",
    "PayloadResolver",
    "payload_feature_violation",
    "resolver_cache_identity",
]

#: The 09 sec. 4 payload-kind table, VERBATIM (single home on the Python
#: side; the Rust `Rank::Payload(String)` carries the same strings but
#: does not enumerate them -- kind values are opaque to the core, only
#: this module's callers (registration code, the mesh/geometry solver
#: directions) are expected to draw from this set).
PAYLOAD_KINDS = frozenset(
    {
        "geometry.parametric",
        "geometry.realized",
        "layout.realized",
        "mesh",
        "table",
        "spectrum",
        "profile",
        "mask",
        "field",
        "flownet",
        "plan",
        "frame",
    }
)


class PayloadRef(BaseModel):
    """A payload PORT VALUE: `{kind, digest, origin}` (09 sec. 4). Exact
    by reference -- uncertainty never propagates through a payload, so
    this carries no interval/eps of its own. `digest` is the content
    address (opaque to feldspar: whatever the orchestrator's store hands
    back); `origin` is a free-form provenance string (e.g. a lowering
    step name or upstream solver_id) kept for `explain()`/audit
    rendering, not interpreted here."""

    model_config = ConfigDict(frozen=True)

    kind: str
    digest: str
    origin: str = ""

    @field_validator("kind")
    @classmethod
    def _kind_is_known(cls, value: str) -> str:
        if value not in PAYLOAD_KINDS:
            _log.warning("PayloadRef constructed with unknown kind %r", value)
            raise ValueError(
                f"unknown payload kind {value!r}; must be one of "
                f"{sorted(PAYLOAD_KINDS)} (09 sec. 4)"
            )
        return value


@runtime_checkable
class PayloadResolver(Protocol):
    """The orchestrator-provided resolver handle (D96/OPEN-2): feldspar
    never performs store IO itself (09 sec. 4 "no store IO in
    feldspar"), so any solver direction that needs a payload's actual
    bytes calls through an object shaped like this one, supplied by the
    caller (the pack/executor boundary), never a feldspar-owned global.
    """

    def resolve(self, ref: PayloadRef) -> "Result[bytes, SolveError]":
        """Look up `ref.digest`'s content; `Err(SolveError.DanglingDigest)`
        if the store has no entry for that hash (02-edge-cases WO-12
        rows)."""
        ...

    def store(self, kind: str, content: bytes, origin: str) -> PayloadRef:
        """Deposit `content` and return its content-addressed ref (the
        store computes the digest -- feldspar never re-derives it, so
        the hash discipline has exactly one home, the orchestrator's
        store). Infallible by contract: a store that cannot accept
        writes is an orchestrator-environment bug, not a solve-time
        error value."""
        ...


def resolver_cache_identity(resolver: "PayloadResolver") -> str:
    """The honest cache-key marker for which `PayloadResolver`
    IMPLEMENTATION a payload-consuming solver was built over (bug fix,
    integration cycle-35: WO-118). A payload's digest already IS its
    identity (FINV-12), so two resolvers handed the SAME digest must
    agree on its bytes for a content-addressed store to be coherent at
    all -- but a resolver that cannot reach a store yet (the pack
    boundary's `NoStoreResolver` stand-in, D154) and one that CAN
    (a real orchestrator-backed adapter) turn the exact same request +
    payload digest into different outcomes: an honest `Err` versus a
    real `Ok` prediction. `SolveCache`'s freshness argument
    (`cache.py` module docstring) only holds if the key is a pure
    function of everything the answer depends on -- and the answer
    depends on WHICH resolver kind is bound, not just the payload
    digest. `type(resolver).__name__` is a stable, no-import marker any
    registration site can fold into its `SolverInfo.settings_digest`
    (`solve/_build.py`'s `settings=` seam) without this module (or any
    caller) depending on where concrete resolver implementations live
    (`feldspar.pack.payload_bridge`, test fixtures, etc.) -- keeping the
    resolver-registry direction one-way (registry/solve never imports
    pack)."""
    return type(resolver).__name__


def payload_feature_violation(port: str, feature: str) -> DomainViolation:
    """The 09 sec. 4a execution-time domain check's violation value: an
    abstraction edge whose domain is over payload FEATURES ("no hole
    within the root band") reports the offending port and the named
    feature through the same `DomainViolation` shape scalar box checks
    use, so `SolveError.OutOfDomain(violation)` needs no payload-special
    variant and the fallback reroute (04) treats both identically."""
    _log.info("payload feature violation: port=%s feature=%s", port, feature)
    return DomainViolation(kind="PayloadFeature", port=port, tag=feature)
