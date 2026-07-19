from __future__ import annotations

"""T-0018 slice 1 tests: the material record schema
(`python/feldspar/materials/records.py`) -- crystal-structure typing,
composition mass-fraction validation, and the full `MaterialRecord`
composition every downstream model (kinetics/hardenability/phase_
equilibria/selection) consumes."""

import pytest
from pydantic import ValidationError

from feldspar.materials.records import (
    Composition,
    CrystalStructure,
    MaterialRecord,
)


# frob:tests python/feldspar/materials/records.py::CrystalStructure kind="unit"
def test_crystal_structure_bcc_rejects_lattice_c():
    with pytest.raises(ValidationError):
        CrystalStructure(system="BCC", lattice_a_m=2.866e-10, lattice_c_m=1.0e-10)


# frob:tests python/feldspar/materials/records.py::CrystalStructure kind="unit"
def test_crystal_structure_hcp_requires_lattice_c():
    with pytest.raises(ValidationError):
        CrystalStructure(system="HCP", lattice_a_m=2.95e-10)


# frob:tests python/feldspar/materials/records.py::CrystalStructure kind="unit"
def test_crystal_structure_hcp_accepts_both_params():
    # alpha-Ti: a = 2.95 Angstrom, c = 4.68 Angstrom (c/a ~ 1.587).
    structure = CrystalStructure(
        system="HCP", lattice_a_m=2.95e-10, lattice_c_m=4.68e-10
    )
    assert structure.system == "HCP"


# frob:tests python/feldspar/materials/records.py::CrystalStructure kind="unit"
def test_crystal_structure_rejects_nonpositive_lattice_a():
    with pytest.raises(ValidationError):
        CrystalStructure(system="FCC", lattice_a_m=0.0)


# frob:tests python/feldspar/materials/records.py::Composition kind="unit"
def test_composition_fraction_of_resolves_base_remainder():
    comp = Composition(base_element="Fe", mass_fractions={"C": 0.004, "Mn": 0.007})
    assert comp.fraction_of("C") == pytest.approx(0.004)
    assert comp.fraction_of("Fe") == pytest.approx(1.0 - 0.004 - 0.007)
    assert comp.fraction_of("Cr") == 0.0


# frob:tests python/feldspar/materials/records.py::Composition kind="unit"
def test_composition_rejects_fractions_summing_over_one():
    with pytest.raises(ValidationError):
        Composition(base_element="Fe", mass_fractions={"C": 0.6, "Mn": 0.6})


# frob:tests python/feldspar/materials/records.py::Composition kind="unit"
def test_composition_rejects_out_of_range_fraction():
    with pytest.raises(ValidationError):
        Composition(base_element="Fe", mass_fractions={"C": 1.5})


# frob:tests python/feldspar/materials/records.py::MaterialRecord kind="unit"
# frob:tests python/feldspar/materials kind="integration"
def test_material_record_full_composition_is_frozen():
    """Integration exercise of the full record shape end to end:
    composition + crystal structure + condition + cost class compose
    into one frozen `MaterialRecord`, the consumption contract every
    downstream materials model (kinetics/hardenability/phase_
    equilibria/selection) relies on."""
    record = MaterialRecord(
        name="AISI 1045",
        composition=Composition(base_element="Fe", mass_fractions={"C": 0.0045}),
        crystal_structure=CrystalStructure(system="BCC", lattice_a_m=2.866e-10),
        condition="as_quenched",
        cost_class="low",
    )
    assert record.condition == "as_quenched"
    assert record.composition.fraction_of("Fe") == pytest.approx(1.0 - 0.0045)
    with pytest.raises(ValidationError):
        record.cost_class = "high"  # frozen model, ty: ignore[unresolved-attribute]
