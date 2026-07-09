# WO-12: payload ports (M2)

Status: todo
Depends: WO-03/06 (registry + facade, done), WO-08 (the mesh/geometry
stages this graduates into graph steps)
Language: Python (`feldspar/solve/`, `feldspar/fea/`) + Rust only if
digest helpers need a core home
Spec: 09 secs. 4/4a (payload ports, abstraction solvers -- NORMATIVE,
incl. the kind table with `frame`), 02 (payloads are exact by
reference), 03 (settings digests), FINV-2; scheduled by 09 sec. 8
(M2) + the 2026-07-08 closure re-review (08).

## Goal

Ports may carry content-addressed payloads: `PortDecl` gains
`payload(kind)` rank; kind checking at registration mirrors unit
checking; meshing becomes a graph step; per-rung/per-payload solve
caching keys on payload digests.

## Deliverables

- `PortDecl` payload rank + kind strings from 09 sec. 4 VERBATIM
  (the table is the single home; includes `frame`); connecting
  mismatched kinds is a registration error with the same shape as a
  unit mismatch (01-interfaces extension recorded there in the same
  change).
- Payload values are `{kind, digest, origin}` refs; digest folding
  into request/solve digests (a payload in a digest is its hash --
  09 sec. 4); no store IO in feldspar (orchestrator-provided
  resolver handle, the D96/OPEN-2 contract).
- `geometry.parametric` + `mesh` kinds live: the WO-08 mesh stage
  registers as a `geometry.* -> mesh` solver direction; static FEA
  consumes the mesh payload; one mesh feeds multiple solves
  (assert: modal-ready).
- Abstraction-edge support (09 sec. 4a): execution-time domain
  checks over payload features returning `SolveError` values;
  `conservative_for` honored; optimistic planning deterministic.
- Per-payload cache keying (04 cache extended); twice-run digest
  equality tests; 02-edge-cases rows for kind mismatch, missing
  payload, dangling digest.

## Acceptance

- A cantilever solve routes geometry.parametric -> mesh -> fea with
  each stage a registry edge; same-mesh reuse proven by cache-hit
  count; planner remains tier-blind by test; all digests stable
  across runs.
