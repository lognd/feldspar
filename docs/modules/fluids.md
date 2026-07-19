# feldspar.fluids

Fluid-mechanics closed-form solver directions (WO-20), split by regime:
`incompressible` (internal flow, pipe networks, turbomachinery, water
hammer), `compressible` (isentropic relations, normal shocks, the Fanno
function), and `network` (the Hardy-Cross flownet-payload solver).

## fluids_init

<!-- frob:describes python/feldspar/fluids/__init__.py::register -->
<!-- frob:describes python/feldspar/fluids/__init__.py::register_network -->

`register(registry)` composes both regimes (incompressible +
compressible) so `from feldspar.fluids import register` works as one
call. `register_network(registry, resolver)` is kept separate (not
folded into `register`) because `network` declares payload ports (F12)
and needs a `PayloadResolver`, following `feldspar.fea.payload_steps`'s
convention: the catalog loader calls it LAST, after every declaration-
free module.

## fluids_compressible

<!-- frob:describes python/feldspar/fluids/compressible.py::isentropic_stagnation_temp_ratio -->
<!-- frob:describes python/feldspar/fluids/compressible.py::isentropic_stagnation_pressure_ratio -->
<!-- frob:describes python/feldspar/fluids/compressible.py::normal_shock_mach2 -->
<!-- frob:describes python/feldspar/fluids/compressible.py::normal_shock_pressure_ratio -->
<!-- frob:describes python/feldspar/fluids/compressible.py::fanno_function -->
<!-- frob:describes python/feldspar/fluids/compressible.py::register -->

Compressible fluid-mechanics closed-form solver directions (D141): pure
marshalling over `feldspar._feldspar.fluids_*` (NO DUPLICATION), each
declaring `accuracy=EXACT` since the model itself is the contract.
`isentropic_stagnation_temp_ratio`/`_pressure_ratio` are the isentropic
relations; `normal_shock_mach2`/`_pressure_ratio` are the normal-shock
jump conditions; `fanno_function` is the Fanno-flow relation. Registered
under the same `fluids` namespace as the incompressible entries,
distinguished by `Domain.tags` ("compressible" vs "incompressible").
`register(registry)` registers the family.

## fluids_incompressible

<!-- frob:describes python/feldspar/fluids/incompressible.py::laminar_friction_factor -->
<!-- frob:describes python/feldspar/fluids/incompressible.py::colebrook_friction_factor -->
<!-- frob:describes python/feldspar/fluids/incompressible.py::haaland_friction_factor -->
<!-- frob:describes python/feldspar/fluids/incompressible.py::darcy_dp -->
<!-- frob:describes python/feldspar/fluids/incompressible.py::minor_loss_dp -->
<!-- frob:describes python/feldspar/fluids/incompressible.py::series_dp -->
<!-- frob:describes python/feldspar/fluids/incompressible.py::parallel_flow -->
<!-- frob:describes python/feldspar/fluids/incompressible.py::pump_operating_flow -->
<!-- frob:describes python/feldspar/fluids/incompressible.py::pump_operating_head -->
<!-- frob:describes python/feldspar/fluids/incompressible.py::npsh_available -->
<!-- frob:describes python/feldspar/fluids/incompressible.py::joukowsky_dp -->
<!-- frob:describes python/feldspar/fluids/incompressible.py::register -->

Incompressible fluid-mechanics closed-form solver directions (WO-20
Phase 2): internal flow (`laminar_friction_factor`,
`colebrook_friction_factor`, `haaland_friction_factor`, `darcy_dp`,
`minor_loss_dp`), series/parallel network reduction (`series_dp`,
`parallel_flow`), turbomachinery (`pump_operating_flow`,
`pump_operating_head`, `npsh_available`), and Joukowsky water hammer
(`joukowsky_dp`). Pure marshalling over `feldspar._feldspar.fluids_*`
(NO DUPLICATION); every direction declares `accuracy=EXACT` (the model
is the contract, even where the model itself -- Haaland -- is a
textbook approximation). Scope note (WO-20 close-out): hydrostatics,
external flow, open channel, flow measurement (ISO 5167), and
multi-branch Hardy-Cross network solving are EXPLICITLY CUT here (see
`fluids.network` for the latter). `register(registry)` registers the
family.

## fluids_network

<!-- frob:describes python/feldspar/fluids/network.py::SolvedNetwork -->
<!-- frob:describes python/feldspar/fluids/network.py::solve_flownet_bytes -->
<!-- frob:describes python/feldspar/fluids/network.py::edge_dp -->
<!-- frob:describes python/feldspar/fluids/network.py::find_path_edges -->
<!-- frob:describes python/feldspar/fluids/network.py::register -->
<!-- frob:describes python/feldspar/fluids/network.py::FLOWNET_PORT -->
<!-- frob:describes python/feldspar/fluids/network.py::SOLUTION_PORT -->

Hardy-Cross fluid-network solver (WO-20 residual): resolves a
`flownet` payload (D154, a feldspar-owned FIELD-NAME-COMPATIBLE subset
of `regolith._schema.models.FlownetPayload` -- this module never
imports regolith, FINV-3/10) into a network topology and iterates the
classical Hardy-Cross loop-correction method (Cross, 1936) to a
converged flow distribution. `SolvedNetwork` holds the per-edge
flow/dp solution; `solve_flownet_bytes` runs the iteration end to end;
`edge_dp` and `find_path_edges` are the per-edge pressure-drop and
path-lookup helpers the solve loop and its callers share. Scope: only
`pipe` and `imposer` edge kinds are in coverage (named cut, not a
silent gap, per pack contract 03). `register(registry, resolver)`
registers the `flownet`-payload direction. `FLOWNET_PORT` is the
`flownet`-kind input payload port name (D154); `SOLUTION_PORT` is the
`table`-kind output payload port name downstream dp/npsh/hammer claims
read instead of re-running the loop solve.
