from __future__ import annotations

"""`feldspar.solver_packs` discovery + composition -- the M9 plug-and-
play seam (10 sec. 3): one level down from lithos's `regolith.plugins`
(AD-26). A solver pack is an ordinary Python distribution exposing ONE
entry point in the group `feldspar.solver_packs` whose target is a bare
`register(registry: SolverRegistry) -> None` callable (10 sec. 3's
`acme_bearings = "acme_bearings:register"` example) -- no manifest
wrapper, unlike the regolith-facing seam one level up; the pack's
version comes from the entry point's OWN installed distribution
metadata (`ep.dist.version`), the ordinary importlib.metadata shape.

Composition is deterministic: whatever built-ins the caller already
registered on `registry` come first, then discovered packs in
sorted-entry-point-name order. A bad pack is skipped LOUDLY -- recorded
as a typed error value naming the offending pack, never a crash and
never a silent partial load (mirrors `lithos:python/regolith/harness/
plugin.py`'s proven shape one level up: each pack is staged onto a
scratch registry first, so a mid-registration failure never partially
lands on the real one)."""

from typing import Callable, Dict, Iterable, List, Optional, Protocol, Tuple, cast

from pydantic import BaseModel, ConfigDict

from feldspar.core import canonical_digest
from feldspar.logging_setup import get_logger
from feldspar.solve.registry import SolverRegistry

_log = get_logger(__name__)

# The one entry-point group every out-of-repo solver pack registers
# through (10 sec. 3). Nothing else may hard-code this string.
SOLVER_PACK_ENTRY_POINT_GROUP = "feldspar.solver_packs"

# Words that name a METHOD/TOOL/TIER rather than WHAT is claimed
# (mirrors lithos D94 sec. 8.1's method-named-kind lint, one level
# down): a namespace or solver id built from these is a bootstrap-style
# vocabulary error, not a legitimate physical word.
_METHOD_WORDS: Tuple[str, ...] = ("fea", "ccx", "gmsh", "spice", "ngspice")

# The standard built-in namespaces (`feldspar/library/*.py`); a pack may
# upstream into one of these through review, but never squat on it
# outright (10 sec. 3 "Namespace etiquette").
DEFAULT_STANDARD_NAMESPACES: Tuple[str, ...] = ("mech", "elec", "fluids", "heat")

RegisterFn = Callable[[SolverRegistry], None]

__all__ = [
    "DEFAULT_STANDARD_NAMESPACES",
    "SOLVER_PACK_ENTRY_POINT_GROUP",
    "DuplicateSolverId",
    "FakeSolverPackEntryPoint",
    "MalformedSolverPack",
    "MethodNamedSolverId",
    "NamespaceViolation",
    "PackInfo",
    "PackRegisterRaised",
    "PortDeclarationFailed",
    "RegisterFn",
    "RegistrationRejected",
    "SolverPackEntryPoint",
    "SolverPackLoadError",
    "SolverPackLoadOutcome",
    "load_solver_packs",
    "method_named_solver_violation",
    "pack_composition_digest",
]


class SolverPackEntryPoint(Protocol):
    """The slice of `importlib.metadata.EntryPoint` discovery reads
    (AD-11 fakes: tests and a pack's own conformance session inject a
    stand-in with no real installed distribution)."""

    @property
    def name(self) -> str:
        """The entry-point name (the pack's id, one per group member)."""
        ...

    def load(self) -> object:
        """Resolve the entry point's target object (a real EntryPoint
        imports here)."""
        ...

    @property
    def dist(self) -> "object | None":
        """The owning distribution, whose `.version` is the pack
        version folded into affected digests (10 sec. 3's WO-20-
        precedent rule, one level down); `None` only for a synthetic
        fake with no real installed distribution."""
        ...


