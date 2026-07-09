from __future__ import annotations

"""`NoStoreResolver` -- the honest stand-in `PayloadResolver` a pack
model closes the engine's payload-step catalog over when no lithos
resolver reaches `Model.estimate` (WO-14 boundary v2, 06 "digests
resolved through the orchestrator store handle only").

Lithos's D154 (design-log `2026-07-08-cycle-28.md`) settles the other
half of the WO-14 residual this module's docstring used to name as
escalated: `orchestrator.discharge.discharge_one` now threads a real
`PayloadStore`-backed resolver to any `Model.estimate` override that
opts in by naming a keyword-only `resolver` parameter
(`regolith.harness.model._accepts_resolver`). `RegolithResolverAdapter`
below is the pack-side seam that makes use of that: it wraps the
lithos callable (`digest -> Result[bytes, <lithos error>]`, structural-
typed here per FINV-3 -- the callable's error type is never imported)
into feldspar's own `feldspar.solve.payload.PayloadResolver` protocol,
and enforces D154's wire-format contract (a payload ref's bytes ARE the
schema-versioned JSON `regolith._schema` publishes) before handing
bytes onward: a major schema-version mismatch is an honest
indeterminate (`SolveError.ParseFailed`), naming both versions, never a
silent parse of a shape this build does not understand.

A pack model with NO lithos resolver available (an unmodified pre-
D154 discharge caller, or a build with no `PayloadStore` configured)
still gets `NoStoreResolver`: every payload-consuming pack model stays
honestly total, reporting the missing channel as a `SolveError.
ToolMissing` -- the same honest-indeterminate shape a genuinely absent
gmsh/ccx tool reports (06 "Failures"), never a silent success and
never an exception. `store()` is unreachable on both resolvers: the
pack boundary never writes payloads of its own (06 "Boundary rules"),
so a call here is a programmer bug, not a recoverable condition."""

import json
from collections.abc import Callable

from typani.result import Err, Ok, Result

from feldspar.logging_setup import get_logger
from feldspar.solve.errors import SolveError
from feldspar.solve.payload import PayloadRef

_log = get_logger(__name__)

__all__ = ["NoStoreResolver", "RegolithResolverAdapter"]

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


class RegolithResolverAdapter:
    """A `feldspar.solve.payload.PayloadResolver` built over a lithos
    D154 resolver callable (`digest: str -> Result[bytes, <error>]`,
    e.g. `regolith.orchestrator.payload_store.PayloadStore.resolver()`
    as threaded through `Model.discharge`).

    The wrapped callable's error type is deliberately never named here
    (structural typing at the FINV-3 boundary -- this module imports
    nothing from `regolith.orchestrator`): only its shape (a one-arg
    callable returning a typani `Result`) is assumed.

    ``resolve`` enforces D154's wire-format contract before handing
    bytes onward: the resolved bytes must be the schema-versioned JSON
    `regolith._schema` publishes, and a MAJOR schema-version mismatch
    between what the payload declares and what this build understands
    is an honest `SolveError.ParseFailed`, naming both versions -- never
    a silent parse of a shape this build was not built to read."""

    __slots__ = ("_resolve",)

    def __init__(self, resolve: Callable[[str], Result[bytes, object]]) -> None:
        """``resolve`` is the bound lithos handle (a digest -> bytes
        callable); this adapter never does its own storage IO, it only
        wraps that one call."""
        self._resolve = resolve

    def resolve(self, ref: PayloadRef) -> Result[bytes, SolveError]:
        """Resolve ``ref.digest`` through the wrapped lithos callable,
        then check the D154 schema-version envelope before returning
        bytes. A digest the wrapped callable cannot resolve is
        `SolveError.DanglingDigest`; bytes that are not valid JSON, or
        whose declared ``schema_version`` does not match the version
        this build understands (`regolith._schema.SCHEMA_VERSION`), are
        `SolveError.ParseFailed` -- both honest indeterminates, never a
        raised exception."""
        # Deferred import: keeps the regolith dependency confined to the
        # call site that actually needs the published schema version
        # (FINV-3 already permits `feldspar.pack` to import regolith;
        # this stays a plain top-of-function import, not a new module
        # global, so a caller with no regolith installed can still
        # import this module and use `NoStoreResolver` unaffected).
        from regolith._schema import SCHEMA_VERSION as _regolith_schema_version

        got = self._resolve(ref.digest)
        if got.is_err:
            _log.info(
                "RegolithResolverAdapter.resolve: digest=%s kind=%s "
                "unresolved via the lithos resolver: %s",
                ref.digest,
                ref.kind,
                got.danger_err,
            )
            return Err(SolveError.DanglingDigest(digest=ref.digest))

        data = got.danger_ok
        try:
            envelope = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _log.warning(
                "RegolithResolverAdapter.resolve: digest=%s kind=%s bytes "
                "are not valid schema JSON: %s",
                ref.digest,
                ref.kind,
                exc,
            )
            return Err(
                SolveError.ParseFailed(
                    context=(
                        f"payload {ref.digest!r} (kind={ref.kind!r}) is not "
                        f"valid schema JSON: {exc}"
                    )
                )
            )

        declared_version = (
            envelope.get("schema_version") if isinstance(envelope, dict) else None
        )
        if declared_version != _regolith_schema_version:
            _log.warning(
                "RegolithResolverAdapter.resolve: digest=%s kind=%s schema "
                "version mismatch: payload declares schema_version=%r, "
                "this build understands schema_version=%r",
                ref.digest,
                ref.kind,
                declared_version,
                _regolith_schema_version,
            )
            return Err(
                SolveError.ParseFailed(
                    context=(
                        f"payload {ref.digest!r} schema version mismatch: "
                        f"payload declares schema_version={declared_version!r}, "
                        f"this build understands "
                        f"schema_version={_regolith_schema_version!r}"
                    )
                )
            )

        _log.debug(
            "RegolithResolverAdapter.resolve: digest=%s kind=%s OK "
            "(schema_version=%s, %d bytes)",
            ref.digest,
            ref.kind,
            declared_version,
            len(data),
        )
        return Ok(data)

    def store(self, kind: str, content: bytes, origin: str) -> PayloadRef:
        """Never called: the pack boundary never writes payloads of its
        own (06 "Boundary rules") -- a call here is a programmer bug."""
        raise AssertionError(
            "RegolithResolverAdapter.store must never be called: "
            "feldspar's pack boundary never performs its own payload "
            "storage IO"
        )
