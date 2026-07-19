from __future__ import annotations

"""The ONE full engine catalog composition (WO111b composition fix):
every closed-form library family plus the FEA and payload-step
directions, registered in the one canonical order, frozen.

This used to live private inside `feldspar.pack.models._engine_registry`
-- which meant the composition could only be exercised with regolith
installed, so a composition-order bug (a module declaring ports and
thereby arming the F12 guard against every LATER-registering module
whose ports were not yet declared) was invisible to the regolith-free
test suite. Extracting it here gives the composition exactly one home
(NO DUPLICATION -- `pack.models` delegates to this function verbatim)
that `tests/unit/test_catalog_composition.py` can drive without lithos.

F12 ordering rules (accumulated-port-table guard,
`solve/registry.py`):

- EVERY module in this catalog now declares its own family ports in
  its `register()` (the WO111b composition fix), so the guard is armed
  from the first registration and every later registration is checked.
- The shared cross-family mech core vocabulary
  (`mech.material.*`, `mech.geom.*`, `mech.load.*`, `mech.section.*`,
  `mech.deflection.tip`, `mech.stress.von_mises`) has its ONE
  declaration home in `feldspar.mech.closed_form.declare_core_ports`,
  which `mech.closed_form.register` calls -- and `mech.closed_form`
  registers FIRST here precisely so every later module referencing
  that vocabulary (fea, payload_steps) finds it declared. (WO-118,
  spec 12 sec. 1: this used to be `feldspar.library.mech`; the
  `feldspar.library` package now only carries compat shims.)
- Payload-port modules (`fea.payload_steps`, `fluids.network`) keep
  their established last-ish slots; their ports are disjoint from
  everything before them.

To add a NEW solver library domain (e.g. a fresh `feldspar.<domain>`
package): implement `register(registry)` (or `register(registry,
resolver)` if the domain owns payload ports, matching `fea.
payload_steps`/`fluids.network`) in that domain module, import it at
the top of `build_engine_catalog` (function-local, like every import
below, to keep this module import-cheap), and add ONE call to it in
the `registry = SolverRegistry()` .. `registry.freeze()` block below --
HERE is the one composition home (this docstring's F12 ordering rules
above govern where in the call sequence it goes). This is a distinct
seam from `feldspar.pack.register(registry)` (`pack/__init__.py`),
which registers regolith `Model` wrappers on a regolith
`ModelRegistry`, not raw `@solver` directions on this engine
`SolverRegistry`."""

from feldspar.logging_setup import get_logger
from feldspar.solve.payload import PayloadResolver
from feldspar.solve.registry import SolverRegistry

_log = get_logger(__name__)

__all__ = ["build_engine_catalog"]


# frob:doc docs/modules/top.md#top_catalog
def build_engine_catalog(resolver: PayloadResolver) -> SolverRegistry:
    """Builds and freezes the full closed-form + FEA + payload-step
    engine registry (WO-07/WO-08/WO-12 lineage). Import-cheap callers
    (FINV-3/10): the module imports below are function-local so
    importing `feldspar.catalog` (or `feldspar.pack`) never pays the
    `feldspar.fea`/`feldspar.mech`/etc. module-load cost until a catalog
    is actually built; building one only adds Python-side metadata (no
    gmsh/ccx probing until a route executes)."""
    from feldspar.elec.signal_integrity import register as register_signal_integrity
    from feldspar.fea import payload_steps
    from feldspar.fea.solver import register as register_fea
    from feldspar.fluids import register as register_fluids
    from feldspar.fluids import register_network as register_fluids_network
    from feldspar.heat.closed_form import register as register_heat
    from feldspar.heat.thermal_transient import register as register_thermal
    from feldspar.mech.bearing_life import register as register_bearing_life
    from feldspar.mech.bolted_joints import register as register_bolted_joints
    from feldspar.mech.closed_form import register as register_mech
    from feldspar.mech.critical_speed import register as register_critical_speed
    from feldspar.mech.drive import register as register_drive
    from feldspar.mech.fatigue import register as register_fatigue
    from feldspar.mech.leadscrew import register as register_leadscrew
    from feldspar.mech.member_capacity import register as register_member_capacity
    from feldspar.mech.plate import register as register_plate
    from feldspar.mech.weld_groups import register as register_weld_groups
    from feldspar.thermo.properties import register as register_thermo

    registry = SolverRegistry()
    # library.mech FIRST: `declare_core_ports` (the shared mech core
    # vocabulary's one home) must land before any module referencing it
    # registers -- see this module's docstring.
    register_mech(registry)
    register_member_capacity(registry)
    register_bolted_joints(registry)
    register_weld_groups(registry)
    register_bearing_life(registry)
    register_fatigue(registry, resolver)
    register_leadscrew(registry)
    register_critical_speed(registry)
    register_drive(registry)
    register_plate(registry)
    register_signal_integrity(registry)
    register_fluids(registry)
    register_heat(registry)
    register_thermal(registry)
    register_thermo(registry)
    register_fea(registry)
    payload_steps.register(registry, resolver)
    # The Hardy-Cross `flownet` solver declares its own payload ports
    # (F12), disjoint from everything above; last by the established
    # WO-20 convention.
    register_fluids_network(registry, resolver)
    registry.freeze()
    _log.info(
        "engine catalog built: %d solvers, %d ports",
        sum(1 for _ in registry),
        len(registry.port_table()),
    )
    return registry
