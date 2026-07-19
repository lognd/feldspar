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

## materials_hardenability

<!-- frob:describes python/feldspar/materials/hardenability.py::grossmann_ideal_critical_diameter -->
<!-- frob:describes python/feldspar/materials/hardenability.py::jominy_distance_to_cooling_rate -->
<!-- frob:describes python/feldspar/materials/hardenability.py::hollomon_jaffe_tempering_parameter -->
<!-- frob:describes python/feldspar/materials/hardenability.py::register -->

Hardenability closed forms: `grossmann_ideal_critical_diameter`
(Grossmann 1942, `D_I = base_diameter * multiplying_factor`, both
caller-supplied -- Grossmann's own base-carbon curve and per-element
multiplying-factor tables are a named cut, transcribing them being the
exact licensing risk this ticket flags); `jominy_distance_to_cooling_
rate` (the Jominy/ASTM A255 end-quench mid-bar power-law correlation,
`cooling_rate = coeff * distance^exponent`, `coeff`/`exponent` caller-
fitted); `hollomon_jaffe_tempering_parameter` (Hollomon & Jaffe 1945,
`P = T*(C + log10(t))`, `C` caller-supplied). Each calibration test is
a hand-computed check of its own cited closed form; each docstring
records where an independent second-source oracle point was not
located this dispatch (named residual). `register(registry)` registers
the family.

## materials_phase_equilibria

<!-- frob:describes python/feldspar/materials/phase_equilibria.py::lever_rule_phase_fraction -->
<!-- frob:describes python/feldspar/materials/phase_equilibria.py::regular_solution_binary_free_energy -->
<!-- frob:describes python/feldspar/materials/phase_equilibria.py::register -->

Binary phase-equilibria closed forms: `lever_rule_phase_fraction` (the
lever rule over a two-phase tie line -- phase-boundary compositions and
overall composition are all RECORD INPUTS, refusing when the overall
composition is not between the boundaries or the boundaries coincide);
`regular_solution_binary_free_energy` (the regular-solution binary
Gibbs free-energy-of-mixing model, `dG_mix = R*T*(x*ln(x) +
(1-x)*ln(1-x)) + Omega*x*(1-x)`, `Omega` caller-supplied -- the honest
CALPHAD-lite tier this ticket scopes; full sublattice CALPHAD
assessment is a named cut). `register(registry)` registers the family.
