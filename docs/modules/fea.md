# feldspar.fea

The discretized FEA pipeline (WO-08, WO-12, WO-16): geometry/material
data models, gmsh mesh generation, CalculiX deck generation, the
external ccx binary boundary, result parsing, Richardson extrapolation,
per-rung caching, and the solver directions that compose all of it into
`fea.static_deflection.cantilever`, `fea.static_stress.cylinder_bore`,
and the modal/payload-step variants.

## fea_ccx

<!-- frob:describes python/feldspar/fea/ccx.py::CcxRun -->
<!-- frob:describes python/feldspar/fea/ccx.py::find_ccx -->
<!-- frob:describes python/feldspar/fea/ccx.py::run_ccx -->
<!-- frob:describes python/feldspar/fea/ccx.py::probe_tools -->

`find_ccx()`/`run_ccx()`: the external CalculiX binary boundary (01,
WO-08). Every invocation runs in a throwaway
`tempfile.TemporaryDirectory`; `CcxRun` holds the `.dat`/`.frd`
CONTENTS (`dat_text`/`frd_text`, not paths) read into memory before the
tempdir is torn down, so callers never hold a path that outlives the
directory. `probe_tools` is a best-effort tool-version scrape.

## fea_deck

<!-- frob:describes python/feldspar/fea/deck.py::build_cantilever_modal_deck -->
<!-- frob:describes python/feldspar/fea/deck.py::build_cantilever_deck -->
<!-- frob:describes python/feldspar/fea/deck.py::build_cylinder_deck -->

CalculiX deck (`.inp`) generation from mesh + boundary conditions
(WO-08): pure text generation, no IO/gmsh/ccx import/subprocess, every
float routed through `feldspar.core.format_f64` for byte-identical
decks across identical inputs. `build_cantilever_deck` builds the
static cantilever-box deck; `build_cantilever_modal_deck` builds the
modal (eigenvalue) variant of the same geometry; `build_cylinder_deck`
builds the thick-wall cylinder deck.

## fea_geometry

<!-- frob:describes python/feldspar/fea/geometry.py::Material -->
<!-- frob:describes python/feldspar/fea/geometry.py::CantileverGeometry -->
<!-- frob:describes python/feldspar/fea/geometry.py::CylinderGeometry -->

Cantilever/cylinder geometry and material data models (WO-08): plain,
IO-free pydantic models describing the two supported FEA families
(cantilever box, thick-wall cylinder) and the linear-elastic material
they are meshed with. `Material` carries isotropic elastic properties
(plus a nominal-steel `density` default for the WO-16 modal tier);
`CantileverGeometry`/`CylinderGeometry` carry each family's dimensions.
Field names are plain domain names, not port strings -- the mapping
between the two lives only in `solver.py`.

## fea_ladder

<!-- frob:describes python/feldspar/fea/ladder.py::RungCache -->
<!-- frob:describes python/feldspar/fea/ladder.py::RungCache.key -->
<!-- frob:describes python/feldspar/fea/ladder.py::RungCache.get -->
<!-- frob:describes python/feldspar/fea/ladder.py::RungCache.put -->
<!-- frob:describes python/feldspar/fea/ladder.py::climb_richardson_ladder -->

`climb_richardson_ladder`/`RungCache` (WO-13, 09 sec. 3): the
deterministic refinement ladder for a self-meshing Richardson
direction. Given an ordered sequence of rungs (coarsest first) and a
way to run one rung, `climb_richardson_ladder` climbs rung-by-rung,
Richardson-pairing each new rung against the previous one, and stops
the first time the pair's eps fits the caller's remaining budget (same
budget, same rungs, same stop -- the determinism contract).
`RungCache` makes per-rung caching literal: `key` derives a cache key
from solver id/version/rung settings/scalar box, `get`/`put` read and
write a rung's raw scalar result so a repeat climb needing only
coarser rungs never re-runs the expensive finer ones.

## fea_mesh

<!-- frob:describes python/feldspar/fea/mesh.py::MeshSettings -->
<!-- frob:describes python/feldspar/fea/mesh.py::MeshData -->
<!-- frob:describes python/feldspar/fea/mesh.py::build_cantilever_mesh -->
<!-- frob:describes python/feldspar/fea/mesh.py::build_cylinder_mesh -->

Structured-mesh generation for the WO-08 FEA pipeline: wraps gmsh's
transfinite (structured, non-adaptive) meshing to build a hex C3D20 box
(cantilever family) and an axisymmetric CAX8 quad rectangle (cylinder
family), flattening the result into plain, gmsh-free arrays
(`MeshData`) so no other fea module needs gmsh installed. `import
gmsh` is deferred into each build function's body so this module stays
importable without the optional `mesh` extra (AD-6). `MeshSettings`
configures refinement; `build_cantilever_mesh`/`build_cylinder_mesh`
are the two build entry points.

## fea_modal

<!-- frob:describes python/feldspar/fea/modal.py::register -->

