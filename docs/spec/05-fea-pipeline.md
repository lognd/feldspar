# 05 -- FEA pipeline

One sentence: a deterministic gmsh -> CalculiX -> parse -> Richardson
pipeline that turns a parametric geometry + material + loads into a
stress or deflection bound with a measured, defensible eps.

## Stages (one module each, dependency arrows point down)

```
fea/solver.py      refinement study orchestration; the registered SolveFns
  fea/mesh.py      gmsh structured meshes         fea/results.py  .dat parsers
  fea/deck.py      ccx input deck builder         fea/richardson.py eps estimate
    fea/ccx.py     find/run the ccx binary
      fea/geometry.py  parametric families + Material
```

### geometry.py

Two v1 parametric families as frozen pydantic models (SI):

- `CantileverGeometry` -- rectangular-section cantilever: length,
  width, height; tip load case.
- `CylinderGeometry` -- thick-walled cylinder: inner/outer radius,
  length; internal pressure case.
- `Material` -- E, nu, yield strength (linear elastic only, v1).

Chosen because each has an exact closed-form oracle (Euler-Bernoulli;
Lame), making known-answer tests and honest eps validation possible.
General geometry is OPEN-2.

Port naming for parametric families (friction F2,
examples/README.md): `mech.geom.<family>.<param>` (e.g.
`mech.geom.cantilever.length`), `mech.material.<property>` (e.g.
`mech.material.youngs_modulus`), `mech.load.<case>` (e.g.
`mech.load.tip_force`) -- the pack signature (06) and the engine
ports are the same strings by construction, so the boundary converter
never renames.

### mesh.py

gmsh SDK, imported lazily (the `mesh` extra may be absent; a missing
gmsh is `SolveError.ToolMissing` at solve time, an importable module
always). Structured/transfinite meshes ONLY:

- cantilever: hexahedral C3D20 (quadratic brick) box mesh,
- cylinder: axisymmetric CAX8 quad mesh on the r-z rectangle.

Fixed algorithm choices and an explicit seed; characteristic length is
the ONE refinement knob. Everything that steers the mesher goes into
`MeshSettings` and thence the settings digest (FINV-2). Output
`MeshData` = node coords + element connectivity + named node/element
sets (for BCs and loads) -- plain arrays, no gmsh handles escape.
(Planned, 09 M2: meshing becomes a graph step -- `geometry.* -> mesh`
as a payload-port solver direction -- so one mesh feeds static,
modal, and thermal solves; `MeshData` is already shaped to be that
payload.)

### deck.py

Pure text generation: `MeshData` + `Material` + BC/load specs -> one
CalculiX static-analysis input deck (`*NODE`, `*ELEMENT`, `*MATERIAL`,
`*BOUNDARY`, `*CLOAD`/`*DLOAD`, `*STATIC`, `*NODE PRINT`,
`*EL PRINT`). Deterministic float formatting (shortest round-trip
`repr`, one `format_f64` home). No file IO here -- returns the deck
string (trivially testable).

### ccx.py

- `find_ccx()`: `FELDSPAR_CCX` env var, then `PATH`. Missing binary is
  a value (`ToolMissing`), reported once with install guidance.
- `run_ccx(deck, timeout_s)`: tempdir, writes `job.inp`, runs with
  `OMP_NUM_THREADS=1` (thread count changes float summation order --
  determinism beats speed here), captures stderr to the module logger,
  returns `CcxRun` (paths to `.dat`/`.frd`, elapsed, tool version).
  Nonzero exit / timeout -> `ToolFailed` / `Timeout` values carrying
  the log tail.

### results.py

Parsers for the `.dat` tables ccx prints: nodal displacements and
integration-point stresses. Returns `Result` -- a malformed or
truncated table is `ParseFailed` with line context, never a partial
silent answer. Reductions: `max_displacement_magnitude`,
`max_von_mises` (via the single `von_mises` formula home in
`library/mech`).

### richardson.py

Two-refinement Richardson extrapolation: solve at characteristic
lengths h and h/2, estimate observed convergence order p, extrapolated
value, and a CONSERVATIVE eps (the extrapolation delta, inflated by a
safety factor; when the pair is non-monotone or p is implausible for
the element order, fall back to the coarse-fine delta itself). The
realized eps replaces the solver's declared `Accuracy` ceiling at
execution time (03/04); if it exceeds the ceiling, the solve reports
`BudgetExceeded` rather than shipping optimism.

## Registered solvers

`fea/solver.py` registers two engine directions (and their pack
mirrors, 06):

- `fea.static_deflection.cantilever`: geometry+material+load ports ->
  `mech.deflection.tip`.
- `fea.static_stress.cylinder_bore`: geometry+material+pressure ports
  -> `mech.stress.von_mises`.

`deterministic=True` is honest because the settings digest folds:
`MeshSettings` (algorithm ids, seed, char lengths, element type),
`SolveSettings` (ccx flags, timeout is excluded -- it cannot change a
successful answer), and `ToolVersions` (gmsh, ccx, feldspar).

## Known-answer discipline

Every registered FEA direction ships an integration test against its
closed-form oracle: |FEA - oracle| <= reported eps, at more than one
geometry point. The oracles live in `library/mech` (07) -- the same
formulas regolith's closed-form tier uses, which is exactly WO-27's
acceptance framing ("the closed-form packs are the oracles").

These known-answer runs double as the FEA directions' calibration
evidence (03): each direction's `citations` carries the method
sources (element formulation, Richardson extrapolation) plus
`calibration` refs to the oracle-comparison run digests, so the FEA
tier meets the same defensibility bar as every closed-form solver.
