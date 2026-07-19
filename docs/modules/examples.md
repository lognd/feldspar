# examples

Runnable example scripts: the top-level `examples/*.py` walk the
register -> solve -> explain / FEA / regolith-pack-discharge happy
paths end to end; `examples/solvers/*.py` are the DX "complexity rung"
ladder (00 raw protocol through 06 coupled groups), each demonstrating
exactly one settled solver-authoring ergonomics tier and the tier
below/above it in the spec's registration-ergonomics design (03).

## examples_top

<!-- frob:describes examples/01_register_and_solve.py::ideal_gas_pv_to_t -->
<!-- frob:describes examples/01_register_and_solve.py::main -->
<!-- frob:describes examples/02_tier_competition.py::lame_chart -->
<!-- frob:describes examples/02_tier_competition.py::lame_exact -->
<!-- frob:describes examples/02_tier_competition.py::main -->
<!-- frob:describes examples/03_fea_cantilever.py::main -->
<!-- frob:describes examples/04_pack_discharge.py::main -->

Top-level example scripts, each a TARGET-API sketch pressure-testing
the spec end to end. `01_register_and_solve.py` is the minimal happy
path: register a closed-form solver (`ideal_gas_pv_to_t`), solve,
explain (`main` runs it). `02_tier_competition.py` shows two tiers on
one port -- a cheap-but-sloppy table solver (`lame_chart`) and a
costly-but-tight closed form (`lame_exact`) both producing
`mech.stress.von_mises`; `main` demonstrates budget-driven tier
selection and fallback rerouting on a killed winner (04). `03_fea_
cantilever.py`'s `main` runs the registered FEA direction with the
same call shape as example 01, at a higher (discretized) tier,
demonstrating a measured Richardson eps and a cache hit on rerun.
`04_pack_discharge.py`'s `main` shows the regolith seam: what feldspar
looks like from the host side (requires the `regolith` extra), using
`DEFAULT_DEFLECTION_CLAIM_KIND` from `feldspar.pack.models`. `R_AIR`
(01), `COMMON` (02), and `EPS_BUDGET` (03) are each script's shared
setup constants (the ideal-gas constant, the two competing solvers'
common registration kwargs, and the requested eps budget,
respectively).

## examples_solvers

<!-- frob:describes examples/solvers/00_raw_protocol.py::rect_second_moment -->
<!-- frob:describes examples/solvers/00_raw_protocol.py::register -->
<!-- frob:describes examples/solvers/01_sugar_coercions.py::rect_second_moment -->
<!-- frob:describes examples/solvers/01_sugar_coercions.py::register -->
<!-- frob:describes examples/solvers/02_relations.py::t_from_pv -->
<!-- frob:describes examples/solvers/02_relations.py::p_from_tv -->
<!-- frob:describes examples/solvers/02_relations.py::v_from_tp -->
<!-- frob:describes examples/solvers/02_relations.py::register -->
<!-- frob:describes examples/solvers/03_tables_correlations.py::register -->
<!-- frob:describes examples/solvers/04_families.py::register -->
<!-- frob:describes examples/solvers/05_expensive_and_abstraction.py::fea_cantilever_tip -->
<!-- frob:describes examples/solvers/05_expensive_and_abstraction.py::flange_as_cantilever -->
<!-- frob:describes examples/solvers/06_coupled_groups.py::register -->

The DX "complexity rung" ladder (registration ergonomics, spec 03),
each script a `register(registry)` demonstrating exactly one settled
tier: **rung 0** (`00_raw_protocol.py`) is the raw `@solver` protocol
with zero conveniences (`rect_second_moment`, the BASELINE every sugar
proposal is measured against). **Rung 1** (`01_sugar_coercions.py`,
F11/F10/F13 DX-SETTLED) is the same formula with every settled
convenience (domain tuples, citation strings, auto-`Ok` wrapping),
digest-equal to rung 0's registration. **Rung 2**
(`02_relations.py`, F7) is the `Relation` builder: one physical law
(`t_from_pv`/`p_from_tv`/`v_from_tp`), N searchable directions, shared
metadata declared once. **Rung 3** (`03_tables_correlations.py`, F8)
is `table_solver_1d/2d` and `Correlation` -- data/published-formula in,
solver out, citation and accuracy band as one object. **Rung 4**
(`04_families.py`, F9) is the plain-factory pattern for near-identical
solver families (a function returning `(SolverInfo, SolveFn)` plus a
loop). **Rung 5** (`05_expensive_and_abstraction.py`) shows two
patterns that must stay on the same protocol: a settings-closure
subprocess solver (`fea_cantilever_tip`, F1) and an abstraction edge
(`flange_as_cantilever`, G1: geometry payload -> family scalars).
**Rung 6** (`06_coupled_groups.py`, G22) is `CoupledGroup` for genuine
two-way physical coupling (e.g. a regen-cooling jacket's hot-gas <->
wall <-> coolant loop) that no DAG edge ordering can express. `PORTS`
(01), `SHAPES` (04), `MESH` (05), and `R` (02) are each script's shared
setup constants (the port-name table, the section-shape family list,
the mesh-settings fixture, and the ideal-gas constant, respectively).
