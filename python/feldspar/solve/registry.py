from __future__ import annotations

"""`SolverRegistry`: explicit, non-global-state solver/port registration
(AD-4, 01-interfaces). Every registration, rejection, and freeze is
logged with the relevant id (WO-03 deliverable)."""

from typing import Dict, Iterator, Mapping, Tuple

from typani.result import Err, Ok, Result

from feldspar.core import PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import digest as _digest
from feldspar.solve._models import SolverInfo
from feldspar.solve.errors import RegistryError
from feldspar.solve.payload import PAYLOAD_KINDS
from feldspar.solve.solver import SolveFn

_log = get_logger(__name__)


# frob:doc docs/modules/solve.md#solve_registry
class SolverRegistry:
    """Sorted-by-id iteration, a folded registry digest (feeds FINV-7),
    and the FINV-6 citation floor -- populated by each namespace
    module's `register(registry)` function, in any order (AD-4)."""

    def __init__(self) -> None:
        self._solvers: Dict[str, Tuple[SolverInfo, SolveFn]] = {}
        self._ports: Dict[str, PortDecl] = {}
        self._frozen = False

    # frob:doc docs/modules/solve.md#solve_registry
    def declare_ports(self, *decls: PortDecl) -> "Result[None, RegistryError]":
        """F12: a namespace module declares its port table once; a
        conflicting redeclaration (same name, different unit or rank --
        or an exact repeat) is a `RegistryError`, never silently
        accepted or silently ignored."""
        if self._frozen:
            _log.warning("declare_ports rejected: registry is frozen")
            return Err(RegistryError.Frozen())
        for decl in decls:
            # WO-12 (09 sec. 4): a payload-rank declaration's kind string
            # must come from the one vocabulary home (PAYLOAD_KINDS) --
            # checked before any conflict logic so a typo'd kind is named
            # as such, never mis-reported as a conflict.
            if decl.rank.kind == "payload":
                declared_kind = decl.rank.payload_kind or ""
                if declared_kind not in PAYLOAD_KINDS:
                    _log.warning(
                        "unknown payload kind %r declared for port %s",
                        declared_kind,
                        decl.name,
                    )
                    return Err(
                        RegistryError.UnknownPayloadKind(
                            port=decl.name, payload_kind=declared_kind
                        )
                    )
            existing = self._ports.get(decl.name)
            if existing is None:
                self._ports[decl.name] = decl
                _log.info(
                    "declared port %s (unit=%s, rank=%s)",
                    decl.name,
                    decl.unit,
                    decl.rank,
                )
                continue
            if existing.unit != decl.unit:
                _log.warning(
                    "port unit conflict for %s: %s vs %s",
                    decl.name,
                    existing.unit,
                    decl.unit,
                )
                return Err(RegistryError.PortUnitConflict(port=decl.name))
            # WO-12: two payload declarations of the same port with
            # DIFFERENT kinds get the dedicated kind-conflict error (the
            # unit-mismatch mirror, 09 sec. 4) rather than the generic
            # rank conflict -- connecting `mesh` to `spectrum` must be
            # named as a KIND error.
            if (
                existing.rank.kind == "payload"
                and decl.rank.kind == "payload"
                and existing.rank.payload_kind != decl.rank.payload_kind
            ):
                _log.warning(
                    "payload kind conflict for %s: %s vs %s",
                    decl.name,
                    existing.rank.payload_kind,
                    decl.rank.payload_kind,
                )
                return Err(RegistryError.PayloadKindConflict(port=decl.name))
            if existing.rank != decl.rank:
                _log.warning(
                    "port rank conflict for %s: %s vs %s",
                    decl.name,
                    existing.rank,
                    decl.rank,
                )
                return Err(RegistryError.PortRankConflict(port=decl.name))
            _log.warning("duplicate port declaration for %s", decl.name)
            return Err(RegistryError.DuplicatePortDecl(port=decl.name))
        return Ok(None)

    # frob:doc docs/modules/solve.md#solve_registry
    def register(self, info: SolverInfo, fn: SolveFn) -> "Result[None, RegistryError]":
        """`Err` on duplicate id, port unit/rank conflict via an
        undeclared port, empty/calibration-only citations (FINV-6),
        non-positive cost, an accuracy/outputs mismatch, or after
        `freeze()`."""
        if self._frozen:
            _log.warning("register rejected (frozen): %s", info.solver_id)
            return Err(RegistryError.Frozen())
        if info.solver_id in self._solvers:
            _log.warning("duplicate solver id: %s", info.solver_id)
            return Err(RegistryError.DuplicateSolverId(solver_id=info.solver_id))
        if info.cost <= 0:
            _log.warning("non-positive cost for %s: %s", info.solver_id, info.cost)
            return Err(RegistryError.NonPositiveCost(solver_id=info.solver_id))
        if set(info.accuracy.keys()) != set(info.outputs):
            _log.warning("accuracy/outputs mismatch for %s", info.solver_id)
            return Err(RegistryError.AccuracyOutputMismatch(solver_id=info.solver_id))
        if not info.citations or all(c.kind == "calibration" for c in info.citations):
            _log.warning("empty/calibration-only citations for %s", info.solver_id)
            return Err(RegistryError.EmptyCitations(solver_id=info.solver_id))

        # F12 is a GUARD you opt into by calling declare_ports, not a
        # blanket requirement (examples/solvers/00_raw_protocol.py,
        # 02_relations.py, 03_tables_correlations.py, and
        # 04_families.py all register successfully without ever
        # declaring a port table -- only 01_sugar_coercions.py uses
        # F12). So an empty port table means "nobody has opted in yet"
        # and skips the check entirely; once ANY module has declared
        # ports, every subsequent register() call is checked against
        # that accumulated table, which is exactly the real multi-
        # module-catalog shape F12 exists to guard.
        if self._ports:
            touched_ports = (*info.inputs, *info.outputs, *info.domain.box.keys())
            for port in touched_ports:
                if port not in self._ports:
                    _log.warning(
                        "unknown port %s referenced by %s", port, info.solver_id
                    )
                    return Err(RegistryError.UnknownPort(port=port))

        self._solvers[info.solver_id] = (info, fn)
        _log.info(
            "registered solver %s (namespace=%s, tier=%s)",
            info.solver_id,
            info.namespace,
            info.tier,
        )
        return Ok(None)

    def _rollback_registration(self, solver_id: str) -> None:
        """Removes a previously-`register()`ed solver id (packs.py L1,
        cycle-29 audit): a pack-loading replay that fails partway must
        be able to undo the solvers it already landed on a real
        (non-staging) registry, so a "skipped" pack never partially
        lands. Package-private: only the pack-loading replay rolls back
        a registry this way -- ordinary callers never unregister."""
        self._solvers.pop(solver_id, None)
        _log.info("rolled back registration of %s", solver_id)

    def _rollback_port_decl(self, port_name: str) -> None:
        """Removes a previously-`declare_ports()`ed port (packs.py L1
        counterpart to `_rollback_registration`)."""
        self._ports.pop(port_name, None)
        _log.info("rolled back port declaration of %s", port_name)

    # frob:doc docs/modules/solve.md#solve_registry
    def get(self, solver_id: str) -> "Tuple[SolverInfo, SolveFn] | None":
        """Look up one registered `(SolverInfo, SolveFn)` pair by id
        (WO-18, 09 sec. 4b): `CoupledGroup`'s closure resolves its
        MEMBER solvers through this at solve-call time (never at
        `register()` time -- AD-4 registration order is arbitrary, so a
        composite may register before its members exist in the same
        registry). `None`, not an exception, for "not (yet) registered"
        -- the closure itself decides what that means for its caller."""
        return self._solvers.get(solver_id)

    # frob:doc docs/modules/solve.md#solve_registry
    def freeze(self) -> None:
        self._frozen = True
        _log.info(
            "registry frozen: %d solvers, %d ports",
            len(self._solvers),
            len(self._ports),
        )

    # frob:doc docs/modules/solve.md#solve_registry
    def is_frozen(self) -> bool:
        return self._frozen

    # frob:doc docs/modules/solve.md#solve_registry
    def digest(self) -> str:
        """Canonical-JSON -> blake3 fold of every registered `SolverInfo`,
        sorted by `solver_id` (FINV-1: import-order-independent; feeds
        FINV-7's cache key)."""
        infos = [info for _id, (info, _fn) in sorted(self._solvers.items())]
        return _digest.canonical_digest(infos)

    def __iter__(self) -> Iterator[Tuple[SolverInfo, SolveFn]]:
        for _id, pair in sorted(self._solvers.items()):
            yield pair

    # frob:doc docs/modules/solve.md#solve_registry
    def port_table(self) -> Mapping[str, PortDecl]:
        return dict(self._ports)