ccx modal direction (WO-16, 07 vibration Phase 3): the discretized
competitor for `mech.vibe.first_mode_freq`, instantiating the mesh-as-
a-graph-step pipeline pattern over the SAME cantilever mesh payload the
WO-12 static direction consumes. Single-mesh, declared-ceiling accuracy
(no Richardson pair -- eigenvalue extraction has no h/h^2 convergence
estimator wired here yet). `register(registry, resolver)` mirrors
`payload_steps.py`'s exact shape: closes over the caller's
`PayloadResolver`, no module-global registry access (AD-4).

## fea_payload_steps

<!-- frob:describes python/feldspar/fea/payload_steps.py::register -->
<!-- frob:describes python/feldspar/fea/payload_steps.py::GEOMETRY_PORT -->
<!-- frob:describes python/feldspar/fea/payload_steps.py::MESH_PORT -->

Mesh-as-a-graph-step (WO-12, 09 sec. 4): the WO-08 mesh stage graduated
into a registry edge, plus the static-FEA direction that consumes the
resulting mesh payload. Registers `fea.mesh.cantilever` (geometry ->
mesh via gmsh, cached so every downstream consumer pays for the mesh
once) and `fea.static_deflection.cantilever_from_mesh` (mesh +
material/load scalars -> deflection via ccx, single-mesh declared-
ceiling accuracy). `register(registry, resolver)` registers both.
`GEOMETRY_PORT` is the cantilever family's parametric-geometry payload
port (kind `geometry.parametric`, frozen `CantileverGeometry` params as
JSON); `MESH_PORT` is the cantilever mesh payload port (kind `mesh`,
gmsh-free `MeshData` arrays as JSON).

## fea_results

<!-- frob:describes python/feldspar/fea/results.py::parse_dat_displacements -->
<!-- frob:describes python/feldspar/fea/results.py::parse_dat_principal_stresses -->
<!-- frob:describes python/feldspar/fea/results.py::parse_dat_frequencies -->
<!-- frob:describes python/feldspar/fea/results.py::first_mode_frequency -->
<!-- frob:describes python/feldspar/fea/results.py::max_displacement_magnitude -->
<!-- frob:describes python/feldspar/fea/results.py::max_von_mises -->

CalculiX `.dat` result parsing into engine port values (WO-08):
`.dat` is a best-effort human-readable format with no machine schema,
so every parser scans for lines starting with an int token as a data
row and fails the WHOLE parse on any malformed row (fail closed, never
partial). `parse_dat_displacements`/`parse_dat_principal_stresses`/
`parse_dat_frequencies` parse the three `*NODE PRINT`/`*EL PRINT`
block shapes ccx emits; `first_mode_frequency`,
`max_displacement_magnitude`, and `max_von_mises` reduce a parsed
result table to the single scalar a solver direction reports.

## fea_richardson

<!-- frob:describes python/feldspar/fea/richardson.py::RichardsonResult -->
<!-- frob:describes python/feldspar/fea/richardson.py::richardson_extrapolate -->
<!-- frob:describes python/feldspar/fea/richardson.py::THEORETICAL_ORDER -->
<!-- frob:describes python/feldspar/fea/richardson.py::SAFETY_FACTOR -->

Richardson extrapolation over mesh refinements for `measured_eps` (05,
WO-08). `richardson_extrapolate` takes a coarse/fine result pair at a
fixed theoretical convergence order (`THEORETICAL_ORDER`, O(h^2) for
the quadratic C3D20/CAX8 element formulations used across the FEA
tier), extrapolates, inflates by `SAFETY_FACTOR`, and falls back to the
raw delta on an implausible pair; `RichardsonResult` carries the
extrapolated value and reported eps. `THEORETICAL_ORDER` (2.0) is the
fixed, cited convergence order for the quadratic C3D20/CAX8 element
formulations (cannot be empirically measured from only two mesh
levels); `SAFETY_FACTOR` (1.5) is the conservative inflation margin
applied to the extrapolation correction, chosen rather than evidence-
derived.

## fea_solver

<!-- frob:describes python/feldspar/fea/solver.py::SolveSettings -->
<!-- frob:describes python/feldspar/fea/solver.py::ToolVersions -->
<!-- frob:describes python/feldspar/fea/solver.py::cantilever -->
<!-- frob:describes python/feldspar/fea/solver.py::cylinder_bore -->
<!-- frob:describes python/feldspar/fea/solver.py::register -->

FEA (discretized-tier) solver directions (WO-08): registers
`fea.static_deflection.cantilever` and `fea.static_stress.cylinder_bore`,
the discretized twins of `mech.closed_form`'s closed-form cantilever
and Lame/von-Mises directions. Each direction runs a fixed two-mesh
(h, h/2) Richardson pair through gmsh -> deck -> ccx -> results,
reporting a MEASURED `SolveOutput.measured_eps` that
`plan.execute._make_corner_fn` uses in place of the declared
`accuracy=` ceiling. `SolveSettings` configures the mesh/refinement
inputs; `ToolVersions` records the probed gmsh/ccx versions;
`cantilever`/`cylinder_bore` are the two `SolveFn` implementations;
`register(registry)` registers both.
