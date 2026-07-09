from __future__ import annotations

"""WO-08 tests: `fea/solver.py`'s settings_digest fold (FINV-2), the
`register()` wiring, and the without-gmsh/ccx `ToolMissing` degrade path
(acceptance bar: "without gmsh/ccx: solve attempts return ToolMissing,
never raise")."""

from feldspar.fea.mesh import MeshSettings
from feldspar.fea.solver import (
    SolveSettings,
    ToolVersions,
    _fold_settings_digest,
    register,
)
from feldspar.solve import SolverRegistry
from feldspar.solve.errors import SolveError

_MESH_H = MeshSettings(family="cantilever", element_type="C3D20", char_length=0.02)
_MESH_H2 = MeshSettings(family="cantilever", element_type="C3D20", char_length=0.01)
_SETTINGS = SolveSettings()
_TOOL_VERSIONS = ToolVersions(
    gmsh_version="unknown", ccx_version="unknown", feldspar_version="0.1.0"
)


def _base_digest() -> str:
    return _fold_settings_digest(_MESH_H, _MESH_H2, _SETTINGS, _TOOL_VERSIONS)


def test_timeout_s_not_a_settings_field() -> None:
    assert "timeout_s" not in SolveSettings.model_fields


def test_fold_changes_when_mesh_h_char_length_changes() -> None:
    other = MeshSettings(family="cantilever", element_type="C3D20", char_length=0.03)
    assert (
        _fold_settings_digest(other, _MESH_H2, _SETTINGS, _TOOL_VERSIONS)
        != _base_digest()
    )


def test_fold_changes_when_mesh_h2_char_length_changes() -> None:
    other = MeshSettings(family="cantilever", element_type="C3D20", char_length=0.005)
    assert (
        _fold_settings_digest(_MESH_H, other, _SETTINGS, _TOOL_VERSIONS)
        != _base_digest()
    )


def test_fold_changes_when_mesh_h_family_changes() -> None:
    other = MeshSettings(family="cylinder", element_type="C3D20", char_length=0.02)
    assert (
        _fold_settings_digest(other, _MESH_H2, _SETTINGS, _TOOL_VERSIONS)
        != _base_digest()
    )


def test_fold_changes_when_mesh_h_element_type_changes() -> None:
    other = MeshSettings(family="cantilever", element_type="CAX8", char_length=0.02)
    assert (
        _fold_settings_digest(other, _MESH_H2, _SETTINGS, _TOOL_VERSIONS)
        != _base_digest()
    )


def test_fold_changes_when_mesh_h_algorithm_id_changes() -> None:
    other = MeshSettings(
        family="cantilever", element_type="C3D20", char_length=0.02, algorithm_id=2
    )
    assert (
        _fold_settings_digest(other, _MESH_H2, _SETTINGS, _TOOL_VERSIONS)
        != _base_digest()
    )


def test_fold_changes_when_mesh_h_seed_changes() -> None:
    other = MeshSettings(
        family="cantilever", element_type="C3D20", char_length=0.02, seed=7
    )
    assert (
        _fold_settings_digest(other, _MESH_H2, _SETTINGS, _TOOL_VERSIONS)
        != _base_digest()
    )


def test_fold_changes_when_omp_num_threads_changes() -> None:
    other = SolveSettings(omp_num_threads=4)
    assert (
        _fold_settings_digest(_MESH_H, _MESH_H2, other, _TOOL_VERSIONS)
        != _base_digest()
    )


def test_fold_changes_when_gmsh_version_changes() -> None:
    other = ToolVersions(
        gmsh_version="4.11", ccx_version="unknown", feldspar_version="0.1.0"
    )
    assert _fold_settings_digest(_MESH_H, _MESH_H2, _SETTINGS, other) != _base_digest()


def test_fold_changes_when_ccx_version_changes() -> None:
    other = ToolVersions(
        gmsh_version="unknown", ccx_version="2.20", feldspar_version="0.1.0"
    )
    assert _fold_settings_digest(_MESH_H, _MESH_H2, _SETTINGS, other) != _base_digest()


def test_fold_changes_when_feldspar_version_changes() -> None:
    other = ToolVersions(
        gmsh_version="unknown", ccx_version="unknown", feldspar_version="9.9.9"
    )
    assert _fold_settings_digest(_MESH_H, _MESH_H2, _SETTINGS, other) != _base_digest()


def test_fold_deterministic_for_identical_inputs() -> None:
    assert _base_digest() == _base_digest()


def test_register_succeeds_on_fresh_registry() -> None:
    registry = SolverRegistry()
    register(registry)
    registry.freeze()
    solver_ids = {info.solver_id: info for info, _fn in registry}
    assert "fea.static_deflection.cantilever" in solver_ids
    assert "fea.static_stress.cylinder_bore" in solver_ids
    assert solver_ids["fea.static_deflection.cantilever"].tier == "discretized"
    assert solver_ids["fea.static_stress.cylinder_bore"].tier == "discretized"


def test_cantilever_returns_tool_missing_without_gmsh_ccx() -> None:
    registry = SolverRegistry()
    register(registry)
    registry.freeze()
    fns = {info.solver_id: fn for info, fn in registry}
    fn = fns["fea.static_deflection.cantilever"]

    result = fn(
        {
            "mech.geom.cantilever.length": 0.5,
            "mech.geom.cantilever.width": 0.04,
            "mech.geom.cantilever.height": 0.06,
            "mech.material.youngs_modulus": 7e10,
            "mech.material.poisson": 0.33,
            "mech.load.tip_force": 1000.0,
        }
    )
    assert result.is_err
    error = result.danger_err
    assert isinstance(error, SolveError)
    assert error.kind == "ToolMissing"


def test_cylinder_bore_returns_tool_missing_without_gmsh_ccx() -> None:
    registry = SolverRegistry()
    register(registry)
    registry.freeze()
    fns = {info.solver_id: fn for info, fn in registry}
    fn = fns["fea.static_stress.cylinder_bore"]

    result = fn(
        {
            "mech.load.internal_pressure": 1e6,
            "mech.geom.cylinder.inner_radius": 0.05,
            "mech.geom.cylinder.outer_radius": 0.08,
            "mech.material.youngs_modulus": 7e10,
            "mech.material.poisson": 0.33,
        }
    )
    assert result.is_err
    error = result.danger_err
    assert isinstance(error, SolveError)
    assert error.kind == "ToolMissing"
