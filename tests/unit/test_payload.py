from __future__ import annotations

"""WO-12 payload-port unit tests: the 09 sec. 4 kind vocabulary,
`PayloadRef` construction, registration-time kind checking (the unit-
mismatch mirror), and the `payload_feature_violation` 4a helper.

Covers the 02-edge-cases "Payload ports (WO-12)" registration rows;
the pipeline rows (execution kind mismatch, missing payload, dangling
digest, mesh reuse, digest stability) live in
tests/unit/test_payload_pipeline.py."""

import pytest
from pydantic import ValidationError

from feldspar.core import PortDecl, Rank
from feldspar.solve import (
    PAYLOAD_KINDS,
    PayloadRef,
    RegistryError,
    SolverRegistry,
    payload_feature_violation,
)


class TestPayloadKinds:
    def test_kind_table_is_the_09_sec4_list_verbatim(self) -> None:
        """The 09 sec. 4 table, VERBATIM, including `frame` (lithos
        D139/D145) -- a drifted vocabulary is a spec bug."""
        assert PAYLOAD_KINDS == frozenset(
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

    def test_payload_ref_accepts_every_kind(self) -> None:
        for kind in PAYLOAD_KINDS:
            ref = PayloadRef(kind=kind, digest="d" * 8)
            assert ref.kind == kind

    def test_payload_ref_rejects_unknown_kind(self) -> None:
        with pytest.raises(ValidationError):
            PayloadRef(kind="geometry.bogus", digest="d" * 8)

    def test_payload_ref_is_frozen(self) -> None:
        ref = PayloadRef(kind="mesh", digest="abc", origin="test")
        with pytest.raises(ValidationError):
            ref.digest = "changed"  # type: ignore[misc]


class TestRegistrationKindChecking:
    """09 sec. 4: payload ports type-check by KIND exactly as scalar
    ports check by unit."""

    def test_payload_port_declares_cleanly(self) -> None:
        registry = SolverRegistry()
        result = registry.declare_ports(
            PortDecl("mech.mesh.cantilever", "", Rank.payload("mesh"))
        )
        assert result.is_ok
        table = registry.port_table()
        assert table["mech.mesh.cantilever"].rank == Rank.payload("mesh")

    def test_mismatched_kinds_same_port_is_kind_conflict(self) -> None:
        """Connecting `mesh` to `spectrum` is a registration error with
        the same shape as a unit mismatch (WO-12 deliverable)."""
        registry = SolverRegistry()
        assert registry.declare_ports(
            PortDecl("mech.signal", "", Rank.payload("mesh"))
        ).is_ok
        result = registry.declare_ports(
            PortDecl("mech.signal", "", Rank.payload("spectrum"))
        )
        assert result.is_err
        err = result.danger_err
        assert err == RegistryError.PayloadKindConflict(port="mech.signal")

    def test_payload_vs_scalar_same_port_is_rank_conflict(self) -> None:
        registry = SolverRegistry()
        assert registry.declare_ports(PortDecl("mech.thing", "m")).is_ok
        result = registry.declare_ports(
            PortDecl("mech.thing", "m", Rank.payload("mesh"))
        )
        assert result.is_err
        assert result.danger_err == RegistryError.PortRankConflict(port="mech.thing")

    def test_unknown_payload_kind_rejected_at_declaration(self) -> None:
        """A typo'd kind is named as UNKNOWN, never mis-reported as a
        conflict (PAYLOAD_KINDS is the one vocabulary home)."""
        registry = SolverRegistry()
        result = registry.declare_ports(
            PortDecl("mech.mesh.cantilever", "", Rank.payload("meshh"))
        )
        assert result.is_err
        assert result.danger_err == RegistryError.UnknownPayloadKind(
            port="mech.mesh.cantilever", payload_kind="meshh"
        )

    def test_exact_repeat_payload_decl_is_duplicate(self) -> None:
        registry = SolverRegistry()
        decl = PortDecl("mech.mesh.cantilever", "", Rank.payload("mesh"))
        assert registry.declare_ports(decl).is_ok
        result = registry.declare_ports(
            PortDecl("mech.mesh.cantilever", "", Rank.payload("mesh"))
        )
        assert result.is_err
        assert result.danger_err == RegistryError.DuplicatePortDecl(
            port="mech.mesh.cantilever"
        )


class TestPayloadFeatureViolation:
    def test_carries_port_and_feature(self) -> None:
        """4a execution-time domain checks report through the same
        DomainViolation shape scalar checks use."""
        violation = payload_feature_violation(
            "mech.geom.boom.realized", "hole_in_root_band"
        )
        assert violation.kind == "PayloadFeature"
        assert violation.port == "mech.geom.boom.realized"
        assert violation.tag == "hole_in_root_band"
