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

from typing import Any, Dict


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
    `NoConvergence` is reserved for M8 coupled groups (09 sec. 4b) and
    intentionally has no constructor yet."""

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
