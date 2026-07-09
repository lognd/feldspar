from __future__ import annotations

"""WO-16 tests: known-answer + edge-case tests for
`python/feldspar/library/vibe.py`'s vibration-tier directions (beam/
SDOF closed-form first_mode, Miles GRMS, mask containment), called
THROUGH the `SolverRegistry`/`SolveFn` protocol -- the same style as
`test_library_mech.py`. Uses an in-memory `DictResolver` (mirrors
`tests/integration/test_fea_payload_steps.py`'s fixture) since the
spectrum/profile/mask directions are payload-consuming."""

import hashlib
import json
import math
from typing import Dict

import pytest
from typani import Err, Ok

from feldspar.core import PortDecl, Rank
from feldspar.library.vibe import (
    FIRST_MODE_PORT,
    GRMS_PORT,
    MASK_CONTAINMENT_PORT,
    MASK_PORT,
    PROFILE_PORT,
    SPECTRUM_PORT,
    register,
)
from feldspar.solve import PayloadRef, SolveError, SolverRegistry


class DictResolver:
    """In-memory orchestrator store stand-in (D96/OPEN-2 handle);
    mirrors `tests/integration/test_fea_payload_steps.py`."""

    def __init__(self) -> None:
        self._blobs: Dict[str, bytes] = {}

    def store(self, kind: str, content: bytes, origin: str) -> PayloadRef:
        digest = hashlib.sha256(content).hexdigest()
        self._blobs[digest] = content
        return PayloadRef(kind=kind, digest=digest, origin=origin)

    def resolve(self, ref: PayloadRef):
        blob = self._blobs.get(ref.digest)
        if blob is None:
            return Err(SolveError.DanglingDigest(digest=ref.digest))
        return Ok(blob)


def _registry_and_resolver():
    resolver = DictResolver()
    registry = SolverRegistry()
    # `library/vibe.py`'s beam direction shares these three ports with
    # `library/mech.py` but deliberately does not declare them itself
    # (see `vibe.register`'s docstring: avoiding a
    # `RegistryError.DuplicatePortDecl` when composed with
    # `fea/payload_steps.py`, which declares `mech.material.
    # youngs_modulus` too) -- a standalone catalog using only vibe.py
    # must declare them itself, exactly like a real catalog assembler
    # would.
    assert registry.declare_ports(
        PortDecl("mech.geom.cantilever.length", "m"),
        PortDecl("mech.section.second_moment", "m^4"),
        PortDecl("mech.material.youngs_modulus", "Pa"),
    ).is_ok
    register(registry, resolver)
    return registry, resolver


def _solvers(registry) -> dict:
    return {info.solver_id: (info, fn) for info, fn in registry}


def test_beam_cantilever_first_mode_known_answer():
    """Steel cantilever E=200e9, I=8e-6, rho=7850, A=0.01, L=1.0:
    f1 = (1.875104^2/(2*pi)) * sqrt(E*I/(rho*A))."""
    registry, _resolver = _registry_and_resolver()
    _info, fn = _solvers(registry)["mech.beam_cantilever_first_mode"]
    result = fn(
        {
            "mech.geom.cantilever.length": 1.0,
            "mech.section.second_moment": 8e-6,
            "mech.material.youngs_modulus": 200e9,
            "mech.material.density": 7850.0,
            "mech.section.area": 0.01,
        }
    )
    assert result.is_ok
    beta1_sq = 1.87510407**2
    expected = (beta1_sq / (2 * math.pi)) * math.sqrt(200e9 * 8e-6 / (7850.0 * 0.01))
    assert result.danger_ok.values[FIRST_MODE_PORT] == pytest.approx(expected, rel=1e-9)


def test_sdof_first_mode_known_answer():
    registry, _resolver = _registry_and_resolver()
    _info, fn = _solvers(registry)["mech.sdof_first_mode"]
    result = fn({"mech.vibe.stiffness": 1000.0, "mech.vibe.mass": 2.0})
    assert result.is_ok
    expected = (1.0 / (2 * math.pi)) * math.sqrt(500.0)
    assert result.danger_ok.values[FIRST_MODE_PORT] == pytest.approx(expected, rel=1e-9)


def _spectrum_ref(resolver, freq_hz, asd):
    payload = json.dumps({"freq_hz": freq_hz, "asd_g2_per_hz": asd}).encode()
    return resolver.store("spectrum", payload, "test-fixture")


