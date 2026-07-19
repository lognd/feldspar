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

## materials_kinetics

<!-- frob:describes python/feldspar/materials/kinetics.py::koistinen_marburger_martensite_fraction -->
<!-- frob:describes python/feldspar/materials/kinetics.py::kirkaldy_diffusional_onset_time -->
<!-- frob:describes python/feldspar/materials/kinetics.py::grange_kiefer_ms_shift -->
<!-- frob:describes python/feldspar/materials/kinetics.py::register -->

Transformation-kinetics closed forms: `koistinen_marburger_martensite_fraction`
(Koistinen & Marburger 1959, `f = 1 - exp(-alpha*(Ms - T))` for `T <=
Ms`, athermal martensite fraction; `alpha` caller-supplied);
`kirkaldy_diffusional_onset_time` (the Kirkaldy/Li-family diffusional
TTT-onset shared Avrami-nucleation Arrhenius form, `t_onset = t0 *
exp(Q/(R*T))`, `t0`/`Q` caller-supplied already-fitted constants --
transcribing Kirkaldy/Li's own multi-element regression coefficients
from memory is a named cut); `grange_kiefer_ms_shift` (Grange & Kiefer
1941's linear-additive Ms depression, `Ms(alloyed) = Ms(base) -
depression`, `depression` composed by the caller from Grange & Kiefer's
own per-element table). Every direction's calibration test is a
hand-computed check of its own cited closed form (the `mech.fatigue`
Shigley-eq calibration convention); each docstring records where an
independent second-source oracle point was not located this dispatch
(named residual). `register(registry)` registers the family.
