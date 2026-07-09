from __future__ import annotations

"""RegistryError, SolveError -- the TOTAL error unions of 03/04
(01-interfaces, FINV-5). Neither fits typani's `ErrorSet` (a flat
string-valued `Enum`): most `RegistryError` variants are flat, but
`BadTable` carries a `reason`, and every `SolveError` variant carries a
payload (`ToolMissing(tool, guidance)`, `OutOfDomain(violation)`, ...).
So both are small tagged value classes -- the same pattern
`feldspar.core.DomainViolation` uses for the one core error that also
needs a payload -- built on one shared `_TaggedError` base here so the
kind/fields/eq/hash/repr machinery has exactly one home (house rule:
no duplication)."""

from typing import Any, Dict, Optional


class _TaggedError:
    """Base for a small closed set of named, optionally-payload-carrying
    error variants -- constructed via the per-variant classmethods on
    the subclass, never directly."""

    __slots__ = ("kind", "_fields")

    def __init__(self, kind: str, **fields: Any) -> None:
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "_fields", fields)

    def __getattr__(self, name: str) -> Any:
        fields: Dict[str, Any] = object.__getattribute__(self, "_fields")
        try:
            return fields[name]
        except KeyError:
            raise AttributeError(name) from None

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return self.kind == other.kind and self._fields == other._fields  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return hash((type(self), self.kind, tuple(sorted(self._fields.items()))))

    def __repr__(self) -> str:
        args = ", ".join(f"{k}={v!r}" for k, v in self._fields.items())
        return f"{type(self).__name__}.{self.kind}({args})"


class RegistryError(_TaggedError):
    """`SolverRegistry` registration failures (01-interfaces
    `RegistryError`); every variant below is reachable via
    `tests/unit/test_registry.py`."""

    @classmethod
    def DuplicateSolverId(cls, solver_id: str) -> "RegistryError":
        return cls("DuplicateSolverId", solver_id=solver_id)

    @classmethod
    def PortUnitConflict(cls, port: str) -> "RegistryError":
        return cls("PortUnitConflict", port=port)

    @classmethod
    def PortRankConflict(cls, port: str) -> "RegistryError":
        return cls("PortRankConflict", port=port)

    @classmethod
    def UnknownPort(cls, port: str) -> "RegistryError":
        return cls("UnknownPort", port=port)

    @classmethod
    def DuplicatePortDecl(cls, port: str) -> "RegistryError":
        return cls("DuplicatePortDecl", port=port)

    @classmethod
    def EmptyCitations(cls, solver_id: str) -> "RegistryError":
        return cls("EmptyCitations", solver_id=solver_id)

    @classmethod
    def NonPositiveCost(cls, solver_id: str) -> "RegistryError":
        return cls("NonPositiveCost", solver_id=solver_id)

    @classmethod
    def AccuracyOutputMismatch(cls, solver_id: str) -> "RegistryError":
        return cls("AccuracyOutputMismatch", solver_id=solver_id)

    @classmethod
    def Frozen(cls) -> "RegistryError":
        return cls("Frozen")

    @classmethod
    def BadTable(cls, reason: str) -> "RegistryError":
        return cls("BadTable", reason=reason)

    # Payload-port declaration failures (WO-12, 09 sec. 4): kind
    # checking at registration mirrors unit checking, so these two are
    # the payload twins of `PortUnitConflict`/`UnknownPort`.

    @classmethod
    def PayloadKindConflict(cls, port: str) -> "RegistryError":
        """Two declarations of the same port name with DIFFERENT payload
        kinds (e.g. `mesh` vs `spectrum`) -- the 09 sec. 4 registration
        error, same shape as a unit mismatch."""
        return cls("PayloadKindConflict", port=port)

    @classmethod
    def UnknownPayloadKind(cls, port: str, payload_kind: str) -> "RegistryError":
        """A payload-rank declaration whose kind string is not in the
        09 sec. 4 table (`feldspar.solve.PAYLOAD_KINDS`, the single
        vocabulary home)."""
        return cls("UnknownPayloadKind", port=port, payload_kind=payload_kind)

    # Symbolic declaration-time failures (WO-11, `Relation.law`):
    # `_feldspar.SymbolicErrorRaised` gets caught and re-wrapped into
    # one of these four variants at the Python boundary, matching
    # `feldspar_core::symbolic::SymbolicError`'s own four variants
    # (crates/feldspar-py/src/errors.rs `symbolic_error_to_py`).

    @classmethod
    def NonInvertible(cls, variable: str, reason: str) -> "RegistryError":
        return cls("NonInvertible", variable=variable, reason=reason)

    @classmethod
    def MultiBranch(cls, variable: str, branches: Any) -> "RegistryError":
        return cls("MultiBranch", variable=variable, branches=branches)

    @classmethod
    def UnboundablePredicate(cls, predicate: str) -> "RegistryError":
        return cls("UnboundablePredicate", predicate=predicate)

    @classmethod
    def EmptyDomain(cls, port: str) -> "RegistryError":
        return cls("EmptyDomain", port=port)


