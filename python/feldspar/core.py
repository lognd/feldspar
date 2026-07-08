from __future__ import annotations

"""feldspar.core: the Rust-backed quantity core (01-interfaces
`feldspar.core`; WO-02). The frozen classes are the compiled
`_feldspar` extension's classes directly (AD-2 -- no Python mirrors);
this module's only job is marshalling `_feldspar`'s raising "checked"
primitives into the typani `Result` values 01-interfaces promises at
the Python surface (feldspar-py is marshalling-only, AD-1 -- and typani
itself has no Rust binding, so that last conversion step has to happen
here, in Python)."""

from typing import Iterable, Mapping, Optional

from typani.error_set import ErrorSet
from typani.result import Err, Ok, Result

from feldspar import _feldspar
from feldspar._feldspar import (
    Accuracy,
    Dimension,
    Domain,
    Interval,
    PortDecl,
    Rank,
    UnitSystem,
    canonical_digest,
    format_f64,
)

__all__ = [
    "Accuracy",
    "CoreError",
    "Dimension",
    "Domain",
    "DomainViolation",
    "EXACT",
    "Interval",
    "PortDecl",
    "Rank",
    "UnitError",
    "UnitSystem",
    "canonical_digest",
    "format_f64",
]


class CoreError(ErrorSet):
    """`Interval` construction failures (01-interfaces `CoreError`)."""

    NonFiniteBound = "an interval bound was NaN or +/-infinity"
    InvertedInterval = "interval lo > hi"


class UnitError(ErrorSet):
    """`UnitSystem` lookup/conversion failures (01-interfaces `UnitError`)."""

    UnknownUnit = "no table entry for this unit label"
    IncompatibleDimensions = "two units named together have different dimensions"
    OffsetInCompound = "an affine (offset) unit was used inside a compound unit"


class DomainViolation:
    """Why a `Domain.admits()` check failed; carries port/tag detail
    (01-interfaces: "DomainViolation carries port/tag details")."""

    __slots__ = ("kind", "port", "tag", "lo", "hi", "box_lo", "box_hi")

    def __init__(
        self,
        kind: str,
        port: Optional[str] = None,
        tag: Optional[str] = None,
        lo: Optional[float] = None,
        hi: Optional[float] = None,
        box_lo: Optional[float] = None,
        box_hi: Optional[float] = None,
    ) -> None:
        self.kind = kind
        self.port = port
        self.tag = tag
        self.lo = lo
        self.hi = hi
        self.box_lo = box_lo
        self.box_hi = box_hi

    def __repr__(self) -> str:
        return (
            f"DomainViolation(kind={self.kind!r}, port={self.port!r}, "
            f"tag={self.tag!r}, lo={self.lo!r}, hi={self.hi!r}, "
            f"box_lo={self.box_lo!r}, box_hi={self.box_hi!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DomainViolation):
            return NotImplemented
        return all(
            getattr(self, f) == getattr(other, f) for f in self.__slots__
        )


def _core_error_from_exc(exc: Exception) -> CoreError:
    variant: str = exc.args[0]
    return getattr(CoreError, variant)


def _unit_error_from_exc(exc: Exception) -> UnitError:
    variant: str = exc.args[0]
    return getattr(UnitError, variant)


def _domain_violation_from_exc(exc: Exception) -> DomainViolation:
    kind, port, tag, lo, hi, box_lo, box_hi = exc.args
    return DomainViolation(
        kind=kind, port=port, tag=tag, lo=lo, hi=hi, box_lo=box_lo, box_hi=box_hi
    )


def _interval_new(lo: float, hi: float) -> Result[Interval, CoreError]:
    """The checked `Result` constructor (01-interfaces `Interval.new`)."""
    try:
        return Ok(Interval._new_checked(lo, hi))
    except _feldspar.CoreErrorRaised as exc:
        return Err(_core_error_from_exc(exc))


def _interval_point(x: float) -> Result[Interval, CoreError]:
    """The checked degenerate-interval constructor (`Interval.point`)."""
    try:
        return Ok(Interval._point_checked(x))
    except _feldspar.CoreErrorRaised as exc:
        return Err(_core_error_from_exc(exc))


# Monkey-patched onto the `_feldspar`-defined class itself (a normal
# heap type), not a Python mirror: `Interval` stays the one frozen class
# (AD-2); only its Result-returning alternate constructors are Python-side
# because typani has no Rust binding to build `Result` values from.
Interval.new = staticmethod(_interval_new)  # ty: ignore[invalid-assignment]
Interval.point = staticmethod(_interval_point)  # ty: ignore[invalid-assignment]


def _domain_admits(
    self: Domain, inputs: Mapping[str, Interval], tags: Iterable[str]
) -> Result[None, DomainViolation]:
    """`Result[None, DomainViolation]` (01-interfaces `Domain.admits`)."""
    try:
        self._admits_checked(dict(inputs), set(tags))
        return Ok(None)
    except _feldspar.DomainViolationRaised as exc:
        return Err(_domain_violation_from_exc(exc))


Domain.admits = _domain_admits


def _unit_system_dimension_of(
    self: UnitSystem, unit: str
) -> Result[Dimension, UnitError]:
    try:
        return Ok(self._dimension_of_checked(unit))
    except _feldspar.UnitErrorRaised as exc:
        return Err(_unit_error_from_exc(exc))


def _unit_system_to_si(
    self: UnitSystem, value: float, unit: str
) -> Result[float, UnitError]:
    try:
        return Ok(self._to_si_checked(value, unit))
    except _feldspar.UnitErrorRaised as exc:
        return Err(_unit_error_from_exc(exc))


def _unit_system_from_si(
    self: UnitSystem, value: float, unit: str
) -> Result[float, UnitError]:
    try:
        return Ok(self._from_si_checked(value, unit))
    except _feldspar.UnitErrorRaised as exc:
        return Err(_unit_error_from_exc(exc))


UnitSystem.dimension_of = _unit_system_dimension_of
UnitSystem.to_si = _unit_system_to_si
UnitSystem.from_si = _unit_system_from_si

#: `Accuracy(0.0, 0.0)`; the EXACT constant (01-interfaces).
EXACT: Accuracy = _feldspar.exact_accuracy()
