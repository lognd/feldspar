# feldspar.materials

Materials-science domain (T-0018, lithos design-log D270): phase
equilibria, TTT/CCT-class transformation kinetics, hardenability, and a
materials-selection solver route, over one typed record schema that
lithos stdlib material records populate (the MODEL/RECORD split, AD-37).
Every closed-form model here is a published equation with its own
citation, calibrated against independently published oracle points --
never a transcribed ASM handbook chart curve (D258/D266/D269 licensing
law). Built up slice by slice (T-0018); this doc grows one section per
landed slice.

## materials_records

<!-- frob:describes python/feldspar/materials/records.py::CrystalStructure -->
<!-- frob:describes python/feldspar/materials/records.py::Composition -->
<!-- frob:describes python/feldspar/materials/records.py::Composition.fraction_of -->
<!-- frob:describes python/feldspar/materials/records.py::MaterialRecord -->

`CrystalStructure` is typed crystal-structure data (`CrystalSystem`
scoped to BCC/FCC/HCP per the ticket's own scope line, plus lattice
parameters in meters -- HCP requires `lattice_c_m`, cubic systems
forbid it). `Composition` is alloy composition as element mass
fractions summing to at most 1.0 (the balance is the implicit
`base_element` remainder), with `fraction_of` resolving that
remainder. `MaterialRecord` composes `composition` +
`crystal_structure` + `condition` (a closed `MaterialCondition`
metallurgical-state enum) + `cost_class` (a closed `CostClass` ordinal
price tier, never a scraped vendor price -- lithos D269/D266 licensing
posture). This is the consumption contract the lithos stdlib
record-population companion ticket populates.
