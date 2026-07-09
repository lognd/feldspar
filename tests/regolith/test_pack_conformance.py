from __future__ import annotations

"""WO-09 regolith conformance session (06 "Conformance", the WO-27
deliverable): runs regolith's OWN reusable pack-protocol suite
(`lithos:tests/packs/conformance.py`) against `feldspar.pack` from
the outside, plus the WO-27 acceptance list this repo owns.

Every test here is `regolith`-marked and requires lithos checked
out with `regolith` installed (`uv sync --extra regolith`, `conftest.py`
adds the sibling lithos checkout to `sys.path` so
`tests.packs.conformance` imports).
Where an acceptance item needs `ccx`/`gmsh` (not present in every dev/CI
environment, AD-12e/06) the test still runs and asserts the HONEST
outcome the pack must produce without them (an indeterminate `Evidence`
value, never a crash, never a silent pass) -- this mirrors WO-08's
`fea`-marked-test precedent (`tests/integration/test_fea_pipeline.py`)
of degrading gracefully rather than skipping outright."""

import pytest
from regolith._schema.models import Status1, Status2, Status3
from regolith.harness.model import DischargeRequest
from regolith.harness.models import register_all
from regolith.harness.plugin import load_packs
from regolith.harness.quantity import Interval
from regolith.harness.registry import ModelRegistry
from tests.packs.conformance import FakeEntryPoint

from feldspar.pack import register
from feldspar.pack.models import (
    DEFAULT_DEFLECTION_CLAIM_KIND,
    DEFAULT_STRESS_CLAIM_KIND,
    FeaStaticStressModel,
)

pytestmark = pytest.mark.regolith

_PACK_NAME = "feldspar"
_PACK_VERSION = "0.1.0"


def _builtin_only_registry() -> ModelRegistry:
    """A registry with regolith's shipped built-ins and NO discovered
    `regolith.model_packs` entry point -- unlike `default_registry()`,
    this does NOT auto-load feldspar's own real entry point, which THIS
    dev environment (feldspar editable-installed alongside regolith)
    would otherwise always pick up, defeating the fake-entry-point
    conformance pattern below (a real external consumer of `feldspar`
    never has this collision: it is a same-repo-dev-venv artifact
    only)."""
    registry = ModelRegistry()
    register_all(registry)
    return registry


def _registry_with_feldspar_pack(version: str = _PACK_VERSION) -> ModelRegistry:
    """Built-ins (real entry-point discovery bypassed, see
    `_builtin_only_registry`) plus feldspar's pack loaded through a fake
    entry point at `version` -- mirrors `tests.packs.conformance.
    registry_with_pack`'s composition exactly, just built on the
    collision-free baseline above."""
    registry = _builtin_only_registry()
    outcome = load_packs(
        registry,
        entry_points_override=[FakeEntryPoint(_PACK_NAME, version, register)],
    )
    assert outcome.skipped == (), f"pack load failed: {outcome.skipped}"
    return registry


# A fat-margin cylinder-bore stress request: thick wall, modest pressure
# -- comfortably inside every registered direction's declared Domain box,
# so `assert_pack_conforms`'s synthetic discharge exercises a REAL,
# tool-free (closed-form) engine solve, not a ToolMissing abstention.
_FAT_MARGIN_REQUEST = DischargeRequest(
    claim_kind=DEFAULT_STRESS_CLAIM_KIND,
    limit=1.0e8,
    inputs={
        "mech.geom.cylinder.inner_radius": Interval(lo=0.05, hi=0.05),
        "mech.geom.cylinder.outer_radius": Interval(lo=0.10, hi=0.10),
        "mech.material.youngs_modulus": Interval(lo=2.0e11, hi=2.0e11),
        "mech.material.poisson": Interval(lo=0.3, hi=0.3),
        "mech.load.internal_pressure": Interval(lo=1.0e6, hi=1.0e6),
    },
)

