from __future__ import annotations

"""The material record schema (T-0018 slice 1, lithos design-log D270
ruling 1: "feldspar gets the MODELS ... lithos stdlib gets the
RECORDS"). This module defines the typed shape lithos stdlib material
records must satisfy -- composition, crystal structure, condition/
state, and cost class -- so every downstream model in this package
(kinetics.py, hardenability.py, phase_equilibria.py, selection.py)
consumes one schema, never a bespoke dict shape per model (NO
DUPLICATION). Frozen pydantic models, same convention as
`feldspar.solve._models.Citation`/`feldspar.calib._models.CalibRecord`.

Crystal structure is scoped to BCC/FCC/HCP (the ticket's own scope
line) -- other Bravais lattices are a named cut; a caller needing them
extends `CrystalSystem` and `CrystalStructure.lattice_c_m`'s validity
note, not this module inventing an unrequested system.

Cost enters as a CLASS (ordinal tier), never a scraped vendor price
(lithos D269/D266 licensing posture: public-domain price CLASSES only,
e.g. USGS Mineral Commodity Summaries tiers) -- `CostClass` is a
closed Literal set, not a float."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

__all__ = [
    "CrystalSystem",
    "CrystalStructure",
    "Composition",
    "MaterialCondition",
    "CostClass",
    "MaterialRecord",
]

#: Scoped Bravais-lattice families (ticket scope: "BCC/FCC/HCP" only;
#: other systems are a named cut, not silently guessed).
CrystalSystem = Literal["BCC", "FCC", "HCP"]

#: Metallurgical condition/state a `MaterialRecord` is evaluated at.
#: Closed set matching the transformation-kinetics/hardenability
#: models this package implements (kinetics.py/hardenability.py) --
#: a condition this package cannot model is a named refusal at the
#: solver layer, not a silently-accepted enum value here.
MaterialCondition = Literal[
    "as_cast",
    "wrought",
    "annealed",
    "normalized",
    "as_quenched",
    "quenched_and_tempered",
    "case_hardened",
]

#: Ordinal price CLASS (lithos D269 ruling 2 / D266 licensing posture:
#: cost enters as a cited public-domain CLASS, e.g. USGS Mineral
#: Commodity Summaries tiers, never a scraped vendor quote or a bare
#: float price). "specialty" covers refractory/precious/rare-earth
#: bearing alloys the commodity-tier classes do not reach.
CostClass = Literal["low", "medium", "high", "specialty"]


# frob:doc docs/modules/materials.md#materials_records
class CrystalStructure(BaseModel):
    """Typed crystal structure: a `CrystalSystem` plus its lattice
    parameter(s) in meters -- carried by the record, never guessed
    from composition by this package (the ticket's own "as typed
    data ... not guessed" line). `lattice_c_m` is required for HCP
    (c/a ratio matters for its anisotropic slip systems) and must be
    omitted for BCC/FCC (cubic: one parameter fully determines the
    cell)."""

    model_config = ConfigDict(frozen=True)

    system: CrystalSystem
    lattice_a_m: float
    lattice_c_m: float | None = None

    @field_validator("lattice_a_m")
    @classmethod
    def _positive_a(cls, value: float) -> float:
        if value <= 0.0:
            raise ValueError(f"lattice_a_m must be positive, got {value!r}")
        return value

    @model_validator(mode="after")
    def _c_matches_system(self) -> "CrystalStructure":
        if self.system == "HCP" and self.lattice_c_m is None:
            raise ValueError("HCP crystal structure requires lattice_c_m")
        if self.system != "HCP" and self.lattice_c_m is not None:
            raise ValueError(
                f"lattice_c_m is only meaningful for HCP, not {self.system}"
            )
        if self.lattice_c_m is not None and self.lattice_c_m <= 0.0:
            raise ValueError(f"lattice_c_m must be positive, got {self.lattice_c_m!r}")
        return self


# frob:doc docs/modules/materials.md#materials_records
class Composition(BaseModel):
    """Alloy composition as element mass fractions (`{"Fe": 0.98,
    "C": 0.004, ...}`, dimensionless, sums to <= 1.0 -- the balance is
    implicitly the `base_element` where fractions do not sum to
    exactly 1.0, matching how published steel/alloy specs quote minor
    alloying elements and leave Fe as remainder)."""

    model_config = ConfigDict(frozen=True)

    base_element: str
    mass_fractions: dict[str, float]

    @field_validator("mass_fractions")
    @classmethod
    def _fractions_in_range(cls, value: dict[str, float]) -> dict[str, float]:
        for element, fraction in value.items():
            if not (0.0 <= fraction <= 1.0):
                raise ValueError(
                    f"mass fraction for {element!r} out of [0,1]: {fraction!r}"
                )
        total = sum(value.values())
        if total > 1.0 + 1e-6:
            raise ValueError(f"mass fractions sum to {total!r} > 1.0")
        return value

    # frob:doc docs/modules/materials.md#materials_records
    def fraction_of(self, element: str) -> float:
        """Returns the mass fraction of `element`, or the implicit
        `base_element` remainder (`1.0 - sum(others)`) if `element`
        equals `base_element` and is not itself listed."""
        if element in self.mass_fractions:
            return self.mass_fractions[element]
        if element == self.base_element:
            return max(0.0, 1.0 - sum(self.mass_fractions.values()))
        return 0.0


# frob:doc docs/modules/materials.md#materials_records
class MaterialRecord(BaseModel):
    """The full typed record a lithos stdlib material entry populates
    and every model in this package consumes: `composition` +
    `crystal_structure` + `condition` (metallurgical state) +
    `cost_class` (cited public-domain price tier). This is the MODEL
    half's consumption contract (T-0018); the lithos stdlib
    record-population ticket (companion, D270 ruling 4) is responsible
    for citing and populating instances of this shape."""

    model_config = ConfigDict(frozen=True)

    name: str
    composition: Composition
    crystal_structure: CrystalStructure
    condition: MaterialCondition
    cost_class: CostClass
