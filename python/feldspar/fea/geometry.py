from __future__ import annotations

"""Cantilever/cylinder geometry and material data models (WO-08).

Plain, IO-free pydantic models describing the two supported FEA
families (cantilever box, thick-wall cylinder) and the linear-elastic
material they are meshed with. Field names are plain domain names, not
port strings -- the port-string <-> field mapping lives only in
solver.py, mirroring how python/feldspar/library/mech.py unpacks
`x["mech.load..."]` at its own boundary. No gmsh/ccx import here."""

from pydantic import BaseModel, ConfigDict

__all__ = ["Material", "CantileverGeometry", "CylinderGeometry"]


class Material(BaseModel):
    """Linear-elastic isotropic material properties (SI units)."""

    model_config = ConfigDict(frozen=True)

    youngs_modulus: float  # Pa
    poisson: float  # dimensionless
    yield_strength: float  # Pa


class CantileverGeometry(BaseModel):
    """Rectangular-box cantilever dimensions (SI units)."""

    model_config = ConfigDict(frozen=True)

    length: float  # m
    width: float  # m
    height: float  # m


class CylinderGeometry(BaseModel):
    """Thick-wall axisymmetric cylinder dimensions (SI units)."""

    model_config = ConfigDict(frozen=True)

    inner_radius: float  # m
    outer_radius: float  # m
    length: float  # m (axial length, axisymmetric r-z rectangle)