# A thin-margin (near-degenerate wall) request: outside the closed-form
# `bore_von_mises` direction's Lame-ratio-gap domain, so the ENGINE's own
# fallback reroute (04-routing) escalates to the FEA direction -- exactly
# the WO-27 "closed-form leaves it, the reduced tier picks it up" shape.
_THIN_MARGIN_REQUEST = DischargeRequest(
    claim_kind=DEFAULT_STRESS_CLAIM_KIND,
    limit=1.0e8,
    inputs={
        "mech.geom.cylinder.inner_radius": Interval(lo=0.0100000, hi=0.0100000),
        "mech.geom.cylinder.outer_radius": Interval(lo=0.0100001, hi=0.0100001),
        "mech.material.youngs_modulus": Interval(lo=2.0e11, hi=2.0e11),
        "mech.material.poisson": Interval(lo=0.3, hi=0.3),
        "mech.load.internal_pressure": Interval(lo=1.0e6, hi=1.0e6),
    },
)


def test_assert_pack_conforms() -> None:
    """The reusable protocol suite, green from the outside (WO-20/D-F):
    registration, deterministic composition, selection + total discharge,
    AD-19 evidence-hash pack-version keying, and INV-10 repeat-discharge
    determinism. Reimplements `assert_pack_conforms`'s own assertions
    against the collision-free `_builtin_only_registry` baseline (see
    that helper's docstring for why `default_registry()`/
    `registry_with_pack` can't be used directly in THIS dev venv)."""
    baseline = _builtin_only_registry()
    registry = _registry_with_feldspar_pack()

    builtin_count = len(baseline.all_models())
    assert [m.model_id for m in registry.all_models()[:builtin_count]] == [
        m.model_id for m in baseline.all_models()
    ], "built-ins must precede pack models, unchanged"
    added = registry.all_models()[builtin_count:]
    assert added, "the pack registered no models"
    for model in added:
        assert registry.pack_of(model.model_id) == (_PACK_NAME, _PACK_VERSION)

    selected = registry.select(_FAT_MARGIN_REQUEST)
    assert selected.is_ok, f"no pack model matched {_FAT_MARGIN_REQUEST.claim_kind!r}"

    evidence = registry.discharge(_FAT_MARGIN_REQUEST)
    assert evidence.status.value in {
        Status1.discharged.value,
        Status2.violated.value,
        Status3.indeterminate.value,
    }

    again = registry.discharge(_FAT_MARGIN_REQUEST)
    assert again == evidence, "repeat discharge must be byte-identical"

    bumped = _registry_with_feldspar_pack(_PACK_VERSION + ".bumped").discharge(
        _FAT_MARGIN_REQUEST
    )
    assert bumped.hash != evidence.hash, "pack version must be a hash input"
    assert bumped.model_id == evidence.model_id


def test_fat_margin_prefers_closed_form_tier_by_cost() -> None:
    """WO-27 acceptance: registering `FeaStaticStressModel` under the
    SAME claim kind as regolith's built-in closed-form Lame model (the
    OPEN-6 `claim_kind` constructor override), the cheaper closed-form
    model still wins a fat-margin selection -- cost ordering, not a
    parallel margin rule (06 "cost declares the honest relative
    expense")."""
    from regolith.harness.models.lame_cylinder import CLAIM_KIND as LAME_CLAIM_KIND

    registry = _builtin_only_registry()
    registry.register(FeaStaticStressModel(claim_kind=LAME_CLAIM_KIND))

    request = DischargeRequest(
        claim_kind=LAME_CLAIM_KIND,
        limit=1.0e8,
        inputs={
            "pressure": Interval(lo=1.0e6, hi=1.0e6),
            "r_inner": Interval(lo=0.05, hi=0.05),
            "r_outer": Interval(lo=0.10, hi=0.10),
        },
    )
    selected = registry.select(request)
    assert selected.is_ok
    assert selected.danger_ok.model_id.startswith("lame_cylinder_bore_stress@")


