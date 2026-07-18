# strata system model

## What this is

`design/feldspar.strata` is feldspar's topology written in strata
(frob's provable system-design language) and checked by `frob sys
audit`. Every node's `code` glob, every flow, and every capability
(`may`) was verified against the real source (import blocks, the two
subprocess call sites, the plan cache, the dev-key script) -- no
aspirational edges. See T-0008 for the pilot ticket.

Two flows deserve a note: `plan -> fea` and `plan -> elec` are NOT
import edges. The planner dispatches solver callables through the
frozen `SolverRegistry`, so at runtime `plan.execute()` really does
drive gmsh/ccx/ngspice work registered by those packages even though
`python/feldspar/plan/` never imports them. The registry indirection
is exactly the kind of edge an import scanner cannot see; the model
declares it explicitly because the data path is real.

## Known gaps not gamed away

- The `regolith_consumer`, `ccx_solver`, and `ngspice_solver` nodes
  have no `code` globs (external binaries/packages); frob has no
  managed/config-only node marker yet (frob T-0172).
- Capabilities that are real but invisible to the scanner stay
  declared and show up as SYS101 "declared but never observed" gaps:
  `ffi` on core_api (importing the compiled pyo3 module) has no
  scanner needle, and gmsh's in-process C++ binding inside fea is
  likewise unobservable today.
- There is no waiver channel for sys-audit findings (frob T-0174), so
  residual gaps stay visible in the audit output and are tracked here.

## Audit end state

As of the pilot commit, `frob sys audit` evaluates 7 claims -- 5
proved, 2 assumed (the CWE-78 exec discharges), 0 refuted -- and
reports 5 residual named gaps, all traceable to frob-side limitations:

- 2x THREAT003: the CWE-78 mitigation contract demands a claim body of
  `noflow <foreign source> -> fea/elec`, but this model honestly has
  NO foreign node (feldspar is a library; every caller is trusted
  toolchain code), so the obligation is undischargeable as specified.
- 1x SYS100 `net` on fea: the capability scanner matches the word
  "requests" inside the `build_cylinder_deck` docstring
  (python/feldspar/fea/deck.py:247) -- a comment/docstring false
  positive, not a network call site.
- 1x SYS100 `eval` on domains: calib/harness.py calls the `.eval()`
  METHOD of feldspar's own expression type; not builtin eval.
- 1x SYS101 `ffi` on core_api: importing the compiled pyo3 module is
  real FFI the scanner has no needle for; the declaration stays.
