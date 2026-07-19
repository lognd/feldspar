from __future__ import annotations

"""WO111b composition-order regression test: build the FULL engine
catalog through the exact code path `feldspar.pack` uses
(`feldspar.catalog.build_engine_catalog` -- `pack.models.
_engine_registry` is a thin delegate) and assert every expected
direction registered.

WHY THIS TEST EXISTS (the bug it would have caught): `solve/
registry.py`'s F12 guard is armed by the FIRST `declare_ports()` call
-- from then on every later `register()` in the same registry is
checked against the accumulated port table. A module that declares
its ports and registers EARLY in the catalog therefore refuses every
later-registering module whose ports are not yet declared
(`RegistryError.UnknownPort`). That failure only manifested when the
full catalog was composed -- which previously happened ONLY inside
`feldspar.pack` (regolith-marked tests, skipped without a lithos
checkout), so per-module unit tests all stayed green while the
composition was broken. This test composes the full catalog with no
regolith anywhere near it."""

import hashlib
from typing import Dict

import pytest
from typani import Err, Ok

from feldspar.catalog import build_engine_catalog
from feldspar.solve import PayloadRef, SolveError

# The full expected catalog, sorted (83 directions as of WO111b). This
# list is deliberately a LITERAL: a direction silently dropped by a
# composition-order regression (rather than a crash) still fails the
# comparison, and a new direction landing is forced to update the
# expectation consciously.
EXPECTED_SOLVER_IDS = [
    "elec.si.ac_shunt_sizing_c",
    "elec.si.ac_shunt_sizing_r",
    "elec.si.microstrip_z0",
    "elec.si.series_termination",
    "elec.si.stripline_z0",
    "elec.si.thevenin_termination_r1",
    "elec.si.thevenin_termination_r2",
    "fea.mesh.cantilever",
    "fea.static_deflection.cantilever",
    "fea.static_deflection.cantilever_from_mesh",
    "fea.static_stress.cylinder_bore",
    "fluids.colebrook_friction_factor",
    "fluids.darcy_dp",
    "fluids.fanno_function",
    "fluids.haaland_friction_factor",
    "fluids.isentropic_stagnation_pressure_ratio",
    "fluids.isentropic_stagnation_temp_ratio",
    "fluids.joukowsky_dp",
    "fluids.laminar_friction_factor",
    "fluids.minor_loss_dp",
    "fluids.network.hardy_cross",
    "fluids.normal_shock_mach2",
    "fluids.normal_shock_pressure_ratio",
    "fluids.npsh_available",
    "fluids.parallel_flow",
    "fluids.pump_operating_flow",
    "fluids.pump_operating_head",
    "fluids.series_dp",
    "heat.coefficient_from_nusselt",
    "heat.convection_resistance",
    "heat.cylindrical_wall_resistance",
    "heat.dittus_boelter_nusselt_heating",
    "heat.plane_wall_resistance",
    "heat.rate_from_resistance",
    "heat.series_resistance",
    "heat.transient.biot_number_from_convection",
    "heat.transient.duty_cycle_peak_temperature",
    "heat.transient.step_temperature",
    "heat.transient.time_to_threshold",
    "materials.hardenability.grossmann_ideal_critical_diameter",
    "materials.hardenability.hollomon_jaffe_tempering_parameter",
    "materials.hardenability.jominy_distance_to_cooling_rate",
    "materials.kinetics.grange_kiefer_ms_shift",
    "materials.kinetics.kirkaldy_diffusional_onset_time",
    "materials.kinetics.koistinen_marburger_martensite_fraction",
    "mech.bearing.bearing_basic_rating_life_l10_ball",
    "mech.bearing.bearing_basic_rating_life_l10_roller",
    "mech.bearing.bearing_basic_rating_life_l10h",
    "mech.bore_von_mises",
    "mech.cantilever_required_youngs_modulus",
    "mech.cantilever_tip_deflection",
    "mech.critical_speed.shaft_critical_speed_from_stiffness",
    "mech.critical_speed.shaft_critical_speed_rayleigh_single_mass",
    "mech.drive.drive_acceleration_torque",
    "mech.drive.leadscrew_collar_torque",
    "mech.drive.leadscrew_efficiency",
    "mech.drive.leadscrew_self_locking_margin",
    "mech.drive.leadscrew_torque_lower",
    "mech.drive.leadscrew_torque_raise",
    "mech.fatigue.fatigue_endurance_limit_baseline",
    "mech.fatigue.fatigue_gerber_factor_of_safety",
    "mech.fatigue.fatigue_goodman_factor_of_safety",
    "mech.fatigue.fatigue_marin_endurance_limit",
    "mech.fatigue.fatigue_marin_surface_factor",
    "mech.fatigue.fatigue_sn_cycles_to_failure",
    "mech.fatigue.miner_damage",
    "mech.joint.bolt_group_shear_torsion",
    "mech.joint.bolt_group_tension_from_moment",
    "mech.joint.bolt_single_load_factor_vdi2230",
    "mech.member.axial_yield_buckling_capacity_e3",
    "mech.member.euler_critical_buckling_load",
    "mech.member.flexural_yield_capacity_f2",
    "mech.plate.plate_circular_uniform_clamped_max_deflection",
    "mech.plate.plate_circular_uniform_clamped_max_stress",
    "mech.plate.plate_circular_uniform_ss_max_deflection",
    "mech.plate.plate_circular_uniform_ss_max_stress",
    "mech.rect_second_moment",
    "mech.weld.weld_group_inplane_shear_torsion",
    "mech.weld.weld_group_outofplane_bending",
    "mech.weld.weld_group_utilization",
    "thermo.air_density",
    "thermo.air_specific_heat_cp",
    "thermo.air_viscosity",
    "thermo.nitrogen_density",
    "thermo.nitrogen_specific_heat_cp",
    "thermo.nitrogen_viscosity",
    "thermo.water_density",
    "thermo.water_specific_heat_cp",
    "thermo.water_viscosity",
]