class SolveError(_TaggedError):
    """Solve/execution failures (01-interfaces `SolveError`); the
    executor (WO-04/WO-06) is what actually raises most of these --
    WO-03 only needs the union to exist and be total (FINV-5).
    `NoConvergence` (WO-18, 09 sec. 4b) is `CoupledGroup`'s honest
    indeterminate: the damped fixed-point closure ran its declared
    `max_iter` without the residual dropping under `tol` -- a value,
    like every other variant here, so fallback rerouting (04) applies
    unchanged."""

    @classmethod
    def ToolMissing(cls, tool: str, guidance: str) -> "SolveError":
        return cls("ToolMissing", tool=tool, guidance=guidance)

    @classmethod
    def ToolFailed(cls, tool: str, log_tail: str) -> "SolveError":
        return cls("ToolFailed", tool=tool, log_tail=log_tail)

    @classmethod
    def Timeout(cls, tool: str, seconds: float) -> "SolveError":
        return cls("Timeout", tool=tool, seconds=seconds)

    @classmethod
    def ParseFailed(cls, context: str) -> "SolveError":
        return cls("ParseFailed", context=context)

    @classmethod
    def OutOfDomain(cls, violation: Any) -> "SolveError":
        return cls("OutOfDomain", violation=violation)

    @classmethod
    def NonFinite(cls, port: str) -> "SolveError":
        return cls("NonFinite", port=port)

    @classmethod
    def MissingOutput(cls, port: str) -> "SolveError":
        return cls("MissingOutput", port=port)

    @classmethod
    def InvalidMeasurement(cls, reason: str) -> "SolveError":
        return cls("InvalidMeasurement", reason=reason)

    @classmethod
    def BudgetExceeded(cls, realized: float, budget: float) -> "SolveError":
        return cls("BudgetExceeded", realized=realized, budget=budget)

    @classmethod
    def NoRouteRemaining(cls, attempts: Any) -> "SolveError":
        return cls("NoRouteRemaining", attempts=attempts)

    @classmethod
    def PayloadKindMismatch(
        cls, port: str, expected_kind: str, actual_kind: str
    ) -> "SolveError":
        """WO-12 (09 sec. 4): a payload value arrived at `port` whose
        `kind` does not match the port's declared payload kind. This is
        the EXECUTION-time twin of `RegistryError.PortRankConflict` --
        registration already rejects two SOLVERS declaring the same port
        name with different payload kinds, but a caller can still hand a
        wrong-kind `PayloadRef` value to a correctly-registered port at
        solve time, and that is this variant's job to catch."""
        return cls(
            "PayloadKindMismatch",
            port=port,
            expected_kind=expected_kind,
            actual_kind=actual_kind,
        )

    @classmethod
    def MissingPayload(cls, port: str) -> "SolveError":
        """WO-12 (09 sec. 4, 02-edge-cases): a payload port had no value
        at all where one was required."""
        return cls("MissingPayload", port=port)

    @classmethod
    def LadderExhausted(
        cls, best_eps: float, budget: Optional[float], rungs_tried: int
    ) -> "SolveError":
        """WO-13 (09 sec. 3): a budget-seeking solver's refinement
        ladder ran out of declared rungs without meeting the caller's
        remaining eps budget. Honest indeterminate carrying the best
        eps actually achieved (feeds regolith's "what would resolve it"
        diagnostic family, regolith/07 sec. 4) -- never a silent
        downgrade to the last rung's eps as if it had met budget.
        `budget` is `Optional` only for the type signature's sake (a
        real exhaustion always has a concrete `eps_budget`, since
        `climb_richardson_ladder` never seeks past the first pair when
        no budget is given)."""
        return cls(
            "LadderExhausted",
            best_eps=best_eps,
            budget=budget,
            rungs_tried=rungs_tried,
        )

    @classmethod
    def NoConvergence(cls, iterations: int, residual: float) -> "SolveError":
        """WO-18 (09 sec. 4b): a `CoupledGroup`'s damped fixed-point
        closure exhausted `settings["max_iter"]` iterations without
        `residual` (the largest relative change between the last two
        iterates) dropping under `settings["tol"]`. `iterations` is
        always the group's declared `max_iter` -- a real exhaustion,
        never a partial count -- matching `LadderExhausted`'s honest-
        indeterminate shape."""
        return cls("NoConvergence", iterations=iterations, residual=residual)

    @classmethod
    def DanglingDigest(cls, digest: str) -> "SolveError":
        """WO-12 (09 sec. 4, 02-edge-cases): a `PayloadRef.digest` that
        the orchestrator-provided `PayloadResolver` could not find any
        content for (a payload in a digest is its hash, per 09 sec. 4 --
        but the store behind that hash is not feldspar's to guarantee)."""
        return cls("DanglingDigest", digest=digest)