class FakeSolverPackEntryPoint:
    """A stand-in for `importlib.metadata.EntryPoint` (AD-11): satisfies
    `SolverPackEntryPoint` structurally, so both `load_solver_packs`
    unit tests and `feldspar.testing.assert_solverpack_conforms` need
    no real installed distribution to exercise composition."""

    def __init__(self, name: str, version: str, register_fn: RegisterFn) -> None:
        self._name = name
        self._version = version
        self._register_fn = register_fn

    @property
    def name(self) -> str:
        return self._name

    def load(self) -> object:
        return self._register_fn

    @property
    def dist(self) -> "object | None":
        return _FakeDist(self._version)


class _FakeDist:
    """The minimal `importlib.metadata.Distribution` slice `dist.version` reads."""

    def __init__(self, version: str) -> None:
        self.version = version


class PackInfo(BaseModel):
    """One successfully composed solver pack's identity (id + version) --
    the pair `pack_composition_digest` folds (10 sec. 3's WO-20-
    precedent rule)."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str


class DuplicateSolverId(BaseModel):
    """A pack declared a solver id something already owns -- the
    built-ins (`owned_by="<builtin>"`) or an earlier pack in this same
    composition pass. Names BOTH the offending pack and the id's
    original owner (never just one side)."""

    model_config = ConfigDict(frozen=True)

    pack: str
    solver_id: str
    owned_by: str


class NamespaceViolation(BaseModel):
    """A pack registered outside its own sub-namespace (`<pack>.*`, or
    `<standard>.<pack>.*` under one of the caller's standard
    namespaces) without being a bare standard namespace itself -- the
    "no squatting" rule (10 sec. 3)."""

    model_config = ConfigDict(frozen=True)

    pack: str
    solver_id: str
    namespace: str


class MethodNamedSolverId(BaseModel):
    """A pack's namespace or solver id names a method/tool/tier instead
    of what is claimed (the D94 lint, one level down)."""

    model_config = ConfigDict(frozen=True)

    pack: str
    solver_id: str
    word: str


class PackRegisterRaised(BaseModel):
    """A pack's `register(registry)` callable raised while composing.
    Third-party pack code is a plugin boundary: its exceptions are our
    recoverable data, never a crashed build."""

    model_config = ConfigDict(frozen=True)

    pack: str
    message: str


class MalformedSolverPack(BaseModel):
    """An entry point's target was not a callable `register(registry)`."""

    model_config = ConfigDict(frozen=True)

    source: str
    message: str


class PortDeclarationFailed(BaseModel):
    """A pack's new port declarations conflicted (F12) once replayed
    onto the base registry."""

    model_config = ConfigDict(frozen=True)

    pack: str
    error: str


class RegistrationRejected(BaseModel):
    """A pack's solver was rejected by `SolverRegistry.register` itself
    (empty citations, non-positive cost, accuracy/output mismatch, ...)
    once replayed onto the base registry."""

    model_config = ConfigDict(frozen=True)

    pack: str
    solver_id: str
    error: str


# The union of pack-load failure values: each names its pack (or entry
# point source) and is surfaced in `SolverPackLoadOutcome.skipped`.
SolverPackLoadError = (
    DuplicateSolverId
    | MalformedSolverPack
    | MethodNamedSolverId
    | NamespaceViolation
    | PackRegisterRaised
    | PortDeclarationFailed
    | RegistrationRejected
)


class SolverPackLoadOutcome(BaseModel):
    """The total result of one solver-pack composition pass. Loading is
    TOTAL: a bad pack lands in `skipped` as a value (never aborting the
    others, never a crash)."""

    model_config = ConfigDict(frozen=True)

    loaded: Tuple[PackInfo, ...] = ()
    skipped: Tuple[SolverPackLoadError, ...] = ()


def method_named_solver_violation(text: str) -> Optional[str]:
    """The first method/tool word found in `text` (a namespace or
    solver id), or `None` if it is clean -- the one vocabulary home
    both `load_solver_packs` and `feldspar.testing` share (NO
    DUPLICATION)."""
    lowered = text.lower()
    for word in _METHOD_WORDS:
        if word in lowered:
            return word
    return None


