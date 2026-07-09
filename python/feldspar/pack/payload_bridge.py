from __future__ import annotations

"""`NoStoreResolver` -- the honest stand-in `PayloadResolver` a pack
model closes the engine's payload-step catalog over until regolith
threads an orchestrator payload-store handle down its discharge path
to `Model.estimate` (WO-14 boundary v2, 06 "digests resolved through
the orchestrator store handle only").

As of this WO, `regolith.orchestrator.discharge.discharge_one` never
passes a store/resolver into `Model.discharge`/`Model.estimate`
(escalated in the WO-14 close-out, not a feldspar-side gap: the D96
channel's TYPE (`DischargeRequest.payloads`) landed with WO-30, but the
resolver-threading half of D96 has not). Every payload-consuming pack
model built against this resolver is therefore honestly total: a
matched request with a payload present ALWAYS reaches this resolver's
`resolve()`, which reports the missing channel as a `SolveError.
ToolMissing` -- the same honest-indeterminate shape a genuinely absent
gmsh/ccx tool reports (06 "Failures"), never a silent success and
never an exception. `store()` is unreachable on this path: the pack
boundary never writes payloads of its own (06 "Boundary rules"), so a
call here is a programmer bug, not a recoverable condition."""

from typani.result import Err, Result

from feldspar.logging_setup import get_logger
from feldspar.solve.errors import SolveError
from feldspar.solve.payload import PayloadRef

_log = get_logger(__name__)

__all__ = ["NoStoreResolver"]

_GUIDANCE = (
    "the D96 payload channel is not yet threaded from regolith's "
    "discharge path to Model.estimate (WO-14 escalated residual); "
    "resolving this digest requires an orchestrator PayloadStore "
    "handle that Model.estimate does not receive yet."
)


class NoStoreResolver:
    """A `feldspar.solve.payload.PayloadResolver` that always reports the
    missing orchestrator-store channel, honestly, for every digest."""

    def resolve(self, ref: PayloadRef) -> Result[bytes, SolveError]:
        """Always `Err(SolveError.ToolMissing(...))`: there is no bytes
        store reachable from this resolver (see module docstring)."""
        _log.info(
            "NoStoreResolver.resolve: digest=%s kind=%s -- no orchestrator "
            "store handle reaches Model.estimate yet",
            ref.digest,
            ref.kind,
        )
        return Err(
            SolveError.ToolMissing(
                tool="regolith.orchestrator.payload_store", guidance=_GUIDANCE
            )
        )

    def store(self, kind: str, content: bytes, origin: str) -> PayloadRef:
        """Never called: the pack boundary never writes payloads of its
        own (06 "Boundary rules") -- a call here is a programmer bug."""
        raise AssertionError(
            "NoStoreResolver.store must never be called: feldspar's pack "
            "boundary never performs its own payload storage IO"
        )