def test_miles_grms_end_to_end_over_spectrum_payload():
    """Acceptance: a random-vibe GRMS claim consumes a spectrum payload
    end to end. fn=100 Hz sits exactly on a grid point: no
    interpolation ambiguity."""
    registry, resolver = _registry_and_resolver()
    spectrum_ref = _spectrum_ref(resolver, [10.0, 100.0, 1000.0], [0.01, 0.1, 0.02])
    _info, fn = _solvers(registry)["mech.vibe.miles_grms"]
    result = fn(
        {
            FIRST_MODE_PORT: 100.0,
            "mech.vibe.q": 10.0,
            SPECTRUM_PORT: spectrum_ref,
        }
    )
    assert result.is_ok
    expected = math.sqrt((math.pi / 2.0) * 100.0 * 10.0 * 0.1)
    assert result.danger_ok.values[GRMS_PORT] == pytest.approx(expected, rel=1e-9)


def test_miles_grms_interpolates_between_grid_points():
    registry, resolver = _registry_and_resolver()
    spectrum_ref = _spectrum_ref(resolver, [0.0, 100.0], [0.0, 0.2])
    _info, fn = _solvers(registry)["mech.vibe.miles_grms"]
    result = fn(
        {FIRST_MODE_PORT: 50.0, "mech.vibe.q": 10.0, SPECTRUM_PORT: spectrum_ref}
    )
    assert result.is_ok
    expected = math.sqrt((math.pi / 2.0) * 50.0 * 10.0 * 0.1)
    assert result.danger_ok.values[GRMS_PORT] == pytest.approx(expected, rel=1e-9)


def test_miles_grms_band_outside_spectrum_domain_is_honest_error():
    """02-edge-cases (WO-16 row): a claim's first_mode_freq outside the
    spectrum's supplied frequency band is `SolveError.OutOfDomain`,
    never a silently extrapolated/clipped value."""
    registry, resolver = _registry_and_resolver()
    spectrum_ref = _spectrum_ref(resolver, [10.0, 1000.0], [0.01, 0.02])
    _info, fn = _solvers(registry)["mech.vibe.miles_grms"]
    result = fn(
        {FIRST_MODE_PORT: 5000.0, "mech.vibe.q": 10.0, SPECTRUM_PORT: spectrum_ref}
    )
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def _profile_ref(resolver, kind, t, y):
    payload = json.dumps({"t": t, "y": y}).encode()
    return resolver.store(kind, payload, "test-fixture")


def test_mask_containment_true_when_profile_stays_within_mask():
    registry, resolver = _registry_and_resolver()
    profile_ref = _profile_ref(resolver, "profile", [0.0, 1.0, 2.0], [0.1, 0.2, 0.15])
    mask_ref = _profile_ref(resolver, "mask", [0.0, 1.0, 2.0], [0.5, 0.5, 0.5])
    _info, fn = _solvers(registry)["mech.vibe.mask_containment"]
    result = fn({PROFILE_PORT: profile_ref, MASK_PORT: mask_ref})
    assert result.is_ok
    assert result.danger_ok.values[MASK_CONTAINMENT_PORT] == 1.0


def test_mask_containment_false_when_profile_exceeds_mask():
    registry, resolver = _registry_and_resolver()
    profile_ref = _profile_ref(resolver, "profile", [0.0, 1.0], [0.6, 0.2])
    mask_ref = _profile_ref(resolver, "mask", [0.0, 1.0], [0.5, 0.5])
    _info, fn = _solvers(registry)["mech.vibe.mask_containment"]
    result = fn({PROFILE_PORT: profile_ref, MASK_PORT: mask_ref})
    assert result.is_ok
    assert result.danger_ok.values[MASK_CONTAINMENT_PORT] == 0.0


def test_mask_containment_domain_misalignment_is_honest_error():
    """02-edge-cases (WO-16 row): mismatched profile/mask sample grids
    are `SolveError.OutOfDomain`, never an implicit resample."""
    registry, resolver = _registry_and_resolver()
    profile_ref = _profile_ref(resolver, "profile", [0.0, 1.0, 2.0], [0.1, 0.2, 0.1])
    mask_ref = _profile_ref(resolver, "mask", [0.0, 1.0], [0.5, 0.5])
    _info, fn = _solvers(registry)["mech.vibe.mask_containment"]
    result = fn({PROFILE_PORT: profile_ref, MASK_PORT: mask_ref})
    assert result.is_err
    assert result.err.kind == "OutOfDomain"


def test_rank_mismatch_at_connection_is_a_registration_error():
    """02-quantities "Non-scalar and structured quantities": "Rank
    mismatch at connection is a registration error, exactly like a unit
    mismatch." Redeclaring the vibration tier's payload spectrum port
    with a ranked (vector) shape instead of its declared payload rank
    must be rejected."""
    registry, _resolver = _registry_and_resolver()
    result = registry.declare_ports(PortDecl(SPECTRUM_PORT, "", Rank.vector(3)))
    assert result.is_err
    assert result.err.kind == "PortRankConflict"