def _namespace_violation(
    pack_name: str,
    namespace: str,
    standard_namespaces: Iterable[str],
    reviewed_namespaces: Iterable[str],
) -> Optional[str]:
    """`None` if `namespace` is the pack's own sub-namespace (equal to
    `pack_name`, or `<standard>.<pack_name>` under a caller-declared
    standard namespace) or is a namespace the caller has explicitly
    marked reviewed via `reviewed_namespaces` (10 sec. 3: "unless it is
    upstreaming into a standard namespace through review" -- the kit
    cannot tell "reviewed" from "not" on its own, so a BARE standard
    namespace is flagged by DEFAULT; the caller opts a specific
    namespace in only after doing that review); otherwise the
    violating namespace string, unchanged (squatting on `mech`/`elec`/
    ... with no matching claim kind/review)."""
    if namespace == pack_name or namespace.startswith(f"{pack_name}."):
        return None
    if namespace in set(reviewed_namespaces):
        return None
    for std in standard_namespaces:
        if namespace.startswith(f"{std}.{pack_name}"):
            return None
    return namespace


def _load_target(
    ep: SolverPackEntryPoint,
) -> "Callable[[SolverRegistry], object] | MalformedSolverPack":
    try:
        target = ep.load()
    except Exception as exc:  # noqa: BLE001 -- plugin boundary: their bugs are our data
        return MalformedSolverPack(
            source=ep.name, message=f"entry point load failed: {exc}"
        )
    if not callable(target):
        return MalformedSolverPack(
            source=ep.name,
            message=f"entry point target {target!r} is not callable",
        )
    return cast("Callable[[SolverRegistry], object]", target)


def _pack_version(ep: SolverPackEntryPoint) -> str:
    dist = getattr(ep, "dist", None)
    version = getattr(dist, "version", None)
    return version if version else "0"