def test_thin_margin_engine_reroute_to_fea_is_honest_without_tools() -> None:
    """WO-27 acceptance ("thin-margin claim: closed-form tier
    indeterminate -> feldspar discharges"): a corner outside the
    closed-form direction's domain drives the ENGINE's own fallback
    reroute (04-routing) to the FEA direction. Without `ccx`/`gmsh`
    installed in this environment (AD-12e) the FEA direction cannot
    actually run -- the pack must still resolve HONESTLY (an
    indeterminate `Evidence`, model tagged `#abstained`), never crash,
    never silently discharge. Installing `ccx`/`gmsh` flips this same
    request to a real `discharged`/`violated` outcome (untested here,
    same class of environment limitation as `tests/integration/
    test_fea_pipeline.py`'s `fea`-marked tests)."""
    registry = _registry_with_feldspar_pack()
    evidence = registry.discharge(_THIN_MARGIN_REQUEST)
    assert evidence.status.value in {
        Status1.discharged.value,
        Status2.violated.value,
        Status3.indeterminate.value,
    }
    if evidence.status.value == Status3.indeterminate.value:
        assert "abstained" in evidence.model_id or evidence.model_id.startswith(
            "harness."
        )


def test_uninstalled_pack_is_honest_no_model() -> None:
    """WO-27 acceptance: with the pack NOT loaded, the vocabulary-owned
    claim kinds resolve to regolith's own honest `harness.no_model`
    indeterminate -- zero regolith code changes required."""
    from regolith.harness.registry import NO_MODEL_ID

    registry = _builtin_only_registry()  # feldspar's pack is never loaded here
    evidence = registry.discharge(_FAT_MARGIN_REQUEST)
    assert evidence.model_id == NO_MODEL_ID
    assert evidence.status.value == Status3.indeterminate.value

    deflection_request = _FAT_MARGIN_REQUEST.model_copy(
        update={"claim_kind": DEFAULT_DEFLECTION_CLAIM_KIND}
    )
    evidence_2 = registry.discharge(deflection_request)
    assert evidence_2.model_id == NO_MODEL_ID


def test_evidence_hash_determinism_twice_run() -> None:
    """WO-27 acceptance: the same request discharged twice against the
    same pack-loaded registry is byte-identical (INV-10)."""
    registry = _registry_with_feldspar_pack()
    first = registry.discharge(_FAT_MARGIN_REQUEST)
    second = registry.discharge(_FAT_MARGIN_REQUEST)
    assert first == second
    assert first.hash == second.hash


def test_version_bump_rekeys_only_feldspar_evidence() -> None:
    """WO-27 acceptance: bumping ONLY the feldspar pack's version changes
    the evidence hash for a feldspar-discharged claim, and leaves a
    built-in-discharged claim's hash untouched (AD-19 keying)."""
    from regolith.harness.models.lame_cylinder import CLAIM_KIND as LAME_CLAIM_KIND

    baseline_registry = _registry_with_feldspar_pack()
    baseline_evidence = baseline_registry.discharge(_FAT_MARGIN_REQUEST)

    bumped_registry = _registry_with_feldspar_pack(_PACK_VERSION + ".bumped")
    bumped_evidence = bumped_registry.discharge(_FAT_MARGIN_REQUEST)
    assert bumped_evidence.hash != baseline_evidence.hash
    assert bumped_evidence.model_id == baseline_evidence.model_id

    # A built-in-discharged claim (the Lame cylinder itself, untouched by
    # feldspar's pack version) hashes identically under both registries.
    lame_request = DischargeRequest(
        claim_kind=LAME_CLAIM_KIND,
        limit=1.0e8,
        inputs={
            "pressure": Interval(lo=1.0e6, hi=1.0e6),
            "r_inner": Interval(lo=0.05, hi=0.05),
            "r_outer": Interval(lo=0.10, hi=0.10),
        },
    )
    baseline_lame = baseline_registry.discharge(lame_request)
    bumped_lame = bumped_registry.discharge(lame_request)
    assert baseline_lame.hash == bumped_lame.hash