class DictResolver:
    """In-memory orchestrator store stand-in (D96/OPEN-2 handle);
    mirrors `tests/unit/test_library_struct.py`'s fixture verbatim."""

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


# frob:tests python/feldspar/catalog.py kind="integration"
# frob:waive PERF004 reason="false positive: frob's PERF004 loop-gate is function-scoped (any earlier top-level for/while anywhere in the function triggers it -- see _loop_gate in frob's perf/_rules.py), not true AST containment. `sorted(info.solver_id for info, _fn in registry)` runs once, after this test's other assertions; there is no repeated per-iteration sort to hoist."
def test_full_catalog_composes_with_every_direction_registered():
    """The pack's exact composition path succeeds end-to-end: every
    module's `register()` lands every direction (each register()
    internally asserts `danger_ok`, so an `UnknownPort`/duplicate/
    conflict refusal crashes this test with the refusing error) and
    the frozen registry's id set matches the literal expectation."""
    registry = build_engine_catalog(DictResolver())
    assert registry.is_frozen()
    got = sorted(info.solver_id for info, _fn in registry)
    assert got == EXPECTED_SOLVER_IDS


def test_full_catalog_ports_are_fully_declared():
    """WO111b invariant: the composed catalog declares EVERY port any
    registered direction touches (the F12 guard is armed from the
    first module, so this is what makes the composition order-safe
    rather than order-lucky)."""
    registry = build_engine_catalog(DictResolver())
    table = registry.port_table()
    missing = set()
    for info, _fn in registry:
        for port in (*info.inputs, *info.outputs, *info.domain.box.keys()):
            if port not in table:
                missing.add((info.solver_id, port))
    assert not missing, f"undeclared ports referenced by the catalog: {sorted(missing)}"


# frob:tests python/feldspar/catalog.py::build_engine_catalog kind="unit"
def test_full_catalog_is_deterministic():
    """Two builds digest identically (FINV-1 at the composition
    level)."""
    a = build_engine_catalog(DictResolver())
    b = build_engine_catalog(DictResolver())
    assert a.digest() == b.digest()


def test_catalog_rejects_after_freeze():
    """The composed catalog is frozen -- a stray post-composition
    registration is refused, not silently accepted."""
    registry = build_engine_catalog(DictResolver())
    result = registry.declare_ports()
    assert result.is_err
    assert result.danger_err.kind == "Frozen"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
