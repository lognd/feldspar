# WO-08: FEA pipeline

Status: done
Depends: WO-07
Language: Python (`feldspar/fea/`), gmsh via `mesh` extra, ccx binary
Spec: 05 (all stages), 03 (external interfacing), FINV-2/5

## Goal

The deterministic gmsh -> ccx -> parse -> Richardson pipeline,
registered as two engine directions.

## Deliverables

- One module per 05 stage, dependency arrows per its diagram:
  `geometry.py` (CantileverGeometry, CylinderGeometry, Material --
  frozen pydantic, SI; scalar port naming per 02), `mesh.py` (lazy
  gmsh, transfinite hex C3D20 / axisym CAX8, MeshSettings ->
  settings digest, MeshData plain arrays), `deck.py` (pure text,
  format_f64 from core, no IO), `ccx.py` (find_ccx: FELDSPAR_CCX
  then PATH; run_ccx: tempdir, OMP_NUM_THREADS=1, stderr to logger,
  CcxRun result; ToolMissing/ToolFailed/Timeout values), `results.py`
  (.dat parsers -> Result, ParseFailed with line context; reductions
  import the WO-07 von Mises home), `richardson.py` (h + h/2, order
  estimate, conservative eps with fallback per 05).
- `solver.py`: registers `fea.static_deflection.cantilever` and
  `fea.static_stress.cylinder_bore` with tier=discretized, measured
  eps replacing declared ceiling at execution, full settings-digest
  folding (MeshSettings + SolveSettings + ToolVersions; timeout
  excluded) -- FINV-2 fold test enumerates every field.
- Tests: deck goldens (byte-stable); parser fixtures incl. truncated
  tables; `fea`-marked integration: |FEA - WO-07 oracle| <= reported
  eps at >= 2 geometry points per family; twice-run digest equality.

## Acceptance

- Without gmsh/ccx installed: modules import, solves return
  ToolMissing values, non-`fea` tests green (FINV-3/AD-6 pattern).
- With tools (CI fea job): known-answer + determinism tests green.