def load_solver_packs(
    registry: SolverRegistry,
    *,
    standard_namespaces: Iterable[str] = DEFAULT_STANDARD_NAMESPACES,
    reviewed_namespaces: Iterable[str] = (),
    entry_points_override: Optional[Iterable[SolverPackEntryPoint]] = None,
) -> SolverPackLoadOutcome:
    """Discovers and composes every `feldspar.solver_packs` entry point
    into `registry`. Deterministic: entry points are processed in
    sorted-by-name order, after whatever built-ins the caller already
    registered. Each pack's solvers are staged onto a scratch registry
    first (seeded with `registry`'s current port table) so a mid-
    registration failure never partially lands; a clean stage is
    replayed onto `registry` itself. `entry_points_override` injects
    fakes for tests and a pack's own conformance session (AD-11).
    `reviewed_namespaces` opts specific standard namespaces (`mech`,
    `elec`, ...) into a pack's namespace etiquette check having ALREADY
    been reviewed (10 sec. 3) -- empty by default, so upstreaming into
    a bare standard namespace is flagged until the caller says
    otherwise."""
    if entry_points_override is not None:
        discovered: Iterable[SolverPackEntryPoint] = entry_points_override
    else:
        from importlib.metadata import entry_points

        discovered = entry_points(group=SOLVER_PACK_ENTRY_POINT_GROUP)

    standard = tuple(standard_namespaces)
    reviewed = tuple(reviewed_namespaces)
    owner_of: Dict[str, str] = {info.solver_id: "<builtin>" for info, _fn in registry}

    loaded: List[PackInfo] = []
    skipped: List[SolverPackLoadError] = []

    for ep in sorted(discovered, key=lambda e: e.name):
        pack_name = ep.name
        target = _load_target(ep)
        if isinstance(target, MalformedSolverPack):
            _log.warning(
                "skipping malformed solver pack %r LOUDLY: %r", pack_name, target
            )
            skipped.append(target)
            continue

        # F12: seed the staging registry with the base's current port
        # table so a pack's own port references resolve exactly as they
        # would against the real registry (re-declaring the base's own
        # decls verbatim never conflicts).
        staging = SolverRegistry()
        base_ports = tuple(registry.port_table().values())
        if base_ports:
            seed = staging.declare_ports(*base_ports)
            assert seed.is_ok, "base registry's own port table must be self-consistent"

        try:
            target(staging)
        except Exception as exc:  # noqa: BLE001 -- plugin boundary
            err = PackRegisterRaised(
                pack=pack_name, message=f"register() raised: {exc}"
            )
            _log.warning("skipping solver pack %r LOUDLY: %r", pack_name, err)
            skipped.append(err)
            continue

        staged_infos = [info for info, _fn in staging]
        violation: Optional[SolverPackLoadError] = None
        for info in staged_infos:
            word = method_named_solver_violation(
                info.namespace
            ) or method_named_solver_violation(info.solver_id)
            if word is not None:
                violation = MethodNamedSolverId(
                    pack=pack_name, solver_id=info.solver_id, word=word
                )
                break
            bad_ns = _namespace_violation(pack_name, info.namespace, standard, reviewed)
            if bad_ns is not None:
                violation = NamespaceViolation(
                    pack=pack_name, solver_id=info.solver_id, namespace=bad_ns
                )
                break
            owner = owner_of.get(info.solver_id)
            if owner is not None:
                violation = DuplicateSolverId(
                    pack=pack_name, solver_id=info.solver_id, owned_by=owner
                )
                break
        if violation is not None:
            _log.warning("skipping solver pack %r LOUDLY: %r", pack_name, violation)
            skipped.append(violation)
            continue

        # New ports the pack declared beyond the seeded base table must
        # also land on the real registry (F12).
        base_port_names = set(registry.port_table().keys())
        new_ports = [
            decl
            for port_name, decl in staging.port_table().items()
            if port_name not in base_port_names
        ]
        if new_ports:
            declared = registry.declare_ports(*new_ports)
            if declared.is_err:
                err = PortDeclarationFailed(
                    pack=pack_name, error=repr(declared.danger_err)
                )
                _log.warning("skipping solver pack %r LOUDLY: %r", pack_name, err)
                skipped.append(err)
                continue

        replay_failed = False
        registered_this_pack: List[str] = []
        for info, fn in staging:
            result = registry.register(info, fn)
            if result.is_err:
                err = RegistrationRejected(
                    pack=pack_name,
                    solver_id=info.solver_id,
                    error=repr(result.danger_err),
                )
                _log.warning("skipping solver pack %r LOUDLY: %r", pack_name, err)
                skipped.append(err)
                replay_failed = True
                break
            owner_of[info.solver_id] = pack_name
            registered_this_pack.append(info.solver_id)
        if replay_failed:
            continue

        version = _pack_version(ep)
        info_out = PackInfo(name=pack_name, version=version)
        loaded.append(info_out)
        _log.info(
            "loaded solver pack %s@%s (%d solver(s))",
            info_out.name,
            info_out.version,
            len(registered_this_pack),
        )

    return SolverPackLoadOutcome(loaded=tuple(loaded), skipped=tuple(skipped))


def pack_composition_digest(base_digest: str, outcome: SolverPackLoadOutcome) -> str:
    """Folds a pack composition's identity into `base_digest` (10 sec.
    3's WO-20-precedent rule): `SolverInfo` itself carries no pack
    identity, so `SolverRegistry.digest()` alone cannot re-key when a
    pack version bumps with no solver-field change. Bumping ANY loaded
    pack's version changes this digest even when `base_digest` (the
    registry's own solver-field digest) does not move."""
    return canonical_digest(
        {
            "base": base_digest,
            "packs": sorted((pack.name, pack.version) for pack in outcome.loaded),
        }
    )
